"""
Skyline — Unified Model Manager
================================
Architectural goal: "Unified business workflow + multiple runtime backends."

Layered design
──────────────
  ┌──────────────────────────────────────────────────────────────┐
  │  Inference entry (inference.py)                              │
  │  • knows: model_id, prompt_classes, selected_classes         │
  │  • does NOT know: whether runtime is PT or ONNX              │
  └──────────────────────────┬───────────────────────────────────┘
                             │  get_detector(model_id)
  ┌──────────────────────────▼───────────────────────────────────┐
  │  ModelManager                                                │
  │  • reads RUNTIME_CONFIG[model_id].runtime_type               │
  │  • instantiates PTDetector or ONNXDetector (lazy, cached)    │
  └──────────────────────────┬───────────────────────────────────┘
                             │
         ┌───────────────────┴────────────────────┐
         │                                        │
  ┌──────▼──────────┐                  ┌──────────▼──────────┐
  │  PTDetector      │                  │  ONNXDetector       │
  │  (ultralytics)  │                  │  (onnxruntime)      │
  │  • YOLOWorld    │                  │  • yolov8_car.onnx  │
  │  • YOLOv8 .pt   │                  │  • future ONNX dirs │
  └─────────────────┘                  └────────────────────┘

Each detector implements BaseDetector:
  • load()         — lazy model loading (double-checked locking)
  • infer()        — unified signature: (image_base64, prompt_classes, selected_classes)
  • detections()   — returns list[Detection]

The inference entry does NOT import from detector sub-modules directly.
Instead it calls get_detector(model_id) which handles dispatch internally.
This means adding TensorRT requires zero changes above ModelManager.
"""

from __future__ import annotations

import base64
import logging
import threading
import time as _time
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass
from typing import ClassVar, Optional

import cv2
import numpy as np

from core.models import Detection

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
#  DetectorResult — structured return from BaseDetector.infer()
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class DetectorResult:
    """
    Structured result from BaseDetector.infer(), carrying detections and
    fine-grained timing data.

    All timing values are in milliseconds (float).

    session_ms / preprocess_ms / postprocess_ms are None when the detector
    cannot expose granular timing (e.g. PT models). Frontend will display "--".
    """
    detections:       list[Detection]
    session_ms:       float | None   # Pure model forward time. None if unavailable.
    preprocess_ms:    float | None   # Input preprocessing. None if unavailable.
    postprocess_ms:   float | None   # Output postprocessing. None if unavailable.


# ════════════════════════════════════════════════════════════════════════════════
#  Image decoding (shared utility — used by all detectors)
# ════════════════════════════════════════════════════════════════════════════════

def decode_base64_image(image_base64: str) -> np.ndarray:
    """
    Decode a data URI base64 JPEG/PNG string to a BGR numpy array.
    Strips the "data:image/*;base64," prefix if present.
    Raises ValueError on malformed input or decode failure.
    """
    try:
        b64_payload = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
        raw_bytes = base64.b64decode(b64_payload)
        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)  # BGR
        if img is None:
            raise ValueError("cv2.imdecode returned None — corrupt or unsupported image data")
        return img
    except (ValueError, IndexError):
        raise
    except Exception as exc:
        raise ValueError(f"Base64 image decode failed: {exc}") from exc


# ════════════════════════════════════════════════════════════════════════════════
#  BaseDetector — abstract interface for all runtime backends
# ════════════════════════════════════════════════════════════════════════════════

