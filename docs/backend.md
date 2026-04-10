# Skyline 后端架构文档

> 本文档面向大型语言模型（LLM）和新开发者，完整描述 Skyline 后端的设计哲学、模块划分和交互流程。
> 代码版本对应 2026-04-09，包含 PT/ONNX 统一 timing 协议、LIFO 调度器、Phase 5 模型冷加载状态通知。

---

## 1. 设计哲学

**"统一业务层 + 多运行时后端"**

推理调度层（`inference.py`）完全不知道也不关心模型跑在 PyTorch 上还是 ONNX 上。它只知道"模型 ID + 要检测哪些类 + 帧图像"。具体用哪套 runtime 由 `ModelManager` 查配置决定。

这样做的好处是：在不改动任何业务逻辑的前提下，可以随时切换或新增 runtime 后端（PT / ONNX / TensorRT / OpenVINO），只需要在 `model_manager.py` 注册一个新 factory。

---

## 2. 目录结构

```
backend/
├── main.py                  # FastAPI 入口，注册路由，启动 lifespan（asynccontextmanager）
├── core/
│   ├── models.py            # Pydantic v2 数据模型（VideoFrame, InferenceResult, Detection, ErrorMessage, StatusMessage）
│   ├── inference.py         # LIFO 调度器（InferenceScheduler）+ _blocking_inference（统一推理入口）
│   └── database.py          # SQLAlchemy 2.0 async + aiosqlite（历史记录存储）
├── models/
│   ├── registry.py          # 双注册表：MODEL_REGISTRY（前端用） + RUNTIME_CONFIG（执行层用）
│   ├── model_manager.py     # ModelManager 工厂 + BaseDetector 抽象类 + PTDetector + ONNXDetector
│   └── history.py           # DetectionRecord SQLAlchemy 模型
├── routers/
│   ├── video_stream.py      # WebSocket /api/ws/video_stream（含心跳 + 模型冷加载状态通知）
│   ├── history.py           # REST /api/history/*（分页列表/详情/删除/下载视频/下载 JSON）
│   ├── agent.py             # REST /api/agent/*（任务解析 + AI 短报告生成）
│   └── models.py            # REST /api/models/*（前端获取模型能力）
└── services/
    └── agent_service.py     # Agent LLM 调用（SiliconFlow）+ 任务解析 + 短报告生成
```

> **注意**：代码中暂未实现 TensorRT（TRTDetector）运行时。`RUNTIME_CONFIG` 中 `runtime_type` 的枚举值 `trt` 和 `openvino` 仅作为预留接口存在。

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
├── timestamp: float          # 回传客户端发送时间戳，用于计算端到端延迟
├── inference_time_ms: float  # 后端单帧总处理耗时（_blocking_inference 整体）
├── session_ms: float|null     # 纯模型 forward 耗时（ONNX: session.run / PT: Results.speed["inference"]）
├── preprocess_ms: float|null # 预处理耗时（ONNX: _preprocess / PT: Results.speed["preprocess"] + decode）
├── postprocess_ms: float|null # 后处理耗时（ONNX: _postprocess / PT: Results.speed["postprocess"]）
├── model_id: str             # 本次推理使用的模型 ID（Phase 5+ 冷加载状态通知用）
└── detections: list[Detection]

Detection
├── class_name: str
├── confidence: float
└── bbox: (x, y, w, h)         # 原始图像坐标系，左上角 + 宽高
```

### 3.3 服务端状态通知（下行）

```
StatusMessage  ← Phase 5+ 模型冷加载生命周期通知
├── message_type: "status"
├── phase: "model_loading"     # 模型首次冷加载开始
└── phase: "model_ready"      # 模型冷加载完成

ErrorMessage
├── message_type: "error"
├── error_code: int
└── detail: str
```

> **`inference_time_ms` vs `session_ms`**：前者是后端总耗时（含 detector 获取、base64 解码、全流程），后者是纯模型 forward。两者口径不同，不可混淆。

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
    │ return InferenceResult(frame_id, timestamp, elapsed_ms, detections,
    │                        session_ms, preprocess_ms, postprocess_ms, model_id)
    ▼
[video_stream.py — _send_result 回调]
    │ # Phase 5+: 若本帧为某模型的首次冷加载帧，先发送 model_ready 状态通知
    │ if model_id not in _cold_loaded_models:
    │     _cold_loaded_models.add(model_id)
    │     await websocket.send_text(StatusMessage(phase="model_ready", model_id=model_id))
    │
    │ await websocket.send_text(result.model_dump_json())
    ▼
[Frontend] 渲染检测结果 + 显示模型就绪提示
```

