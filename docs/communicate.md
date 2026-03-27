# Skyline 天际线智能视觉检测系统 — 项目现状分析文档

> **文档目的**：为技术路线设计、方案包装、PPT 整理提供事实基础。  
> **分析依据**：基于代码审查（非猜测），所有结论均标注代码出处。  
> **编写日期**：2026-03-27

---

## A. 项目概述

### A.1 项目基本信息

| 属性 | 内容 |
|------|------|
| **项目名称** | Skyline（天际线）智能视觉检测系统 |
| **项目定位** | 面向无人机航拍与高空视角的实时开放词汇目标检测系统 |
| **当前阶段** | **系统雏形** — 核心推理链路已打通，前端界面完整，但训练、评估、部署等环节尚未落地 |
| **代码规模** | 后端约 1,200 行 Python（不含注释），前端约 3,500 行 TypeScript/Vue |
| **开发者** | LiPume（GitHub: `LiPume/skyline_detection_system`） |

### A.2 核心目标

从 README.md 与代码分析，项目的核心目标为：

1. **实时视频流分析**：通过 WebSocket 全双工通信，接收前端推送的视频帧，进行实时目标检测
2. **开放词汇检测**：利用 YOLO-World-V2 实现无需预定义类别的开放集检测，用户可自定义任意检测目标（"无人机"、"施工车辆"、"异常人员"等）
3. **可视化交互界面**：提供检测画布（BBox 实时叠加）、历史记录库、性能监控页面
4. **云边协同架构**：支持局域网任意终端访问（前端绑定 `0.0.0.0`），后端 GPU 推理

### A.3 当前定位评估

| 维度 | 现状 | 说明 |
|------|------|------|
| **推理链路** | ✅ 已完成 | WebSocket → Base64 解码 → YOLO-World-V2 推理 → 结果返回 |
| **前端界面** | ✅ 已完成 | 检测舱、历史库、性能页，三页完整 |
| **模型管理** | ⚠️ 部分完成 | 仅支持 YOLO-World-V2 和 YOLOv8-Base，无切换逻辑，无训练能力 |
| **训练/微调** | ❌ 未实现 | 代码中无任何训练、Fine-tuning 相关模块 |
| **评估体系** | ⚠️ 概念层 | Performance.vue 使用 Mock 数据，无真实评测管道 |
| **轻量化部署** | ❌ 未实现 | 无 ONNX/TensorRT/INT8 量化导出，无模型压缩 |
| **生产部署** | ❌ 未实现 | 仅 `start_backend.sh` 一键脚本，无 Docker/容器化 |

---

## B. 代码结构梳理

### B.1 目录树概览

