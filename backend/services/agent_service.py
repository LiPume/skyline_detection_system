"""
Skyline — Agent Service
Task parsing and recommendation via LLM API (SiliconFlow / OpenAI-compatible).
Only handles "task understanding / plan recommendation" — never triggers real detection.
"""
import json
import logging
import os
from typing import Optional

import httpx

from models.registry import (
    MODEL_REGISTRY,
    list_all_models,
    filter_supported_classes,
)

logger = logging.getLogger(__name__)

# ── Environment config ─────────────────────────────────────────────────────────

_AGENT_API_KEY: str | None = None
_AGENT_BASE_URL: str = "https://api.siliconflow.cn/v1"
_AGENT_MODEL: str = "deepseek-ai/DeepSeek-V3.2"

# ── Closed-set priority: model_id → list of class-name sets it fully covers ──
# Maps each closed-set model to a list of frozensets representing equivalent class groups.
# A target class that appears in one of these sets is considered "covered" by this model.
_CLOSED_SET_COVERAGE_GROUPS: dict[str, list[frozenset]] = {
    "YOLOv8-Base": [
        frozenset({"person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
                    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
                    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
                    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
                    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
                    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
                    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
                    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
                    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
                    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
                    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
                    "toothbrush"}),
    ],
    "YOLOv8-Car": [
        frozenset({"car", "truck", "bus", "van", "freight_car"}),
    ],
    "YOLOv8-VisDrone": [
        frozenset({"pedestrian", "people", "bicycle", "car", "van", "truck",
                    "tricycle", "awning-tricycle", "bus", "motor"}),
    ],
    # Person-only specialized models — covered by person detection only
    "YOLOv8-Person": [
        frozenset({"person"}),
    ],
    "YOLOv8-Thermal-Person": [
        frozenset({"person"}),
    ],
}

# Person-only model IDs (registered in registry.py MODEL_REGISTRY)
_PERSON_ONLY_MODELS = {"YOLOv8-Person", "YOLOv8-Thermal-Person"}

# ── Highway / traffic-jam scene keywords ──────────────────────────────────────
# 规则 1（高速车辆检测）：
#   "我在高速上要检测车辆" / "巡查高速交通情况" / "看高速路面上的车流"
#   → YOLOv8-VisDrone + {car, van, truck, bus}
#
# 规则 2（堵车 / 拥堵场景）：
#   "我要找堵车" / "看堵车时有没有人下车" / "检测拥堵路段的车辆和人员活动"
#   → YOLOv8-VisDrone + {car, van, truck, bus, pedestrian, people}
_HIGHWAY_KEYWORDS = frozenset({
    "高速", "高速公路", "高架", "快速路", "道路监控", "道路交通",
})

_TRAFFIC_JAM_KEYWORDS = frozenset({
    "堵车", "拥堵", "交通拥堵", "塞车",
})

_VISDRONE_VEHICLE_CLASSES = ["car", "van", "truck", "bus"]
_VISDRONE_JAM_CLASSES    = ["car", "van", "truck", "bus", "pedestrian", "people"]

# Keywords that indicate low-light / thermal-infrared scenarios.
# Matched case-insensitively against the raw user_text.
_LOW_LIGHT_KEYWORDS = frozenset({
    "夜间", "弱光", "低照度", "黑暗", "红外", "热红外",
    "热成像", "夜视", "夜搜救", "夜间搜救",
})

# Keywords that indicate the task is person-only (not multi-class).
_PERSON_ONLY_KEYWORDS = frozenset({
    "人", "人员", "行人", "人体", "找人", "搜救找人",
})

# Keywords that indicate attribute / descriptive constraints on the target.
# When the task combines a target class with any of these descriptors,
# the closed-set priority should NOT apply — open vocabulary is preferred.
_ATTRIBUTE_CONSTRAINT_KEYWORDS = frozenset({
    # Colors — prefer 2-char forms to avoid accidental matches on single chars
    "白", "黑", "红", "蓝", "绿", "黄", "灰", "银", "金色", "橙色",
    "紫色", "棕色", "深色", "浅色", "彩色",
    # Appearance / shape
    "大", "小", "长", "短", "圆", "方", "扁", "宽", "窄", "高", "矮", "胖", "瘦",
    # Clothing / accessories
    "帽子", "头盔", "背包", "反光衣", "雨伞", "围巾", "手套", "外套",
    "制服", "工装", "西装", "T恤", "裙子", "短裤", "长裤", "鞋子", "靴子",
    "口罩", "眼镜", "墨镜",
    # State / behaviour
    "奔跑", "跑步", "骑行", "站立", "行走", "坐着", "躺卧", "聚集",
    "停放", "移动", "静止", "逃跑", "摔倒", "挥手",
    # Vehicle attributes
    "SUV", "轿车", "卡车", "面包车", "公交车", "大巴", "出租车",
    # Age/people descriptors — multi-char only to avoid "人" collateral matches
    "老人", "儿童", "小孩", "年轻人", "成年人",
})