class BaseDetector(ABC):
    """
    Abstract base class for all detector backends.

    Subclasses must implement:
      load()       — lazy model loading, thread-safe
      _do_infer()  — runtime-specific inference (device, preprocessing, postprocessing)

    The public infer() method handles:
      • Base64 decoding (shared)
      • Classification of model_type (open_vocab vs closed_set)
      • Prompt清洗 (open_vocab only)
      • Post-inference class filtering (closed_set only)

    Subclasses only need to implement _do_infer(raw_image, clean_prompt_classes).
    """

    # Set by subclasses
    model_id: ClassVar[str] = ""
    model_type: ClassVar[str] = "closed_set"   # "open_vocab" | "closed_set"
    conf_threshold: ClassVar[float] = 0.01

    def __init__(self) -> None:
        self._loaded = False
        self._load_lock = threading.Lock()

    # ── Public interface ──────────────────────────────────────────────────────

    def infer(
        self,
        image_base64: str,
        prompt_classes: list[str],
        selected_classes: list[str],
    ) -> DetectorResult:
        """
        Unified inference entry for all runtime backends.

        Args:
            image_base64: JPEG frame as "data:image/jpeg;base64,..." string.
            prompt_classes: Detection targets for open_vocab models.
                            Ignored for closed_set models.
            selected_classes: Post-inference filter for closed_set models.
                              Ignored for open_vocab models.

        Returns:
            DetectorResult with detections and fine-grained timing.
            Timing values are in milliseconds; None means unavailable.

        Timing attribution:
          preprocess_ms  — base64 decode (always) + runtime-specific input prep
                          (e.g. ONNX _preprocess(): resize/letterbox/normalize).
                          NOTE: runtime-specific prep is added inside _do_infer().
          session_ms     — purely the model forward pass. None if unavailable (PT).
          postprocess_ms — runtime-specific output processing (e.g. ONNX NMS +
                          coordinate transform) + optional class filtering.
                          NOTE: ONNX postprocess is fully handled inside
                          _do_infer(). Class filtering is added here if needed.
        """
        # ── Step 1: Decode image (base64) — always attributed to preprocess_ms ──
        t_decode_start = _time.perf_counter()
        img = decode_base64_image(image_base64)
        decode_ms = (_time.perf_counter() - t_decode_start) * 1000

        # ── Step 2: Clean prompt classes (open_vocab only) — no timing cost ──────
        if self.model_type == "open_vocab":
            clean_prompts = self._clean_prompt_classes(prompt_classes)
        else:
            clean_prompts = []

        # ── Step 3: Runtime-specific inference (timing done inside) ─────────────
        # Returns (detections, preprocess_ms_without_decode, session_ms, postprocess_ms)
        detections, rt_preprocess_ms, session_ms, postprocess_ms = self._do_infer(
            img, clean_prompts
        )

        # Combine base64 decode into preprocess_ms
        if rt_preprocess_ms is not None:
            preprocess_ms = decode_ms + rt_preprocess_ms
        else:
            preprocess_ms = None

        # ── Step 4: Post-inference class filtering (closed_set only) ─────────────
        if self.model_type == "closed_set" and selected_classes:
            filter_set = {c.lower() for c in selected_classes}
            detections = [
                d for d in detections
                if d.class_name.lower() in filter_set
            ]
        # NOTE: class filtering cost is negligible (< 0.01 ms) and is NOT
        # added to postprocess_ms to keep the metric comparable across runtimes.

        # ── Step 5: Cleanup ─────────────────────────────────────────────────
        del img

        return DetectorResult(
            detections=detections,
            session_ms=session_ms,
            preprocess_ms=preprocess_ms,
            postprocess_ms=postprocess_ms,
        )

    # ── Abstract methods (subclass implements) ───────────────────────────────

    @abstractmethod
    def _do_infer(
        self,
        img: np.ndarray,
        clean_prompt_classes: list[str],
    ) -> tuple[list[Detection], float | None, float | None, float | None]:
        """
        Runtime-specific inference. Called after image decode and prompt cleaning.

        Args:
            img: BGR numpy array (HxWx3), already decoded from base64.
            clean_prompt_classes: Cleaned, lowercased class list (open_vocab only;
                                  empty list for closed_set).

        Returns:
            (detections, preprocess_ms, session_ms, postprocess_ms)
              preprocess_ms — runtime-specific input prep (e.g. ONNX resize/letterbox).
                              None if unavailable.
              session_ms    — pure model forward time. None if unavailable (PT).
              postprocess_ms — runtime-specific output processing (NMS, coord transform).
                              None if unavailable.
        """
        ...

    @abstractmethod
    def load(self) -> None:
        """Load the model into memory (e.g. onto GPU). Called lazily on first infer."""
        ...

    # ── Shared utilities ─────────────────────────────────────────────────────

    @staticmethod
    def _clean_prompt_classes(classes: list[str]) -> list[str]:
        """Flatten comma-separated tokens and lowercase them."""
        clean: list[str] = []
        for c in classes:
            clean.extend(x.strip().lower() for x in c.split(",") if x.strip())
        return clean or ["object"]

    @staticmethod
    def _parse_boxes(
        boxes,
        names: dict[int, str],
        img: np.ndarray,
    ) -> list[Detection]:
        """Parse ultralytics Boxes object → list[Detection]."""
        h, w = img.shape[:2]
        detections: list[Detection] = []
        if boxes is None:
            return detections
        for i in range(len(boxes)):
            x1, y1, x2, y2 = boxes.xyxy[i].tolist()
            conf = float(boxes.conf[i])
            cls_idx = int(boxes.cls[i])
            cls_name = names.get(cls_idx, str(cls_idx))
            detections.append(Detection(
                class_name=cls_name,
                confidence=round(conf, 3),
                bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
            ))
        return detections

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} model_id={self.model_id}>"


# ════════════════════════════════════════════════════════════════════════════════
#  PTDetector — Ultralytics (YOLO-World, YOLOv8 .pt)
# ════════════════════════════════════════════════════════════════════════════════

