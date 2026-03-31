# Skyline 后端架构文档

> 本文档面向大型语言模型（LLM）和新开发者，完整描述 Skyline 后端的设计哲学、模块划分和交互流程。
> 代码版本对应 2026-03-31，包含 ONNX CUDA 加速链路和 LIFO 调度器。

---

## 1. 设计哲学

**"统一业务层 + 多运行时后端"**

推理调度层（`inference.py`）完全不知道也不关心模型跑在 PyTorch 上还是 ONNX 上。它只知道"模型 ID + 要检测哪些类 + 帧图像"。具体用哪套 runtime 由 `ModelManager` 查配置决定。

这样做的好处是：在不改动任何业务逻辑的前提下，可以随时切换或新增 runtime 后端（PT / ONNX / TensorRT / OpenVINO），只需要在 `model_manager.py` 注册一个新 factory。

---

## 2. 目录结构

```
backend/
├── main.py                  # FastAPI 入口，注册路由，启动 lifespan
├── core/
│   ├── models.py            # Pydantic 数据模型（VideoFrame, InferenceResult, Detection）
│   ├── inference.py         # LIFO 调度器 + _blocking_inference（统一推理入口）
│   └── database.py          # SQLite 初始化（历史记录存储）
├── models/
│   ├── registry.py          # 双注册表：MODEL_REGISTRY（前端用） + RUNTIME_CONFIG（执行层用）
│   ├── model_manager.py     # ModelManager 工厂 + BaseDetector 抽象类 + PTDetector + ONNXDetector
│   └── history.py           # 历史记录 CRUD
└── routers/
    ├── video_stream.py      # WebSocket /api/ws/video_stream
    ├── history.py           # REST /api/history/*
    └── models.py            # REST /api/models/*（前端获取模型能力）
```

---

## 3. 数据模型

### 3.1 客户端 → 服务端（上行）

```
VideoFrame
├── message_type: "video_frame"
├── timestamp: float
├── frame_id: int
├── image_base64: str          # "data:image/jpeg;base64,..." 或纯 base64
├── model_id: str              # 模型 ID，如 "YOLOv8-Car"
├── prompt_classes: list[str]  # 开放词汇：用户输入的类别名
├── selected_classes: list[str]# 闭集：前端筛选器选中的类别
├── selected_model: str|null  # 兼容旧客户端的别名
└── target_classes: list[str] # 兼容旧字段
```

### 3.2 服务端 → 客户端（下行）

```
InferenceResult
├── message_type: "inference_result"
├── frame_id: int
├── timestamp: float
├── inference_time_ms: float  # 端到端耗时
└── detections: list[Detection]

Detection
├── class_name: str
├── confidence: float
└── bbox: (x, y, w, h)         # 原始图像坐标系
```

---

## 4. 完整交互流程