def _contains_attribute_constraints(user_text: str) -> bool:
    """Return True if user_text contains any attribute/descriptive constraint keyword."""
    return any(kw in user_text for kw in _ATTRIBUTE_CONSTRAINT_KEYWORDS)


def _load_config() -> None:
    """Read environment variables lazily (call once at first use)."""
    global _AGENT_API_KEY, _AGENT_BASE_URL, _AGENT_MODEL
    if _AGENT_API_KEY is None:
        _AGENT_API_KEY = os.environ.get("AGENT_API_KEY", "").strip()
        _AGENT_BASE_URL = os.environ.get("AGENT_BASE_URL", "").strip() or "https://api.siliconflow.cn/v1"
        _AGENT_MODEL = os.environ.get("AGENT_MODEL", "").strip() or "deepseek-ai/DeepSeek-V3.2"


def _normalize_model_id(raw: str) -> str:
    """Strip whitespace and return a cleaned model identifier."""
    return raw.strip()


def _find_best_closed_set_model(target_classes: list[str]) -> str | None:
    """
    Find the closed-set model that best covers the target classes.

    Returns the model_id of the most appropriate closed-set model if ALL target
    classes are covered by it, otherwise None (indicating no closed-set model
    is suitable and open_vocab should be used).
    """
    if not target_classes:
        return None
    target_set = {c.lower().strip() for c in target_classes}

    best_model: str | None = None

    for model_id, coverage_groups in _CLOSED_SET_COVERAGE_GROUPS.items():
        caps = MODEL_REGISTRY.get(model_id)
        if not caps or caps.model_type != "closed_set":
            continue
        for group in coverage_groups:
            group_covered = target_set & group
            if not group_covered:          # no overlap with this group
                continue
            # Does this group fully cover every target class?
            if group_covered == target_set:
                # Perfect cover — use the smallest group to prefer more specific models
                if best_model is None or len(group) < len(coverage_groups[0] if not best_model else _CLOSED_SET_COVERAGE_GROUPS.get(best_model, [frozenset()])[0]):
                    best_model = model_id
                break

    return best_model


def _apply_closed_set_priority(
    model_id: str,
    target_classes: list[str],
    raw_reason: str,
    user_text: str,
) -> tuple[str, list[str], str]:
    """
    Apply closed-set priority: if all target classes are covered by a closed-set
    model, switch to that model and update the reason accordingly.

    IMPORTANT — boundary guard: closed-set priority must NOT apply when the
    task contains attribute constraints or unsupported-modality keywords, even
    if all classes happen to be in a closed-set group's class list.  The task
    has already been re-routed by Step 3/4, and Step 5 must not undo it.

    Returns (final_model_id, final_target_classes, final_reason).
    """
    if _contains_attribute_constraints(user_text):
        return model_id, target_classes, raw_reason
    if _contains_low_light_keywords(user_text):
        return model_id, target_classes, raw_reason

    closed_caps = _find_best_closed_set_model(target_classes)

    if closed_caps is None:
        # No closed-set model can cover all targets; keep whatever LLM returned
        return model_id, target_classes, raw_reason

    if model_id == closed_caps:
        # LLM already picked the right closed-set model
        return model_id, target_classes, raw_reason

    # Switch: open_vocab was recommended but a closed-set model covers all targets
    final_model_id = closed_caps
    final_target_classes = [c for c in target_classes if c.strip()]

    caps = MODEL_REGISTRY.get(final_model_id)
    display = caps.display_name if caps else final_model_id

    final_reason = (
        f"目标类别（{', '.join(final_target_classes)}）均属于 {display} 的固定类别，"
        f"优先使用专用模型以获得更精确的检测效果。"
    )

    return final_model_id, final_target_classes, final_reason


def _contains_low_light_keywords(user_text: str) -> bool:
    """Return True if user_text contains any low-light / thermal-infrared keyword."""
    return any(kw in user_text for kw in _LOW_LIGHT_KEYWORDS)


def _is_person_only_task(user_text: str, target_classes: list[str]) -> bool:
    """
    Return True if the task is clearly person-only:
      - target_classes is a single-element list containing only "person"
      - AND user_text contains at least one person-only keyword
    """
    if not target_classes:
        return False
    class_set = {c.lower().strip() for c in target_classes}
    return (class_set == {"person"} and any(kw in user_text for kw in _PERSON_ONLY_KEYWORDS))


def _is_highway_traffic_scene(user_text: str) -> bool:
    """Return True if user_text explicitly mentions highway / expressway / road traffic."""
    return any(kw in user_text for kw in _HIGHWAY_KEYWORDS)


def _is_traffic_jam_scene(user_text: str) -> bool:
    """Return True if user_text explicitly mentions traffic jam / congestion."""
    return any(kw in user_text for kw in _TRAFFIC_JAM_KEYWORDS)


