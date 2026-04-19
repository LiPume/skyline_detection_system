# Skyline 后端实现说明

> 本文档以当前 `skyline/backend` 代码为准，描述真实的架构、模块边界与协议语义。
> 面向：比赛评委、指导老师、后续维护者

---

## 1. 后端架构概览

### 1.1 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 框架 | FastAPI + Starlette | ASGI 应用 |
| 序列化 | Pydantic v2 | 请求/响应模型 |
| ORM | SQLAlchemy 2.0（async） | 检测记录持久化 |
| 数据库 | SQLite + aiosqlite | 异步文件数据库 |
| 模型运行时 | Ultralytics YOLO（PT）、onnxruntime（ONNX） | 推理引擎 |
| LLM 服务 | SiliconFlow API（DeepSeek-V3.2） | Agent 智能服务 |
| 线程池 | asyncio.to_thread / concurrent.futures.ThreadPoolExecutor | 阻塞推理解阻塞 |

### 1.2 模块结构

```
backend/
├── main.py                         # FastAPI 入口，CORS，注册路由，init_db
├── core/
│   ├── models.py                  # Pydantic v2 数据模型（VideoFrame / InferenceResult / StatusMessage / ErrorMessage）
│   ├── inference.py               # InferenceScheduler（LIFO）+ _blocking_inference
│   └── database.py                # SQLAlchemy 异步配置（aiosqlite + SQLite）
├── models/
│   ├── registry.py                # 双注册表：MODEL_REGISTRY（前端元数据）+ RUNTIME_CONFIG（后端执行配置）
│   ├── model_manager.py           # ModelManager（工厂+缓存）+ BaseDetector + PTDetector + ONNXDetector
│   └── history.py                # DetectionRecord ORM 模型
├── routers/
│   ├── video_stream.py            # WebSocket /api/ws/video_stream
│   ├── history.py                 # REST CRUD /api/history*
│   ├── models.py                  # REST /api/models, /api/models/:id/capabilities
│   └── agent.py                  # REST /api/agent/parse-task, /api/agent/generate-report
└── services/
    └── agent_service.py           # LLM 调用 + 规则增强（parse_task / generate_short_report）
```

---

## 2. 核心模块职责

### 2.1 推理调度：InferenceScheduler

**文件**：`core/inference.py`

**职责**：管理推理请求队列，防止积压。

**LIFO 策略**：
- 队列最多保留 **1 帧**（latest_frame）
- 新帧到达时若前帧未处理，直接覆盖（丢弃旧帧）
- 前端背压配合：前端最多 1 帧 in-flight

**线程安全**：
- `asyncio.Lock` 保护队列读写
- `asyncio.Event`（`ai_done`）用于通知推理完成

### 2.2 推理执行：_blocking_inference

**文件**：`core/inference.py`

**职责**：在 `ThreadPoolExecutor` 中执行同步推理，不阻塞事件循环。

**流程**：
```
入参：VideoFrame（base64图片 + 模型ID + prompt/类别）
  1. resolve model_id → RUNTIME_CONFIG
  2. build unified kwargs（model_type 区分 open_vocab / closed_set）
  3. detector = ModelManager.get_detector(model_id)
  4. results = detector.infer(image_bgr, **kwargs)
  5. 构建 InferenceResult（timing + model_id + detections）
出参：InferenceResult（Pydantic 模型）
```

**Timing 字段来源**：
| 字段 | 来源 | PT | ONNX |
|------|------|-----|------|
| session_ms | `Results.speed['inference']` | ✅ | `perf_counter` 全程 |
| preprocess_ms | 内部计时 | ✅ | 内部计时 |
| postprocess_ms | 内部计时 | ✅ | 内部计时 |
| inference_time_ms | 三者之和 | ✅ | ✅ |

**异常处理**：捕获超时、CUDA 错误、模型未找到，返回结构化 ErrorMessage。

### 2.3 模型管理器：ModelManager

**文件**：`models/model_manager.py`

**职责**：模型懒加载 + 缓存 + 运行时分发。