#### 4.x 冷启动异常修复（no running event loop）

**问题**：模型冷加载回调（`_cold_load_callback`）运行在线程池 worker 线程中，直接调用 `get_running_loop()` 会抛出 `no running event loop` 异常。

**修复方案**：在 WebSocket 握手后立即捕获事件循环引用，worker 线程通过 `asyncio.run_coroutine_threadsafe()` 安全调度到主事件循环：

```python
# 在 websocket handler 入口（async context）中捕获循环
_ws_loop = asyncio.get_running_loop()

def _cold_load_callback(model_id: str) -> None:
    coro = websocket.send_text(StatusMessage(...).model_dump_json())
    asyncio.run_coroutine_threadsafe(coro, _ws_loop)  # 线程安全
```

**`NoneType doesn't define __round__` 修复**：在 `inference.py` 中，`session_ms` / `preprocess_ms` / `postprocess_ms` 可能为 `None`（某些 runtime 路径），修复方式为：

```python
inference_time_ms=round(elapsed_ms, 3),  # inference_time_ms 始终有值
session_ms=round(detector_result.session_ms, 3) if detector_result.session_ms is not None else None,
preprocess_ms=round(detector_result.preprocess_ms, 3) if ... else None,
postprocess_ms=round(detector_result.postprocess_ms, 3) if ... else None,
```

前端接收到的 `session_ms` / `preprocess_ms` / `postprocess_ms` 可能为 `null`，前端已正确处理此情况。

---

## 5. 各模块职责详解

### 5.1 `main.py`

仅负责：创建 FastAPI 实例、注册 CORS、注册三个路由器、启动时执行 `init_db()`。

### 5.2 `core/models.py`

Pydantic v2 数据模型。用 `model_validate` 做 WebSocket 消息校验，格式错误返回 `ErrorMessage` 而不 crash。

### 5.3 `core/inference.py`

**`_blocking_inference(frame)`**：运行在线程池（`run_in_threadpool`），完全不知道 runtime 类型，只负责：模型 ID 解析（+ 降级到 default）、验证模型存在、区分 open_vocab/closed_set、调用 `detector.infer()`、异常捕获（ValueError/RuntimeError/Exception）、返回 `InferenceResult`（含 session_ms / preprocess_ms / postprocess_ms / model_id）。

**`InferenceScheduler`**：LIFO 单帧缓冲调度器。
- 新帧到来时若 AI 线程忙，新帧直接覆盖 `_latest_frame`，丢弃旧帧（记录 `_dropped_frames` 计数）
- 仪表盘永远显示当前时刻，不会积压延迟
- `asyncio.Lock` 保证 `_latest_frame` 写操作线程安全
- `asyncio.Event`（`_has_frame`）用于协调 pop 线程与 push 线程的等待/唤醒
- `stop()` 方法通过 `_running=False` + `_has_frame.set()` 安全退出循环

### 5.4 `models/registry.py` — 双注册表

**`MODEL_REGISTRY[model_id] → ModelCapabilities`**（前端用）：display_name、model_type、supported_classes、class_filter_enabled、description。前端 `GET /api/models` 返回这个。

**`RUNTIME_CONFIG[model_id] → ModelConfig`**（执行层用）：runtime_type、weight_path、confidence_threshold、warmup_enabled、device。`ModelManager` 查这个决定实例化哪个 detector。

两表分离保证：运行时后端切换不影响前端 API 响应。

当前注册模型：

| model_id | runtime_type | model_type | 说明 |
|----------|-------------|------------|------|
| `YOLO-World-V2` | pt | open_vocab | ultralytics YOLOWorld，开放词汇 |
| `YOLOv8-Base` | pt | closed_set | ultralytics YOLOv8n，COCO 80 类 |
| `YOLOv8-Car` | onnx | closed_set | yolov8_car.onnx，自定义车辆 5 类 |
| `YOLOv8-VisDrone` | onnx | closed_set | yolov8x_visdrone_best.onnx，VisDrone 10 类 |

> TensorRT（trt）和 OpenVINO（openvino）的 `runtime_type` 值在 `ModelConfig` 中已预留，但代码中尚未实现对应的 detector 类。

### 5.5 `models/model_manager.py`

#### BaseDetector 抽象类