```
[Frontend]
    │
    │ WebSocket text (JSON: VideoFrame)
    ▼
[routers/video_stream.py]
    │
    ├─ 创建 InferenceScheduler()
    ├─ asyncio.create_task(scheduler.run(callback))
    │
    │ while True:
    │     raw = await websocket.receive_text()
    │     frame = VideoFrame.model_validate(data)   ← Pydantic 校验
    │     await scheduler.push_frame(frame)          ← LIFO 入队
    ▼
[core/inference.py — InferenceScheduler]
    │
    │ async run(callback):
    │     while _running:
    │         frame = await self._pop_frame()       ← LIFO 出队（丢弃旧帧）
    │         result = await run_in_threadpool(     ← 线程池，避免阻塞事件循环
    │             _blocking_inference, frame
    │         )
    │         await callback(result)
    ▼
[core/inference.py — _blocking_inference]
    │
    │ t0 = perf_counter()
    │
    │ # 1. 模型 ID 解析（含降级逻辑）
    │ selected_model = frame.model_id or frame.selected_model or "YOLO-World-V2"
    │
    │ # 2. 根据 model_type 构造调用参数
    │ if caps.model_type == "open_vocab":
    │     prompt_classes = [清洗后的类别名], selected_classes = []
    │ else:
    │     prompt_classes = [], selected_classes = list(frame.selected_classes)
    │
    │ # 3. 获取 detector（懒加载 + 缓存）
    │ detector = get_detector(selected_model)
    │     │
    │     │ ModelManager.get_detector(model_id):
    │     │   1. 查 RUNTIME_CONFIG[model_id].runtime_type
    │     │   2. 调对应 factory
    │     │   3. 缓存，返回 detector 实例
    │     ▼
    │     detector.load()  ← 首次调用时触发
    │     │
    │     │ ONNXDetector.load():
    │     │   1. ort.get_available_providers() 打印版本
    │     │   2. import torch + ort.preload_dlls()
    │     │   3. ort.InferenceSession(providers=[CUDA, CPU])
    │     │   4. session.get_providers() 确认实际 EP
    │     ▼
    │
    │ # 4. 调用统一推理接口
    │ detections = detector.infer(image_base64, prompt_classes, selected_classes)
    │
    │     BaseDetector.infer():
    │     │
    │     │ Step 1: base64 解码 → img (BGR HxWx3 np.ndarray)
    │     │ Step 2: prompt 清洗（open_vocab）
    │     │ Step 3: self._do_infer(img, clean_prompts)
    │     │     │
    │     │     │ ONNXDetector._do_infer():
    │     │     │ t0 = perf_counter()
    │     │     │ input_tensor = self._preprocess(img)
    │     │     │     # BGR→RGB, resize 640x640 letterbox, HWC→CHW, /255.0
    │     │     │     # 返回 shape=[1, 3, 640, 640] float32
    │     │     │ outputs = self._session.run([output_name], {input_name: input_tensor})
    │     │     │ detections = self._postprocess(outputs[0], img)
    │     │     │     # raw [1, P, N] → [N, P]
    │     │     │     # 自动识别 5-class（yolov8_car）或 80-class（COCO）格式
    │     │     │     # conf 过滤 + letterbox 坐标还原 + 边界裁剪
    │     │     │ t3 = perf_counter()
    │     │     │ logger.info("onnx timing | preprocess=%.1f | session=%.1f | postprocess=%.1f")
    │     │     │ return detections
    │     │
    │     │ Step 4: 闭集后置过滤（closed_set + selected_classes）
    │     │
    │ elapsed_ms = (perf_counter() - t0) * 1000
    │
    │ return InferenceResult(frame_id, timestamp, elapsed_ms, detections)
    ▼
[video_stream.py — callback]
    │ await websocket.send_text(result.model_dump_json())
    ▼
[Frontend] 渲染检测结果
```

---

## 5. 各模块职责详解

### 5.1 `main.py`

仅负责：创建 FastAPI 实例、注册 CORS、注册三个路由器、启动时执行 `init_db()`。

### 5.2 `core/models.py`

Pydantic v2 数据模型。用 `model_validate` 做 WebSocket 消息校验，格式错误返回 `ErrorMessage` 而不 crash。

### 5.3 `core/inference.py`

**`_blocking_inference(frame)`**：运行在线程池（`run_in_threadpool`），完全不知道 runtime 类型，只负责：模型 ID 解析、区分 open_vocab/closed_set、调用 `detector.infer()`、异常捕获、返回 `InferenceResult`。

**`InferenceScheduler`**：LIFO 单帧缓冲调度器。
- 新帧到来时若 AI 线程忙，新帧直接覆盖 `_latest_frame`，丢弃旧帧
- 仪表盘永远显示当前时刻，不会积压延迟
- `asyncio.Lock` 保证 `_latest_frame` 写操作线程安全

### 5.4 `models/registry.py` — 双注册表

**`MODEL_REGISTRY[model_id] → ModelCapabilities`**（前端用）：display_name、model_type、supported_classes、description。前端 `GET /api/models` 返回这个。