**get_detector(model_id) 逻辑**：
1. 检查缓存（`self._cache` dict）
2. 未命中 → 从 `RUNTIME_CONFIG[model_id].runtime_type` 分发
   - `"pt"` → `_build_pt_detector`
   - `"onnx"` → `_build_onnx_detector`
3. 缓存并返回

**BaseDetector 抽象接口**：
- `load()`：懒加载模型文件到内存（子类实现）
- `_do_infer(image_bgr, **kwargs)`：运行时推理（子类实现）
- `infer(image_bgr, **kwargs)`：对外统一入口，含 base64 解码、prompt 清洗、类别过滤、统一输出格式

**PTDetector 实现**（对应 `_build_pt_detector`）：
- YOLO-World-V2：调用 `set_classes(prompt)` + `predict`
- `threading.Lock` 序列化 `set_classes` + `predict` 调用（共享 GPU）

**ONNXDetector 实现**（对应 `_build_onnx_detector`）：
- `_preprocess`：Letterbox 等比缩放（保持长宽比，灰色填充）+ 归一化
- `_do_infer`：`session.run` 执行 ONNX 推理
- `_postprocess`：NMS + 坐标从 letterbox 空间映射回原图 + 置信度过滤
- 动态检测 ONNX 输出格式（5 列 / 84 列 / 117 列）
- `ort.preload_dlls()` 优化 CUDA 集成

### 2.4 双注册表：MODEL_REGISTRY + RUNTIME_CONFIG

**文件**：`models/registry.py`

**设计意图**：解耦前端元数据和后端执行配置。

**MODEL_REGISTRY**：前端展示用元数据（`ModelCapabilities` dataclass）

```python
@dataclass
class ModelCapabilities:
    model_id: str
    display_name: str
    card_name: str
    model_type: Literal["open_vocab", "closed_set"]
    supports_prompt: bool
    prompt_editable: bool
    supported_classes: list[str]  # [] for open_vocab
    class_filter_enabled: bool
    description: str
```

**RUNTIME_CONFIG**：后端执行配置（`ModelConfig` dataclass）

```python
@dataclass
class ModelConfig:
    runtime_type: Literal["pt", "onnx", "trt", "openvino"]
    weight_path: Path | str
    confidence_threshold: float = 0.25
    warmup_enabled: bool = True
    device: str = "cuda:0"
```

**当前已注册模型**：

| model_id | runtime_type | model_type | 描述 |
|----------|-------------|------------|------|
| YOLO-World-V2 | pt | open_vocab | 开放词汇通用检测（推荐） |
| YOLOv8-VisDrone / SKY-Monitor | onnx | closed_set | VisDrone 航拍 10 类 |
| YOLOv8-Person / SKY-Person | onnx | closed_set | 人员专项（person） |

**共享类别列表**：
- `COCO_CLASSES`：80 类（COCO 数据集标准）
- `VEHICLE_CLASSES`：`['car', 'truck', 'bus', 'van', 'freight_car']`
- `VISDRONE_CLASSES`：10 类（VisDrone 标准）—— `pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor`

### 2.5 历史存储：DetectionRecord

**文件**：`models/history.py`

**ORM 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| created_at | DateTime | 创建时间 |
| duration | Float | 分析时长（秒） |
| video_name | String | 原始文件名 |
| video_path | String | 原始路径 |
| model_name | String | 模型显示名（兼容字段） |
| class_counts | JSON | 类别计数字典 |
| total_detections | Integer | 检测事件总次数 |
| status | String | completed / failed / paused |
| thumbnail_path | String, nullable | 缩略图路径 |
| extra_data | JSON | 灵活扩展数据 |

**extra_data 用途**：

```python
# Detection.vue autoSave 时写入
extra_data = {
    "model_config": {
        "model_id": "YOLO-World-V2",
        "display_name": "YOLO-World V2",
        "model_type": "open_vocab",
        "prompt_classes": ["car", "person"],
        "selected_classes": []
    },
    "detection_summary": { ... }
}

# generate_short_report 成功后补写
extra_data["short_report"] = "本次检测..."
# patchHistoryExtraData 合并写入
```

### 2.6 Agent 服务

**文件**：`services/agent_service.py` + `routers/agent.py`

**两个核心能力**：

