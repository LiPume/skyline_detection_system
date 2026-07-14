# Skyline（天际线）智能视觉检测系统

> 面向无人机航拍场景的多模型实时目标检测、智能任务解析与检测结果归档平台。

本仓库是**第十七届中国大学生服务外包创新创业大赛东部区域赛企业命题类 A27 赛题**的项目封板归档。它保留了可运行的前后端源码、页面演示资源、评测素材、启动脚本与架构文档，方便答辩展示、成果留存和后续复现。

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3.5-42b883?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Git LFS](https://img.shields.io/badge/Demo%20assets-Git%20LFS-ff6b6b)](https://git-lfs.com/)

## 项目做什么

Skyline 将浏览器端视频流、后端 GPU 推理和检测任务管理整合为一个可交互的 Web 系统。用户可以从本地视频或摄像头输入画面，选择适合的目标检测模型，在浏览器中实时查看检测框、类别和耗时；完成后可归档检测结果，生成简短的中文分析报告。

系统面向航拍巡查、道路交通、园区人员监测、低照度场景等演示需求，重点解决实时展示中“推理排队导致画面越来越落后”的问题：后端只保留最新帧进行推理，宁可丢弃旧帧也不累积延迟。

## 功能一览

| 模块 | 已实现能力 |
| --- | --- |
| 多场景首页 | 城市道路、低照度、高空小目标、复杂背景等预置视频展示。 |
| 智能检测舱 | 本地视频/摄像头取流、模型和类别配置、实时 Canvas 检测框叠加、耗时反馈。 |
| 实时传输 | 浏览器 WebSocket 推送 JPEG 帧；后端 LIFO 单帧覆盖缓冲与自动重连机制。 |
| 多模型推理 | YOLO-World V2 开放词汇检测，以及 VisDrone、Person 两个闭集 ONNX 模型。 |
| 任务助手 | 自然语言任务解析，给出模型与类别推荐；用户确认后才应用配置。 |
| 结果归档 | SQLite 保存检测记录、检测统计、结果视频/JSON 下载及详情查看。 |
| AI 短报告 | 任务完成后可按需调用 LLM 生成中文短报告，不配置密钥时不影响核心检测。 |
| 性能评测 | 标准评测、鲁棒性场景、PR 曲线和典型案例展示；数据与页面随仓库保留。 |

## 系统架构

```text
浏览器（Vue 3）
  视频帧捕获 ── WebSocket ──> FastAPI
  Canvas 结果绘制 <──────────  推理调度器（仅保留最新帧）
                                  │
                         ModelManager / GPU 推理
                        ┌─────────┴─────────┐
                    PyTorch YOLO-World   ONNX Runtime
                                  │
             SQLite 历史记录 <───┴───> 任务助手 / AI 短报告（可选）
```

详细设计见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、[docs/backend.md](docs/backend.md) 和 [docs/frontend.md](docs/frontend.md)。云端平台文档是后续设计方案，并不表示全部已落地。

## 仓库内容与大文件策略

这不是“只含代码的空壳”仓库。前端实际使用的页面视频、性能评测图表、源图片，以及 `demo1/` 中的 4 个检测输入样例均已纳入版本管理。

| 内容 | 位置 | 状态 |
| --- | --- | --- |
| 首页与评测视频 | `frontend/public/demo/` | 随仓库发布，使用 Git LFS 管理。 |
| 可上传的检测样例 | `demo1/` | 随仓库发布，使用 Git LFS 管理。 |
| 评测 CSV、PR 曲线、Excel 摘要 | `frontend/public/metrics/` | 随仓库发布。 |
| 前端 Logo 与页面图片 | `frontend/src/assets/` | 随仓库发布。 |
| 运行时数据库与历史输出 | `data/` | 本地运行态，不随仓库发布。 |
| 模型权重 | `weights/` | 不随仓库发布；文件大、部分为训练产物。见 [weights/README.md](weights/README.md)。 |
| 重复素材与构建产物 | `demo/`、`frontend/public/demo.zip`、`frontend/dist/` | 不发布。它们是已发布资源的重复副本或可重新构建产物。 |

首次克隆必须安装 Git LFS 并拉取资源，否则视频文件会是 LFS 指针：

```bash
git clone https://github.com/LiPume/skyline_detection_system.git
cd skyline_detection_system
git lfs pull
```

若只需要源码而不需要视频，可使用 `GIT_LFS_SKIP_SMUDGE=1 git clone ...`；之后按需执行 `git lfs pull`。

## 快速启动

### 1. 环境要求

- Python 3.10 或更高版本
- Node.js 18 或更高版本
- Git LFS（获取仓库内演示视频所必需）
- NVIDIA GPU 与 CUDA 环境（建议；模型注册默认使用 `cuda:0`）
- Linux、macOS、Windows/WSL2 均可用于开发；GPU 推理环境应与 PyTorch、ONNX Runtime 匹配

### 2. 配置后端

```bash
pip install -r requirements.txt
cp backend/.env.example backend/.env
```

`AGENT_API_KEY` 仅用于“任务助手”和“AI 短报告”。不填该项时，视频检测、模型查询和历史记录仍然可以使用；需要 LLM 功能时再填写自己的服务密钥。不要提交 `backend/.env`。

### 3. 准备权重

将权重按下列路径放入 `weights/`：

```text
weights/
├── yolov8m-worldv2.pt
├── VisDrone/yolov8x_visdrone_best.onnx
└── person_only/best_person.onnx
```

权重来源和恢复说明见 [weights/README.md](weights/README.md)。其中 YOLO-World 可遵循 Ultralytics 的官方获取方式；两个项目训练模型需要从原项目归档取得。后端的模型路径定义在 `backend/models/registry.py`。

### 4. 启动服务

开两个终端，在仓库根目录分别执行：

```bash
bash start_backend.sh
```

```bash
bash start_frontend.sh
```

第一次启动前端会自动使用已有依赖；若 `frontend/node_modules` 不存在，请先执行：

```bash
cd frontend
npm install
npm run dev
```

默认地址：

| 服务 | 地址 |
| --- | --- |
| 前端 | `http://localhost:5173` |
| 后端健康检查 | `http://localhost:8000/health` |
| 接口文档 | `http://localhost:8000/docs` |

后端健康检查期望返回：

```json
{"status":"ok","service":"skyline-backend","version":"1.0.0"}
```

> 局域网演示时，前端会依据浏览器当前主机名拼接后端地址。请确保 5173 和 8000 端口可访问；也可用 `VITE_BACKEND_PORT`、`VITE_WS_URL` 覆盖前端配置。

## 演示流程

1. 打开首页，确认预置展示视频可以播放。
2. 进入“智能检测舱”，上传 [demo1/README.md](demo1/README.md) 中任一视频，或开启摄像头。
3. 选择模型：开放类别任务使用 `YOLO-World-V2`；道路航拍多类任务使用 `YOLOv8-VisDrone`；人员任务使用 `YOLOv8-Person`。
4. 对 YOLO-World 输入英文类别词，例如 `person, car, bus`；闭集模型使用界面中的可选类别。
5. 启动检测，观察画面、边界框与推理耗时；完成后保存历史记录，可下载 JSON/视频并在详情页查看统计。
6. 如已配置 `AGENT_API_KEY`，可先用任务助手生成推荐配置，或在完成态生成 AI 短报告。

## 模型与适用范围

| 模型 ID | 展示名 | 类型 | 类别/适用场景 |
| --- | --- | --- | --- |
| `YOLO-World-V2` | YOLO-Worldv2 | 开放词汇，PyTorch | 可输入任意英文类别，适用于临时目标定义。 |
| `YOLOv8-VisDrone` | SKY-Monitor | 闭集，ONNX | `pedestrian`、`people`、`bicycle`、`car`、`van`、`truck`、`tricycle`、`awning-tricycle`、`bus`、`motor`。 |
| `YOLOv8-Person` | SKY-Person | 闭集，ONNX | `person`，适用于可见光人员检测。 |

模型能力由 `GET /api/models` 提供，前端和后端分别通过 `MODEL_REGISTRY` 与 `RUNTIME_CONFIG` 维护能力描述和运行时配置，避免将推理实现细节暴露给界面。

## 接口概览

| 接口 | 用途 |
| --- | --- |
| `GET /health` | 服务健康检查。 |
| `GET /api/models` | 模型列表与可用能力。 |
| `GET /api/models/{model_id}/capabilities` | 指定模型能力。 |
| `WS /api/ws/video_stream` | 浏览器视频帧上行与推理结果下行。 |
| `POST /api/history` / `GET /api/history` | 检测历史记录创建与列表。 |
| `GET /api/history/{id}` / `DELETE /api/history/{id}` | 历史详情与删除。 |
| `GET /api/history/{id}/video` / `data` | 下载归档视频或 JSON。 |
| `POST /api/agent/parse-task` | 自然语言任务解析（可选 LLM）。 |
| `POST /api/agent/generate-report` | 生成检测短报告（可选 LLM）。 |

WebSocket 上行发送 JPEG Base64 帧、模型 ID 与类别配置；下行返回检测框、分类结果以及 `inference_time_ms`、`session_ms`、`preprocess_ms`、`postprocess_ms`。边界框格式为 `[x_min, y_min, width, height]`，单位为视频原始分辨率像素。

## 核心实现

- **LIFO 单帧覆盖缓冲**：推理线程始终取最新画面，旧帧直接丢弃，防止 GPU 较慢时积压出“回看式”监控画面。
- **事件循环保护**：阻塞式 GPU 推理通过线程池执行，WebSocket I/O 不被模型 forward 阻塞。
- **多客户端保护**：锁住类别设置与推理调用，避免多终端共享模型时相互覆盖配置。
- **统一耗时协议**：PyTorch 与 ONNX 路径向前端暴露一致的 timing 字段，便于可视化与横向比较。
- **按需 AI 调用**：任务推荐不会自动启动推理，报告也由用户手动触发，避免意外外部调用。

## 项目结构

```text
skyline_detection_system/
├── backend/                 # FastAPI、推理调度、模型管理、路由与 Agent 服务
├── frontend/                # Vue 3 + TypeScript + Vite 用户界面
│   ├── public/demo/         # 已发布的页面演示视频（Git LFS）
│   └── public/metrics/      # 评测图表、CSV 与 Excel 摘要
├── demo1/                   # 可上传的检测输入样例（Git LFS）
├── docs/                    # 架构、前端、后端、需求和开发过程文档
├── weights/README.md        # 模型权重恢复说明
├── requirements.txt         # Python 依赖
├── start_backend.sh         # 后端启动脚本
├── start_frontend.sh        # 前端启动脚本
└── STARTUP.md               # 补充启动说明
```

## 复现与归档边界

- 本仓库保留演示系统所需的源码、前端运行素材和评测展示素材；不保留 Python/Node 依赖目录、构建产物、SQLite 运行数据和重复压缩包。
- 数据库中的历史记录、用户上传视频及检测输出是运行时数据，默认位于 `data/`，若需要长期留存应单独导出。
- 模型权重、数据集与视频素材可能有各自的来源和许可，使用、再分发或公开展示前请确认相应授权和隐私合规性。
- 性能页部分内容由 mock 数据和已归档评测文件驱动，适合答辩展示；若用于严谨实验，请替换为可追溯的真实实验记录。
- TensorRT 是预留扩展方向，当前封板代码未实现 `TRTDetector`。

## 开发与验证

前端可用以下命令构建：

```bash
cd frontend
npm run build
```

项目没有单独的自动化测试套件；封板验证建议至少完成以下检查：后端 `/health` 返回正常、`/api/models` 可列出三个模型、前端构建成功、预置视频可播放，以及在已放置权重的环境中成功完成一次检测任务。

## 许可证与致谢

本项目仅供学术研究、比赛展示与个人学习使用。仓库未单独授予第三方商业使用授权；各模型、数据和依赖仍受其原始许可证约束。

- [Ultralytics YOLO-World](https://docs.ultralytics.com/models/yolo-world/)
- [Ultralytics YOLOv8](https://docs.ultralytics.com/models/yolov8/)
- [Vue.js](https://vuejs.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [ONNX Runtime](https://onnxruntime.ai/)