**`RUNTIME_CONFIG[model_id] → ModelConfig`**（执行层用）：runtime_type、weight_path、confidence_threshold、device。`ModelManager` 查这个决定实例化哪个 detector。

两表分离保证：运行时后端切换不影响前端 API 响应。

### 5.5 `models/model_manager.py`

#### BaseDetector 抽象类

所有 detector 共享 `infer()`（base64 解码 + prompt 清洗 + 后置类别过滤），子类只需实现：
- `load()`：懒加载模型
- `_do_infer(img, clean_prompt_classes)`：推理逻辑

#### PTDetector

内部区分 open_vocab（YOLOWorld）和 closed_set（YOLOv8）。`set_classes()` + `predict()` 序列化为 `self._infer_lock`。有 GPU 预热。

#### ONNXDetector

见第六节专题。

### 5.6 `models/history.py`

SQLite 存储历史检测记录。

### 5.7 `routers/`

| 端点 | 类型 | 作用 |
|------|------|------|
| `/api/ws/video_stream` | WebSocket | 双向视频流推理 |
| `/api/models` | GET | 列表所有模型能力 |
| `/api/models/{model_id}/capabilities` | GET | 单模型详细信息 |
| `/api/history` | GET/POST | 查询/保存历史记录 |

---

## 6. ONNXDetector 专题

### 6.1 为什么用 ONNX

- 比 PyTorch 更轻量（不需要完整 torch 运行时）
- 对 CUDA / TensorRT / DirectML 等硬件有原生 Execution Provider
- 图优化（常量折叠、算子融合）比 eager mode 更彻底
- 模型文件（.onnx）静态序列化，部署简单

### 6.2 Execution Provider 机制

ORT 支持多个 EP，按列表顺序优先级尝试：

```python
providers = [
    ("CUDAExecutionProvider", {"device_id": 0}),
    "CPUExecutionProvider",   # fallback
]
```

创建 `InferenceSession` 时，ORT 从左到右尝试每个 EP：
- 初始化成功则用它
- 失败则静默回退到下一个

**`session.get_providers()`** 返回的是实际生效的 EP 列表，不一定是请求的列表。

### 6.3 `ort.preload_dlls()` 的作用

**问题**：在 conda / 多 CUDA 版本共存环境中，torch 和 onnxruntime 各自独立搜索 CUDA 库。ORT 报告 `CUDAExecutionProvider` 在 `available_providers` 里存在（编译期检测），但创建 session 时找不到 `libcudnn.so.9`（运行期动态链接失败），静默回退到 CPU。

**解决**：创建 session 前先 `import torch`（torch 加载 CUDA 库更鲁棒），再调用 `ort.preload_dlls()`，通知 ORT 复用 torch 已加载的同一套 CUDA 动态库。

```python
import torch
ort.preload_dlls()
self._session = ort.InferenceSession(path, sess_opts, providers=[...])
```

### 6.4 分段计时日志

每帧推理打印三个阶段耗时：

```
[ONNXDetector] onnx timing | preprocess=3.2 ms | session=18.7 ms | postprocess=5.1 ms | detections=12
```

- **preprocess**：cv2 resize + letterbox + BGR→RGB + CHW transpose + normalize
- **session**：ORT 执行推理（GPU 或 CPU）
- **postprocess**：NMS 替代逻辑 + 坐标还原 + 边界裁剪

### 6.5 ONNX 输出格式自动识别

`_postprocess()` 通过检查 tensor 第二维大小自动识别格式，无需改代码：

| 第二维大小 | 格式 | 说明 |
|-----------|------|------|
| `4 + 1 + len(class_names)` | 5-class YOLOv8-Org | 4 bbox + 1 objectness + N class scores |
| `4 + len(class_names)` | COCO 80-class | 4 bbox + 80 class scores |

---

## 7. 日志解读指南

### 7.1 模型加载阶段（仅首次推理时打印一次）