def _apply_highway_jam_scene_boost(
    model_id: str,
    target_classes: list[str],
    user_text: str,
    raw_reason: str,
    confidence: str,
) -> tuple[str, list[str], str, str]:
    """
    Highway / traffic-jam scene boost: enhance recommendation when user explicitly
    expresses intent to monitor highway traffic or detect traffic congestion.

    Two supported scenarios:
      1. Highway vehicle detection → YOLOv8-VisDrone + {car, van, truck, bus}
         e.g. "我在高速上要检测车辆" / "巡查高速交通情况"
      2. Traffic jam / congestion   → YOLOv8-VisDrone + {car, van, truck, bus,
                                                         pedestrian, people}
         e.g. "我要找堵车" / "看堵车时有没有人下车" / "检测拥堵路段的车辆和人员活动"

    This step runs AFTER Steps 3-5 (unsupported-modality, attribute-constraint,
    person-only-fallback) and BEFORE Step 6 (closed-set priority), so it will NOT
    override decisions already made by those guards.

    Returns (final_model_id, final_target_classes, final_reason, final_confidence).
    """
    # Priority: traffic-jam scene first, then highway-only
    is_jam   = _is_traffic_jam_scene(user_text)
    is_highway = _is_highway_traffic_scene(user_text)

    if not (is_jam or is_highway):
        return model_id, target_classes, raw_reason, confidence

    # Pick the richer class set for traffic-jam scenes
    new_classes = _VISDRONE_JAM_CLASSES if is_jam else _VISDRONE_VEHICLE_CLASSES

    final_model_id = "YOLOv8-VisDrone"
    final_reason   = (
        f"任务场景为{'高速' if is_highway and not is_jam else ''}"
        f"{'交通拥堵巡查' if is_jam else '道路交通/高速巡查'}，"
        f"需要覆盖航拍交通场景下的主要机动车类别（car/van/truck/bus）"
        f"{'和人员活动类别（pedestrian/people），以便观察拥堵期间人员下车、路边活动等伴随行为' if is_jam else ''}，"
        f"VisDrone 闭集类别完整覆盖上述目标，优先推荐。"
    )
    final_confidence = confidence if confidence == "high" else "medium"

    return final_model_id, new_classes, final_reason, final_confidence


def _apply_person_only_fallback(
    model_id: str,
    target_classes: list[str],
    user_text: str,
    raw_reason: str,
    confidence: str,
) -> tuple[str, list[str], str, str]:
    """
    Person-only fallback: if the parsed result is person-only, override the model
    to the appropriate specialized person detector.

    IMPORTANT — boundary guards:
      1. Attribute-constrained tasks (e.g. "穿红衣服的人", "找戴帽子的人")
         must NOT be overridden — the Step 4 open-vocab decision stands.
      2. Unsupported-modality tasks (thermal/IR) must NOT be overridden —
         the Step 3 capability-boundary disclaimer (confidence=low) stands.
         We intentionally do NOT force-switch to YOLOv8-Thermal-Person here,
         because doing so would silently lift the "low confidence" signal that
         Step 3 carefully planted.

    Returns (final_model_id, final_target_classes, final_reason, final_confidence).
    """
    if not _is_person_only_task(user_text, target_classes):
        return model_id, target_classes, raw_reason, confidence

    # Guard 1: attribute-constrained → keep Step 4 decision
    if _contains_attribute_constraints(user_text):
        return model_id, target_classes, raw_reason, confidence

    # Guard 2: unsupported-modality → keep Step 3 decision (do NOT upgrade confidence)
    if _contains_low_light_keywords(user_text):
        return model_id, target_classes, raw_reason, confidence

    # Pure person-only: switch to specialized model and lift confidence
    final_model_id = "YOLOv8-Person"
    final_target_classes = ["person"]
    final_reason = (
        "检测任务为人员/人体识别，强制使用专用人体模型 YOLOv8-Person 以获得更精确的检测效果。"
    )
    final_confidence = "high"

    return final_model_id, final_target_classes, final_reason, final_confidence


def _apply_attribute_constraint_correction(
    model_id: str,
    target_classes: list[str],
    user_text: str,
    raw_reason: str,
    confidence: str,
) -> tuple[str, list[str], str, str]:
    """
    Detect attribute-constrained tasks (e.g. "找白车", "穿红衣服的人")
    and redirect them to open-vocabulary models.

    Rule: if the task contains BOTH a target class AND any attribute
    descriptor, closed-set priority should NOT force the result into
    a specialized model — open vocabulary is more appropriate.

    Boundary guard: if the task also contains unsupported-modality keywords
    (thermal/IR), Step 3 has already set confidence=low and injected the
    boundary disclaimer.  We must NOT override Step 3's decision by
    switching the model away — keep the model as-is and only lift confidence
    back to "medium" if it makes sense for the attribute constraint.

    Returns (final_model_id, final_target_classes, final_reason, final_confidence).
    """
    if not _contains_attribute_constraints(user_text):
        return model_id, target_classes, raw_reason, confidence

    # If the task contains unsupported-modality keywords, Step 3 already
    # set confidence=low and wrote a boundary disclaimer — do NOT override it.
    if _contains_low_light_keywords(user_text):
        return model_id, target_classes, raw_reason, confidence

    # Task has attribute constraints — only override if currently on a closed-set model
    caps = MODEL_REGISTRY.get(model_id)
    if caps and caps.model_type == "closed_set":
        final_model_id = "YOLO-World-V2"
        final_classes = list(target_classes)
        final_reason = (
            f"检测任务包含外观/属性描述（{user_text.strip()}），"
            f"闭集专用模型无法表达此类属性约束，"
            f"切换为开放词汇模型 YOLO-World-V2 以支持自然语言类别表达。"
        )
        final_confidence = "medium"
        return final_model_id, final_classes, final_reason, final_confidence

    # Already on open vocab — keep it
    return model_id, target_classes, raw_reason, confidence