所有 detector 共享 `infer()`（base64 解码 + prompt 清洗 + 后置类别过滤），子类只需实现：
- `load()`：懒加载模型（双检查锁，线程安全）
- `_do_infer(img, clean_prompt_classes)`：推理逻辑，返回 `(detections, preprocess_ms, session_ms, postprocess_ms)`

共享工具方法：
- `_clean_prompt_classes()`：扁平化逗号分隔字符串并小写化
- `_parse_boxes()`：ultralytics Boxes → list[Detection]，用于 PTDetector

回调机制：
- `set_on_loaded_callback(cb)`：设置冷加载完成后回调，仅触发一次

#### PTDetector

内部区分 open_vocab（YOLOWorld）和 closed_set（YOLOv8）：
- `open_vocab`：`model.set_classes(prompts)` + `model.predict()`，每次推理前重新设定类别
- `closed_set`：`model.predict()`，直接全量输出

关键机制：
- `_infer_lock`（threading.Lock）：保证 `set_classes()` + `predict()` 在共享 GPU 上序列化
- 冷加载完成后触发模块级 `_cold_load_callback(model_id)`

PTDetector 子类（每个模型一个，不重复逻辑）：
- `_YOLOWorldV2`：权重 `yolov8s-worldv2.pt`，conf=0.25，有 GPU 预热
- `_YOLOv8Base`：权重 `yolov8n.pt`（ultralytics 自动下载），conf=0.25，无预热
- `_YOLOv8Car`：权重 `.pt`（PT 路径但已标记为备用），conf=0.5，无预热

#### ONNXDetector

见第六节专题。

#### ModelManager 工厂

- `get_detector(model_id)`：懒加载 + 缓存（双检查锁）
- `_create_detector()`：读取 `RUNTIME_CONFIG` → 查 `_RUNTIME_FACTORIES` 注册表 → 调用对应 factory
- 相对路径权重自动解析到 `skyline/weights/` 目录
- ONNX 路径额外注入 `class_names`（从 `MODEL_REGISTRY` 取）

### 5.6 `models/history.py`

SQLAlchemy 2.0 `DetectionRecord` 模型：
- 字段：id、created_at、duration、video_name、video_path、model_name、class_counts（JSON）、total_detections、status、thumbnail_path、extra_data（JSON）
- `to_dict()` 方法将 `extra_data.model_config` 展开为 `detection_model` 字段（兼容旧格式）

**extra_data 字段内容**（JSON，动态写入）：
| key | 类型 | 说明 |
|-----|------|------|
| `model_config` | object | 保存时的模型配置快照（写入时机：保存检测记录） |
| `detection_summary` | object | 结构化检测摘要（写入时机：保存检测记录） |
| `short_report` | string | AI 短报告文本（写入时机：AI 报告生成成功后补写） |

> **注意**：`extra_data` 为 JSON 列，可以动态扩展。但 `short_report` 和 `detection_summary` **不作为数据库正式列**，而是作为元数据字段承载。

### 5.7 `routers/`

| 端点 | 类型 | 作用 |
|------|------|------|
| `/api/ws/video_stream` | WebSocket | 双向视频流推理（含心跳 ping/pong + 模型冷加载状态通知） |
| `/api/models` | GET | 列表所有模型能力（model_id、display_name、model_type、description） |
| `/api/models/{model_id}/capabilities` | GET | 单模型详细信息（含 supported_classes） |
| `/api/history` | POST | 保存检测记录 |
| `/api/history` | GET | 分页查询历史记录（page、limit、status 过滤） |
| `/api/history/{id}` | GET | 获取单条记录详情 |
| `/api/history/{id}` | DELETE | 删除记录 |
| `/api/history/{id}/extra-data` | PATCH | 合并写入 extra_data 字段（AI 报告补写用） |
| `/api/history/{id}/video` | GET | 下载原始视频文件 |
| `/api/history/{id}/data` | GET | 导出检测数据 JSON |
| `/api/agent/parse-task` | POST | 自然语言任务解析 → 结构化推荐（模型 + 类别） |
| `/api/agent/generate-report` | POST | 基于检测摘要生成 AI 短报告 |

---

## 6. Agent 服务系统（Phase 1）

### 6.1 职责边界

Agent 服务**只负责理解与建议**，不触发任何实际检测操作：

- **能做**：自然语言任务解析、模型推荐、类别推荐、短报告生成
- **不能做**：启动检测、修改系统状态、写数据库

### 6.2 `POST /api/agent/parse-task`