class PTDetector(BaseDetector):
    """
    PyTorch detector via ultralytics.

    Handles two sub-types internally (controlled by self.model_type):
      • open_vocab  — YOLOWorld path: use set_classes(prompt) before predict
      • closed_set  — YOLOv8 path:   predict all classes, filter post-inference

    Thread-safety:
      • _load_lock:    double-checked locking for lazy init
      • _infer_lock:   serializes set_classes()+predict() on shared GPU
    """

    # Set via __init__ per-subclass
    _weight_path: Path | str
    _device: str = "cuda:0"
    _warmup: bool = True

    def __init__(self) -> None:
        super().__init__()
        self._model: Optional["YOLO_T"] = None   # YOLO or YOLOWorld
        self._infer_lock = threading.Lock()

    # ── load() — lazy init ───────────────────────────────────────────────────

    def load(self) -> None:
        if self._loaded:
            return
        with self._load_lock:
            if self._loaded:
                return
            self._model = self._load_impl()
            self._loaded = True
            logger.info("[PTDetector] model_id=%s loaded, device=%s", self.model_id, self._device)

    def _load_impl(self) -> "YOLO_T":
        """Subclass-specific loading. Override in subclasses."""
        raise NotImplementedError

    # ── _do_infer() — dispatch by model_type ─────────────────────────────────

    def _do_infer(
        self,
        img: np.ndarray,
        clean_prompt_classes: list[str],
    ) -> tuple[list[Detection], float | None, float | None, float | None]:
        """
        Runtime-specific inference.

        Returns:
            (detections, preprocess_ms, session_ms, postprocess_ms)
              All three timing values are None — ultralytics does not expose
              internal layer timing granularity. Frontend will display "--".
        """
        self.load()
        model = self._model

        if self.model_type == "open_vocab":
            detections = self._infer_open_vocab(model, img, clean_prompt_classes)
        else:
            detections = self._infer_closed_set(model, img)

        return detections, None, None, None

    def _infer_open_vocab(
        self,
        model: "YOLO_T",
        img: np.ndarray,
        clean_prompt_classes: list[str],
    ) -> list[Detection]:
        """YOLOWorld path: set_classes() then predict()."""
        try:
            with self._infer_lock:
                # set_classes() rebuilds text embeddings on CPU; re-pin to GPU after.
                model.set_classes(clean_prompt_classes)
                model.to(self._device)
                results = model.predict(img, verbose=False, conf=self.conf_threshold, device=self._device)
        finally:
            pass

        if results and results[0].boxes is not None:
            return self._parse_boxes(results[0].boxes, results[0].names, img)
        return []

    def _infer_closed_set(
        self,
        model: "YOLO_T",
        img: np.ndarray,
    ) -> list[Detection]:
        """YOLOv8 path: predict all classes, let caller filter by selected_classes."""
        try:
            with self._infer_lock:
                results = model.predict(img, verbose=False, conf=self.conf_threshold, device=self._device)
        finally:
            pass

        if results and results[0].boxes is not None:
            return self._parse_boxes(results[0].boxes, results[0].names, img)
        return []


# ── Concrete PT subclasses ────────────────────────────────────────────────────
# Each subclass pins its model_id, model_type, weight_path, device, warmup.
# No logic duplication — everything inherited from PTDetector.

class _YOLOWorldV2(PTDetector):
    """YOLO-World-V2 open-vocabulary detector (ultralytics.YOLOWorld)."""
    model_id = "YOLO-World-V2"
    model_type = "open_vocab"
    conf_threshold = 0.25   # 调高置信度阈值以减少误检

    def __init__(self, weight_path: Path | str, device: str = "cuda:0",
                 conf_threshold: float = 0.5) -> None:
        self._weight_path = weight_path
        self._device = device
        self._warmup = True
        self.conf_threshold = conf_threshold
        super().__init__()

    def _load_impl(self) -> "YOLOWorld":
        from ultralytics import YOLOWorld
        logger.info("[YOLOWorldV2] Loading from %s …", self._weight_path)
        model: "YOLOWorld" = YOLOWorld(str(self._weight_path))
        model.to(self._device)

        if self._warmup:
            logger.info("[YOLOWorldV2] Running GPU warmup …")
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            model.set_classes(["object"])
            model.to(self._device)
            model.predict(dummy, verbose=False, conf=0.99, device=self._device)
            del dummy
            logger.info("[YOLOWorldV2] Warmup complete.")
        return model


class _YOLOv8Base(PTDetector):
    """YOLOv8n COCO pre-trained detector (ultralytics.YOLO)."""
    model_id = "YOLOv8-Base"
    model_type = "closed_set"
    conf_threshold = 0.25

    def __init__(self, weight_path: Path | str, device: str = "cuda:0",
                 conf_threshold: float = 0.5) -> None:
        self._weight_path = weight_path
        self._device = device
        self._warmup = False     # Small model — no warmup needed
        self.conf_threshold = conf_threshold
        super().__init__()

    def _load_impl(self) -> "YOLO":
        from ultralytics import YOLO
        logger.info("[YOLOv8Base] Loading from %s …", self._weight_path)
        model: "YOLO" = YOLO(str(self._weight_path))
        model.to(self._device)
        return model