```
skyline/
├── backend/                          # FastAPI 后端（Python 3.10+）
│   ├── main.py                       # 【入口】FastAPI app，CORS，路由注册
│   ├── core/
│   │   ├── database.py              # SQLite 异步数据库（aiosqlite + SQLAlchemy 2.0）
│   │   ├── inference.py              # 【核心】LIFO 推理调度器（InferenceScheduler）
│   │   ├── models.py                 # Pydantic v2 数据模型（VideoFrame, InferenceResult）
│   │   └── __init__.py
│   ├── models/
│   │   ├── model_manager.py          # 【核心】YOLO 模型懒加载单例，模型工厂
│   │   ├── history.py                # SQLAlchemy ORM 模型（DetectionRecord）
│   │   └── __init__.py
│   ├── routers/
│   │   ├── video_stream.py           # 【核心】WebSocket 端点 /api/ws/video_stream
│   │   ├── history.py                # REST API（CRUD + 视频/JSON 下载）
│   │   └── __init__.py
│   └── yolov8n.pt                    # 默认 YOLOv8n 权重（ ultralytics 首次自动下载缓存）
│
├── frontend/                         # Vue 3 + TypeScript + Tailwind CSS v4 前端
│   ├── src/
│   │   ├── main.ts                   # 入口
│   │   ├── App.vue                   # 根组件
│   │   ├── router/index.ts           # 路由表（/detection, /history, /history/:id, /performance）
│   │   ├── config/index.ts           # 全局配置（FPS、JPEG 质量、阈值等魔法数字）
│   │   ├── store/systemStatus.ts     # Pinia 状态（WS 连接状态、GPU 活跃状态）
│   │   ├── types/skyline.ts          # 共享类型定义 + CLASS_COLORS 调色板
│   │   ├── api/history.ts            # 前端 REST API 客户端
│   │   ├── composables/
│   │   │   ├── useWebSocket.ts       # WebSocket 连接 + 指数退避自动重连
│   │   │   ├── useVideoStream.ts     # 视频源管理 + 帧节流推流
│   │   │   └── useCanvasRenderer.ts  # RAF 60fps 渲染 + BBox 绘制
│   │   ├── layouts/MainLayout.vue    # 侧边栏 + 顶栏布局
│   │   └── views/
│   │       ├── Detection.vue         # 【核心】智能检测舱（主功能页面）
│   │       ├── History.vue           # 历史记录库（CRUD + 预览 + 下载）
│   │       ├── HistoryDetail.vue     # 历史数据详情页
│   │       └── Performance.vue       # 性能监控页（Mock 数据，未连接真实评测）
│   └── vite.config.ts               # Vite 配置（0.0.0.0 外部访问）
│
├── weights/                          # 模型权重目录
│   ├── yolov8n.pt                   # ~6.5MB，nano 版本（ultralytics 默认下载）
│   ├── yolov8s.pt                   # ~22MB，small 版本
│   ├── yolov8m.pt                   # ~52MB，medium 版本
│   ├── yolov8l.pt                   # ~88MB，large 版本
│   ├── yolov8x.pt                  # ~137MB，extra-large 版本
│   └── yolov8s-worldv2.pt          # ~26MB，YOLO-World V2（当前生产使用）
│
├── data/                             # 数据目录
│   ├── skyline.db                   # SQLite 数据库文件
│   ├── demo_flight.mp4              # 演示视频
│   ├── demo_slow_test.mp4           # 慢速测试视频
│   └── visdrone/                    # VisDrone2019 测试集（未集成到推理管道）
│
├── docs/                             # 文档
│   ├── ARCHITECTURE.md              # 系统架构文档
│   ├── description.md               # 前端样式规范
│   ├── log.md                       # 开发修改日志
│   └── communicate.md               # 本文档
│
├── requirements.txt                  # Python 依赖（fastapi, ultralytics, sqlalchemy, aiosqlite）
├── start_backend.sh                  # 后端启动脚本
├── start_frontend.sh                 # 前端启动脚本
└── STARTUP.md                        # 详细启动说明书
```

### B.2 关键文件说明

#### 后端核心文件

| 文件 | 职责 | 关键类/函数 |
|------|------|-------------|
| `main.py` | FastAPI 应用入口，路由注册，中间件配置 | `app`, `lifespan` |
| `core/inference.py` | LIFO 单帧缓冲调度器，线程池隔离推理 | `InferenceScheduler`, `_blocking_inference` |
| `models/model_manager.py` | 模型懒加载工厂，线程安全锁，YOLO-World 调用 | `YOLOWorldV2`, `YOLOv8Base`, `get_model` |
| `routers/video_stream.py` | WebSocket 全双工端点 | `video_stream_endpoint` |
| `routers/history.py` | REST API（CRUD + 导出） | `create_detection_record`, `list_detection_records` |
| `core/database.py` | SQLite 异步连接池 | `async_session`, `init_db` |
| `core/models.py` | Pydantic v2 数据校验 | `VideoFrame`, `InferenceResult`, `Detection` |

#### 前端核心文件

| 文件 | 职责 | 关键逻辑 |
|------|------|----------|
| `views/Detection.vue` | 主检测页面，状态机，UI 控制台 | 分析状态机（standby/ready/analyzing/paused/finished） |
| `composables/useWebSocket.ts` | WS 连接管理，自动重连 | 指数退避（1s → 30s max） |
| `composables/useVideoStream.ts` | 视频帧捕获与推流 | 帧节流（20fps → 10fps） |
| `composables/useCanvasRenderer.ts` | Canvas BBox 渲染 | RAF 60fps + 角标绘制 |
| `config/index.ts` | 全局配置常量 | FPS、阈值、字体等 |
| `types/skyline.ts` | 类型定义 | WebSocket 协议类型 |

---

## C. 当前已实现能力分析

### C.1 复杂场景高精度检测

#### 已实现内容

**代码证据**：`backend/models/model_manager.py` — `YOLOWorldV2` 类

