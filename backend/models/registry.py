"""
Skyline — Model Registry and Capabilities
========================================
Centralized registry for all vision models with their capabilities.
This is the single source of truth for frontend dynamic form rendering.

Each model entry contains:
- model_id: unique identifier (matches model_manager._REGISTRY keys)
- display_name: human-readable name for UI
- model_type: 'open_vocab' | 'closed_set'
- supports_prompt: whether the model accepts custom class prompts
- prompt_editable: whether user can freely edit the prompt
- supported_classes: list of classes this model can detect (empty for open_vocab)
- class_filter_enabled: whether user can filter results among supported classes
- description: model description for UI tooltips
"""
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class ModelCapabilities:
    """Capabilities and metadata for a single model."""
    model_id: str
    display_name: str
    model_type: str  # 'open_vocab' | 'closed_set'
    supports_prompt: bool
    prompt_editable: bool
    supported_classes: list[str] = field(default_factory=list)
    class_filter_enabled: bool = False
    description: str = ""

    def to_dict(self) -> dict:
        """Serialize to dict for JSON API responses."""
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "model_type": self.model_type,
            "supports_prompt": self.supports_prompt,
            "prompt_editable": self.prompt_editable,
            "supported_classes": self.supported_classes,
            "class_filter_enabled": self.class_filter_enabled,
            "description": self.description,
        }


# ── COCO 80 classes for YOLOv8-Base ────────────────────────────────────────────

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
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
    "toothbrush",
]


# ── Model Registry ─────────────────────────────────────────────────────────────

MODEL_REGISTRY: dict[str, ModelCapabilities] = {
    "YOLO-World-V2": ModelCapabilities(
        model_id="YOLO-World-V2",
        display_name="YOLO-World V2",
        model_type="open_vocab",
        supports_prompt=True,
        prompt_editable=True,
        supported_classes=[],  # Open vocabulary: no fixed class list
        class_filter_enabled=False,
        description="开放词汇目标检测，支持自定义任意类别。输入自然语言描述即可检测。",
    ),
    "YOLOv8-Base": ModelCapabilities(
        model_id="YOLOv8-Base",
        display_name="YOLOv8 Base (COCO)",
        model_type="closed_set",
        supports_prompt=False,
        prompt_editable=False,
        supported_classes=COCO_CLASSES,
        class_filter_enabled=True,  # Can filter which COCO classes to display
        description="COCO 预训练模型，支持 80 类固定类别。不可自定义类别，但可筛选显示。",
    ),
    "YOLOv8-Car": ModelCapabilities(
        model_id="YOLOv8-Car",
        display_name="YOLOv8 Car (Custom)",
        model_type="closed_set",
        supports_prompt=False,
        prompt_editable=False,
        supported_classes=["car", "truck", "bus", "van", "freight_car"],
        class_filter_enabled=True,
        description="车辆专用模型，Fine-tuned on car, truck, bus, van, freight_car。不可自定义类别，但可筛选显示。",
    ),
}


def get_model_capabilities(model_id: str) -> ModelCapabilities | None:
    """Get capabilities for a specific model."""
    return MODEL_REGISTRY.get(model_id)


def list_all_models() -> list[ModelCapabilities]:
    """Get all registered models as a list."""
    return list(MODEL_REGISTRY.values())


def is_model_open_vocab(model_id: str) -> bool:
    """Check if a model is open vocabulary (supports custom prompts)."""
    caps = get_model_capabilities(model_id)
    return caps.supports_prompt if caps else False


def is_class_supported(model_id: str, class_name: str) -> bool:
    """Check if a class is in the model's supported list."""
    caps = get_model_capabilities(model_id)
    if not caps:
        return False
    if caps.model_type == "open_vocab":
        return True  # Open vocab supports any class
    return class_name.lower() in [c.lower() for c in caps.supported_classes]


def filter_supported_classes(model_id: str, classes: list[str]) -> list[str]:
    """Filter a list of classes to only those supported by the model."""
    caps = get_model_capabilities(model_id)
    if not caps:
        return []
    if caps.model_type == "open_vocab":
        return classes  # Open vocab: all classes are valid
    # Closed set: filter to only supported classes
    supported_lower = {c.lower() for c in caps.supported_classes}
    return [c for c in classes if c.lower() in supported_lower]