**功能**：将自然语言检测任务解析为结构化推荐。

**输入**：`{ user_text: string }`（用户任务描述）

**输出**：
```
{
  intent: string,
  recommended_model_id: string,  // 来自 MODEL_REGISTRY
  target_classes: string[],
  report_required: boolean,
  reason: string,
  confidence: "high" | "medium" | "low"
}
```

**LLM 调用**：SiliconFlow API（`deepseek-ai/DeepSeek-V3.2`），超时 30 秒。

**闭集优先级逻辑**：若用户目标类别全部被某个闭集模型覆盖，自动将推荐从 `YOLO-World-V2` 切换为该闭集模型，并附带说明原因。

**异常处理**：
- `ValueError`：Agent API Key 未配置 → HTTP 503
- `RuntimeError`：LLM 调用失败或响应解析异常 → HTTP 502
- `Exception`：其他错误 → HTTP 500

### 6.3 `POST /api/agent/generate-report`

**功能**：基于检测摘要数据，生成中文短报告（100-200 字）。

**输入**（结构化摘要）：
```
{
  modelId, modelLabel, targetClasses,
  totalDetectionEvents, detectedClassCount,
  classCounts, maxFrameDetections,
  durationSec, summaryText, taskPrompt?
}
```

**输出**：`{ reportText: string }`

**LLM 调用**：同 `parse-task`，temperature=0.3（比任务解析更低）。

**使用场景**：用户在 Detection 页面完成检测后，手动点击"生成 AI 短报告"按钮触发。**非自动触发**。

**异常处理**：同 `parse-task`。

### 6.4 extra_data 承载方式

AI 报告与检测摘要**不作为数据库正式列**，而是通过 `extra_data` JSON 字段承载：

| 字段 | 写入时机 | 说明 |
|------|---------|------|
| `detection_summary` | 保存检测记录时（`autoSave`） | 结构化检测摘要 |
| `short_report` | AI 报告生成成功后（补写） | AI 生成的中文报告文本 |
| `model_config` | 保存检测记录时 | 模型配置快照（兼容性字段） |

### 6.5 `PATCH /api/history/{id}/extra-data`

**功能**：合并写入已有历史记录的 `extra_data` 字段。

**语义**：顶层 key merge（`merged.update(req.extra_data)`），请求中传入的字段直接覆盖。

**典型用途**：AI 短报告生成成功后，将 `short_report` 补写入历史记录的 `extra_data`。

> **注意**：该接口**仅做补写**，不修改 `class_counts`、`total_detections` 等核心数据。

---

## 7. ONNXDetector 专题

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

### 6.6 NMS 后处理

ONNXDetector 内置了逐类 NMS（非极大值抑制）：
- `self._nms()`：按类分组，对每类独立执行 NMS（IoU threshold=0.45）
- `self._compute_iou()`：xyxy 格式 IoU 计算
- NMS 在置信度过滤之后、坐标还原之前执行
- 适用于 5-class 和 80-class 两种输出格式

### 6.7 Letterbox 坐标还原流程

1. 计算 scale = min(640/iw, 640/ih)
2. 将检测框从模型空间（640×640 canvas）还原到原始图像坐标
3. 使用浮点精度避免截断误差
4. Clip 到图像边界（防止越界）

---

## 8. Timing 口径专题（Phase 5）

### 7.1 后端 timing 字段总览

后端对前端返回以下四个 timing 字段：

|| 字段名 | 必须返回 | 说明 |
||--------|---------|------|
|| `inference_time_ms` | ✅ 始终返回 | `_blocking_inference()` 整体耗时 |
|| `preprocess_ms` | ⚠️ 可为 null | 预处理耗时 |
|| `session_ms` | ⚠️ 可为 null | 纯模型 forward 耗时 |
|| `postprocess_ms` | ⚠️ 可为 null | 后处理耗时 |

### 7.2 四个字段的严格语义

#### `inference_time_ms`

**语义**：`_blocking_inference()` 从入口到返回的总耗时。

**包含**：
- detector 获取（已缓存时极快，首次获取时有额外开销）
- `detector.infer()` 整体（含 decode + preprocess + session + postprocess）
- `InferenceResult` 结果对象构造
- Python 函数调用开销

**不包含**：
- 帧在队列中的等待时间（LIFO 调度器丢弃旧帧）

**与 `session_ms` 的区别**：`inference_time_ms` 是"后端总耗时"，不是"纯推理耗时"。

#### `preprocess_ms`