def _apply_unsupported_modality_correction(
    model_id: str,
    target_classes: list[str],
    user_text: str,
    raw_reason: str,
    confidence: str,
) -> tuple[str, list[str], str, str]:
    """
    Detect unsupported modality / perception-condition keywords
    (infrared, thermal, night-vision) and downgrade confidence + inject
    a capability-boundary note.

    The system currently only supports visible-light video input.
    Thermal / IR tasks should NOT receive high-confidence normal recommendations.

    Returns (final_model_id, final_target_classes, final_reason, final_confidence).
    """
    if not _contains_low_light_keywords(user_text):
        return model_id, target_classes, raw_reason, confidence

    # Downgrade confidence — do NOT silently pretend the system handles thermal
    if confidence == "high":
        final_confidence = "low"
    elif confidence == "medium":
        final_confidence = "low"
    else:
        final_confidence = "low"

    final_reason = (
        f"检测任务涉及红外/热成像/夜视场景（{user_text.strip()}），"
        f"当前系统主要基于可见光视频输入，不原生支持红外/热成像数据链路。 "
        f"此次推荐仅作近似可见光尝试，效果可能受限，建议在可见光画面下使用或确认红外数据源已接入。"
    )

    return model_id, target_classes, final_reason, final_confidence


# ── Attribute-phrase restoration for open_vocab models ──────────────────────
# Chinese → English attribute/colour/size word mappings
_ATTRIBUTE_WORD_MAP: dict[str, str] = {
    "白": "white",
    "黑": "black",
    "红": "red",
    "蓝": "blue",
    "绿": "green",
    "黄": "yellow",
    "灰": "gray",
    "银": "silver",
    "金色": "golden",
    "橙": "orange",
    "紫": "purple",
    "棕": "brown",
    "深色": "dark",
    "浅色": "light",
    "彩色": "colorful",
    "小": "small",
    "大": "large",
    "微": "tiny",
    "很": "",      # 单独"很"不构成属性，继续匹配下一个词
    "受": "",      # 单独"受"不构成属性，继续匹配下一个词
    "停放": "parked",
    "移动": "moving",
    "聚集": "crowd",
    "倒地": "fallen",
    "受损": "damaged",
}

# Chinese base noun → English base noun mappings (lowercase)
_BASE_NOUN_MAP: dict[str, str] = {
    "汽车": "car",
    "车辆": "car",
    "车": "car",
    "轿车": "car",
    "小车": "car",
    "卡车": "truck",
    "货车": "truck",
    "大巴": "bus",
    "公交车": "bus",
    "巴士": "bus",
    "人员": "person",
    "行人": "person",
    "人体": "person",
    "兔子": "rabbit",
    "兔": "rabbit",
    "猫": "cat",
    "狗": "dog",
    "鸟": "bird",
    "马": "horse",
    "羊": "sheep",
    "牛": "cow",
    "猪": "pig",
}

# Single-word attribute tokens that, if present, indicate an attribute constraint
_SINGLE_ATTR_TOKENS = frozenset({
    "白色", "黑色", "红色", "蓝色", "绿色", "黄色", "灰色", "银色",
    "金色", "橙色", "紫色", "棕色", "深色", "浅色", "彩色",
    "小型", "大型", "微小", "很小",
    "停放", "移动", "聚集", "倒地", "受损",
    "奔跑", "骑行", "站立", "躺卧", "摔倒",
})


def _extract_chinese_attributes(text: str) -> list[str]:
    """Extract attribute/colour/size words from Chinese user text."""
    attrs: list[str] = []
    for attr, eng in _ATTRIBUTE_WORD_MAP.items():
        if attr in text and eng:   # skip empty-string placeholders
            attrs.append(eng)
    return attrs


def _extract_chinese_noun(text: str) -> str | None:
    """Extract the most likely Chinese base noun from user text."""
    for cn, en in _BASE_NOUN_MAP.items():
        if cn in text:
            return en
    return None


def _looks_like_bare_noun(phrase: str) -> bool:
    """Return True if phrase looks like a bare English noun (car, person, rabbit)."""
    bare_nouns = {"car", "truck", "bus", "person", "rabbit", "cat", "dog", "bird",
                  "horse", "sheep", "cow", "pig", "motorcycle", "bicycle"}
    return phrase.lower().strip() in bare_nouns


