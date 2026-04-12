"""
Skyline — Model Registry and Capabilities
=========================================
Centralized registry for all vision models.

This module holds two conceptually separate registries:

  1. MODEL_REGISTRY[model_id] → ModelCapabilities
     • Single source of truth for the **frontend** (GET /api/models).
     • Contains only UI-facing fields: display_name, model_type, supported_classes,
       class_filter_enabled, description.
     • Does NOT expose runtime_type — the frontend does not need to know PT vs ONNX.

  2. RUNTIME_CONFIG[model_id] → ModelConfig
     • Single source of truth for the **backend execution layer**.
     • Contains runtime fields: runtime_type, weight_path, confidence_threshold, etc.
     • Used exclusively by model_manager.py to instantiate the correct detector.

Rationale for the split: keeping the two concerns (UI capability vs. runtime loading)
in separate registries avoids bloating the frontend API response and makes it trivial
to add a new backend runtime (TensorRT, OpenVINO …) without touching the frontend.

Adding a new model is a two-step process:
  (a) Add a ModelCapabilities entry to MODEL_REGISTRY   (frontend / API)
  (b) Add a ModelConfig entry to RUNTIME_CONFIG          (backend / execution)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# ── Resolve weights directory relative to this file ─────────────────────────────
#   backend/models/registry.py → ../../weights/
_WEIGHTS_DIR = Path(__file__).resolve().parent.parent.parent / "weights"


# ════════════════════════════════════════════════════════════════════════════════
#  Layer 1: ModelCapabilities  (frontend-facing)
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class ModelCapabilities:
    """UI-facing metadata for a single model."""
    model_id: str
    display_name: str
    model_type: Literal["open_vocab", "closed_set"]
    supports_prompt: bool          # Can user type arbitrary class names?
    prompt_editable: bool          # Can user freely edit the prompt?
    supported_classes: list[str] = field(default_factory=list)  # [] for open_vocab
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


# ════════════════════════════════════════════════════════════════════════════════
#  Layer 2: ModelConfig  (backend execution-facing)
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class ModelConfig:
    """
    Backend execution configuration for a single model.

    runtime_type determines which detector class is instantiated by ModelManager:
      • "pt"   → PTDetector  (ultralytics YOLO / YOLOWorld)
      • "onnx" → ONNXDetector (onnxruntime)
      • "trt"  → TRTDetector (future: tensorrt-python)
      • "openvino" → OpenVINODetector (future)
    """
    runtime_type: Literal["pt", "onnx", "trt", "openvino"]
    weight_path: Path | str          # Relative to WEIGHTS_DIR, or absolute
    confidence_threshold: float = 0.25
    warmup_enabled: bool = True      # Run dummy inference after first load
    device: str = "cuda:0"          # CUDA device string; "cpu" for fallback


# ════════════════════════════════════════════════════════════════════════════════
#  Shared class lists
# ════════════════════════════════════════════════════════════════════════════════

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

VEHICLE_CLASSES = ["car", "truck", "bus", "van", "freight_car"]

# VisDrone 训练集 10 类，索引顺序与模型输出 argmax 严格对应
# 格式：[4 bbox + 10 class_scores]，class_scores.argmax() 的返回值直接映射到此列表
# 来源：yolov8x_visdrone_best.yaml names 字段
VISDRONE_CLASSES = [
    "pedestrian",       # 0
    "people",           # 1
    "bicycle",          # 2
    "car",              # 3
    "van",              # 4
    "truck",            # 5
    "tricycle",         # 6
    "awning-tricycle",  # 7
    "bus",              # 8
    "motor",            # 9
]


# ════════════════════════════════════════════════════════════════════════════════
#  MODEL_REGISTRY  —  frontend / API source of truth
# ════════════════════════════════════════════════════════════════════════════════

MODEL_REGISTRY: dict[str, ModelCapabilities] = {
    "YOLO-World-V2": ModelCapabilities(
        model_id="YOLO-World-V2",
        display_name="YOLO-World V2",
        model_type="open_vocab",
        supports_prompt=True,
        prompt_editable=True,
        supported_classes=[],       # Open vocabulary: no fixed class list
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
        class_filter_enabled=True,
        description="COCO 预训练模型，支持 80 类固定类别。不可自定义类别，但可筛选显示。",
    ),
    "YOLOv8-Car": ModelCapabilities(
        model_id="YOLOv8-Car",
        display_name="YOLOv8 Car (Custom)",
        model_type="closed_set",
        supports_prompt=False,
        prompt_editable=False,
        supported_classes=VEHICLE_CLASSES,
        class_filter_enabled=True,
        description="车辆专用模型（ONNX），Fine-tuned on car, truck, bus, van, freight_car。不可自定义类别，但可筛选显示。",
    ),
    "YOLOv8-VisDrone": ModelCapabilities(
        model_id="YOLOv8-VisDrone",
        display_name="YOLOv8 VisDrone",
        model_type="closed_set",
        supports_prompt=False,
        prompt_editable=False,
        supported_classes=VISDRONE_CLASSES,
        class_filter_enabled=True,
        description="VisDrone 数据集 Fine-tuned 模型，支持 pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor 十类。",
    ),
    # ── Person-only specialized models ────────────────────────────────────────
    "YOLOv8-Person": ModelCapabilities(
        model_id="YOLOv8-Person",
        display_name="YOLOv8 Person (可见光专用)",
        model_type="closed_set",
        supports_prompt=False,
        prompt_editable=False,
        supported_classes=["person"],
        class_filter_enabled=True,
        description="可见光场景人体检测专用模型（ONNX），Fine-tuned on person 类。适合正常光照条件下的行人、人员、人体检测。",
    ),
    "YOLOv8-Thermal-Person": ModelCapabilities(
        model_id="YOLOv8-Thermal-Person",
        display_name="YOLOv8 Thermal Person (热红外专用)",
        model_type="closed_set",
        supports_prompt=False,
        prompt_editable=False,
        supported_classes=["person"],
        class_filter_enabled=True,
        description="热红外/弱光场景人体检测专用模型（ONNX），针对夜间、弱光、低照度、热成像、红外等环境下的人体识别 Fine-tuned。",
    ),
}


# ════════════════════════════════════════════════════════════════════════════════
#  RUNTIME_CONFIG  —  backend execution source of truth
# ════════════════════════════════════════════════════════════════════════════════
#  weight_path is resolved relative to _WEIGHTS_DIR (skyline/weights/).
#  Use an absolute Path or prefix "~/…" for paths outside that directory.

RUNTIME_CONFIG: dict[str, ModelConfig] = {
    # ── PT models ──────────────────────────────────────────────────────────────
    "YOLO-World-V2": ModelConfig(
        runtime_type="pt",
        weight_path=_WEIGHTS_DIR / "yolov8s-worldv2.pt",
        confidence_threshold=0.25,
        warmup_enabled=True,
        device="cuda:0",
    ),
    "YOLOv8-Base": ModelConfig(
        runtime_type="pt",
        weight_path="yolov8n.pt",          # ultralytics auto-downloads to ~/.cache/
        confidence_threshold=0.25,
        warmup_enabled=False,              # Small model, no warmup needed
        device="cuda:0",
    ),

    # ── ONNX models ──────────────────────────────────────────────────────────
    "YOLOv8-Car": ModelConfig(
        runtime_type="onnx",
        weight_path=_WEIGHTS_DIR / "yolov8_car.onnx",
        confidence_threshold=0.25,
        warmup_enabled=True,
        device="cuda:0",                   # CUDAExecutionProvider when onnxruntime-gpu installed
    ),
    "YOLOv8-VisDrone": ModelConfig(
        runtime_type="onnx",
        weight_path=_WEIGHTS_DIR / "VisDrone" / "yolov8x_visdrone_best.onnx",
        confidence_threshold=0.25,
        warmup_enabled=True,
        device="cuda:0",
    ),
    # ── Person-only specialized ONNX models ──────────────────────────────────
    "YOLOv8-Person": ModelConfig(
        runtime_type="onnx",
        weight_path=_WEIGHTS_DIR / "person_only" / "best_person.onnx",
        confidence_threshold=0.25,
        warmup_enabled=True,
        device="cuda:0",
    ),
    "YOLOv8-Thermal-Person": ModelConfig(
        runtime_type="onnx",
        weight_path=_WEIGHTS_DIR / "person_only" / "best_thermal_person.onnx",
        confidence_threshold=0.25,
        warmup_enabled=True,
        device="cuda:0",
    ),
}


# ════════════════════════════════════════════════════════════════════════════════
#  Public helpers
# ════════════════════════════════════════════════════════════════════════════════

def get_model_capabilities(model_id: str) -> ModelCapabilities | None:
    return MODEL_REGISTRY.get(model_id)


def list_all_models() -> list[ModelCapabilities]:
    """Frontend-facing: all models with UI metadata."""
    return list(MODEL_REGISTRY.values())


def get_runtime_config(model_id: str) -> ModelConfig | None:
    """Backend execution-facing: get runtime config for a model."""
    return RUNTIME_CONFIG.get(model_id)


def is_model_open_vocab(model_id: str) -> bool:
    caps = get_model_capabilities(model_id)
    return caps.supports_prompt if caps else False


def is_class_supported(model_id: str, class_name: str) -> bool:
    caps = get_model_capabilities(model_id)
    if not caps:
        return False
    if caps.model_type == "open_vocab":
        return True
    return class_name.lower() in [c.lower() for c in caps.supported_classes]


def filter_supported_classes(model_id: str, classes: list[str]) -> list[str]:
    """Filter a class list to only those supported by the model."""
    caps = get_model_capabilities(model_id)
    if not caps:
        return []
    if caps.model_type == "open_vocab":
        return classes
    supported_lower = {c.lower() for c in caps.supported_classes}
    return [c for c in classes if c.lower() in supported_lower]


def validate_model_exists(model_id: str) -> None:
    """Raise KeyError if model_id is not registered in both layers."""
    if model_id not in MODEL_REGISTRY:
        raise KeyError(f"Unknown model '{model_id}'. Available: {list(MODEL_REGISTRY)}")
    if model_id not in RUNTIME_CONFIG:
        raise KeyError(
            f"Model '{model_id}' has no runtime config. "
            f"Add an entry to RUNTIME_CONFIG."
        )