**语义**：输入准备阶段耗时。

| Runtime | 来源 |
|---------|------|
| ONNX | `decode_ms + _preprocess()` (resize/letterbox/normalize) |
| PT | `decode_ms + Results.speed["preprocess"]` |

#### `session_ms`

**语义**：纯模型执行阶段耗时。

| Runtime | 来源 |
|---------|------|
| ONNX | `session.run()` wall-clock 计时 |
| PT | `Ultralytics Results.speed["inference"]` |

> **重要**：`session_ms` 是前端"纯推理耗时 / 纯推理 FPS"的直接来源。

#### `postprocess_ms`

**语义**：输出后处理阶段耗时。

| Runtime | 来源 |
|---------|------|
| ONNX | `_postprocess()` (NMS + 坐标变换 + 阈值过滤) |
| PT | `Ultralytics Results.speed["postprocess"]` |

### 7.3 ONNX 与 PT 路径的统一协议

**设计原则**：前端协议统一，高于内部 runtime 实现统一。

两条路径向前端暴露的字段完全一致：

```
前端收到：{ inference_time_ms, session_ms, preprocess_ms, postprocess_ms }
```

**内部实现差异**（前端无感知）：

| 阶段 | ONNX 实现 | PT 实现 |
|------|-----------|---------|
| 计时方式 | wall-clock `time.perf_counter()` | Ultralytics `Results.speed` |
| `preprocess_ms` | `_preprocess()` 计时（+ decode） | `Results.speed["preprocess"]`（+ decode） |
| `session_ms` | `session.run()` 计时 | `Results.speed["inference"]` |
| `postprocess_ms` | `_postprocess()` 计时 | `Results.speed["postprocess"]` |

### 7.4 算法全流程与后端总耗时的区别

```
算法全流程耗时 = preprocess_ms + session_ms + postprocess_ms
后端总耗时     = inference_time_ms
```

二者不一定严格相等，因为 `inference_time_ms` 还可能额外包含：
- detector 获取开销（已缓存时极小）
- `DetectorResult` / `InferenceResult` 对象构造
- Python 函数调用栈开销

### 7.5 Phase 5+ 新增字段：model_id

`model_id` 字段用于前端判断"某模型的首次冷加载帧已推理完成"，触发模型就绪提示：

- 首次冷加载时，后端先通过 `_cold_load_callback` 发送 `StatusMessage(phase="model_loading")`
- 冷加载完成后，在 `_send_result` 回调中发送 `StatusMessage(phase="model_ready")`
- 前端收到 `model_ready` 后，将状态从 `loading_model` 切换为 `analyzing`

### 7.6 哪些后端字段必须长期保留

以下字段属于前后端统一协议核心字段，**后续不能随意删除**：

| 字段 | 原因 |
|------|------|
| `inference_time_ms` | 支撑"后端处理耗时 / FPS" |
| `session_ms` | 支撑"纯推理耗时 / FPS"（比赛硬指标） |
| `preprocess_ms` | 支撑"算法全流程耗时"计算 |
| `postprocess_ms` | 支撑"算法全流程耗时"计算 |
| `model_id` | 支撑 Phase 5+ 模型冷加载状态通知 |

---

## 9. 日志解读指南

### 8.1 模型加载阶段

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

### 8.2 判断问题根因

| 日志现象 | 根因 | 解决方向 |
|---------|------|---------|
| `ACTUAL providers=['CPUExecutionProvider']` | cuDNN/CUDA 库缺失导致 CUDA EP 初始化失败 | 检查 conda cuda-toolkit/cudnn 版本，或确认 `ort.preload_dlls()` 是否生效 |
| `ACTUAL providers=['CUDAExecutionProvider', ...]` 但 `session=80~200 ms` | GPU 工作但速度不正常 | 检查模型精度（FP16/INT8）、batch size、GPU 利用率 |
| `ACTUAL providers=['CUDAExecutionProvider', ...]` 但 `postprocess > 50 ms` | 后处理在 CPU 成为瓶颈 | 优化 postprocess（numba/Cython） |
| `preprocess > 20 ms` | cv2 resize + letterbox 慢 | 检查输入分辨率，考虑减少 resize 目标尺寸 |

---

## 10. 扩展指南

### 9.1 新增 PT 模型

1. `registry.py` → `MODEL_REGISTRY` 加 `ModelCapabilities`
2. `registry.py` → `RUNTIME_CONFIG` 加 `ModelConfig`（runtime_type="pt"）
3. `model_manager.py` → `_build_pt_detector()` 加 if 分支
4. inference.py 零改动

