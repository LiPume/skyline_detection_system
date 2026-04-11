# 五、云端平台设计

> 本文档为云端平台扩展方案设计说明，不代表当前代码已全部实现。
> 文档以当前项目真实代码现状为基础，区分已实现能力与后续可扩展方向。
> 适用于比赛材料整理与答辩讲解中的方案说明部分。

---

## 5.1 云端平台概述

### 当前系统现状

当前 Skyline 系统已具备本地 / 演示版完整链路：

- **前端**：Vue 3 + TypeScript + Tailwind CSS，单页应用，支持局域网多终端访问
- **后端**：FastAPI + WebSocket，推理调度（LIFO）、模型管理（双注册表）、历史记录存储（SQLite）
- **推理**：PyTorch / ONNX 双 runtime，YOLO-World / YOLOv8 系列模型，开放词汇 + 闭集两条路径
- **AI 能力**：任务助手（自然语言解析）、AI 短报告生成，接入 SiliconFlow API
- **评测**：Performance 页展示标准评测结果、场景分析、典型案例，数据由 mock 驱动

当前系统的限制：
- 模型权重本地存储，无统一模型管理服务
- 视频来源为本地文件或摄像头，无视频上传与云端分析任务
- 历史记录存储在本地 SQLite，无跨设备共享
- Agent 服务依赖本地环境变量配置 API Key

### 云端平台扩展目标

云端平台设计面向以下扩展目标：

- **视频上传与云端分析**：支持用户上传无人机航拍视频，创建云端分析任务，后端异步调度推理
- **任务管理**：分析任务的创建、查询、取消、状态流转（pending / running / completed / failed）
- **结果查看与归档**：云端存储分析结果，支持多设备查看与历史归档
- **模型管理服务化**：将模型管理从本地文件系统迁移至云端模型仓库，支持多版本管理
- **可扩展推理服务**：支持 GPU 集群扩展，支持 TensorRT / OpenVINO 等多种推理 runtime 接入
- **容器化部署**：后端服务容器化，支持横向扩展与高可用部署

### 设计原则

- 延续当前系统的前后端分层架构与 WebSocket 实时推理链路
- 云端扩展不破坏本地演示系统的独立运行能力
- 新增 API 与现有 API 保持风格一致（REST + WebSocket）
- 数据存储从 SQLite 扩展到 MySQL / PostgreSQL + 对象存储

---

## 5.2 产品设计

### 5.2.1 技术栈

#### 当前已有

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + TypeScript + Tailwind CSS | 当前已实现，扩展方向：组件库升级、SSR/SSG |
| 后端框架 | FastAPI + Starlette + Pydantic v2 | 当前已实现，继续沿用 |
| 数据库 | SQLite（本地） | 当前已实现；云端扩展为 MySQL / PostgreSQL |
| 推理引擎 | PyTorch + ONNXRuntime | 当前 PT/ONNX 双路径已实现；云端可扩展 TensorRT |
| 模型管理 | 本地文件 + 双注册表 | 当前已实现；云端扩展为模型仓库服务 |
| AI 能力 | SiliconFlow API（DeepSeek-V3.2） | 当前已实现任务解析与短报告生成，继续沿用 |
| 前端构建 | Vite | 当前已实现 |
| 后端运行 | Uvicorn | 当前已实现 |

#### 后续可扩展

| 层级 | 技术 | 说明 |
|------|------|------|
| 数据库 | MySQL / PostgreSQL | 替代 SQLite，支持多用户并发与数据持久化 |
| 对象存储 | S3 兼容存储（MinIO / OSS / COS） | 存储上传视频、分析结果图片、模型权重 |
| 异步任务队列 | Celery + Redis / RabbitMQ | 调度云端视频分析任务，支持任务取消与重试 |
| 推理服务拆分 | 独立推理微服务 | GPU 推理从主后端拆分，支持横向扩展 |
| 容器化 | Docker + Docker Compose | 后端服务容器化，支持 Kubernetes 部署 |
| CI/CD | GitHub Actions | 自动化构建、测试与部署 |
| 缓存层 | Redis | 会话缓存、模型元数据缓存、速率限制 |
| 日志与监控 | Prometheus + Grafana / ELK | 系统可观测性 |

