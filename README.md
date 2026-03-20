# Skyline — 天际线智能视觉检测系统

> 面向无人机航拍与高空视角的实时开放词汇目标检测系统

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue-3.5-42b883?logo=vue.js)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![YOLO-World](https://img.shields.io/badge/YOLO--World-v8s--worldv2-red?logo=yolo)](https://docs.ultralytics.com/models/yolo-world/)

---

## 系统概述

Skyline（天际线）是一个面向无人机航拍与高空视角的实时智能视频分析系统。通过云边协同架构，接收高频连续视频流，利用大模型（YOLO-World）进行低延迟、高精度的**开放词汇目标检测**（Open-Vocabulary Detection），将结构化检测结果实时渲染至 Web 交互界面。

**核心能力：**

- **开放词汇检测**：无需预定义类别，用户可自定义任意目标词汇（如 "无人机"、"施工车辆"、"异常人员"）
- **实时视频分析**：WebSocket 全双工通信，LIFO 缓冲策略消除累积延迟
- **跨设备访问**：前端 Vite 服务绑定 `0.0.0.0`，支持局域网任意终端访问
- **高性能推理**：YOLO-World + PyTorch GPU 加速，帧推理延迟毫秒级

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  用户终端（Mac / PC / 手机）                                │
│  ┌──────────────────┐    ┌──────────────────────────────┐ │
│  │  Vue 3 前端       │    │  频帧捕获 + Base64 编码       │ │
│  │  Canvas 渲染      │    │  WebSocket ──────────────────┼─┼──┐
│  │  BBox 可视化      │◄───┼──────────────────────────────┘ │  │
│  └──────────────────┘    │                                │  │
└──────────────────────────┼────────────────────────────────┼──┘
                           │       ws://server:8000         │
                           │                                ▼
              ┌─────────────────────────────┐  ┌──────────────────┐
              │  FastAPI 后端                 │  │  GPU 推理节点     │
              │  WebSocket /api/ws/stream    │  │  RTX 4090        │
              │  Pydantic 数据校验            │  │  YOLO-World      │
              │  LIFO 缓冲调度器              │  │  (weights/)      │
              └─────────────────────────────┘  └──────────────────┘
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | Vue 3 + TypeScript（严格模式）| Composition API，热更新 |
| 构建工具 | Vite + Tailwind CSS v4 | 原子化 CSS，深蓝企业 SaaS 配色 |
| 路由管理 | Vue Router | SPA 多页面：`/detection`、`/history` |
| 视频渲染 | Canvas 2D + requestAnimationFrame | 60fps 高帧率 BBox 覆盖绘制 |
| 网络通信 | 原生 WebSocket API | 全双工，指数退避自动重连 |
| 后端框架 | FastAPI + Starlette | 异步 WebSocket 路由 |
| 数据校验 | Pydantic v2 | 严格 schema，非法数据熔断 |
| 推理引擎 | Ultralytics YOLO-World | 开放词汇目标检测 |
| 深度学习 | PyTorch 2.0+（CUDA 12.1）| GPU 加速推理 |

---

## 目录结构

```
skyline/
├── docs/
│   ├── ARCHITECTURE.md          # 系统架构文档（唯一事实来源）
│   ├── description.md            # 前端样式规范
│   ├── log.md                   # 开发修改日志
│   └── 项目需求书.pdf            # 原始需求文档
│
├── backend/                      # FastAPI 后端（Python 3.10+）
│   ├── main.py                  # 应用入口，CORS，路由注册
│   ├── core/
│   │   ├── models.py            # Pydantic v2 数据模型
│   │   ├── inference.py         # LIFO 推理调度器
│   │   └── database.py          # SQLite 异步数据库
│   ├── models/
│   │   ├── model_manager.py     # YOLO-World / YOLOv8 懒加载单例
│   │   └── history.py           # 检测历史记录 ORM 模型
│   └── routers/
│       ├── video_stream.py       # WebSocket 路由 /api/ws/video_stream
│       └── history.py            # 历史记录 REST API
│
├── frontend/                     # Vue 3 + TS + Tailwind 前端
│   ├── vite.config.ts           # Vite 配置（0.0.0.0 外部访问）
│   └── src/
│       ├── main.ts               # 入口
│       ├── App.vue               # 根组件
│       ├── router/index.ts       # 路由表
│       ├── store/systemStatus.ts # 共享 WS / GPU 状态
│       ├── types/skyline.ts      # 共享类型定义 + CLASS_COLORS
│       ├── layouts/MainLayout.vue # 侧边栏 + 顶栏布局
│       ├── composables/
│       │   ├── useWebSocket.ts    # WS 连接 + 指数退避重连
│       │   ├── useVideoStream.ts  # 视频源管理 + 帧节流推流
│       │   └── useCanvasRenderer.ts # RAF 60fps 渲染 + BBox 绘制
│       └── views/
│           ├── Detection.vue     # 智能检测舱（主功能）
│           ├── History.vue       # 历史记录库
│           ├── HistoryDetail.vue # 历史数据详情页
│           └── Performance.vue   # 性能监控页
│
├── weights/                      # 模型权重（需单独下载，见下方说明）
│   ├── yolov8n.pt               # nano
│   ├── yolov8s.pt               # small
│   ├── yolov8m.pt               # medium
│   ├── yolov8l.pt               # large
│   ├── yolov8x.pt               # extra-large
│   └── yolov8s-worldv2.pt       # YOLO-World V2（推荐）
│
├── start_backend.sh              # 一键启动后端
├── start_frontend.sh             # 一键启动前端
├── requirements.txt              # Python 依赖
└── STARTUP.md                    # 详细启动说明书
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
# YOLOv8 官方模型（从 https://docs.ultralytics.com/models/yolov8/ 下载）
# YOLO-World V2（推荐用于开放词汇检测）
# ultralytics 会在首次运行时自动下载，也可手动放置于 weights/
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
  "selected_model": "YOLO-World-V2",
  "target_classes": ["car", "person", "drone"]
}
```

### 下行结果（Server → Client）

```json
{
  "message_type": "inference_result",
  "frame_id": 1024,
  "timestamp": 1710345678.123,
  "inference_time_ms": 45.2,
  "detections": [
    { "class_name": "car",    "confidence": 0.95, "bbox": [120, 45, 80, 60]  },
    { "class_name": "person", "confidence": 0.88, "bbox": [200, 150, 40, 100] }
  ]
}
```

**BBox 格式**：`[x_min, y_min, width, height]`，单位：视频自然分辨率绝对像素。

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

### 降频保护

端到端延迟 > 200ms 时，前端自动将推流从 20 FPS 降至 10 FPS，面板显示「已节流至 10 FPS」警告。

---

## 页面说明

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | → 自动跳转 `/detection` | |
| `/detection` | 智能检测舱 | 主功能：视频上传/摄像头 → AI 检测 → Canvas 可视化 |
| `/history` | 历史记录库 | 查看历史检测任务，支持视频预览与数据导出 |
| `/history/:id` | 任务详情 | 单次任务的完整检测数据与统计 |
| `/performance` | 性能监控 | 推理延迟、吞吐量、GPU 利用率实时图表 |

---

## 配置说明

### 前端 WebSocket 地址

默认通过 `window.location.hostname` 动态解析，无需硬编码。可通过环境变量覆盖：

```bash
# frontend/.env.local
VITE_WS_URL=ws://your-server-ip:8000/api/ws/video_stream
```

### 服务器 IP

`STARTUP.md` 中的默认服务器 IP 为 `10.31.112.43`，请根据实际部署环境修改。

---

## 开发相关

### 前后端分离

- **后端**：`http://localhost:8000`（FastAPI + Uvicorn）
- **前端**：`http://localhost:5173`（Vite 开发服务器）

两者通过 WebSocket 通信，端口独立，域名相同时前端会自动解析到正确地址。

### 防火墙

如无法从外部访问，确保开放以下端口：

```bash
sudo ufw allow 8000   # FastAPI 后端
sudo ufw allow 5173   # Vite 前端
```

---

## 许可证

本项目仅供学术研究与个人学习使用。

---

## 致谢

- [Ultralytics YOLO-World](https://docs.ultralytics.com/models/yolo-world/) — 开源开放词汇目标检测模型
- [Vue.js](https://vuejs.org/) — 渐进式 JavaScript 框架
- [FastAPI](https://fastapi.tiangolo.com/) — 现代 Python Web 框架
