"""
Skyline — Model Manager (Phase 3: Real YOLO Integration)

Architecture decisions:
  - YOLOWorldV2 uses `ultralytics.YOLOWorld` (the correct subclass with set_classes())
  - YOLOv8Base uses `ultralytics.YOLO` with post-inference class filtering
  - Both models are **lazily loaded** on first infer() call (prevents blocking FastAPI startup)
  - A threading.Lock serializes set_classes() + predict() to prevent race conditions
    when multiple WebSocket clients share the same model instance on a single GPU
  - Base64 decode errors raise ValueError (caught by inference.py, returned as empty frame)
  - CUDA OOM and other runtime errors propagate up and are logged by inference.py

Thread-safety model:
  - _load_lock: protects lazy initialization (double-checked locking pattern)
  - _infer_lock: serializes set_classes()+predict() pair on shared GPU resource
"""
import base64
import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Optional

import cv2
import numpy as np
from ultralytics import YOLO, YOLOWorld

from core.models import Detection

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = ["YOLO-World-V2", "YOLOv8-Base", "YOLOv8-Car"]

# Resolve weights directory relative to this file: backend/models/ → ../../weights/
WEIGHTS_DIR = Path(__file__).resolve().parent.parent.parent / "weights"


# ── Image decoding ─────────────────────────────────────────────────────────────

def _decode_base64_image(image_base64: str) -> np.ndarray:
    """
    Decode a data URI base64 JPEG/PNG string to a BGR numpy array.

    Strips the "data:image/*;base64," prefix if present.
    Raises ValueError on malformed input or decode failure.
    """
    try:
        b64_payload = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
        raw_bytes = base64.b64decode(b64_payload)
        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)  # returns BGR
        if img is None:
            raise ValueError("cv2.imdecode returned None — corrupt or unsupported image data")
        return img
    except (ValueError, IndexError):
        raise
    except Exception as exc:
        raise ValueError(f"Base64 image decode failed: {exc}") from exc


# ── Abstract base ──────────────────────────────────────────────────────────────

class BaseVisionModel(ABC):
    """Abstract interface every vision model backend must implement."""

    name: ClassVar[str]

    @abstractmethod
    def infer(self, image_base64: str, target_classes: list[str]) -> list[Detection]:
        """
        Run inference on a single frame.

        Args:
            image_base64: JPEG frame as "data:image/jpeg;base64,..." string
            target_classes: open-vocabulary class names, e.g. ["car", "person"]

        Returns:
            List of Detection(class_name, confidence, bbox=[x,y,w,h]) objects
        """
        ...

    def __repr__(self) -> str:
        return f"<VisionModel: {self.name}>"


# ── YOLO-World-V2 (open-vocabulary) ───────────────────────────────────────────