def _restore_attribute_phrases(
    model_id: str,
    target_classes: list[str],
    user_text: str,
) -> list[str]:
    """
    Minimal post-processing fallback for open_vocab models.

    Activates only when:
      1. model_id belongs to an open_vocab model
      2. target_classes contains exactly ONE bare noun (car / person / rabbit …)
      3. user_text contains explicit attribute tokens (colour, size, state …)

    In that case, attempts to reconstruct a richer English detection phrase
    by combining extracted attributes with the base noun.

    Returns the original target_classes unchanged if any of the preconditions
    are not met, or if LLM already returned a richer phrase.
    """
    caps = MODEL_REGISTRY.get(model_id)
    if not caps or caps.model_type != "open_vocab":
        return target_classes

    if len(target_classes) != 1 or not _looks_like_bare_noun(target_classes[0]):
        return target_classes

    attrs = _extract_chinese_attributes(user_text)
    if not attrs:
        return target_classes

    base_noun = _extract_chinese_noun(user_text)
    if base_noun is None:
        return target_classes

    restored = " ".join(attrs + [base_noun]).strip()
    if restored and restored.lower() != target_classes[0].lower():
        logger.info(
            "[agent_service] Restored attribute phrase: %s -> %s (user_text=%r)",
            target_classes[0], restored, user_text,
        )
        return [restored]

    return target_classes


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_models_context() -> str:
    """Construct the capability constraint block for the LLM prompt."""
    lines = []
    for caps in list_all_models():
        type_label = "开放词汇（支持任意自然语言类别）" if caps.model_type == "open_vocab" else "固定类别"
        if caps.supported_classes:
            classes_str = ", ".join(caps.supported_classes)
            lines.append(f"  • {caps.model_id}（{caps.display_name}）")
            lines.append(f"    类型：{type_label}")
            lines.append(f"    支持类别：{classes_str}")
        else:
            lines.append(f"  • {caps.model_id}（{caps.display_name}）")
            lines.append(f"    类型：{type_label}（可输入任意类别）")
    return "\n".join(lines)


def _build_system_prompt() -> str:
    return """你是一个目标检测任务理解助手。

## 你的职责
根据用户的自然语言检测需求，从以下可用模型中推荐最合适的一个，并给出推荐的检测类别。

## 可用模型（必须严格从中选择，禁止编造）
""" + _build_models_context() + """

## 输出要求
你必须**只输出一个 JSON 对象**，不要输出任何其他文字、markdown或解释。

JSON 必须包含以下字段：
{
  "intent": "object_detection" | "other",
  "recommended_model_id": "模型ID，必须来自上述可用模型列表",
  "target_classes": ["类别1", "类别2", ...]，必须是上述模型支持的类别，
                    如果该模型是开放词汇模型则可以是任意合理英文单词类别，
                    如果是固定类别模型则必须是上述列表中的类别，
  "report_required": true | false，是否建议生成检测报告，
  "reason": "推荐原因的简短中文说明（50字以内）",
  "confidence": "high" | "medium" | "low"，模型/类别推荐的确信度
}

## 保守策略
- 如果用户提到"汽车、车辆、卡车、公交车"等，优先用车辆专用模型（YOLOv8-Car 或 VisDrone）
- 如果用户提到 COCO 常见目标（人、猫、狗、杯子等），推荐 YOLOv8-Base
- 如果用户使用中文抽象描述或明确说"任意目标"，优先用开放词汇模型 YOLO-World-V2
- 如果模型不支持用户提到的类别，修正为该模型支持的最接近类别
- 如果完全不明确，返回 {"intent": "other", "recommended_model_id": "YOLO-World-V2", "target_classes": ["object"], "report_required": false, "reason": "任务描述不明确，默认使用开放词汇模型", "confidence": "low"}

## 开放词汇模型 target_classes 保留属性短语规则（★★★ 关键 ★★★）
当推荐的模型是开放词汇模型（open_vocab）时，**必须**在 target_classes 中保留属性限定词（颜色、大小、状态、外观等），不要将其压缩为仅基础名词。具体要求：

1. 若任务包含颜色/尺寸/外观/状态等修饰词，必须将其合并进英文检测短语
   - "白色的汽车" / "白车" → ["white car"]  （不是 ["car"]）
   - "红色车辆" / "红车" → ["red car"]  （不是 ["car"]）
   - "白色的小兔子" / "白兔" → ["white rabbit"] 或 ["small white rabbit"]  （不是 ["rabbit"]）
   - "黑色的人" → ["person"]  （颜色不改变人这个类别，保持 person）
   - "穿橙色背心的人" → ["person wearing orange vest"]  （不是 ["person"]）
   - "受损的汽车" → ["damaged car"]  （不是 ["car"]）
   - "聚集的人群" → ["crowd"] 或 ["group of people"]  （不是 ["person"]）
   - "停放的车辆" → ["parked car"]  （不是 ["car"]）

2. 目标基础词中英文对照参考（小写英文）：
   - 汽车 / 车辆 / 车 / 小汽车 / 轿车 → car
   - 卡车 / 大货车 → truck
   - 公交车 / 大巴 / 巴士 → bus
   - 人 / 人员 / 行人 / 人体 / 人类 → person（除非有外观修饰）
   - 兔子 / 小兔子 / 白兔 → rabbit
   - 猫 → cat
   - 狗 → dog
   - 鸟 → bird
   - 马 → horse

3. 禁止行为：
   - 禁止将带属性的 open_vocab 任务简化为 ["car"]、["rabbit"]、["person"] 等裸基础词
   - 禁止在 target_classes 中同时出现 ["car", "red car"]（只需一个完整短语）

## 人员检测专用模型优先规则
- 当用户目标仅为"人 / 人员 / 行人 / 人体 / 找人 / 搜救找人"等单一人物检测时，优先推荐专用人体模型，而非通用开放词汇模型或 YOLOv8-Base：
    • 正常光照 / 可见光场景：YOLOv8-Person（target_classes=["person"]）
    • 弱光 / 夜间 / 热成像 / 红外 / 夜视等场景：YOLOv8-Thermal-Person（target_classes=["person"]）
- 上述人员专用模型仅适用于纯 person 检测任务；混合多类别任务（车辆+行人、无人机+人员等）保持现有推荐逻辑不变
- 推荐的人员模型 ID 必须在上述可用模型列表中，禁止返回未注册模型 ID"""