### 5.2.2 目录结构（云端扩展方向）

以下为云端平台扩展后的目录结构变化说明。**当前代码未变更**，仅列出扩展方向。

```
skyline/                          # 现有根目录（不变）
├── backend/                       # 现有后端（扩展）
│   ├── main.py                   # FastAPI 入口（扩展：新增任务路由、健康检查）
│   ├── core/                      # 核心模块（不变）
│   ├── models/                    # 模型管理（不变）
│   ├── routers/
│   │   ├── video_stream.py       # WebSocket 推理（扩展：支持云端任务关联）
│   │   ├── history.py            # 历史记录（不变）
│   │   ├── agent.py             # Agent 服务（不变）
│   │   └── tasks.py             # [新增] 云端分析任务 CRUD
│   └── services/
│       ├── agent_service.py     # Agent LLM 调用（不变）
│       └── task_scheduler.py    # [新增] 任务调度器（Celery）
│
├── cloud/                        # [新增] 云端平台模块
│   ├── models/                   # 数据库 ORM 模型
│   │   ├── user.py              # 用户模型
│   │   ├── video.py             # 视频文件模型
│   │   └── task.py             # 分析任务模型
│   ├── storage/                  # 对象存储客户端
│   │   └── s3_client.py        # S3 兼容存储抽象
│   ├── inference_client.py      # 推理服务客户端（与主后端通信）
│   └── celery_app.py            # Celery 配置
│
├── frontend/                     # 现有前端（扩展）
│   └── src/
│       ├── views/
│       │   ├── CloudUpload.vue  # [新增] 视频上传页
│       │   ├── TaskList.vue     # [新增] 任务列表页
│       │   └── TaskDetail.vue   # [新增] 任务详情页
│       └── api/
│           └── tasks.ts         # [新增] 任务 API
│
├── docker/                       # [新增] 容器化配置
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── Dockerfile.inference     # 独立推理服务镜像
│   └── docker-compose.yml
│
└── weights/                      # 现有模型权重目录（不变）
```

> 说明：以上目录结构为云端扩展的设计方向。**当前代码中 cloud/ 和 docker/ 目录不存在**，相关模块尚未实现。

### 5.2.3 主要技术细节

#### 前后端分离设计（延续当前架构）

云端平台继续沿用当前前后端分离架构：

- **前端**：SPA 应用，通过 REST API 与后端交互，WebSocket 接收实时推理结果
- **后端**：FastAPI 应用，提供 REST API + WebSocket 推理端点 + 异步任务调度
- **扩展点**：新增文件上传端点、任务管理端点、历史记录云端同步端点

#### WebSocket 实时分析链路（云端扩展）

当前本地 WebSocket 链路：

```
前端 → WebSocket → FastAPI → LIFO 调度器 → 推理引擎（PT/ONNX）→ 前端 Canvas 渲染
```

云端扩展链路：

```
前端 → WebSocket → 云端后端（推理路由）→ 推理微服务 → 推理引擎（PT/ONNX/TRT）→ 推送结果
                     ↓
              异步任务队列（Celery）
                     ↓
              云端存储（结果 JSON / 标注视频）
```

- **实时推理**：保持现有 WebSocket 链路，支持云端实时推理（需低延迟网络）
- **异步推理**：视频上传后创建分析任务，由 Celery worker 异步执行，结果写入对象存储
- **结果推送**：任务完成后通过 WebSocket 通知前端，或通过 Webhook 回调

#### 模型管理与 runtime 扩展

当前实现：

- 模型权重本地存储于 `weights/` 目录
- `MODEL_REGISTRY` 定义前端能力展示（display_name / model_type / supported_classes）
- `RUNTIME_CONFIG` 定义运行时配置（runtime_type / weight_path / device）
- `ModelManager` 通过懒加载 + 缓存提供 detector 实例

云端扩展方向：

