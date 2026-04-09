"""
Skyline — Agent Service
Task parsing and recommendation via LLM API (SiliconFlow / OpenAI-compatible).
Only handles "task understanding / plan recommendation" — never triggers real detection.
"""
import json
import logging
import os
from typing import Literal

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


def _load_config() -> None:
    """Read environment variables lazily (call once at first use)."""
    global _AGENT_API_KEY, _AGENT_BASE_URL, _AGENT_MODEL
    if _AGENT_API_KEY is None:
        _AGENT_API_KEY = os.environ.get("AGENT_API_KEY", "").strip()
        _AGENT_BASE_URL = os.environ.get("AGENT_BASE_URL", "").strip() or "https://api.siliconflow.cn/v1"
        _AGENT_MODEL = os.environ.get("AGENT_MODEL", "").strip() or "deepseek-ai/DeepSeek-V3.2"


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
    recommended_model_id = result.get("recommended_model_id", "")
    if recommended_model_id not in MODEL_REGISTRY:
        logger.warning(
            "[agent_service] LLM returned unknown model '%s', falling back to YOLO-World-V2",
            recommended_model_id,
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

    return {
        "intent": intent,
        "recommended_model_id": recommended_model_id,
        "target_classes": target_classes,
        "report_required": bool(result.get("report_required", False)),
        "reason": str(result.get("reason", ""))[:100],
        "confidence": confidence,
    }