class _YOLOv8Car(PTDetector):
    """YOLOv8 custom vehicle detector (ultralytics.YOLO, fine-tuned .pt)."""
    model_id = "YOLOv8-Car"
    model_type = "closed_set"
    conf_threshold = 0.5

    def __init__(self, weight_path: Path | str, device: str = "cuda:0",
                 conf_threshold: float = 0.5) -> None:
        self._weight_path = weight_path
        self._device = device
        self._warmup = False     # Large 400 MB model — skip warmup
        self.conf_threshold = conf_threshold
        super().__init__()

    def _load_impl(self) -> "YOLO":
        from ultralytics import YOLO
        logger.info("[YOLOv8Car] Loading from %s …", self._weight_path)
        model: "YOLO" = YOLO(str(self._weight_path))
        model.to(self._device)
        return model


# ════════════════════════════════════════════════════════════════════════════════
#  ONNXDetector — onnxruntime
# ════════════════════════════════════════════════════════════════════════════════

class ONNXDetector(BaseDetector):
    """
    ONNX detector via onnxruntime (GPU-accelerated via CUDAExecutionProvider).

    Expected ONNX layout (ultralytics YOLOv8 export, opset >= 11):
      Input:   name="images",   shape=[1, 3, H, W]   (float32, RGB, NCHW)
               H and W are typically 640; preprocessing applies letterbox resize.

      Output formats — detected automatically from tensor shape:
        (a) 5-class YOLOv8-Org  (yolov8_car.onnx):
              shape=[1, 10, N]
              10 = 4 (cx,cy,w,h) + 1 (objectness) + 5 (class scores)
              Class names are passed in at construction time.

        (b) 80-class COCO YOLOv8:
              shape=[1, 84, N]
              84 = 4 (cx,cy,w,h) + 80 (class scores)

      Post-processing pipeline:
        1. Run session.run() — raw tensor on GPU EP or CPU EP
        2. Transpose [1, P, N] → [N, P]
        3. Detect format from second dimension (10 vs 84 + len(class_names))
        4. Split bbox from class scores; skip objectness for 5-class format
        5. Filter by confidence_threshold
        6. Convert letterbox coordinates back to original image space
        7. Clip bboxes to image bounds

    Requirements:
      pip install onnxruntime-gpu     # GPU acceleration (CUDA EP)
      pip install onnxruntime          # CPU-only fallback
    """

    model_type = "closed_set"     # YOLOv8 ONNX is always fixed-class
    conf_threshold = 0.25

    def __init__(
        self,
        model_id: str,
        weight_path: Path | str,
        class_names: list[str],
        device: str = "cuda:0",
        conf_threshold: float = 0.01,
    ) -> None:
        """
        Args:
            model_id: Registry model identifier.
            weight_path: Path to the .onnx file.
            class_names: Ordered list of class names (index → name).
            device: "cuda:0" → use CUDA EP; "cpu" → CPU EP.
            conf_threshold: Minimum confidence to include a detection.
        """
        super().__init__()
        self._model_id = model_id
        self._weight_path = Path(weight_path) if isinstance(weight_path, str) else weight_path
        self._class_names = class_names
        self._device = device
        self.conf_threshold = conf_threshold     # override class-level default
        self._session: Optional["onnxruntime.InferenceSession"] = None
        self._input_name: str = ""
        self._output_name: str = ""

    @property
    def model_id(self) -> str:
        return self._model_id

    # ── load() ────────────────────────────────────────────────────────────────

    def load(self) -> None:
        if self._loaded:
            return
        with self._load_lock:
            if self._loaded:
                return

            import onnxruntime as ort

            # ── Version + available providers (one-time log at load) ─────────────
            logger.info(
                "[ONNXDetector] ort version=%s | available_providers=%s",
                ort.__version__,
                ort.get_available_providers(),
            )

            # ── Build ExecutionProvider list ───────────────────────────────────
            providers: list = []
            cuda_requested = "cuda" in self._device.lower()

            if cuda_requested:
                available = ort.get_available_providers()
                if "CUDAExecutionProvider" in available:
                    providers = [
                        ("CUDAExecutionProvider", {
                            "device_id": int(self._device.split(":")[-1]) if ":" in self._device else 0,
                        }),
                        "CPUExecutionProvider",
                    ]
                    logger.info("[ONNXDetector] CUDAExecutionProvider available — creating GPU session")
                else:
                    providers = ["CPUExecutionProvider"]
                    logger.warning(
                        "[ONNXDetector] device=cuda but CUDAExecutionProvider not in available_providers=%s. "
                        "Falling back to CPUExecutionProvider.",
                        available,
                    )
            else:
                providers = ["CPUExecutionProvider"]

            # ── SessionOptions ──────────────────────────────────────────────────
            sess_opts = ort.SessionOptions()
            sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            if cuda_requested:
                sess_opts.enable_mem_pattern = True
                sess_opts.enable_cpu_mem_arena = True
                sess_opts.intra_op_num_threads = 4

            # ── Preload CUDA shared libs via torch before creating session ───────
            # torch.cuda is already verified available; this forces ORT to find
            # the same CUDA/cuDNN libs that torch loaded, avoiding the
            # "libcudnn.so.9: cannot open shared object file" error.
            try:
                import torch  # noqa: F401
                ort.preload_dlls()
                logger.info(
                    "[ONNXDetector] torch imported + ort.preload_dlls() called. "
                    "ORT available providers after preload: %s",
                    ort.get_available_providers(),
                )
            except Exception as exc:
                logger.warning(
                    "[ONNXDetector] torch import / ort.preload_dlls() failed: %s. "
                    "Continuing without preload — CUDA may still fail.",
                    exc,
                )

            # ── Create session ───────────────────────────────────────────────────
            logger.info("[ONNXDetector] Creating session for %s with providers=%r …", self._model_id, providers)
            self._session = self._make_session(str(self._weight_path), sess_opts, providers)

            # ── Confirm ACTUAL providers in the live session (only at load) ──────
            if self._session is not None:
                self._input_name = self._session.get_inputs()[0].name
                self._output_name = self._session.get_outputs()[0].name
                actual_providers = self._session.get_providers()
                provider_opts = {}
                if "CUDAExecutionProvider" in actual_providers:
                    try:
                        provider_opts = self._session.get_provider_options().get("CUDAExecutionProvider", {})
                    except Exception:
                        pass

                logger.info(
                    "[ONNXDetector] %s loaded. input=%r output=%r | ACTUAL providers=%r",
                    self._model_id, self._input_name, self._output_name, actual_providers,
                )

                if "CUDAExecutionProvider" in actual_providers:
                    logger.info(
                        "[ONNXDetector] %s — CUDA EP ACTIVE (device=%s, options=%r)",
                        self._model_id, self._device, provider_opts,
                    )
                else:
                    logger.warning(
                        "[ONNXDetector] %s — CUDA EP NOT ACTIVE. Session is using: %s. "
                        "Inference will be slow (~650–740 ms/frame). "
                        "Fix: conda install -c nvidia cuda-nvcc cuda-toolkit cudnn "
                        "to make CUDA 12.x + cuDNN 9 available for onnxruntime-gpu.",
                        self._model_id, actual_providers,
                    )

            self._loaded = True

    def _make_session(
        self,
        path: str,
        sess_opts: "ort.SessionOptions",
        providers: list,
    ) -> "onnxruntime.InferenceSession | None":
        """Factory method — overridable for testing."""
        try:
            import onnxruntime as ort
            return ort.InferenceSession(path, sess_opts, providers=providers)  # type: ignore[return-value]
        except ImportError:
            logger.error("[ONNXDetector] onnxruntime is not installed. Run: pip install onnxruntime-gpu")
            return None
        except Exception as exc:
            logger.error("[ONNXDetector] Failed to load ONNX model %s: %s", path, exc)
            return None

    # ── _do_infer() ──────────────────────────────────────────────────────────

    def _do_infer(
        self,
        img: np.ndarray,
        clean_prompt_classes: list[str],
    ) -> tuple[list[Detection], float | None, float | None, float | None]:
        """
        ONNX inference with YOLOv8 post-processing.

        Timing attribution:
          preprocess_ms  — _preprocess(): resize + letterbox + BGR→RGB + CHW transpose + normalize.
                           NOTE: base64 decode is added in BaseDetector.infer().
          session_ms     — purely session.run() (pure model forward).
          postprocess_ms — _postprocess(): NMS + coordinate transform + threshold filter.
        """
        import time as _time

        self.load()

        if self._session is None:
            logger.warning("[ONNXDetector] No session loaded for %s", self._model_id)
            return [], None, None, None

        # ── preprocess_ms: _preprocess() — resize + letterbox + normalize ────────
        t_pre_start = _time.perf_counter()
        input_tensor = self._preprocess(img)
        preprocess_ms = (_time.perf_counter() - t_pre_start) * 1000

        # ── session_ms: pure model forward ───────────────────────────────────────
        t_session_start = _time.perf_counter()
        try:
            outputs = self._session.run(
                [self._output_name],
                {self._input_name: input_tensor},
            )
        except Exception as exc:
            logger.error("[ONNXDetector] Inference failed for %s: %s", self._model_id, exc)
            return [], preprocess_ms, None, None
        session_ms = (_time.perf_counter() - t_session_start) * 1000

        # ── postprocess_ms: NMS + coordinate transform ──────────────────────────
        t_post_start = _time.perf_counter()
        raw = outputs[0]
        detections = self._postprocess(raw, img)
        postprocess_ms = (_time.perf_counter() - t_post_start) * 1000

        return detections, preprocess_ms, session_ms, postprocess_ms

    @staticmethod
    def _nms(
        boxes: np.ndarray,
        scores: np.ndarray,
        class_indices: np.ndarray,
        iou_threshold: float = 0.45,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Per-class Non-Maximum Suppression.

        Args:
            boxes: [N, 4] array of bounding boxes in xyxy format (model space).
            scores: [N] array of confidence scores.
            class_indices: [N] array of class indices.
            iou_threshold: IoU threshold for NMS.

        Returns:
            Filtered (boxes, scores, class_indices) after NMS.
        """
        if len(boxes) == 0:
            return boxes, scores, class_indices

        # Convert to list for per-class processing
        boxes = boxes.tolist()
        scores = scores.tolist()
        class_indices = class_indices.tolist()

        # Group boxes by class
        from collections import defaultdict
        class_groups: dict[int, list[int]] = defaultdict(list)
        for idx, cls_idx in enumerate(class_indices):
            class_groups[int(cls_idx)].append(idx)

        keep_indices: list[int] = []

        # Apply NMS per class
        for cls_idx, indices in class_groups.items():
            cls_boxes = np.array([boxes[i] for i in indices], dtype=np.float32)
            cls_scores = np.array([scores[i] for i in indices], dtype=np.float32)

            # Sort by score descending
            order = cls_scores.argsort()[::-1]

            keep = []
            suppressed = set()

            for i in order:
                if i in suppressed:
                    continue
                keep.append(i)
                # Suppress overlapping boxes with lower scores
                for j in order:
                    if j == i or j in suppressed:
                        continue
                    iou = ONNXDetector._compute_iou(
                        cls_boxes[i], cls_boxes[j]
                    )
                    if iou > iou_threshold:
                        suppressed.add(j)

            # Map back to global indices
            for k in keep:
                keep_indices.append(indices[k])

        keep_indices = sorted(keep_indices)
        return (
            np.array([boxes[i] for i in keep_indices], dtype=np.float32),
            np.array([scores[i] for i in keep_indices], dtype=np.float32),
            np.array([class_indices[i] for i in keep_indices], dtype=np.int32),
        )

    @staticmethod
    def _compute_iou(box1: np.ndarray, box2: np.ndarray) -> float:
        """
        Compute IoU between two boxes in xyxy format.

        Args:
            box1, box2: [4] arrays in [x1, y1, x2, y2] format.

        Returns:
            IoU value in [0, 1].
        """
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        inter_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        if inter_area == 0:
            return 0.0

        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union_area = box1_area + box2_area - inter_area

        return inter_area / union_area if union_area > 0 else 0.0

    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        """
        Resize img to model input size and normalize to [0,1] float32.
        Returns CHW tensor of shape [1, 3, H, W].
        """
        # Default: 640x640, letterbox resize
        target_h, target_w = 640, 640
        h, w = img.shape[:2]

        # Compute scale to fit within 640x640 preserving aspect ratio
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)

        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Create canvas and paste
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        y_offset = (target_h - new_h) // 2
        x_offset = (target_w - new_w) // 2
        canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized

        # BGR → RGB, HWC → CHW
        canvas = canvas[:, :, ::-1]                      # BGR → RGB
        canvas = canvas.transpose(2, 0, 1)               # HWC → CHW
        canvas = canvas.astype(np.float32) / 255.0       # Normalize [0, 1]

        # Add batch dimension: [1, 3, H, W]
        return np.expand_dims(canvas, axis=0)

    def _postprocess(self, raw: np.ndarray, original_img: np.ndarray) -> list[Detection]:
        """
        Parse YOLOv8 ONNX output → list[Detection].

        raw shape: [1, num_params, num_predictions]

          5-class YOLOv8-Org (yolov8_car.onnx): [1, 10, N]
            10 = 4 (cx,cy,w,h) + 1 (objectness) + 5 (class scores)

          80-class COCO YOLOv8: [1, 84, N]
            84 = 4 (cx,cy,w,h) + 80 (class scores)

          This method detects the format dynamically by checking the second
          dimension of the output tensor.

        Post-processing steps:
          1. Squeeze batch dim: [1, P, N] → [P, N]
          2. Transpose: [P, N] → [N, P]
          3. Split bbox (cols 0:4) from class scores (cols 4:)
          4. For 5-class format: skip objectness (col 4), take class_scores = cols 5:
          5. Filter by confidence_threshold
          6. Convert letterbox coordinates back to original image space
        """
        # ── 1. Remove batch dim → [P, N], then transpose → [N, P] ──────────────
        data = np.squeeze(raw, axis=0)      # [P, N]
        data = data.T                       # [N, P]

        ih, iw = original_img.shape[:2]

        # ── 2. Detect format and extract class scores ───────────────────────────
        num_bbox = 4
        if data.shape[1] == num_bbox + 1 + len(self._class_names):
            # 5-class format: [cx, cy, w, h, obj, c0, c1, c2, c3, c4]
            # Skip objectness (col 4), take only class score columns
            bbox_cols = data[:, :num_bbox]           # cols 0:4
            class_scores = data[:, num_bbox + 1:]    # cols 5:  (skip objectness)
        elif data.shape[1] == num_bbox + len(self._class_names):
            # COCO / class-score-only format: [cx, cy, w, h, c0, c1, ...]
            bbox_cols = data[:, :num_bbox]
            class_scores = data[:, num_bbox:]
        else:
            # Fallback: assume [cx, cy, w, h, class0..classN]
            bbox_cols = data[:, :num_bbox]
            class_scores = data[:, num_bbox:]

        # ── 3. Per-box: max class score + class index ───────────────────────────
        scores = class_scores.max(axis=1)       # confidence for top class
        class_indices = class_scores.argmax(axis=1)

        # ── 4. Filter by confidence threshold ───────────────────────────────────
        mask = scores >= self.conf_threshold
        bbox_cols = bbox_cols[mask]
        scores = scores[mask]
        class_indices = class_indices[mask]

        # ── 4.5. NMS (Non-Maximum Suppression) ─────────────────────────────────────
        # Apply per-class NMS to remove overlapping boxes
        # NMS needs xyxy format (top-left + bottom-right corners)
        if len(bbox_cols) > 0:
            # Convert from xywh (center + size) to xyxy (top-left + bottom-right)
            cx, cy, bw, bh = bbox_cols[:, 0], bbox_cols[:, 1], bbox_cols[:, 2], bbox_cols[:, 3]
            boxes_xyxy = np.stack([
                cx - bw / 2,  # x1
                cy - bh / 2,  # y1
                cx + bw / 2,  # x2
                cy + bh / 2,  # y2
            ], axis=1)

            boxes_xyxy, scores, class_indices = self._nms(
                boxes_xyxy, scores, class_indices, iou_threshold=0.45
            )
            # Keep as xyxy for coordinate conversion below
            bbox_cols = boxes_xyxy

        # ── 5. Letterbox → original image coordinate conversion ─────────────────
        # Model was trained / exported for 640x640 input.
        # _preprocess letterboxes the image into a 640x640 canvas.
        # We undo that letterboxing here.
        TARGET_W, TARGET_H = 640, 640
        # Original image dims are floats; use them as-is (not int-truncated)
        orig_scale = min(TARGET_W / iw, TARGET_H / ih)        # float scale factor
        new_w = iw * orig_scale   # scaled width (float)
        new_h = ih * orig_scale   # scaled height (float)
        x_off = (TARGET_W - new_w) / 2.0   # letterbox left offset (float)
        y_off = (TARGET_H - new_h) / 2.0   # letterbox top offset  (float)

        detections: list[Detection] = []
        for j in range(len(bbox_cols)):
            x1, y1, x2, y2 = bbox_cols[j]

            # Undo letterbox: model-space → scaled-image-space → original-space
            ox1 = (x1 - x_off) / orig_scale
            oy1 = (y1 - y_off) / orig_scale
            ox2 = (x2 - x_off) / orig_scale
            oy2 = (y2 - y_off) / orig_scale

            # Convert to top-left + width/height format for Detection
            x1 = int(round(ox1))
            y1 = int(round(oy1))
            ow = int(round(ox2 - ox1))
            oh = int(round(oy2 - oy1))

            # Clip to original image bounds
            x1 = max(0, min(x1, iw - 1))
            y1 = max(0, min(y1, ih - 1))
            ow = max(1, min(ow, iw - x1))
            oh = max(1, min(oh, ih - y1))

            conf = float(scores[j])
            cls_idx = int(class_indices[j])
            cls_name = (
                self._class_names[cls_idx]
                if 0 <= cls_idx < len(self._class_names)
                else str(cls_idx)
            )

            detections.append(Detection(
                class_name=cls_name,
                confidence=round(conf, 3),
                bbox=(x1, y1, ow, oh),
            ))

        return detections


# ════════════════════════════════════════════════════════════════════════════════
#  Detector factory registry  (model_id → subclass of BaseDetector)
# ════════════════════════════════════════════════════════════════════════════════
#  ModelManager reads RUNTIME_CONFIG[model_id].runtime_type and looks up the
#  corresponding factory function here. Adding TensorRT just means adding:
#    "trt": _build_trt_detector,
#  to _RUNTIME_FACTORIES — no changes needed elsewhere.

_RUNTIME_FACTORIES: dict[str, callable] = {}


def _register_runtime(runtime_type: str):
    """Decorator: register a factory function for a runtime_type."""
    def decorator(fn: callable) -> callable:
        _RUNTIME_FACTORIES[runtime_type] = fn
        return fn
    return decorator


# ── PT factories ──────────────────────────────────────────────────────────────

@_register_runtime("pt")
def _build_pt_detector(model_id: str, weight_path: Path | str, device: str,
                       conf_threshold: float = 0.5, **kwargs) -> PTDetector:
    """Route a PT model_id to the correct PTDetector subclass."""
    if model_id == "YOLO-World-V2":
        return _YOLOWorldV2(weight_path=weight_path, device=device, conf_threshold=conf_threshold)
    elif model_id == "YOLOv8-Base":
        return _YOLOv8Base(weight_path=weight_path, device=device, conf_threshold=conf_threshold)
    else:
        raise ValueError(
            f"PT model '{model_id}' has no PTDetector subclass. "
            f"Add a _YOLOv8* subclass and register it in _build_pt_detector."
        )


# ── ONNX factories ─────────────────────────────────────────────────────────────

@_register_runtime("onnx")
def _build_onnx_detector(
    model_id: str,
    weight_path: Path | str,
    class_names: list[str],
    device: str,
    conf_threshold: float = 0.01,
    **kwargs,
) -> ONNXDetector:
    """Build an ONNXDetector for a given model_id."""
    return ONNXDetector(
        model_id=model_id,
        weight_path=weight_path,
        class_names=class_names,
        device=device,
        conf_threshold=conf_threshold,
    )


# ════════════════════════════════════════════════════════════════════════════════
#  ModelManager — unified entry point for the execution layer
# ════════════════════════════════════════════════════════════════════════════════

class ModelManager:
    """
    Factory that creates and caches detector instances by runtime_type.

    Public API (used by inference.py):
        get_detector(model_id) → BaseDetector
        list_models() → list[str]

    Internal state:
        _cache:  model_id → BaseDetector  (lazy singleton per model)
        _lock:   protects cache writes during concurrent first access

    Extending to a new runtime (e.g. TensorRT):
        1. Add "trt" → _RUNTIME_FACTORIES
        2. Implement TRTDetector(BaseDetector)
        3. Add a _build_trt_detector() factory and @_register_runtime("trt")
        4. Add ModelConfig entry in registry.py RUNTIME_CONFIG
        → Zero changes needed in inference.py or above.
    """

    def __init__(self) -> None:
        self._cache: dict[str, BaseDetector] = {}
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_detector(self, model_id: str) -> BaseDetector:
        """
        Return a lazy-loaded, cached detector instance for model_id.

        Reads RUNTIME_CONFIG[model_id] to determine runtime_type, then
        dispatches to the appropriate factory (PTDetector or ONNXDetector).
        """
        if model_id in self._cache:
            return self._cache[model_id]

        with self._lock:
            if model_id in self._cache:          # double-check after acquiring lock
                return self._cache[model_id]

            detector = self._create_detector(model_id)
            self._cache[model_id] = detector
            logger.info("[ModelManager] Cached detector: model_id=%s runtime=%s",
                        model_id, type(detector).__name__)
            return detector

    @staticmethod
    def list_models() -> list[str]:
        """Return all registered model IDs (from RUNTIME_CONFIG)."""
        from models.registry import RUNTIME_CONFIG
        return list(RUNTIME_CONFIG.keys())

    # ── Internal ─────────────────────────────────────────────────────────────

    def _create_detector(self, model_id: str) -> BaseDetector:
        """
        Look up RUNTIME_CONFIG, resolve weight_path, call the runtime factory.
        Raises ValueError if model_id is unknown or runtime_type is unregistered.
        """
        from models.registry import RUNTIME_CONFIG, MODEL_REGISTRY

        cfg = RUNTIME_CONFIG.get(model_id)
        if cfg is None:
            raise ValueError(
                f"Model '{model_id}' has no RUNTIME_CONFIG entry. "
                f"Available: {list(RUNTIME_CONFIG)}"
            )

        factory = _RUNTIME_FACTORIES.get(cfg.runtime_type)
        if factory is None:
            raise ValueError(
                f"Runtime '{cfg.runtime_type}' for model '{model_id}' is not registered. "
                f"Register a factory with @_register_runtime('{cfg.runtime_type}'). "
                f"Available: {list(_RUNTIME_FACTORIES)}"
            )

        # Resolve weight_path: if relative, resolve to WEIGHTS_DIR
        weight_path: Path | str = cfg.weight_path
        if isinstance(weight_path, str) and not Path(weight_path).is_absolute():
            # Assume it is relative to WEIGHTS_DIR (e.g. "yolov8n.pt")
            weights_dir = Path(__file__).resolve().parent.parent.parent / "weights"
            weight_path = weights_dir / weight_path

        # Build kwargs from ModelConfig fields
        kwargs: dict = {
            "weight_path": str(weight_path),
            "device": cfg.device,
        }

        # ONNX needs class_names (from MODEL_REGISTRY)
        if cfg.runtime_type == "onnx":
            caps = MODEL_REGISTRY.get(model_id)
            if caps is None:
                raise ValueError(f"ONNX model '{model_id}' has no MODEL_REGISTRY entry.")
            kwargs["class_names"] = caps.supported_classes

        # Apply per-model confidence override
        if "conf_threshold" not in kwargs:
            kwargs["conf_threshold"] = cfg.confidence_threshold

        return factory(model_id=model_id, **kwargs)


# ── Module-level singleton ─────────────────────────────────────────────────────

_manager = ModelManager()


def get_detector(model_id: str) -> BaseDetector:
    """
    Convenience shortcut to the module-level ModelManager singleton.
    Used exclusively by inference.py — the rest of the system uses model_id strings.
    """
    return _manager.get_detector(model_id)
