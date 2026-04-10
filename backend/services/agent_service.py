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
}


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
) -> tuple[str, list[str], str]:
    """
    Apply closed-set priority: if all target classes are covered by a closed-set
    model, switch to that model and update the reason accordingly.

    Returns (final_model_id, final_target_classes, final_reason).
    """
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
- 如果完全不明确，返回 {"intent": "other", "recommended_model_id": "YOLO-World-V2", "target_classes": ["object"], "report_required": false, "reason": "任务描述不明确，默认使用开放词汇模型", "confidence": "low"}"""


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

    # Step 3: Apply closed-set priority — may override recommended_model_id
    final_model_id, final_classes, final_reason = _apply_closed_set_priority(
        recommended_model_id, target_classes, raw_reason
    )

    return {
        "intent": intent,
        "recommended_model_id": final_model_id,
        "target_classes": final_classes,
        "report_required": bool(result.get("report_required", False)),
        "reason": final_reason,
        "confidence": confidence,
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