class YOLOWorldV2(BaseVisionModel):
    """
    YOLO-World-V2 open-vocabulary detector.

    Uses ultralytics.YOLOWorld (the only subclass that exposes set_classes()).
    set_classes() injects the user's natural-language prompt as detection targets.
    The _infer_lock ensures set_classes() and predict() execute atomically on one GPU.
    """
    name = "YOLO-World-V2"
    _WEIGHT = WEIGHTS_DIR / "yolov8s-worldv2.pt"

    def __init__(self) -> None:
        self._model: Optional[YOLOWorld] = None
        self._load_lock  = threading.Lock()   # guards lazy init
        self._infer_lock = threading.Lock()   # serializes set_classes + predict

    def _ensure_loaded(self) -> YOLOWorld:
        """Double-checked locking: fast path if already loaded."""
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is None:
                weight_path = str(self._WEIGHT)
                logger.info("Loading YOLO-World-V2 from %s …", weight_path)
                self._model = YOLOWorld(weight_path)

                # ── 强制显存对齐 ───────────────────────────────────────────────
                # set_classes() 每次都在 CPU 新建文本嵌入；加载后立刻整体移到
                # cuda:0，确保后续所有参数都在同一设备上。
                self._model.to("cuda:0")
                logger.info("YOLO-World-V2 moved to cuda:0.")

                # ── GPU 预热（Warmup）────────────────────────────────────────
                # 用一张随机噪声图跑一次 predict，强制 CUDA 内核编译完毕、
                # 计算图在 GPU 里锁死，避免第一帧真实请求触发 JIT 卡顿。
                logger.info("Running GPU warmup inference …")
                dummy = np.zeros((640, 640, 3), dtype=np.uint8)
                self._model.set_classes(["object"])
                self._model.to("cuda:0")   # set_classes 后再钉一次
                self._model.predict(dummy, verbose=False, conf=0.99, device=0)
                del dummy
                logger.info("YOLO-World-V2 warmup complete — GPU graph locked.")

        return self._model

    def infer(self, image_base64: str, target_classes: list[str]) -> list[Detection]:
        model = self._ensure_loaded()

        # ── 1. 强制 Prompt 清洗 ────────────────────────────────────────────────
        # 前端可能传来 ["car, person"] 单元素逗号串，强行拆分展平
        clean_classes: list[str] = []
        for c in target_classes:
            clean_classes.extend([x.strip().lower() for x in c.split(",") if x.strip()])
        if not clean_classes:
            clean_classes = ["object"]   # 终极兜底

        logger.warning("!!! [DEBUG] raw target_classes=%s → clean_classes=%s",
                       target_classes, clean_classes)

        # ── 2. 解码 + 图像核验日志 ─────────────────────────────────────────────
        img = _decode_base64_image(image_base64)
        logger.warning("!!! [DEBUG] Image shape: %s, dtype: %s, classes set to: %s",
                       img.shape, img.dtype, clean_classes)
        h, w = img.shape[:2]

        # ── 3. 推理（极限低阈值 conf=0.01，连噪点都框出来）──────────────────────
        detections: list[Detection] = []
        try:
            with self._infer_lock:
                model.set_classes(clean_classes)
                # set_classes() 在 CPU 上新建文本嵌入张量；调用后必须重新
                # 将整个模型钉回 cuda:0，否则 predict() 时设备不一致报错。
                model.to("cuda")
                results = model.predict(img, verbose=True, conf=0.01, device=0)
        finally:
            del img

        # ── 4. 解析检测框 ──────────────────────────────────────────────────────
        if results and results[0].boxes is not None:
            boxes = results[0].boxes
            names = results[0].names
            logger.warning("!!! [DEBUG] Raw boxes count: %d, names mapping: %s",
                           len(boxes), names)
            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                conf     = float(boxes.conf[i])
                cls_idx  = int(boxes.cls[i])
                cls_name = names.get(cls_idx, str(cls_idx))
                detections.append(Detection(
                    class_name=cls_name,
                    confidence=round(conf, 3),
                    bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                ))
        else:
            logger.warning("!!! [DEBUG] results[0].boxes is None — model returned nothing")

        # ── 5. 将后端渲染结果保存到磁盘，用于与前端渲染对比 ─────────────────────
        try:
            res_plotted = results[0].plot()
            cv2.imwrite("debug_backend_out.jpg", res_plotted)
            logger.warning("!!! [DEBUG] Saved debug_backend_out.jpg (%dx%d)",
                           res_plotted.shape[1], res_plotted.shape[0])
        except Exception as e:
            logger.error("Failed to save debug image: %s", e)

        del results
        logger.warning("!!! [DEBUG] Final detections count: %d → %s",
                       len(detections), [(d.class_name, d.confidence) for d in detections])
        return detections


# ── YOLOv8-Base (COCO fixed classes) ──────────────────────────────────────────

class YOLOv8Base(BaseVisionModel):
    """
    YOLOv8n detector pre-trained on COCO (80 fixed classes).

    target_classes acts as a post-inference filter: results are pruned to
    class names that appear in the user's prompt (case-insensitive match).
    Auto-downloads yolov8n.pt on first run if not cached by ultralytics.
    """
    name = "YOLOv8-Base"
    _WEIGHT = "yolov8n.pt"   # ultralytics auto-downloads to ~/.cache/ultralytics/

    def __init__(self) -> None:
        self._model: Optional[YOLO] = None
        self._load_lock  = threading.Lock()
        self._infer_lock = threading.Lock()

    def _ensure_loaded(self) -> YOLO:
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is None:
                logger.info("Loading YOLOv8-Base (%s) …", self._WEIGHT)
                self._model = YOLO(self._WEIGHT)
                logger.info("YOLOv8-Base loaded successfully.")
        return self._model

    def infer(self, image_base64: str, target_classes: list[str]) -> list[Detection]:
        model = self._ensure_loaded()
        img = _decode_base64_image(image_base64)
        h, w = img.shape[:2]

        # Optional class filter (lowercase for case-insensitive match)
        filter_set: Optional[set[str]] = (
            {c.lower() for c in target_classes} if target_classes else None
        )

        detections: list[Detection] = []
        try:
            with self._infer_lock:
                results = model.predict(img, verbose=False, conf=0.01)
        finally:
            del img

        if results and results[0].boxes is not None:
            boxes = results[0].boxes
            names = results[0].names
            for i in range(len(boxes)):
                cls_idx  = int(boxes.cls[i])
                cls_name = names.get(cls_idx, str(cls_idx))
                # Apply user prompt filter
                if filter_set and cls_name.lower() not in filter_set:
                    continue
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                conf = float(boxes.conf[i])
                detections.append(Detection(
                    class_name=cls_name,
                    confidence=round(conf, 3),
                    bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                ))

        del results
        logger.info("[%s] %dx%d → %d detection(s), filter=%s",
                    self.name, w, h, len(detections), list(filter_set or []))
        return detections