1. **YOLO-World-V2 开放词汇检测**：
   - 使用 `ultralytics.YOLOWorld` 子类（而非通用 `YOLO`）
   - `set_classes()` 方法注入用户自定义的自然语言 Prompt 作为检测目标
   - 强制置信度阈值 `conf=0.01`（极低，以捕获更多候选目标）

2. **GPU 加速与预热**：
   - 加载后强制 `model.to("cuda:0")` 确保 GPU 运行
   - Warmup 推理：用随机噪声图跑一次 `predict()`，强制 CUDA 内核 JIT 编译完毕
   - `threading.Lock` 保护多客户端共享 GPU 的线程安全

3. **多模型支持框架**：
   - 已注册 `YOLOWorldV2` 和 `YOLOv8Base` 两种模型
   - `ModelManager` 单例工厂支持动态切换（前端 `selected_model` 参数）
   - 模型懒加载，首次推理时才初始化

#### 评估

| 维度 | 现状 | 比赛答辩支撑 |
|------|------|-------------|
| 复杂场景适应性 | ⚠️ 依赖 YOLO-World 预训练能力，未针对特定场景微调 | 可声称"使用 YOLO-World 大模型，具备复杂场景泛化能力"，但无自定义训练证据 |
| 小目标检测 | ❌ 未发现专项优化（如 TPH-YOLO、注意力机制等） | 易被问住：航拍小目标多，如何保证召回？ |
| 数据增强 | ❌ 未实现 | 易被问住：模型在复杂场景下的鲁棒性如何保证？ |
| 高精度 | ⚠️ conf=0.01 激进阈值，高召回但可能低精度 | 需解释置信度策略 |

**结论**：基础能力具备，但无自定义优化。适合声称"基于 YOLO-World 预训练大模型的开放词汇检测"，不适合声称"针对复杂场景的高精度定制方案"。

---

### C.2 开放类别泛化识别

#### 已实现内容

**代码证据**：`backend/models/model_manager.py` 第 133-196 行

1. **开放词汇检测（核心能力）**：
   - `YOLOWorldV2.set_classes(clean_classes)` — 将用户 Prompt 转换为文本嵌入向量
   - 支持逗号分隔多类别：`"car, person, drone"` → `["car", "person", "drone"]`
   - Prompt 清洗逻辑：去除首尾空格、转小写、展平嵌套逗号

2. **前端开放词汇界面**：
   - `Detection.vue` 第 98 行：`promptInput` 默认值为 `'car, person, drone'`
   - 快捷类别芯片（Quick Chips）：car、person、drone、truck、motorcycle、boat、backpack
   - 实时解析为 `targetClasses` 数组，通过 WebSocket 发送给后端

3. **YOLO-World 原理**：
   - YOLO-World 使用视觉-语言对齐的 CLIP 文本编码器
   - 用户自定义 Prompt 转换为文本 embedding，与视觉特征匹配
   - 无需类别定义文件，无需重新训练

#### 评估

| 维度 | 现状 | 比赛答辩支撑 |
|------|------|-------------|
| 开放类别能力 | ✅ 完整实现，可检测任意用户定义的词汇 | **强项，可直接展示** |
| 零样本泛化 | ✅ YOLO-World 预训练模型天然支持 | 可声称"零样本泛化" |
| 类别描述能力 | ⚠️ 仅支持单词/短语，无短语描述（如"穿红衣的人"） | 易被问住：能否做属性检测？ |
| 新类别适应 | ⚠️ 依赖预训练数据集覆盖范围 | 建议在 PPT 中限定应用场景 |

**结论**：开放词汇检测是**当前系统最完整、最可展示的核心能力**。适合作为比赛答辩的 Demo 亮点。

---

### C.3 轻量化实时部署

#### 已实现内容

**代码证据**：`frontend/src/config/index.ts`、`backend/core/inference.py`

1. **实时推理管道**：
   - WebSocket 全双工通信，前端 Base64 编码帧 → 后端推理 → 结果返回
   - LIFO（Last-In-First-Out）调度器：**仅处理最新帧**，旧帧直接丢弃，消除累积延迟
   - `run_in_threadpool` 将 GPU 推理隔离到线程池，不阻塞 FastAPI 事件循环