### 9.2 新增 ONNX 模型

1. `registry.py` 两个注册表各加一条（model_id、display_name、supported_classes → MODEL_REGISTRY；runtime_type="onnx"、weight_path、class_names → RUNTIME_CONFIG）
2. 如输出格式非标准，在 `ONNXDetector._postprocess()` 加识别分支
3. inference.py 零改动

### 9.3 新增 TensorRT runtime（预留，尚未实现）

1. 实现 `TRTDetector(BaseDetector)`
2. `model_manager.py` 注册：`@_register_runtime("trt")`
3. `registry.py` 改 `runtime_type="trt"`
4. inference.py 零改动

> **当前状态**：代码中 `TRTDetector` 类尚未实现，`ModelConfig` 的 `runtime_type` 枚举中有 `"trt"` 和 `"openvino"` 作为预留值，但对应 factory 尚未注册。

### 9.4 当前 WebSocket 心跳机制（Phase 5+）

后端 WebSocket 端点内置心跳 ping/pong 机制：

- **服务端 → 客户端**：每 15 秒发送 `__heartbeat_ping__`
- **客户端 → 服务端**：收到后回复 `__heartbeat_pong__`
- **超时检测**：若 20 秒内未收到 pong，认定连接已死亡，退出消息循环

前端 `useWebSocket.ts` 同步实现了相同的心跳逻辑（对应 15s/20s 配置），双方互相探测死连接。

---

## 11. 关键配置位置

| 配置项 | 位置 |
|--------|------|
| ONNX 模型权重路径 | `registry.py` → `RUNTIME_CONFIG["YOLOv8-Car"].weight_path`（相对于 `skyline/weights/`） |
| CUDA device ID | `registry.py` → `RUNTIME_CONFIG[model_id].device`（默认值 `cuda:0`） |
| 置信度阈值 | `registry.py` → `RUNTIME_CONFIG[model_id].confidence_threshold`（默认 0.25） |
| ONNX EP 配置 | `model_manager.py` → `ONNXDetector.load()`（providers 列表） |
| 前端 API 模型列表 | `registry.py` → `MODEL_REGISTRY` |
| 日志格式 | `main.py` → `logging.basicConfig(level=INFO)` |
| 历史记录 DB | `core/database.py` → `DB_PATH = skyline/data/skyline.db` |
| WebSocket 端点 | `routers/video_stream.py` �� `/api/ws/video_stream` |
| 心跳间隔 | `routers/video_stream.py` → `HEARTBEAT_INTERVAL_MS=15_000` / `HEARTBEAT_TIMEOUT_MS=20_000` |

---

## 12. 已知限制与未实现功能

- **TensorRT 尚未实现**：`TRTDetector` 类预留但不存在，`runtime_type="trt"` 仅作占位。
- **OpenVINO 尚未实现**：`runtime_type="openvino"` 仅作占位。
- **PT 路径 timing 不完整**：PT 模型（YOLO-World-V2、YOLOv8-Base）使用 ultralytics 原生 `Results.speed`，完整暴露 `session_ms` / `preprocess_ms` / `postprocess_ms`，口径与 ONNX 一致。
- **视频保存**：历史记录中 `video_path` 字段目前由前端写入，后端本身不处理视频文件上传。
- **ONNX warmup**：ONNXDetector 加载时无 warmup 推理（仅打印 EP 信息），GPU 预热由首次实际推理完成。
- **YOLOv8-Car PT 路径**：registry 中 `YOLOv8-Car` 已标注为 `runtime_type="onnx"`，不存在 PT 版本。
- **Agent 服务依赖 LLM API**：任务解析和短报告生成依赖 SiliconFlow API Key（`AGENT_API_KEY` 环境变量），未配置时 `parse-task` 和 `generate-report` 均返回 503 错误。
- **AI 报告非自动触发**：Detection 页面完成后，用户需手动点击"生成 AI 短报告"按钮才会触发后端 `/api/agent/generate-report`，**不会自动生成**。
- **数据库 schema 未改造**：AI 报告（`short_report`）和检测摘要（`detection_summary`）通过 `extra_data` JSON 字段承载，不作为数据库正式列。
- **不支持复杂问答 / 轨迹分析 / RAG**：Agent 服务当前仅支持任务解析和短报告生成，不支持基于历史检测记录的问答、目标轨迹分析或 RAG 增强。