# ── YOLOv8-Car (custom fine-tuned, 5 vehicle classes) ─────────────────────────

class YOLOv8Car(BaseVisionModel):
    """
    YOLOv8 fine-tuned on vehicle dataset (car, truck, bus, van, freight_car).

    post-inference filter: results are pruned to class names that appear in
    the user's selected_classes list (case-insensitive match).
    Loads the custom weight from WEIGHTS_DIR / "yolov8_car.pt".
    GPU warmup is skipped here because the model file may be large (≈400 MB);
    warmup is safe to add later if startup latency becomes a concern.
    """
    name = "YOLOv8-Car"
    _WEIGHT = WEIGHTS_DIR / "yolov8_car.pt"

    def __init__(self) -> None:
        self._model: Optional[YOLO] = None
        self._load_lock  = threading.Lock()
        self._infer_lock = threading.Lock()

    def _ensure_loaded(self) -> YOLO:
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is None:
                weight_path = str(self._WEIGHT)
                logger.info("Loading YOLOv8-Car from %s …", weight_path)
                self._model = YOLO(weight_path)
                # Pin to GPU immediately so all subsequent predict() calls are on GPU
                self._model.to("cuda:0")
                logger.info("YOLOv8-Car loaded and pinned to cuda:0.")
        return self._model

    def infer(self, image_base64: str, target_classes: list[str]) -> list[Detection]:
        """
        Args:
            image_base64: JPEG frame as "data:image/jpeg;base64,..." string
            target_classes: ignored for closed-set models (use selected_classes instead)

        Returns:
            List of Detection(class_name, confidence, bbox=[x,y,w,h]) objects
        """
        model = self._ensure_loaded()
        img = _decode_base64_image(image_base64)
        h, w = img.shape[:2]

        # Optional class filter (lowercase for case-insensitive match)
        filter_set: Optional[set[str]] = (
            {c.lower() for c in target_classes} if target_classes else None
        )

        detections: list[Detection] = []
        try:
            with self._infer_lock:
                results = model.predict(img, verbose=False, conf=0.01, device=0)
        finally:
            del img

        if results and results[0].boxes is not None:
            boxes = results[0].boxes
            names = results[0].names
            for i in range(len(boxes)):
                cls_idx  = int(boxes.cls[i])
                cls_name = names.get(cls_idx, str(cls_idx))
                # Apply user selected_classes filter
                if filter_set and cls_name.lower() not in filter_set:
                    continue
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                conf = float(boxes.conf[i])
                detections.append(Detection(
                    class_name=cls_name,
                    confidence=round(conf, 3),
                    bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                ))

        del results
        logger.info("[%s] %dx%d → %d detection(s), filter=%s",
                    self.name, w, h, len(detections), list(filter_set or []))
        return detections


# ── Registry & Factory ─────────────────────────────────────────────────────────

_REGISTRY: dict[str, type[BaseVisionModel]] = {
    YOLOWorldV2.name: YOLOWorldV2,
    YOLOv8Base.name:  YOLOv8Base,
    YOLOv8Car.name:  YOLOv8Car,
}


class ModelManager:
    """
    Factory that instantiates model objects on demand and caches them.
    Each model is a singleton within this manager — lazy-loaded on first use.
    """

    def __init__(self) -> None:
        self._cache: dict[str, BaseVisionModel] = {}

    def get_model(self, name: str) -> BaseVisionModel:
        if name in self._cache:
            return self._cache[name]
        cls = _REGISTRY.get(name)
        if cls is None:
            raise ValueError(
                f"Unknown model '{name}'. Available: {list(_REGISTRY.keys())}"
            )
        instance = cls()
        self._cache[name] = instance
        logger.info("Model registered in cache: %s", name)
        return instance

    @staticmethod
    def list_models() -> list[str]:
        return list(_REGISTRY.keys())


# Module-level singleton — shared across all WebSocket sessions
_manager = ModelManager()


def get_model(name: str) -> BaseVisionModel:
    """Convenience shortcut to the module-level ModelManager singleton."""
    return _manager.get_model(name)
