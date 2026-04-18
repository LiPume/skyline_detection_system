# Skyline - 航拍场景智能检测系统

> 基于 YOLO 的航拍车辆与人员目标实时检测系统，支持开放词汇检测、固定类别检测、AI 任务解析与报告生成。

---

## 1. 项目概述

**Skyline** 是一个面向航拍视频场景的端到端目标检测系统，提供实时视频流推理、历史记录管理、模型评测对比三大核心能力。

**核心价值**：将 YOLO 系列模型（开放词汇 + 固定类别）封装为可直接演示、可交付验收的 Web 应用，链路完整，覆盖从视频输入到 AI 报告输出的完整闭环。

**适用场景**：无人机航拍监控、交通要道监测、安防巡逻、赛事展示与答辩演示。

---

## 2. 系统能力总览

### 2.1 核心功能

| 功能 | 说明 |
|------|------|
| 视频文件分析 | 本地 MP4/AVI 等视频文件，实时逐帧推理 |
| 摄像头实时分析 | 支持接入网络摄像头或 USB 摄像头进行实时检测 |
| 开放词汇检测 | YOLO-World-V2，支持用户自定义英文类别词（car, person, drone...） |
| 固定类别检测 | YOLOv8 系列，针对 COCO / 车辆 / VisDrone / 人员 / 热成像等场景 |
| AI 任务助手 | 自然语言描述任务，自动推荐合适的模型与类别组合 |
| AI 短报告生成 | 检测完成后，基于检测统计生成结构化中文分析报告 |
| 历史记录管理 | 保存/查看/删除/导出历史检测任务（视频、JSON 数据） |
| 模型评测对比 | 评测报告总览、标准评测结果、场景鲁棒性分析、典型案例展示 |

### 2.2 已集成模型

| 模型 | 类型 | 说明 |
|------|------|------|
| YOLO-World-V2 | open_vocab | 开放词汇，适用自定义类别（推荐） |
| YOLOv8-Base | closed_set | COCO 80 类基准模型 |
| YOLOv8-Car | closed_set | 车辆专项（car/truck/bus/bicycle/motorcycle） |
| YOLOv8-VisDrone | closed_set | VisDrone 航拍 10 类 |
| YOLOv8-Person | closed_set | 人员专项（高精度） |
| YOLOv8-Thermal-Person | closed_set | 热成像/红外人员检测 |

### 2.3 评测数据来源

- **Drone-Vehicle 数据集**：无人机航拍车辆与人员标准数据集，用于模型精度评测（mAP@0.5 / mAP@0.5:0.95 / Precision / Recall）
- **训练曲线**：基于 VisDrone 航拍数据集的训练历史数据

---

## 3. 页面与功能说明

### 3.1 首页（Dashboard）

系统入口，展示 demo 视频与核心能力卡片，引导用户进入各功能模块。

### 3.2 智能检测舱（Detection）

**主要操作流程**：

1. **选择视频来源**：上传本地视频文件，或接入实时摄像头
2. **选择模型**：从下拉菜单选择检测模型（6 个可选）
3. **配置类别**：
   - 开放词汇模型：输入英文类别词（支持快捷芯片 car/person/drone 等）
   - 固定类别模型：从类别列表中勾选要检测的类别
4. **启动分析**：点击"启动实时分析"，后端开始推理
5. **查看结果**：实时视频画面叠加检测框，右侧显示当前帧检测数量与帧率
6. **任务助手**（可选）：在右侧面板输入自然语言（"帮我检测视频中的汽车和行人"），点击理解任务获取推荐配置，一键应用
7. **视频结束或手动停止**：自动保存检测记录到历史记录
8. **生成 AI 报告**（可选）：点击"生成 AI 短报告"，后端生成结构化中文分析（基于检测统计与场景证据）

**检测口径说明**：检测次数 = 逐帧推理事件累计，同一目标在多帧中重复检测时分别计入。

### 3.3 历史记录（History / HistoryDetail）

- **History**：分页列表，展示历史任务（视频名、模型、分析时长、检测总数、状态）
- **HistoryDetail**：单次任务详情，包含 AI 智能总结、类别统计条形图、模型配置、原始 JSON 归档数据
- 支持：视频下载、JSON 数据导出、删除记录

### 3.4 评测对比（Performance）

面向比赛与答辩的展示页面，包含 5 个纵向模块：

1. **评测总览**：顶部指标卡（mAP@0.5 / mAP@0.5:0.95 / Precision / Recall / FPS）+ 模型配置 + 评测结论
2. **标准评测结果**：PR 曲线 + AP 排名 + 详细数据表（来自 Drone-Vehicle 评测数据）
3. **场景鲁棒性分析**：4 类场景分析（白天城区 / 夜间低照度 / 高空密集小目标 / 复杂背景）
4. **典型案例分析**：3 个典型案例卡片，点击弹出详情模态框
5. **轻量训练摘要**：精度演进曲线 + 最佳轮次标记（来自训练历史 CSV）

**注意**：顶部核心指标来自 Drone-Vehicle 标准评测结果；训练历史曲线来自真实训练数据；场景分析和典型案例为展示增强数据。

---

## 4. 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                     前端 (Vue 3 + TS)                    │
│  Detection.vue / History.vue / Performance.vue / ...   │
│  ├── composables: useWebSocket / useVideoStream        │
│  ├──         useCanvasRenderer / useModelConfig          │
│  └── api: agent.ts / history.ts / models.ts             │
└──────────────┬──────────────────────────────┬──────────┘
               │ WebSocket                    │ REST API
