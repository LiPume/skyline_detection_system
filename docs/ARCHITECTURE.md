# Skyline 天际线智能视觉系统 — 系统架构文档
> 最后更新：2026-03-20 

---

## 【Part 1】系统总体架构与技术栈

### 1. 项目概述
Skyline（天际线）是一个面向无人机航拍/高空视角的实时智能视频分析系统。系统通过云边协同架构，接收高频连续视频流，利用大模型（YOLO-World）进行低延迟、高精度的开放词汇（Open-Vocabulary）目标检测，并将结构化结果实时渲染至交互式监控大屏。

### 2. 系统物理拓扑
- **边缘算力节点 (backend)**：部署于配置 NVIDIA RTX 4090 的 Linux 服务器，负责视频流拆帧推理。
- **用户交互终端 (frontend)**：通过 Web 访问，负责视频流采集、Base64 编码分发与 Canvas 高帧率回放及 BBox 渲染。

### 3. 核心技术栈

#### 3.1 前端展现层
| 层级 | 技术 | 说明 |
|------|------|------|
| 核心框架 | Vue 3 (Composition API) + Vite | 构建工具，热更新 |
| 路由管理 | Vue Router | 多页面 SPA；`/` → `/detection`、`/history` |
| 样式框架 | Tailwind CSS + @tailwindcss/vite | 原子化 CSS，深蓝企业 SaaS 配色 |
| 开发语言 | TypeScript（严格模式） | 防止前后端字段对齐报错 |
| 视频渲染 | 隐藏 `<video>` 用于帧捕获，主 `<canvas>` 渲染检测结果 |
| 网络通信 | 浏览器原生 WebSocket API | 全双工，指数退避自动重连 |
| 共享状态 | 模块级 reactive ref（无 Pinia）| `src/store/systemStatus.ts` 跨组件共享 WS/GPU 状态 |

#### 3.2 后端服务层
| 层级 | 技术 | 说明 |
|------|------|------|
| 核心框架 | FastAPI + Starlette | 异步 WebSocket 路由 |
| 开发语言 | Python 3.10+ | asyncio 全异步 |
| 数据校验 | Pydantic v2 | 严格 schema，非法数据熔断 |
| 推理隔离 | `run_in_threadpool` | 阻塞推理下放线程池，保护事件循环 |

#### 3.3 算法引擎层
- 深度学习框架：PyTorch 2.0+（CUDA 12.1）
- 视觉大模型：Ultralytics YOLO-World（yolov8s-worldv2.pt）
- 图像处理：OpenCV-Python / NumPy（零磁盘 I/O）

### 4. 核心业务数据流
```
[前端] 高频帧捕获（按端到端延迟自动节流）→ capture frame → JPEG Base64 → JSON → WebSocket ──►
                                                                    [后端] Pydantic 校验 → LIFO 缓冲覆盖
                                                                    [后端] run_in_threadpool → YOLO
◄── WebSocket ← JSON (仅检测框数据，无图片) ← InferenceResult ──
[前端] 解析 detections → RAF 60fps → drawImage + drawBBox → Canvas
```

**带宽优化决议**：后端不回传原图 Base64，只返回轻量的结构化检测框 JSON（每帧仅几 KB）。前端直接将检测框覆盖绘制在自己持有的实时视频画面上，实现"数据与视图分离"。

---

## 【Part 2】WebSocket 通信协议与数据字典

### 1. 通信端点
```
ws://<服务器IP>:8000/api/ws/video_stream
```

### 2. 上行帧（Client → Server）
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

### 3. 下行结果（Server → Client）
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

### 4. 错误响应
```json
{
  "message_type": "error",
  "detail": "CUDA Out of Memory / Base64 Decode Failed"
}
```

### 5. BBox 坐标系
- 格式：`[x_min, y_min, width, height]`，单位：视频自然分辨率绝对像素
- 前端绘制前换算：`scaleX = canvas.width / video.videoWidth`

---

## 【Part 3】前端架构（Phase 5 重构后）

### 1. 多页面路由架构
```
/             → 重定向至 /detection
/detection    → 智能检测舱（Detection.vue）
/history      → 历史记录库（History.vue）
```