2. **帧率自适应降频**：
   - `useVideoStream.ts` 第 87 行：端到端延迟 > 200ms 时自动从 20 FPS 降至 10 FPS
   - 前端显示"已节流至 10 FPS"警告

3. **轻量化模型可选**：
   - `weights/` 目录包含 yolov8n（6.5MB）到 yolov8x（137MB）全系列
   - 前端可切换模型：`selectedModel` 参数透传给后端
   - YOLOv8n 为 ultralytics 默认下载，推理速度最快

4. **多客户端并发安全**：
   - `threading.Lock` 保护 `set_classes()` + `predict()` 原子执行
   - 多个 WebSocket 连接共享同一 GPU 模型实例

#### 评估

| 维度 | 现状 | 比赛答辩支撑 |
|------|------|-------------|
| 实时性 | ✅ LIFO 策略消除延迟，FPS 节流机制 | **可展示**：监控大屏永远显示实况 |
| 模型选择 | ⚠️ 代码支持但前端仅暴露 YOLO-World-V2 和 YOLOv8-Base | 可扩展切换不同大小模型 |
| 推理加速 | ❌ 无 TensorRT/ONNX/INT8/QAT | 易被问住：有想过用 TensorRT 加速吗？ |
| 端侧部署 | ❌ 仅服务端 GPU 推理 | 易被问住：能否部署到嵌入式/移动端？ |
| 并发处理 | ⚠️ LIFO 调度 + 线程锁，适合单 GPU | 多路视频流并发需评估 |

**结论**：实时性设计合理，但推理加速和端侧部署未实现。建议以"LIFO 实时流处理架构"为技术亮点，不建议声称"轻量化推理优化"。

---

## D. 当前缺口与未完成项

### D.1 明确未实现的功能

| 功能 | 代码证据 | 影响 |
|------|----------|------|
| **训练/微调管道** | 全项目无任何 `train`、`finetune`、`augment` 关键词（仅 `model_manager.py` 的注释中提到） | 无法针对比赛数据集定制优化 |
| **模型导出与优化** | `requirements.txt` 无 ONNX/TensorRT/OpenVINO 相关包 | 无法量化部署 |
| **真实评估体系** | `Performance.vue` 第 19-36 行：所有数据为硬编码 Mock（mAP50=0.782 等） | 性能页无实际意义 |
| **VisDrone 数据集集成** | `data/visdrone/` 目录存在但未接入推理管道 | 无法批量评测 |
| **视频存储** | `DetectionRecord.video_path` 字段存在，但前端 `saveDetection` 不传视频文件 | 历史记录无视频预览 |
| **Docker/容器化部署** | 无 Dockerfile | 生产部署需手动配置环境 |
| **多模型联合推理** | 仅支持单模型推理，无模型融合/集成 | 无法做模型 ensemble |

### D.2 概念提及但未落地的功能

| 功能 | 文档提及 | 代码实现 |
|------|----------|----------|
| GPU 利用率监控 | `Performance.vue` 提及 | 无真实 GPU 指标采集代码 |
| 置信度过滤 | 推理使用 conf=0.01 | 无后处理置信度过滤（返回全部 conf > 0.01 的检测） |
| 类别映射与过滤 | `CLASS_COLORS` 调色板 | 仅用于渲染，无语义映射 |

### D.3 优先补齐建议（按性价比排序）

#### 高优先级（直接提升比赛竞争力）

1. **补充 YOLO-World 微调代码**（⚠️ 性价比最高）
   - 路径：`backend/models/` 下新增 `trainer.py`
   - 使用 VisDrone 数据集进行 few-shot 微调
   - 只需：数据标注 + 20 行训练脚本
   - 答辩可以说："针对航拍场景定制优化"

2. **完善 Performance.vue 真实评测**
   - 调用 `ultralytics` 的 `val()` 方法获取真实 mAP
   - 对接 VisDrone 测试集
   - 生成 P-R 曲线数据

#### 中优先级（提升系统完整性）

3. **视频文件存储与回放**
   - 前端上传视频时，同时上传到后端 `data/videos/` 目录
   - 历史记录关联视频文件，支持回放

4. **推理加速初步探索**
   - 至少尝试导出 ONNX（`model.export(format='onnx')`）
   - 可作为"技术探索"写入 PPT

#### 低优先级（锦上添花）