┌──────────────▼──────────────────────────────▼──────────┐
│                    后端 (FastAPI)                        │
│  /api/ws/video_stream    ← 实时视频流推理               │
│  /api/history*           ← 历史记录 CRUD                │
│  /api/models*            ← 模型列表与能力               │
│  /api/agent/parse-task   ← AI 任务解析                  │
│  /api/agent/generate-report  ← AI 短报告生成            │
└──────────────┬──────────────────────────────┬──────────┘
               │                             │
┌──────────────▼──────────────┐  ┌───────────▼────────────┐
│    推理引擎                  │  │  Agent 服务             │
│  PTDetector (YOLO)          │  │  SiliconFlow API        │
│  ONNXDetector (onnxruntime) │  │  (DeepSeek-V3.2)        │
│  InferenceScheduler (LIFO)  │  │                         │
└──────────────┬──────────────┘  └─────────────────────────┘
               │
┌──────────────▼──────────────┐
│  SQLite 数据库              │
│  detection_records 表       │
│  (aiosqlite 异步)           │
└─────────────────────────────┘
```

### 4.1 前端技术栈

- Vue 3（Composition API）+ TypeScript（严格模式）
- Vite + Tailwind CSS v4
- Vue Router（SPA 路由）
- 原生 WebSocket API（指数退避重连 + 心跳）
- Canvas 2D（BBox 叠加绘制）

### 4.2 后端技术栈

- FastAPI + Starlette（ASGI）
- Pydantic v2（请求/响应模型）
- SQLAlchemy 2.0 async + aiosqlite
- Ultralytics YOLO（PyTorch 模型）
- onnxruntime（ONNX 模型）
- SiliconFlow API（LLM 智能服务）

### 4.3 推理链路特点

- **LIFO 背压调度**：推理队列最多保留 1 帧，新帧覆盖旧帧，防止积压
- **异步推理**：推理在 ThreadPoolExecutor 中执行，不阻塞 ASGI 事件循环
- **懒加载模型**：模型首次使用时才加载到内存，并缓存在 ModelManager 中
- **模型类型分发**：通过 `runtime_type`（pytorch / onnx）分发动态构建合适的检测器

---

## 5. 快速启动

### 5.1 环境要求

- Python 3.10+
- Node.js 18+
- CUDA 11.8+（GPU 推理，推荐）/ 仅 CPU 亦可运行（速度较慢）

### 5.2 安装依赖

```bash
# 后端
cd skyline
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 5.3 启动服务

**方式一：分开启动（开发模式）**

```bash
# 终端 1：后端
cd skyline
python -m backend.main
# 或 uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2：前端
cd frontend
npm run dev
```

**方式二：前后端联调**

前端 `VITE_API_BASE_URL` 指向后端地址（默认 `http://localhost:8000`）。

### 5.4 启动后访问

- 前端地址：`http://localhost:5173`
- 后端地址：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`

### 5.5 必要配置

| 环境变量 | 说明 | 必填 |
|----------|------|------|
| `AGENT_API_KEY` | SiliconFlow API 密钥（用于 AI 任务助手与报告生成） | Agent 功能必填 |
| 模型权重文件 | 需将模型权重文件放置在 `backend/weights/` 目录，对应路径见 `RUNTIME_CONFIG` | 对应模型推理必填 |

---

## 6. 重要说明

### 6.1 展示增强 vs 核心链路

| 模块 | 性质 | 数据来源 |
|------|------|----------|
| Detection 实时推理链路 | **核心链路，稳定** | 实时推理 |
| History 记录与导出 | **核心链路，稳定** | 真实检测数据 |
| Performance 顶部指标 | **展示增强** | Drone-Vehicle 标准评测 |
| Performance 训练曲线 | **真实数据** | 训练历史 CSV |
| Performance 场景分析 | **展示增强** | mock 数据 |
| Performance 典型案例 | **展示增强** | mock 数据 |

### 6.2 当前限制

- **无模型热加载**：切换模型时需等待重新加载，不支持运行时热替换
- **无 TensorRT / OpenVINO**：registry 中预留位置，当前未实现
- **无逐帧目标追踪**：每帧独立推理，无 MOT 跨帧追踪
- **Agent 依赖外部 API**：需要配置 SiliconFlow API Key，无本地 LLM fallback
- **无权限认证**：所有 API 公开，无用户认证机制
- **laneDensityHint 为 0**：当前系统无逐帧坐标数据，车道密度相关判断为 0

### 6.3 检测口径

- "检测次数" = 逐帧推理事件累计（同一目标在连续帧中被重复检测时分别计入）
- "推理耗时" 中 `session_ms / preprocess_ms / postprocess_ms` 可能显示为 `--`（后端未返回时）

### 6.4 目录结构

```
skyline/
├── frontend/                 # Vue 3 前端应用
│   ├── src/
│   │   ├── views/           # 页面组件
│   │   ├── composables/     # 组合式函数（WebSocket、视频流、Canvas渲染、模型配置）
│   │   ├── api/             # API 客户端
│   │   ├── components/      # 可复用组件
│   │   ├── types/           # TypeScript 类型定义
│   │   └── router/          # 路由配置
│   └── ...
├── backend/                  # FastAPI 后端应用
│   ├── main.py              # 应用入口
│   ├── core/                # 核心逻辑（推理调度、数据库）
│   ├── models/              # 模型管理（注册表、检测器、ORM）
│   ├── routers/             # API 路由（WebSocket、REST）
│   ├── services/            # Agent 服务（LLM 调用）
│   └── weights/             # 模型权重文件（需自行放置）
├── docs/                     # 项目文档
│   ├── frontend.md          # 前端实现说明
│   ├── backend.md          # 后端实现说明
│   └── README.md            # 项目主说明
└── requirements.txt          # Python 依赖
```