- 模型权重上传至对象存储，通过模型版本管理
- 新增模型注册 API（`POST /api/models/upload`），支持团队共享模型
- 推理微服务从模型仓库拉取权重，按需加载
- TensorRT / OpenVINO 作为新增 runtime_type 注册到 RUNTIME_CONFIG，ModelManager 零改动扩展

#### 历史记录与结果归档

当前实现：

- SQLite 数据库存储 `DetectionRecord`，本地文件系统存储视频路径
- `extra_data` JSON 字段承载 `detection_summary` / `short_report` / `model_config`
- History 页面从本地数据库读取

云端扩展方向：

- MySQL / PostgreSQL 替代 SQLite，支持多用户数据隔离
- 视频文件上传至对象存储，`video_path` 改为 `video_url`（对象存储地址）
- 分析结果（检测框 JSON、标注视频）写入对象存储，通过签名 URL 访问
- 历史记录支持跨设备同步

#### AI 任务解析与短报告（延续当前设计）

当前已实现：
- `POST /api/agent/parse-task`：自然语言任务解析为结构化推荐
- `POST /api/agent/generate-report`：基于检测摘要生成 AI 短报告
- SiliconFlow API（DeepSeek-V3.2）调用，本地环境变量配置 API Key

云端扩展：
- Agent 服务保持不变，作为独立微服务或后端内置模块
- 多用户场景下需增加 API Key 隔离（每个用户配置自己的 LLM API Key 或使用统一计费账户）

#### 云端部署后的任务状态流转

```
[用户上传视频]
     ↓
[POST /api/tasks] → 创建任务（status=pending）→ 返回 task_id
     ↓
[Celery worker 抢接任务] → status=running
     ↓
[执行推理] → 写入检测结果到对象存储
     ↓
[任务完成] → status=completed → WebSocket 通知前端
     ↓
[用户查看任务详情] → GET /api/tasks/{id} → 返回结果 URL
```

任务状态：
- `pending`：任务已创建，等待 worker 接收
- `running`：worker 正在执行推理
- `completed`：推理完成，结果已存储
- `failed`：推理失败，错误信息记录

#### 演示系统到云端平台的平滑演进路径

| 阶段 | 能力 | 说明 |
|------|------|------|
| 阶段 0（当前） | 本地演示系统 | 本地视频 + 实时推理，完整链路可运行 |
| 阶段 1 | 文件上传 | 前端新增上传组件，后端新增文件存储（MinIO），历史记录关联云端视频 URL |
| 阶段 2 | 异步任务队列 | Celery + Redis，接入现有推理链路，任务状态 WebSocket 推送 |
| 阶段 3 | 推理服务拆分 | GPU 推理作为独立服务，支持多实例横向扩展 |
| 阶段 4 | 多租户与高可用 | MySQL + Redis 缓存 + Kubernetes 部署 |

演进原则：
- 阶段 1~2 不影响现有本地实时推理链路的稳定运行
- 每个阶段可独立交付，不要求一次性完成全部扩展

---

## 5.3 功能概述

以下功能点按"当前已实现"与"后续云端扩展"分开列出。

### 当前已实现

| 功能 | 说明 |
|------|------|
| 多场景视频展示 | Dashboard 页 demo 视频覆盖白天城区 / 夜间低照度 / 高空密集小目标 / 复杂背景等典型无人机航拍场景 |
| 实时目标检测与模型切换 | Detection 页：视频加载 → 模型选择（开放词汇 / 闭集） → 实时推理 → Canvas 可视化 |
| 自然语言任务助手 | TaskAssistantPanel：用户输入自然语言任务，AI 解析为模型 + 类别推荐，支持一键应用到当前配置 |
| 检测摘要与 AI 短报告 | 完成态自动生成检测摘要；用户手动触发 AI 短报告生成，完成后自动补写入历史记录 extra_data |
| 历史记录归档与详情复盘 | History 列表支持查看 / 下载视频 / 下载 JSON / 在线播放 / 删除；HistoryDetail 展示完整统计与 AI 总结 |
| 模型评估与典型案例分析 | Performance 页：评测总览 + 标准评测结果 + 场景鲁棒性分析 + 典型案例分析 + 轻量训练摘要 |