**parse_detection_task（任务解析）**：
- 输入：用户自然语言描述
- 输出：结构化推荐 `{ intent, recommended_model_id, target_classes, report_required, reason, confidence }`
- LLM：DeepSeek-V3.2（SiliconFlow API），系统提示包含 MODEL_REGISTRY 所有能力
- 规则增强（LLM 输出后处理）：

| 规则 | 条件 | 动作 |
|------|------|------|
| 热成像纠正 | prompt 含 thermal/红外/热成像 | 强制 YOLOv8-Thermal-Person |
| 属性约束纠正 | "白车"/"红车"等属性描述 | 重定向到 YOLO-World-V2 |
| 纯人员兜底 | 仅需 person，无其他属性 | 推荐 YOLOv8-Person（精度更高） |
| 高速/拥堵场景 | 含 highway/traffic jam/高速/拥堵 | YOLOv8-VisDrone + vehicle 类 |
| 开放词汇优先 | 属性类描述（颜色/大小/模糊） | YOLO-World-V2 |
| 属性恢复 | open_vocab 模型推荐 | 恢复属性短语（"白车" → prompt） |

**generate_short_report（短报告生成）**：
- 输入：detection_summary（含 classCounts、duration、sceneEvidence）
- 输出：结构化中文报告文本
- LLM：DeepSeek-V3.2
- 提示词策略：
  - 提供 sceneEvidence 结构化证据（vehicleMix、laneDensityHint 恒为 0、crowdingHigh、congestionHint、highwayRatio、sceneHint）
  - 证据门控：laneDensityHint=0 时不生成车道相关结论
  - 报告结构：场景概述 → 目标统计 → 关键发现 → 安全建议
  - 字数：约 200 字左右

---

## 3. API / WebSocket 边界

### 3.1 WebSocket：/api/ws/video_stream

**协议**：Starlette WebSocket（`websocket_router`）

**连接流程**：
1. 前端通过 `useWebSocket.connect()` 建立连接
2. 心跳：`receive_text == "__heartbeat_ping__"` → `send_text("__heartbeat_pong__")`
3. 心跳超时：20s 无活动触发 `close(code=1000)`

**入站消息**：`VideoFrame`（Pydantic 校验）

**出站消息**：

| message_type | 触发时机 |
|--------------|----------|
| `inference_result` | 推理完成返回 |
| `status`（`model_loading`） | 模型冷加载开始（通过 run_coroutine_threadsafe 发送） |
| `status`（`model_ready`） | 模型冷加载完成 |
| `error` | 推理异常 |

**冷加载通知机制**：`asyncio.run_coroutine_threadsafe(send_status(...), self.websocket_loop)` 安全地将 worker 线程中的通知派发到主事件循环。

### 3.2 REST API

**历史记录**：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/history` | 创建记录 |
| GET | `/api/history` | 列表（分页，limit/offset） |
| GET | `/api/history/{id}` | 详情 |
| DELETE | `/api/history/{id}` | 删除 |
| PATCH | `/api/history/{id}/extra-data` | 合并更新 extra_data（用于 AI 报告补写） |
| GET | `/api/history/{id}/video` | 视频文件下载 |
| GET | `/api/history/{id}/data` | JSON 导出 |

**模型**：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models` | 模型列表（来自 MODEL_REGISTRY） |
| GET | `/api/models/{model_id}/capabilities` | 模型能力详情 |

