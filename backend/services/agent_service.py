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

    # Step 6: Closed-set priority — only applies to pure-category tasks;
    # guarded by _contains_attribute_constraints and _contains_low_light_keywords internally,
    # so it will NOT override decisions already made by Steps 3–5
    final_model_id, final_classes, final_reason = _apply_closed_set_priority(
        final_model_id, final_classes, final_reason, user_text
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

    # Build class counts string for the prompt
    class_str = ", ".join(
        f"{item['className']}（{item['count']}次）" for item in class_counts
    ) if class_counts else "无"

    duration_str = f"{duration_sec:.1f}秒" if duration_sec else "未知"

    prompt_parts = [
        f"检测任务使用 {model_label}（{model_id}）模型，",
        f"目标类别：{', '.join(target_classes) if target_classes else '未指定'}。",
        f"检测时长 {duration_str}，",
        f"系统共记录 {total_detection_events} 次目标事件，",
        f"共检测到 {detected_class_count} 个不同类别，",
        f"单帧最大检测数 {max_frame_detections}，",
        f"各类别分布：{class_str}。",
    ]
    if task_prompt:
        prompt_parts.append(f"原始任务描述：{task_prompt}。")

    detection_context = "\n".join(prompt_parts)

    system_prompt = """你是一个专业的目标检测结果分析助手。

## 你的职责
根据提供的结构化检测摘要数据，生成一段简洁的中文短报告（100-200字），帮助用户快速理解检测结果。

## 报告要求
- 必须使用中文输出
- 长度控制在 100-200 字之间
- 内容包括：使用的模型、主要检测结果、类别分布特征、整体评价
- 语言简洁专业，不要啰嗦
- 只需要输出一段文字，不要使用 JSON 或其他格式
- 不要编造数据，所有数据必须来自用户提供的摘要信息
- 不要提及"根据您提供的信息"等套话，直接开始描述结果"""

    user_prompt = f"请根据以下检测摘要生成短报告：\n\n{detection_context}"

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