### 后续云端扩展

| 功能 | 说明 | 关联架构模块 |
|------|------|------------|
| 视频上传与异步分析任务 | 用户上传无人机航拍视频，创建云端分析任务，后端异步调度推理，结果写入对象存储 | CloudUpload.vue、tasks.py、task_scheduler.py |
| 任务状态管理与进度通知 | 任务列表页展示所有任务状态（pending/running/completed/failed），WebSocket 推送任务进度 | TaskList.vue、WebSocket 扩展 |
| 任务详情与结果查看 | 任务详情页展示分析结果（检测统计、标注视频播放、结果 JSON 下载） | TaskDetail.vue、s3_client.py |
| 云端视频存储与访问 | 视频文件上传至 S3 兼容对象存储，通过签名 URL 访问，支持视频在线播放 | video.py、storage/ |
| 多用户数据隔离 | 用户注册 / 登录，任务与历史记录按用户隔离，支持团队协作 | user.py、数据库迁移 |
| 云端模型仓库 | 模型权重上传至对象存储，团队成员共享模型，支持版本管理与模型切换 | models/upload API、model_manager 扩展 |
| TensorRT / OpenVINO runtime | 在 RUNTIME_CONFIG 中注册新 runtime_type，ModelManager 零改动扩展支持新推理后端 | TRTDetector / OpenVINODetector（待实现） |
| 推理服务横向扩展 | GPU 推理从主后端拆分，独立部署，支持多实例负载均衡 | inference 微服务、Dockerfile.inference |
| 容器化部署 | Docker Compose 一键部署前后端 + 推理服务 + Redis + 对象存储（MinIO） | docker/、docker-compose.yml |

### 与当前项目无关的模板内容（明确排除）

以下内容与当前无人机目标检测系统无关，**不会出现在本文档中**：

- 动作评分（健身动作评估）
- 训练建议（健身计划建议）
- ECharts 健身分析图表
- 运动姿态检测
- 体感游戏相关内容
- 其他与航拍目标检测无关的功能

---

## 5.4 扩展优先级建议

| 优先级 | 扩展方向 | 理由 |
|--------|----------|------|
| P0 | 视频上传 + 异步任务 | 解决本地演示系统的核心限制（无法处理大视频、无法异步分析长视频） |
| P1 | 对象存储集成 | 支撑视频上传与结果存储的基础设施 |
| P1 | 任务状态 WebSocket 通知 | 提供用户可见的异步任务进度反馈 |
| P2 | TensorRT runtime | 提升推理速度，满足更高实时性要求 |
| P2 | 多用户数据隔离 | 为团队协作与比赛提交准备 |
| P3 | 推理服务拆分 | 支持 GPU 集群横向扩展，适合大规模部署 |
| P3 | Kubernetes 部署 | 高可用、弹性伸缩，适合生产环境 |

---

## 5.5 风险说明

| 风险 | 说明 | 缓解措施 |
|------|------|----------|
| 云端功能尚未实现 | 当前代码中 cloud/ 和 docker/ 目录不存在，相关模块均为设计方案 | 在比赛材料中明确标注"云端平台为后续扩展方案"，不作为已交付内容 |
| 视频上传大文件处理 | 无人机航拍视频可能较大（GB 级别），Web 上传有带宽限制 | 支持断点续传、分片上传；异步分析任务不要求实时性 |
| GPU 推理服务扩展 | 推理服务横向扩展需要任务队列 + 负载均衡，设计复杂度较高 | 初期可保持推理在主后端，P3 再拆分 |
| 多用户 LLM API 计费 | Agent 服务依赖 SiliconFlow API，多用户场景下需考虑计费控制 | 支持配置每用户 API Key 或统一账户限流 |
| TensorRT 模型转换 | YOLO 模型导出为 TensorRT 格式需要额外工具链（trtexec） | 已有 ONNX 中间格式，TensorRT 转换作为可选优化项 |
