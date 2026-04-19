# Skyline — 天际线智能视觉检测系统

> 基于无人机实时航拍的多场景目标智能检测与识别系统

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue-3.5-42b883?logo=vue.js)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![YOLO-World](https://img.shields.io/badge/YOLO--World-v8s--worldv2-red?logo=yolo)](https://docs.ultralytics.com/models/yolo-world/)

---

## 项目简介

Skyline（天际线）是面向比赛展示与答辩的多场景目标检测系统，基于无人机航拍视频流，实现实时目标检测与智能分析。

**核心定位**：
- 面向比赛展示与答辩的材料交付
- 基于无人机航拍视频的多场景目标检测系统
- 兼顾实时性、稳定性、系统完整度与可解释性
- 为参赛作品提供可演示、可继续打磨的完整系统

---

## 当前系统能力

系统已实现以下完整功能链路：

- **首页多场景展示**：Dashboard 页面呈现多场景 demo 视频，覆盖白天城区道路 / 夜间低照度 / 高空密集小目标 / 复杂背景等典型无人机航拍场景
- **Detection 实时检测**：视频加载 → 模型配置 → 实时推理 → Canvas 可视化完整链路
- **WebSocket 视频流推理**：全双工 WebSocket 通信，LIFO 单帧覆盖缓冲，消除累积延迟
- **模型切换与视频切换**：支持三种模型：
  - **YOLO-World-V2**（开放词汇，PT）：支持自定义任意英文类别词
  - **YOLOv8-VisDrone / SKY-Monitor**（通用航拍，ONNX）：VisDrone 航拍 10 类（pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor）
  - **YOLOv8-Person / SKY-Person**（人员专用，ONNX）：人体检测专用模型
- **任务助手（自然语言任务解析）**：用户输入自然语言任务描述，AI 解析后推荐模型与类别配置，支持"应用到当前配置"
- **推荐配置应用**：任务助手解析结果可一键写入当前检测配置，不会自动启动检测，由用户手动触发
- **检测完成态摘要**：检测结束时自动生成本地检测摘要（检测次数 / 类别分布 / 最大帧目标数 / 本地结论文本）
- **AI 短报告生成**：用户在完成态手动点击"生成 AI 短报告"，后端调用 LLM 生成中文短报告，完成后自动补写入历史记录 extra_data
- **历史记录归档与详情页展示**：检测记录自动保存，支持查看 / 下载视频 / 下载 JSON / 在线播放 / 删除操作；HistoryDetail 展示完整检测统计与 AI 总结
- **模型评估页**：评测总览 / 标准评测结果 / 场景鲁棒性分析 / 典型案例分析 / 轻量训练摘要
- **PT / ONNX 双运行时路径**：PyTorch（YOLO-World-V2）与 ONNX（YOLOv8-VisDrone、YOLOv8-Person）两条路径统一向前端暴露 timing 字段；TensorRT 为后续扩展方向

---

## 系统架构概览

```
┌────────────────────────────────────────────────────────────┐
│  用户终端（浏览器）                                         │
│  ┌─────────────────┐     ┌──────────────────────────────┐ │
│  │  Vue 3 前端      │     │  Canvas 渲染 / BBox 可视化    │ │
│  │  状态机控制      │◄────│  WebSocket 实时推理结果       │ │
│  └─────────────────┘     └───────────────────────────────┘ │
└─────────────────────────────┬──────────────────────────────┘
                              │  ws://host:8000/api/ws/video_stream
┌────────────────────────────┴────────────────────────────┐
│  FastAPI 后端                                             │
│  InferenceScheduler（LIFO 单帧缓冲调度）                  │
│  _blocking_inference（统一推理入口）                      │
│  ModelManager + PTDetector / ONNXDetector                │
└──────────────────────────────────────────────────────────┘
          │
          │ PTDetector / ONNXDetector
          ▼
    GPU 推理节点
  YOLO-World / YOLOv8

───────────────────────────────────────────────────────────
  Agent 服务：任务解析（/api/agent/parse-task）
             AI 短报告生成（/api/agent/generate-report）
  历史记录：SQLite + /api/history/*
```

**简要说明**：
- 前端负责视频帧捕获、WebSocket 推流、Canvas 可视化与状态机控制
- 后端负责 LIFO 调度、WebSocket 路由、模型懒加载与推理执行
- 模型管理层（ModelManager）通过双注册表（MODEL_REGISTRY + RUNTIME_CONFIG）解耦前端能力展示与后端运行时选择
- Agent 服务（独立 LLM 调用）提供任务解析与短报告生成，通过 `services/agent_service.py` 接入 SiliconFlow API
- 历史记录通过 SQLite 数据库持久化，extra_data JSON 字段承载 detection_summary 与 short_report

---

## 页面说明

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | Dashboard | 首页，多场景 demo 视频展示与功能入口 |
| `/detection` | Detection | 智能检测舱：视频加载 → 模型配置 → 实时分析 → Canvas 可视化 |
| `/history` | History | 历史记录库：查看、保存、下载历史检测任务 |
| `/history/:id` | HistoryDetail | 单次任务详情：完整检测统计 + AI 智能总结 |
| `/performance` | Performance | 模型评测总览：标准评测结果 + 场景鲁棒性分析 + 典型案例分析 + 轻量训练摘要 |

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | Vue 3 + TypeScript（严格模式） | Composition API，热更新 |
| 构建工具 | Vite + Tailwind CSS v4 | 原子化 CSS，深蓝企业 SaaS 配色 |
| 路由管理 | Vue Router | SPA 多页面路由 |
| 视频渲染 | Canvas 2D + requestAnimationFrame | 60fps BBox 覆盖绘制 |
| 网络通信 | 原生 WebSocket API | 全双工，指数退避自动重连 |
| 后端框架 | FastAPI + Starlette | 异步 WebSocket 路由 |
| 数据校验 | Pydantic v2 | 严格 schema，非法数据熔断 |
| 推理引擎 | Ultralytics YOLO-World + YOLOv8 | 开放词汇 + 闭集目标检测 |
| 深度学习 | PyTorch 2.0+（CUDA 12.1） + ONNXRuntime | PT / ONNX 双 runtime |
| 数据库 | SQLite（SQLAlchemy 2.0 async + aiosqlite） | 历史记录持久化 |
| AI 能力 | SiliconFlow API（DeepSeek-V3.2） | 任务解析 + 短报告生成 |

---

## 目录结构

```
skyline/
├── docs/
│   ├── ARCHITECTURE.md             # 系统架构文档
│   ├── backend.md                  # 后端架构文档
│   ├── frontend.md                 # 前端页面样式与行为文档
│   ├── cloud_platform_design.md   # 云端平台设计方案（后续扩展）
│   ├── communicate.md              # 项目现状分析文档
│   ├── log.md                     # 开发修改日志
│   └── README.md                  # 项目主说明文档

├── backend/                        # FastAPI 后端（Python 3.10+）
│   ├── main.py                    # 应用入口，CORS，路由注册，init_db
│   ├── core/
│   │   ├── models.py              # Pydantic v2 数据模型（VideoFrame / InferenceResult / StatusMessage / ErrorMessage）
│   │   ├── inference.py           # InferenceScheduler（LIFO）+ _blocking_inference
│   │   └── database.py            # SQLAlchemy 异步配置（aiosqlite + SQLite）
│   ├── models/
│   │   ├── registry.py           # 双注册表：MODEL_REGISTRY（前端元数据）+ RUNTIME_CONFIG（后端执行配置）
│   │   ├── model_manager.py       # ModelManager（工厂+缓存）+ BaseDetector + PTDetector + ONNXDetector
│   │   └── history.py             # DetectionRecord ORM 模型
│   ├── routers/
│   │   ├── video_stream.py        # WebSocket 路由 /api/ws/video_stream
│   │   ├── history.py             # 历史记录 REST API
│   │   ├── agent.py               # Agent 任务解析 + AI 报告生成 API
│   │   └── models.py              # 模型能力查询 API
│   └── services/
│       └── agent_service.py        # Agent LLM 调用（SiliconFlow）

├── frontend/                      # Vue 3 + TS + Tailwind 前端
│   ├── vite.config.ts             # Vite 配置（0.0.0.0 外部访问）
│   └── src/
│       ├── main.ts                # 入口
│       ├── App.vue                # 根组件
│       ├── router/index.ts        # 路由表
│       ├── store/systemStatus.ts  # 共享 WS / GPU 状态
│       ├── config/index.ts        # 全局配置常量（FPS、JPEG 质量、阈值）
│       ├── types/skyline.ts       # 共享类型定义 + CLASS_COLORS
│       ├── api/
│       │   ├── agent.ts           # Agent 接口：parse-task / generate-report
│       │   ├── history.ts         # 历史记录接口：列表/详情/保存/补写
│       │   └── models.ts          # 模型列表与能力接口
│       ├── composables/
│       │   ├── useWebSocket.ts    # WebSocket 连接、重连、心跳、waitForConnected
│       │   ├── useVideoStream.ts  # 视频帧捕获、背压推送
│       │   ├── useCanvasRenderer.ts # Canvas BBox 渲染
│       │   ├── useModelConfig.ts  # 模型选择与配置状态
│       │   ├── useBufferedLocalPlayback.ts
│       │   └── useDelayedDisplay.ts
│       ├── components/detection/
│       │   └── TaskAssistantPanel.vue # 任务助手：自然语言任务解析推荐
│       ├── layouts/
│       │   └── MainLayout.vue     # 侧边栏 + 顶栏布局
│       ├── views/
│       │   ├── Dashboard.vue      # 首页（多场景 demo 展示）
│       │   ├── Detection.vue      # 智能检测舱（主功能）
│       │   ├── History.vue        # 历史记录列表
│       │   ├── HistoryDetail.vue  # 历史数据详情页
│       │   └── Performance.vue    # 模型评测页
│       └── data/
│           ├── performanceReport.mock.ts   # 评测报告 mock 数据
│           └── performanceCsvAdapter.ts     # CSV 适配器（训练历史）

├── weights/                       # 模型权重（需单独下载）
│   ├── yolov8m-worldv2.pt        # YOLO-World V2（开放词汇，PT）
│   ├── VisDrone/
│   │   └── yolov8x_visdrone_best.onnx  # SKY-Monitor（通用航拍，ONNX）
│   └── person_only/
│       └── best_person.onnx      # SKY-Person（人员专用，ONNX）

├── data/                          # SQLite 数据库存储目录
├── start_backend.sh              # 一键启动后端
├── start_frontend.sh             # 一键启动前端
├── requirements.txt              # Python 依赖
├── STARTUP.md                    # 详细启动说明书
└── README.md                    # 本文件
```

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- NVIDIA GPU + CUDA 12.1（如需 GPU 推理）
- Ubuntu / macOS / Windows（WSL2 兼容）

### 1. 克隆仓库

```bash
git clone https://github.com/LiPume/skyline_detection_system.git
cd skyline_detection_system
```

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 下载模型权重

YOLO 模型权重需单独下载，放置到 `weights/` 目录：

```bash
# YOLO-World V2（开放词汇，推荐）
# ultralytics 会在首次运行时自动下载，也可手动从 https://www.ultralytics.com 下载
# YOLOv8-VisDrone ONNX 和 YOLOv8-Person ONNX 需自行训练或获取
```

### 4. 启动后端

```bash
bash start_backend.sh
# 或手动：
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

验证：
```bash
curl http://localhost:8000/health
# {"status":"ok","service":"skyline-backend","version":"1.0.0"}
```

### 5. 启动前端

```bash
bash start_frontend.sh
# 或手动：
cd frontend && npm install && npm run dev
```

### 6. 访问系统

在浏览器打开：`http://<服务器IP>:5173`

---

## WebSocket 通信协议

### 上行帧（Client → Server）

```json
{
  "message_type": "video_frame",
  "timestamp": 1710345678.123,
  "frame_id": 1024,
  "image_base64": "data:image/jpeg;base64,/9j/...",
  "model_id": "YOLO-World-V2",
  "prompt_classes": ["car", "person"],
  "selected_classes": [],
  "selected_model": "YOLO-World-V2",
  "target_classes": ["car", "person"]
}
```

### 下行结果（Server → Client）

```json
{
  "message_type": "inference_result",
  "frame_id": 1024,
  "timestamp": 1710345678.123,
  "inference_time_ms": 45.2,
  "session_ms": 38.7,
  "preprocess_ms": 3.2,
  "postprocess_ms": 5.1,
  "model_id": "YOLO-World-V2",
  "detections": [
    { "class_name": "car",    "confidence": 0.95, "bbox": [120, 45, 80, 60]  },
    { "class_name": "person", "confidence": 0.88, "bbox": [200, 150, 40, 100] }
  ]
}
```

**BBox 格式**：`[x_min, y_min, width, height]`，单位：视频自然分辨率绝对像素。

**Timing 字段说明**：
- `inference_time_ms`：后端单帧总处理耗时（_blocking_inference 整体）
- `session_ms`：纯模型 forward 耗时（ONNX: session.run / PT: Results.speed["inference"]）
- `preprocess_ms`：预处理耗时
- `postprocess_ms`：后处理耗时
- `model_id`：本次推理使用的模型 ID（冷加载状态通知）

---

## 核心设计亮点

### LIFO 单帧覆盖缓冲（背压防御）

```
推流帧队列：
  帧#1 → 帧#2 → 帧#3 → 帧#4 → 帧#5
                          ↑
                   AI 推理线程始终只取最新帧
                   旧帧直接丢弃，永不排队等待
```

彻底消除累积延迟，监控大屏永远显示实况。

### 事件循环保护

所有 GPU 推理通过 `run_in_threadpool` 下放至线程池，网络 I/O 与 GPU 计算在物理调度上完全解耦。

### 多客户端 GPU 线程安全

`_infer_lock`：`threading.Lock()` 序列化 `set_classes()` + `predict()` 原子执行，多终端连接共享 GPU 而不冲突。

### 统一 PT / ONNX timing 协议

前端协议统一，两条 runtime 路径向前端暴露的字段完全一致（inference_time_ms / session_ms / preprocess_ms / postprocess_ms / model_id）。

### 模型冷加载状态通知

首次冷加载模型时，后端通过 WebSocket 发送 `StatusMessage(phase="model_ready")`，前端收到后从"加载中"状态切换为"分析中"。

---

## 当前说明

- 当前项目为"可演示、可继续打磨"的完整系统，文档以当前代码现状为准
- 云端平台设计部分（`docs/cloud_platform_design.md`）为后续扩展方案，不代表已全部实现
- 性能评测页（Performance.vue）数据来源为独立 mock 数据，后续可替换为真实评测 JSON / PR 数据 / 训练 CSV
- TensorRT runtime 为预留扩展方向，当前代码中尚未实现 TRTDetector

---

## 许可证

本项目仅供学术研究与个人学习使用。

---

## 致谢

- [Ultralytics YOLO-World](https://docs.ultralytics.com/models/yolo-world/) — 开源开放词汇目标检测模型
- [Ultralytics YOLOv8](https://docs.ultralytics.com/models/yolov8/) — 高性能目标检测模型
- [Vue.js](https://vuejs.org/) — 渐进式 JavaScript 框架
- [FastAPI](https://fastapi.tiangolo.com/) — 现代 Python Web 框架
- [ONNXRuntime](https://onnxruntime.ai/) — 高性能跨平台推理引擎