# ── Public API ────────────────────────────────────────────────────────────────

def parse_detection_task(user_text: str) -> dict:
    """
    Parse a natural-language detection task via LLM and return a
    structured recommendation.

    Args:
        user_text: The user's natural-language description of the detection task.

    Returns:
        A dict with keys: intent, recommended_model_id, target_classes,
        report_required, reason, confidence.

    Raises:
        ValueError: If API key is missing.
        RuntimeError: If the LLM call fails or response is unparseable.
    """
    _load_config()

    if not _AGENT_API_KEY:
        raise ValueError("Agent API key 未配置（AGENT_API_KEY 环境变量）")

    system_prompt = _build_system_prompt()

    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = client.post(
                f"{_AGENT_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {_AGENT_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _AGENT_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 512,
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"Agent 请求超时：{exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Agent API 错误（{exc.response.status_code}）：{exc.response.text[:200]}") from exc
    except Exception as exc:
        raise RuntimeError(f"Agent 请求失败：{exc}") from exc

    # ── Parse LLM response ─────────────────────────────────────────────────────
    try:
        raw = data["choices"][0]["message"]["content"].strip()
        # Remove markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("[agent_service] Failed to parse LLM response: %s | raw=%r", exc, raw[:300])
        raise RuntimeError(f"Agent 返回格式异常，无法解析：{exc}") from exc

    # ── Validate & sanitize ────────────────────────────────────────────────────
    # Step 1: Normalize the model id and validate against registry
    raw_model_id = _normalize_model_id(result.get("recommended_model_id", ""))
    if raw_model_id and raw_model_id in MODEL_REGISTRY:
        recommended_model_id = raw_model_id
    else:
        logger.warning(
            "[agent_service] LLM returned unknown model '%s', falling back to YOLO-World-V2",
            raw_model_id,
        )
        recommended_model_id = "YOLO-World-V2"

    target_classes = result.get("target_classes", [])
    if not isinstance(target_classes, list):
        target_classes = []

    # Filter to only supported classes for the recommended model
    caps = MODEL_REGISTRY.get(recommended_model_id)
    if caps and caps.model_type == "closed_set":
        target_classes = filter_supported_classes(recommended_model_id, target_classes)
        if not target_classes:
            # Fallback: pick first supported class
            target_classes = [caps.supported_classes[0]] if caps.supported_classes else []

    intent: str = result.get("intent", "object_detection")
    if intent not in ("object_detection", "other"):
        intent = "object_detection"

    confidence: str = result.get("confidence", "medium")
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"

    # Step 2: Capture the raw reason BEFORE any model/priority changes
    raw_reason: str = str(result.get("reason", ""))[:200]

    # Step 3: Unsupported modality correction — highest priority, runs FIRST
    # to establish the capability boundary before any model switching
    final_model_id, final_classes, final_reason, final_confidence = _apply_unsupported_modality_correction(
        recommended_model_id, target_classes, user_text, raw_reason, confidence
    )

    # Step 4: Attribute-constraint correction — redirect closed-set models to
    # open vocabulary when the task contains descriptive/attribute keywords
    final_model_id, final_classes, final_reason, final_confidence = _apply_attribute_constraint_correction(
        final_model_id, final_classes, user_text, final_reason, final_confidence
    )

    # Step 5: Person-only fallback — override to specialized person model if needed;
    # only triggers when the task is genuinely pure person + no attribute/modality qualifiers
    final_model_id, final_classes, final_reason, final_confidence = _apply_person_only_fallback(
        final_model_id, final_classes, user_text, final_reason, final_confidence
    )

    # Step 5.5: Highway / traffic-jam scene boost — enhance recommendation for
    # expressway vehicle monitoring or congestion detection; runs after person-only
    # fallback so it will NOT override that decision for pure-person tasks that
    # don't also mention highway/jam keywords
    final_model_id, final_classes, final_reason, final_confidence = _apply_highway_jam_scene_boost(
        final_model_id, final_classes, user_text, final_reason, final_confidence
    )

    # Step 6: Closed-set priority — only applies to pure-category tasks;
    # guarded by _contains_attribute_constraints and _contains_low_light_keywords internally,
    # so it will NOT override decisions already made by Steps 3–5
    final_model_id, final_classes, final_reason = _apply_closed_set_priority(
        final_model_id, final_classes, final_reason, user_text
    )

    # Step 7: Restore attribute phrases for open_vocab models.
    # If LLM returned a bare noun (car / rabbit / person …) but user_text
    # clearly contains attribute tokens, try to reconstruct a richer phrase.
    # Only activates for open_vocab models with a single bare-noun target.
    final_classes = _restore_attribute_phrases(
        final_model_id, final_classes, user_text
    )

    return {
        "intent": intent,
        "recommended_model_id": final_model_id,
        "target_classes": final_classes,
        "report_required": bool(result.get("report_required", False)),
        "reason": final_reason,
        "confidence": final_confidence,
    }