5. Docker 容器化
6. 多模型 ensemble
7. 移动端/嵌入式部署

### D.4 答辩高风险问题清单

以下问题如果被问到，没有代码证据支撑，需要提前准备话术：

| 问题 | 风险等级 | 建议话术方向 |
|------|----------|--------------|
| "你们的模型在复杂场景下怎么保证精度？" | 🔴 高 | 强调 YOLO-World 预训练泛化能力，承认"目前使用预训练模型，后续可针对数据集微调" |
| "航拍小目标多，怎么检测？" | 🔴 高 | 准备 YOLO-World 的 TTA（Test-Time Augmentation）策略，或说"配合高分辨率输入" |
| "有没有针对 VisDrone 评测过？指标是多少？" | 🔴 高 | **必须准备**：目前无评测，需补上 |
| "推理延迟是多少？怎么测的？" | 🟡 中 | 代码可获取 `inference_time_ms`，已在性能监控页显示 |
| "部署到嵌入式设备可以吗？" | 🟡 中 | 说"支持导出 ONNX，可对接 TensorRT"，承认"当前为服务端 GPU 版本" |
| "用的什么训练策略？" | 🔴 高 | **必须承认**：无训练代码，使用预训练模型 |
| "类别描述能支持吗？比如'穿红色衣服的人'？" | 🟡 中 | 说"YOLO-World 支持简单词汇，复杂描述需 CLIP + LLM" |

---

## E. 数据流与业务流程梳理

### E.1 完整数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端（Vue 3 + Canvas）                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. 视频输入                                                                     │
│     - 本地文件：拖拽/选择 MP4/MOV/AVI → videoEl.src = blobURL                  │
│     - 摄像头：navigator.mediaDevices.getUserMedia → MediaStream               │
│     证据：useVideoStream.ts loadFile() / selectWebcam()                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. 帧捕获 + Base64 编码                                                         │
│     - requestAnimationFrame 控制帧率（默认 20fps，延迟>200ms 时降至 10fps）      │
│     - canvas.toDataURL('image/jpeg', 0.7) → Base64 字符串                      │
│     - 封装：{ message_type, frame_id, timestamp, image_base64,                 │
│              selected_model, target_classes }                                 │
│     证据：useVideoStream.ts captureAndSend() 第 63-77 行                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼ WebSocket ws://server:8000/api/ws/video_stream
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. 后端 WebSocket 接收                                                         │
│     - Pydantic v2 校验（ValidationError → error 消息返回）                    │
│     - LIFO 调度器：push_frame() → 覆盖旧帧                                    │
│     证据：routers/video_stream.py 第 19-64 行                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼ run_in_threadpool（线程池隔离）
┌─────────────────────────────────────────────────────────────────────────────┐
│  4. 模型推理                                                                     │
│     - 懒加载：首次 infer() 时加载模型权重                                       │
│     - 线程锁：set_classes() + predict() 原子执行                               │
│     - YOLO-World：set_classes(prompt) → predict(img) → boxes.xyxy/conf/cls    │
│     - conf 阈值：0.01（极低，尽量多返回）                                       │
│     证据：models/model_manager.py YOLOWorldV2.infer() 第 133-196 行            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5. 结果封装与返回                                                               │
│     - { message_type: 'inference_result', frame_id, timestamp,               │
│         inference_time_ms, detections: [{class_name, confidence, bbox}] }    │
│     证据：core/models.py InferenceResult 第 38-44 行                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼ WebSocket 返回
┌─────────────────────────────────────────────────────────────────────────────┐
│  6. 前端结果渲染                                                                 │
│     - RAF 60fps Canvas 渲染循环                                                 │
│     - drawImage(video) 绘制当前帧                                               │
│     - drawDetection() 绘制 BBox（角标 + 标签 + 置信度）                         │
│     - drawSummaryOverlay() 实时统计面板                                        │
│     - 性能指标：systemLatency（端到端延迟）、inferenceTime（推理耗时）、FPS      │
│     证据：useCanvasRenderer.ts renderFrame() 第 191-233 行                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  7. 结果持久化（分析结束时）                                                     │
│     - autoSave() → POST /api/history                                           │
│     - 保存：video_name, duration, model_name, class_counts, total_detections   │
│     - 历史记录：SQLite skyline.db                                               │
│     证据：Detection.vue autoSave() 第 77-94 行                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### E.2 各模块完成度