**Agent**：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agent/parse-task` | 自然语言 → 结构化任务推荐 |
| POST | `/api/agent/generate-report` | 检测摘要 → AI 短报告 |

---

## 4. 协议字段说明

### 4.1 VideoFrame（前端 → 后端）

```json
{
  "message_type": "video_frame",
  "frame_id": 0,
  "timestamp": 1710345678.123,
  "image_base64": "data:image/jpeg;base64,...",
  "model_id": "YOLO-World-V2",
  "prompt_classes": ["car", "person"],
  "selected_classes": [],
  "selected_model": "YOLO-World-V2",
  "target_classes": ["car", "person"]
}
```

**字段约束**：
- `model_id`：必须在 MODEL_REGISTRY 中存在
- `prompt_classes`：open_vocab 模型使用
- `selected_classes`：closed_set 模型使用，从 supported_classes 中筛选
- `image_base64`：必须是 data URI 格式（`data:image/jpeg;base64,...`）
- `selected_model` / `target_classes`：兼容性别名字段（前向兼容）

### 4.2 InferenceResult（后端 → 前端）

```json
{
  "message_type": "inference_result",
  "frame_id": 0,
  "timestamp": 1710345678.123,
  "inference_time_ms": 45.2,
  "session_ms": 38.7,
  "preprocess_ms": 3.2,
  "postprocess_ms": 5.1,
  "model_id": "YOLO-World-V2",
  "detections": [
    {
      "class_name": "car",
      "confidence": 0.95,
      "bbox": [120.0, 340.5, 80.2, 65.1]
    }
  ]
}
```

**BBox 语义**：`[x, y, w, h]`，像素坐标，已从 letterbox 空间映射回原图坐标系（ONNX 路径）。

**Timing 说明**：
- `inference_time_ms` = 后端总处理耗时，始终存在
- PT 运行时 `session_ms` 来自 Ultralytics `Results.speed['inference']`，`preprocess_ms`/`postprocess_ms` 为 `None`
- ONNX 运行时三个字段均为 `float`

### 4.3 StatusMessage（后端 → 前端）

```json
{
  "message_type": "status",
  "phase": "model_ready",
  "model_id": "YOLO-World-V2"
}
```

| phase | 含义 |
|-------|------|
| `model_loading` | 模型文件加载中（冷加载） |
| `model_ready` | 模型加载完成，可开始推理 |

---

## 5. 稳定边界与限制区域

### 5.1 稳定主链路

- **推理链路**：`video_stream.py` → `InferenceScheduler` → `_blocking_inference` → `ModelManager` → `PTDetector/ONNXDetector`：**核心主链路**，稳定
- **History CRUD**：`history.py` → `DetectionRecord` → `database.py`：**稳定**
- **Agent LLM**：`agent_service.py` → SiliconFlow API：**稳定**（依赖外部 API）
- **数据库初始化**：`init_db` 在 main.py lifespan 中调用

### 5.2 当前限制

| 限制 | 说明 |
|------|------|
| 模型文件未下载 | 对应 PT/ONNX 文件未在 weights 目录时后端报错 |
| 无 TensorRT | registry 预留，未实现 `_build_trt_detector` |
| 无 OpenVINO | registry 预留，未实现 `_build_openvino_detector` |
| 无模型热加载 | 模型切换时需重新加载，不支持热替换 |
| ONNX 输出格式适配 | 依赖动态检测（5/84/117 列），固定输出格式模型需适配 |
| Agent 服务依赖外部 API | SiliconFlow API key 必须配置，无本地 LLM fallback |
| 无视频文件存储 | 后端不保存视频，`video_path` 仅记录原始路径 |
| 无权限控制 | 所有 API 公开，无认证机制 |

### 5.3 不要轻易修改的区域

- `core/inference.py` 中的 LIFO 队列逻辑：与前端背压机制强耦合
- `models/model_manager.py` 中的 `threading.Lock`：PTDetector 共享 GPU 序列化
- `services/agent_service.py` 中的规则增强逻辑：依赖 prompt 设计，修改易导致推荐/报告退化
- `models/registry.py` 中的 `MODEL_REGISTRY` 和 `RUNTIME_CONFIG` 分离设计：解耦前端展示和后端执行

---

## 6. 启动与依赖

### 6.1 环境变量

| 变量 | 用途 | 必填 |
|------|------|------|
| `AGENT_API_KEY` | SiliconFlow API 密钥 | Agent 功能必填 |
| 模型权重文件 | 见 `RUNTIME_CONFIG.weight_path` | 对应模型必填 |

### 6.2 启动命令

```bash
cd skyline
pip install -r requirements.txt
python -m backend.main
# 或 uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6.3 数据库

- 路径：`skyline/data/skyline.db`（aiosqlite）
- 表：`detection_records`（`init_db` 自动创建）
- 迁移：当前无 Alembic 迁移机制，schema 变更需手动处理