# ── Short Report Generation ──────────────────────────────────────────────────────

# ── Report generation scene-hint detection ───────────────────────────────────────
# Keywords matched against the original task_prompt (if provided).
# These are used to add scene context to the report prompt — NOT to fabricate
# conclusions, only to orient the model toward the right domain language.

_HIGHWAY_REPORT_KEYWORDS  = frozenset({
    "高速", "高速公路", "高架", "快速路", "道路交通", "道路监控",
})
_TRAFFIC_JAM_REPORT_KEYWORDS = frozenset({
    "堵车", "拥堵", "塞车", "交通拥堵",
})
_PERSON_REPORT_KEYWORDS    = frozenset({
    "人", "人员", "行人", "人体", "找人", "搜救",
})


def _detect_report_scene(task_prompt: str | None) -> str:
    """
    Return a scene label based on task_prompt keywords.
    Returns one of: "highway_traffic" | "traffic_jam" | "person_search" | "general"
    """
    if not task_prompt:
        return "general"
    if any(kw in task_prompt for kw in _TRAFFIC_JAM_REPORT_KEYWORDS):
        return "traffic_jam"
    if any(kw in task_prompt for kw in _HIGHWAY_REPORT_KEYWORDS):
        return "highway_traffic"
    if any(kw in task_prompt for kw in _PERSON_REPORT_KEYWORDS):
        return "person_search"
    return "general"