**正常（CUDA 激活）**：
```
[ONNXDetector] ort version=1.23.2 | available_providers=[...]
[ONNXDetector] CUDAExecutionProvider available — creating GPU session
[ONNXDetector] torch imported + ort.preload_dlls() called. ORT available providers after preload: [...]
[ONNXDetector] Creating session for YOLOv8-Car with providers=[...]
[ONNXDetector] YOLOv8-Car loaded. input='images' output='output0' | ACTUAL providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
[ONNXDetector] YOLOv8-Car — CUDA EP ACTIVE (device=cuda:0, options={...})
```

**异常（CUDA 回退到 CPU）**：
```
[ONNXDetector] ort version=1.23.2 | available_providers=[...]
[ONNXDetector] CUDAExecutionProvider available — creating GPU session
[ONNXDetector] torch imported + ort.preload_dlls() called. ORT available providers after preload: [...]
[ONNXDetector] Creating session for YOLOv8-Car with providers=[...]
[ONNXDetector] YOLOv8-Car loaded. input='images' output='output0' | ACTUAL providers=['CPUExecutionProvider']
[ONNXDetector] YOLOv8-Car — CUDA EP NOT ACTIVE. Session is using: ['CPUExecutionProvider'].
```

**CUDA 激活时的 onnx timing**：
```
[ONNXDetector] onnx timing | preprocess=3.2 ms | session=18.7 ms | postprocess=5.1 ms | detections=12
```

**CPU 回退时的 onnx timing**：
```
[ONNXDetector] onnx timing | preprocess=3.5 ms | session=680.0 ms | postprocess=4.8 ms | detections=5
```

### 7.2 判断问题根因

| 日志现象 | 根因 | 解决方向 |
|---------|------|---------|
| `ACTUAL providers=['CPUExecutionProvider']` | cuDNN/CUDA 库缺失导致 CUDA EP 初始化失败 | 检查 conda cuda-toolkit/cudnn 版本，或确认 `ort.preload_dlls()` 是否生效 |
| `ACTUAL providers=['CUDAExecutionProvider', ...]` 但 `session=80~200 ms` | GPU 工作但速度不正常 | 检查模型精度（FP16/INT8）、batch size、GPU 利用率 |
| `ACTUAL providers=['CUDAExecutionProvider', ...]` 但 `postprocess > 50 ms` | 后处理在 CPU 成为瓶颈 | 优化 postprocess（numba/Cython） |
| `preprocess > 20 ms` | cv2 resize + letterbox 慢 | 检查输入分辨率，考虑减少 resize 目标尺寸 |

---

## 8. 扩展指南

### 新增 PT 模型

1. `registry.py` → `MODEL_REGISTRY` 加 `ModelCapabilities`
2. `registry.py` → `RUNTIME_CONFIG` 加 `ModelConfig`（runtime_type="pt"）
3. `model_manager.py` → `_build_pt_detector()` 加 if 分支
4. inference.py 零改动

### 新增 ONNX 模型

1. `registry.py` 两个注册表各加一条
2. 如输出格式非标准，在 `ONNXDetector._postprocess()` 加识别分支
3. inference.py 零改动

### 新增 TensorRT runtime

1. 实现 `TRTDetector(BaseDetector)`
2. `model_manager.py` 注册：`@_register_runtime("trt")`
3. `registry.py` 改 `runtime_type="trt"`
4. inference.py 零改动

---

## 9. 关键配置位置

| 配置项 | 位置 |
|--------|------|
| ONNX 模型权重路径 | `registry.py` → `RUNTIME_CONFIG["YOLOv8-Car"].weight_path` |
| CUDA device ID | `registry.py` → `RUNTIME_CONFIG["YOLOv8-Car"].device` |
| 置信度阈值 | `registry.py` → `RUNTIME_CONFIG["YOLOv8-Car"].confidence_threshold` |
| 前端 API 模型列表 | `registry.py` → `MODEL_REGISTRY` |
| 日志格式 | `main.py` → `logging.basicConfig` |
| 历史记录 DB | `core/database.py` |