| 模块 | 完成度 | 说明 |
|------|--------|------|
| **视频输入** | ✅ 90% | 本地文件 + 摄像头，缺少 RTSP/流媒体拉流 |
| **帧捕获** | ✅ 95% | Base64 编码、帧节流、拖拽上传 |
| **WebSocket 通信** | ✅ 95% | 指数退避重连、Pydantic 校验、错误封装 |
| **模型推理** | ✅ 80% | YOLO-World 推理链路完整，缺少置信度过滤 |
| **结果渲染** | ✅ 95% | BBox、角标、统计面板、状态机 |
| **历史记录** | ⚠️ 60% | 数据库持久化完成，但无视频文件关联 |
| **性能监控** | ⚠️ 40% | 前端界面完整，**无真实数据来源** |
| **训练管道** | ❌ 0% | 无 |
| **模型导出** | ❌ 0% | 无 |
| **部署脚本** | ⚠️ 50% | 一键启动脚本有，但无容器化 |

---

## F. 后续建议

### F.1 比赛方案包装建议

#### 可作为"技术亮点"的内容（代码支撑较强）

1. **LIFO 实时流处理架构**
   - 代码证据：`InferenceScheduler` 类，`push_frame()` 覆盖旧帧逻辑
   - 可画在 PPT 技术路线图上
   - 对比"传统队列 FIFO"：消除累积延迟

2. **开放词汇检测能力**
   - 代码证据：`YOLOWorldV2.set_classes()`、`promptInput` 前端界面
   - Demo 效果最强：用户输入任意词汇，实时检测

3. **WebSocket 全双工 + 事件循环保护**
   - 代码证据：`run_in_threadpool` 隔离 GPU 推理
   - 可解释"AI 推理不阻塞 Web 服务响应"

4. **线程安全的 GPU 共享**
   - 代码证据：`_infer_lock` 锁保护多客户端并发
   - 可展示"多终端共享 GPU 资源"

#### 适合作为"功能点"的内容

| 功能点 | 实现难度 | 说明 |
|--------|----------|------|
| 本地视频 + 摄像头双输入 | ⭐ | 已完成，可直接展示 |
| 快捷类别芯片（Quick Chips） | ⭐ | 已完成，提升用户体验 |
| 分析暂停/继续 | ⭐ | 已完成，Space 键交互 |
| 历史记录库 + 数据导出 | ⭐⭐ | 已完成，但视频回放需补充 |
| 性能监控仪表盘 | ⭐ | UI 完整，需接真实数据 |
| 模型切换（YOLO-World vs YOLOv8） | ⭐ | 代码支持，前端可扩展 |

### F.2 技术路线图建议

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Skyline 技术路线图                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  【当前】                           【短期 · 1-2周】           【中期 · 1个月】     │
│  ┌─────────────┐                    ┌─────────────┐           ┌─────────────┐   │
│  │ YOLO-World  │                    │ VisDrone    │           │ TensorRT    │   │
│  │ 预训练推理   │  ──微调──→        │ 数据微调     │ ──导出──→  │ 推理加速     │   │
│  │ (开放词汇)   │                    │ (定制优化)   │           │ (INT8/QAT)  │   │
│  └─────────────┘                    └─────────────┘           └─────────────┘   │
│       │                                   │                        │            │
│       ▼                                   ▼                        ▼            │
│  ┌─────────────┐                    ┌─────────────┐           ┌─────────────┐   │
│  │ LIFO 调度   │                    │ 真实评测指标 │           │ 边缘部署     │   │
│  │ 实时流处理   │                    │ mAP/P-R     │           │ ONNX Runtime│   │
│  └─────────────┘                    └─────────────┘           └─────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### F.3 改进优先级矩阵

| 改进项 | 技术价值 | 比赛竞争力 | 实现成本 | 推荐度 |
|--------|----------|------------|----------|--------|
| VisDrone 数据微调 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Performance.vue 真实评测 | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| ONNX 导出尝试 | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| 视频文件存储 | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| TensorRT 加速 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| Docker 容器化 | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ |

---

## G. 总结表