def generate_short_report(
    model_id: str,
    model_label: str,
    target_classes: list[str],
    total_detection_events: int,
    detected_class_count: int,
    class_counts: list[dict],
    max_frame_detections: int,
    duration_sec: float | None,
    summary_text: str,
    task_prompt: str | None = None,
) -> str:
    """
    Generate a short AI report based on structured detection summary data.

    Args:
        model_id: Model identifier used for detection.
        model_label: Human-readable model name.
        target_classes: Target classes that were detected.
        total_detection_events: Total number of detection events recorded.
        detected_class_count: Number of distinct classes detected.
        class_counts: List of {className, count} sorted by frequency.
        max_frame_detections: Maximum detections in a single frame.
        duration_sec: Total analysis duration in seconds.
        summary_text: Local summary text already computed.
        task_prompt: Optional original task prompt (not required).

    Returns:
        A short Chinese-language report as a plain string.

    Raises:
        ValueError: If API key is missing.
        RuntimeError: If the LLM call fails.
    """
    _load_config()

    if not _AGENT_API_KEY:
        raise ValueError("Agent API key 未配置（AGENT_API_KEY 环境变量）")

    # ── Class counts & statistical helpers ─────────────────────────────────────
    class_str = ", ".join(
        f"{item['className']}（{item['count']}次）" for item in class_counts
    ) if class_counts else "无"

    duration_str = f"{duration_sec:.1f}秒" if duration_sec else "未知"

    # Detect scene type from task_prompt
    scene = _detect_report_scene(task_prompt)

    # Check evidence conditions for cautious inference
    vehicle_classes  = {"car", "van", "truck", "bus", "motor"}
    person_classes  = {"pedestrian", "people", "person"}
    detected_set     = {item["className"].lower() for item in class_counts}
    has_vehicle      = bool(detected_set & vehicle_classes)
    has_person       = bool(detected_set & person_classes)
    dominant_class   = class_counts[0]["className"].lower() if class_counts else ""
    is_dominant_car  = dominant_class in vehicle_classes
    has_high_density = max_frame_detections >= 10

    # ── Build structured context block ──────────────────────────────────────────
    prompt_parts = [
        f"【检测模型】{model_label}（{model_id}）",
        f"【目标类别】{', '.join(target_classes) if target_classes else '未指定'}",
        f"【检测时长】{duration_str}",
        f"【总目标事件】{total_detection_events} 次",
        f"【检测到类别数】{detected_class_count} 类",
        f"【单帧最大检测数】{max_frame_detections}",
        f"【类别分布】{class_str}",
    ]
    if task_prompt:
        prompt_parts.append(f"【用户任务描述】{task_prompt}")
    if scene != "general":
        prompt_parts.append(f"【场景类型】{scene}")

    detection_context = "\n".join(prompt_parts)

    # ── Build scene-aware system prompt ────────────────────────────────────────
    base_instructions = """你是一个专业的目标检测结果分析助手，服务于"空中视角智能检测系统"的比赛展示场景。

## 核心原则
1. **所有结论必须有数据支撑**——报告内容必须严格基于【检测摘要】中的数据，不编造、不夸大、不脑补。
2. **谨慎推断**——如果检测数据支持某种可能性，可以使用"可能""疑似""提示"等措辞；数据不足时直接描述观测结果，不要强下结论。
3. **结合任务目标**——如果提供了【用户任务描述】，报告应回应该目标，而不只是罗列统计数字。
4. **空中视角意识**——本系统处理的是航拍/俯拍视频，目标在画面中通常较小，检测到少量目标也可能是正常稀疏分布，不宜过度解读。

## 报告风格
- 100~200 字左右，中文输出
- 先描述核心发现，再提供整体评价
- 结尾有结论感，不要只报流水账
- 直接输出正文，不要前缀"报告："等标签，不要输出 JSON"""

    # ── Scene-specific guidance ──────────────────────────────────────────────────
    # Each block adds domain language orientation; they do NOT override evidence rules.
    scene_guidance: dict[str, str] = {
        "traffic_jam": """
## 交通拥堵场景提示
当检测到车辆类别（car/van/truck/bus）时：
  - 若某类车辆（如 car）明显占主导，可描述"画面中车辆目标高度集中，car 占比最高"
  - 若单帧最大检测数较高，可谨慎提及"画面密度较高，可能存在局部拥堵"
  - 若同时检测到 pedestrian/people，可提及"出现人员目标，提示可能存在下车查看等伴随行为"
  - 用词示例："可能存在车流堆积""提示局部通行压力较大""伴随人员活动迹象"
  - 不要写"确认发生拥堵"，只能说"结合密度判断，可能存在拥堵现象" """,
        "highway_traffic": """
## 高速/道路交通巡查场景提示
关注车辆类型的分布特征：
  - 描述主要车型（如 car 为主，或 car+truck+bus 混合）
  - 若多车型同时出现，可提及"多种车型混行"
  - 关注密度，若单帧检测数较高，可谨慎提及"车流密集"
  - 不要编造车道信息、速度信息、拥堵时长等画面中没有的数据
  - 用词示例："车辆以 car 为主""多类型车辆混行""车流密度较高" """,
        "person_search": """
## 人员搜索/搜救场景提示
关注人员目标的检测情况：
  - 描述检测到的人员目标数量和分布
  - 若同时有其他类别出现，说明其他目标类型
  - 谨慎描述搜救相关活动，不确定时不强行推断
  - 用词示例："画面中检测到人员目标""未检测到人员目标""伴随其他目标出现" """,
        "general": """
## 通用场景提示
- 描述主要检测结果和类别分布特征
- 如有任务描述，回应任务目标
- 给出整体评价（检测有效性、覆盖度等）
- 结尾有结论感 """,
    }

    system_prompt = base_instructions + (scene_guidance.get(scene, scene_guidance["general"]))

    # ── Reference example (shown only for traffic/vehicle scenes) ───────────────
    # This is a style reference, not a template to copy verbatim.
    if scene in ("traffic_jam", "highway_traffic") and has_vehicle:
        example_block = """

## 参考报告风格（交通/高速场景示例，仅供风格参考，非模板）
输入摘要特征：
  - 目标类别：car, van, truck, bus, pedestrian, people
  - 车辆类别明显占主导，car 为最多数
  - 单帧最大检测数较高（>= 10）
  - 出现少量 pedestrian / people 目标

示例风格：
"本次检测以高速交通巡查为目标，结果显示画面中车辆目标高度集中，主要以 car 为主，同时检测到 truck、bus、van 等车型，并伴随少量 pedestrian/people 目标。结合类别分布与单帧检测密度判断，该场景可能存在车流明显堆积甚至局部拥堵现象；人员目标的出现也提示部分车辆可能处于低速或停滞状态，并伴随下车查看、路侧活动等情况。整体来看，模型较好地覆盖了高速拥堵场景中的主要交通参与目标，为后续交通态势研判提供了有效依据。"

注意：上述仅为风格参考。若输入摘要中不存在 pedestrian/people，不要写相关内容。"""
    else:
        example_block = ""

    user_prompt = f"请根据以下检测摘要生成中文短报告：\n\n{detection_context}{example_block}"

    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = client.post(
                f"{_AGENT_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {_AGENT_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _AGENT_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 512,
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"Agent 请求超时：{exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Agent API 错误（{exc.response.status_code}）：{exc.response.text[:200]}") from exc
    except Exception as exc:
        raise RuntimeError(f"Agent 请求失败：{exc}") from exc

    try:
        raw = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        logger.warning("[agent_service] Failed to extract report text: %s", exc)
        raise RuntimeError("Agent 返回格式异常") from exc

    return raw