### 2. 视觉规范
| 类别 | 值 | 说明 |
|------|----|------|
| 主背景 | `bg-slate-950` (#020817) | 深藏青，替代纯黑 |
| 面板背景 | `bg-slate-900` (#0f172a) | 侧边栏与卡片 |
| 卡片/输入 | `bg-slate-800` (#1e293b) | 表单元素 |
| 强调色 | `blue-600/500` (#2563eb) | 按钮、选中态、活跃状态灯 |
| 正文 | `slate-200` (#e2e8f0) | 主要文字 |
| 辅助文字 | `slate-500` (#64748b) | 标签、描述 |
| 成功/在线 | `emerald-400` | WS ONLINE，ARMED 状态 |
| 危险/停止 | `red-400/500` | 停止按钮，OFFLINE 状态 |

### 3. 布局结构（SaaS 三栏）
```
┌─────────────────────────────────────────────────────────────┐
│ [▲ SKYLINE] Sidebar │     Header: 页面名称 | WS • GPU 状态  │
│                     ├─────────────────────────────────────── │
│  🔍 智能检测舱       │                                       │
│  📁 历史记录库       │          <router-view>                │
│                     │     Detection.vue / History.vue        │
│                     │                                       │
│  v1.0.0             │                                       │
└─────────────────────┴───────────────────────────────────────┘
```

### 4. Detection.vue 布局（左右分栏）
```
┌────────────────────────────┬─────────────────────────┐
│  视觉舞台 (flex-1 ≈70%)    │ AI 控制台 (w-80 ≈30%)   │
│                            │                         │
│  [状态 Pill 左上]           │  视频来源 (本地/摄像头) │
│                            │  推理模型 (Dropdown)    │
│  Canvas / Drop Zone        │  快捷类别 Chips         │
│  (占满剩余空间)             │  Prompt 输入框          │
│                            │  🚀 启动实时分析 (CTA)  │
│  [READY / FINISHED 浮层]   │  性能监控 (延迟/FPS)    │
│  [目标计数 Badge 右上]      │  网络控制               │
└────────────────────────────┴─────────────────────────┘
```

### 5. 交互状态机（与 Phase 4 一致）
```
standby  → [文件加载 / 摄像头]  → ready / analyzing
ready    → [🚀 启动分析]        → analyzing
analyzing→ [视频结束]           → finished
         → [停止分析]           → finished
finished → [🚀 重新启动]        → analyzing
         → [新文件加载]         → ready
```

### 6. 降频保护
- 延迟 > 200ms → 推流从 20 FPS 自动降至 10 FPS
- 面板显示「已节流至 10 FPS」警告

---

## 【Part 4】后端并发架构与调度策略

### 1. 事件循环保护
- 所有推理通过 `starlette.concurrency.run_in_threadpool` 下放至线程池
- 网络 I/O（收发帧）与 GPU 推理在物理调度上完全解耦

### 2. LIFO 单帧覆盖缓冲（背压防御）
```python
async def push_frame(self, frame):
    async with self._lock:
        self._latest_frame = frame   # 直接覆盖旧帧
        self._has_frame.set()
```
- AI 线程永远只处理**最新一帧**，旧帧直接丢弃
- 彻底消除累积延迟，保障大屏永远显示实况

### 3. 全双工熔断机制
- 客户端断连 → 捕获 `WebSocketDisconnect` → `finally` 块清理 scheduler + task
- 非法数据 → Pydantic v2 `ValidationError` → 返回标准 `ErrorMessage`，连接不中断

### 4. 多客户端 GPU 线程安全
- `_infer_lock`：`threading.Lock()` 序列化 `set_classes()` + `predict()` 原子执行
- `_load_lock`：双重检查锁保护懒加载单例

---

## 【Part 5】代码目录结构（Phase 5 最终版）

```
skyline/
├── docs/
│   └── ARCHITECTURE.md              # 本文档（唯一事实来源）
│
├── backend/                         # FastAPI 后端（Python 3.10+）
│   ├── main.py                      # 应用入口，CORS，路由注册
│   ├── core/
│   │   ├── models.py                # Pydantic v2 数据模型
│   │   └── inference.py             # LIFO 推理调度器
│   ├── models/
│   │   └── model_manager.py         # YOLO-World / YOLOv8 lazily-loaded singleton
│   └── routers/
│       └── video_stream.py          # WebSocket 路由 /api/ws/video_stream
│
├── frontend/                        # Vue 3 + TS + Tailwind 前端
│   ├── index.html
│   ├── vite.config.ts               # Vite + @tailwindcss/vite plugin
│   └── src/
│       ├── main.ts                  # createApp + useRouter
│       ├── App.vue                  # <MainLayout />
│       ├── style.css                # @import "tailwindcss" + global reset
│       ├── main.js                  # 兼容/遗留入口（如项目需要）
│       ├── components/
│       │   ├── HelloWorld.vue      # Vite 默认示例（当前路由不依赖）
│       │   └── SkylineDashboard.vue# 历史/原型组件（非当前主路由）
│       ├── router/
│       │   └── index.ts             # Vue Router 路由表
│       ├── store/
│       │   └── systemStatus.ts      # 模块级共享 wsStatus / isGpuActive
│       ├── layouts/
│       │   └── MainLayout.vue       # Sidebar + Header + <RouterView>
│       ├── views/
│       │   ├── Detection.vue        # 智能检测舱（含完整状态机 + 所有 composable）
│       │   └── History.vue          # 历史记录库（mock 数据展示）
│       ├── types/
│       │   └── skyline.ts           # 共享 TS 类型 + CLASS_COLORS
│       └── composables/
│           ├── useWebSocket.ts      # WS 连接管理 + 指数退避重连
│           ├── useVideoStream.ts    # 视频源管理 + 帧推流
│           └── useCanvasRenderer.ts # RAF 60fps 渲染 + BBox 绘制
│
├── weights/
│   └── yolov8s-worldv2.pt           # 模型权重（需单独下载）
│
├── start_backend.sh
├── start_frontend.sh
└── STARTUP.md
```

---

## 【Part 6】启动指南

### 后端
```bash
cd skyline/backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端
```bash
cd skyline/frontend
npm run dev      # 开发模式（http://0.0.0.0:5173，可外部访问）
npm run build    # 生产构建（dist/）
```

### 路由访问
| URL | 页面 |
|-----|------|
| `/` | 自动跳转 `/detection` |
| `/detection` | 智能检测舱（主功能页） |
| `/history` | 历史记录库 |

### 环境变量（可选）
```bash
# frontend/.env.local
VITE_WS_URL=ws://your-server-ip:8000/api/ws/video_stream
```

---

## 【Part 7】YOLO-World 模型接入说明

### 关键 API 差异
- 必须使用 `from ultralytics import YOLOWorld`（非 `YOLO`）
- 只有 `YOLOWorld` 子类暴露 `set_classes()` 方法用于开放词汇注入
- `set_classes()` + `predict()` 必须在同一 `threading.Lock()` 内原子执行（多客户端安全）

### 权重路径
```
weights/yolov8s-worldv2.pt   ← 相对于 skyline/ 根目录
```
WEIGHTS_DIR 在 `backend/models/model_manager.py` 中动态解析为绝对路径。