| 方向 | 当前状态 | 已实现内容 | 未完成内容 | 建议优先级 |
|------|----------|------------|------------|------------|
| **复杂场景高精度检测** | ⚠️ 部分实现 | YOLO-World 预训练模型、GPU 加速、Warmup 预热、conf=0.01 激进阈值 | 针对航拍场景的数据微调、小目标专项优化、数据增强 | ⭐⭐⭐⭐⭐（补 VisDrone 微调） |
| **开放类别泛化识别** | ✅ 完整实现 | YOLO-World set_classes()、前端 Prompt 输入、快捷类别芯片、多类别逗号解析 | 复杂短语描述（如属性检测）、零样本到少样本的自适应切换 | ⭐⭐⭐（已是强项，适度包装） |
| **轻量化实时部署** | ⚠️ 基础具备 | LIFO 调度、WebSocket 全双工、帧率自适应降频、多客户端线程安全、模型可选（n-s-x） | ONNX/TensorRT 量化导出、端侧部署、多模型集成 | ⭐⭐⭐（先尝试 ONNX 导出） |
| **训练管道** | ❌ 未实现 | 无 | 训练脚本、Fine-tuning 代码、数据增强管道 | ⭐⭐⭐⭐⭐（比赛必需） |
| **评估体系** | ❌ 未实现 | Performance.vue UI 框架 | 真实 mAP 计算、P-R 曲线生成、VisDrone 批量评测 | ⭐⭐⭐⭐⭐（比赛必需） |
| **模型导出/压缩** | ❌ 未实现 | 无 | ONNX 导出、TensorRT 加速、INT8 量化 | ⭐⭐⭐（有 ONNX 导出意识即可） |
| **系统完整性** | ⚠️ 雏形 | 推理链路、前端界面、数据库持久化 | 视频存储、Docker 部署、多路并发 | ⭐⭐（后续补充） |

---

## H. 附录：关键代码索引

### H.1 WebSocket 通信协议

**上行帧格式**（`frontend/src/types/skyline.ts` 第 6-13 行）：
```typescript
interface VideoFrame {
  message_type: 'video_frame'
  frame_id: number
  timestamp: number        // epoch seconds
  image_base64: string    // "data:image/jpeg;base64,..."
  selected_model: string  // 'YOLO-World-V2' | 'YOLOv8-Base'
  target_classes: string[] // ['car', 'person', 'drone']
}
```

**下行结果格式**（`backend/core/models.py` 第 31-44 行）：
```python
class InferenceResult(BaseModel):
    message_type: Literal["inference_result"]
    frame_id: int
    timestamp: float
    inference_time_ms: float
    detections: List[Detection]
```

### H.2 模型推理核心逻辑

`backend/models/model_manager.py` 第 133-196 行：
```python
# 1. 强制 Prompt 清洗
clean_classes: list[str] = []
for c in target_classes:
    clean_classes.extend([x.strip().lower() for x in c.split(",") if x.strip()])

# 2. 解码图像
img = _decode_base64_image(image_base64)

# 3. 推理（conf=0.01 极低阈值）
with self._infer_lock:
    model.set_classes(clean_classes)
    model.to("cuda")
    results = model.predict(img, verbose=True, conf=0.01, device=0)

# 4. 解析检测框
if results and results[0].boxes is not None:
    boxes = results[0].boxes
    for i in range(len(boxes)):
        x1, y1, x2, y2 = boxes.xyxy[i].tolist()
        conf = float(boxes.conf[i])
        detections.append(Detection(
            class_name=cls_name,
            confidence=round(conf, 3),
            bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
        ))
```

### H.3 LIFO 调度器

`backend/core/inference.py` 第 84-137 行：
```python
class InferenceScheduler:
    """LIFO single-frame-buffer scheduler.
    旧帧直接丢弃，永不排队等待，监控大屏永远显示实况。"""
    
    async def push_frame(self, frame: VideoFrame) -> None:
        async with self._lock:
            self._latest_frame = frame  # 覆盖旧帧
            self._has_frame.set()
    
    async def run(self, result_callback) -> None:
        while self._running:
            frame = await self._pop_frame()  # 只取最新帧
            result = await run_in_threadpool(_blocking_inference, frame)
            await result_callback(result)
```

---

*文档版本：v1.0*  
*分析范围：代码审查（2026-03-27 前的代码状态）*  
*下一步：可基于本文档进行 PPT 制作、技术方案设计、代码补全计划制定*
