# Skyline 修改日志

---

## 2026-03-20（下午）

### 历史记录库增强功能 & 实时视频暂停功能

#### 后端 `backend/routers/history.py`

- **新增视频下载接口** `GET /api/history/{record_id}/video`：
  - 根据 record_id 查找数据库中的 video_path 字段
  - 返回原始视频文件的 FileResponse（支持浏览器直接播放或下载）
  - 支持绝对路径和相对路径，自动处理路径解析
  - 文件不存在时返回 404 错误

- **新增 JSON 数据导出接口** `GET /api/history/{record_id}/data`：
  - 导出结构化 JSON 数据，包含：record_id、created_at、video_info、model_info、statistics、metadata
  - 使用 StreamingResponse 流式返回，设置正确的 Content-Disposition 头实现文件下载
  - 文件名格式：`detection_{record_id}_{video_name}.json`

#### 前端 `frontend/src/api/history.ts`

- **新增 `getVideoUrl(id)`**：生成视频下载 URL
- **新增 `getDataUrl(id)`**：生成 JSON 数据下载 URL

#### 前端 `frontend/src/views/History.vue`（历史记录库）

- **新增视频预览功能**：
  - 点击"播放"按钮打开全屏模态框
  - 模态框内嵌 `<video>` 播放器，支持 controls 控件（播放、暂停、进度条等）
  - 底部显示检测统计信息和下载视频按钮
  - 点击遮罩层或右上角关闭按钮关闭预览

- **新增"数据"按钮**：
  - 点击跳转到 `/history/:id` 详情页面，展示完整的检测数据分析

- **新增"JSON"下载按钮**：
  - 点击直接下载该记录的 JSON 数据文件

- **新增"视频"下载按钮**（仅当 video_path 存在时显示）：
  - 点击直接下载原始视频文件

- **操作按钮布局调整**：
  - 从单列"删除"按钮扩展为：数据、JSON、视频、播放、删除（最多5个按钮）
  - 使用不同颜色区分功能：蓝色=数据、紫色=JSON、绿色=视频、青色=播放、红色=删除

#### 新增 `frontend/src/views/HistoryDetail.vue`（数据详情页）

- **页面路由**：`/history/:id`
- **概览卡片**：4 个信息卡片展示视频信息、模型、分析时间、总检测数
- **检测类别柱状图**：按检测次数排序的条形图，每种类别用不同颜色区分
- **JSON 数据预览**：实时预览导出的 JSON 结构，底部有下载按钮
- **数据结构说明**：解释 JSON 中每个字段的含义
- **返回按钮**：左上角返回历史记录列表

#### 前端 `frontend/src/router/index.ts`

- 新增 `HistoryDetail` 组件导入
- 新增路由 `{ path: '/history/:id', component: HistoryDetail, name: 'history-detail' }`

#### 前端 `frontend/src/views/Detection.vue`（检测页面）

- **新增分析状态 `paused`**：
  - 状态机新增 `paused` 状态
  - 新增 `isPaused` 计算属性
  - `isLocked` 现在包含 analyzing 和 paused 两种状态

- **新增暂停/继续功能**：
  - 分析中按空格键（Space）暂停
  - 暂停后显示模态对话框，显示当前检测统计
  - 对话框提供三个选项：继续播放、保存到历史记录库、关闭（按空格继续）
  - 点击"继续播放"或按空格键恢复分析

- **新增暂停按钮**：
  - 分析中显示"暂停"按钮（蓝色），点击暂停分析
  - 暂停时显示"继续播放"按钮（绿色）和"停止分析"按钮（红色）

- **新增暂停状态显示**：
  - 左下角状态栏显示"ANALYSIS PAUSED · 按空格继续"

- **键盘事件处理**：
  - 监听全局 `keydown` 事件
  - 分析中按空格暂停
  - 暂停状态按空格继续播放
  - `onUnmounted` 时移除事件监听防止内存泄漏

- **暂停对话框**：
  - 显示当前检测统计：总检测次数、目标类别数、当前帧目标数
  - 深色毛玻璃背景，模态框居中显示
  - 支持点击遮罩关闭并继续播放

---

## 2026-03-20

## 2026-03-20

### 历史记录库持久化 & 检测仓保存机制

#### 新增 `backend/core/database.py`

- 新增 SQLite 异步数据库配置，使用 aiosqlite + SQLAlchemy 2.0
- 数据库文件位于 `data/skyline.db`，启动时自动创建表结构
- 导出 `get_db`（FastAPI 依赖注入）、`init_db`（启动时初始化）、`async_session`（会话工厂）

#### 新增 `backend/models/history.py`

- 定义 `DetectionRecord` 数据模型，对应数据库 `detection_records` 表
- 字段：id、created_at、duration、video_name、video_path、model_name、class_counts、total_detections、status、thumbnail_path、extra_data
- `extra_data` 存储额外 JSON 元数据（因 `metadata` 是 SQLAlchemy 保留字段而重命名）

#### 新增 `backend/routers/history.py`

- REST API 路由：`POST /api/history`（保存记录）、`GET /api/history`（列表，支持分页和状态筛选）、`GET /api/history/{id}`（详情）、`DELETE /api/history/{id}`（删除）
- 列表接口按 `created_at` 倒序返回，支持 `page`、`limit`、`status` 查询参数

#### 新增 `frontend/src/api/history.ts`

- 前端 API 客户端，封装 `saveDetection`、`listHistory`、`getHistory`、`deleteHistory` 四个函数
- 统一使用 `API_BASE_URL`（`http://{hostname}:{port}`）拼接请求路径
- 响应非 2xx 时自动解析后端错误信息抛出异常

#### 新增 `src/config/index.ts`

- 新增统一配置文件，集中管理所有魔法数字和环境变量
- 包含：后端端口、WebSocket 配置、视频/摄像头参数、性能阈值、Canvas 渲染参数
- 所有常量均以具名 export 导出，便于维护和修改
- 新增 `API_BASE_URL` 导出：REST API 基础 URL，由 `window.location.hostname` + `VITE_BACKEND_PORT` 动态拼接

### 新增 `.env.example`

- 新增 `.env.example` 文件，记录所有可配置环境变量
- 包括 `VITE_BACKEND_PORT`（后端端口，默认 8000）和 `VITE_WS_URL`（WebSocket 地址，可选）
- `.env.local` 已被 `.gitignore` 忽略，开发者需复制 `.env.example` 使用

### `composables/useWebSocket.ts`

- WebSocket 回退 URL 端口从硬编码 `8000` 改为读取 `VITE_BACKEND_PORT` 环境变量
- 重连最大延迟和基础延迟从硬编码改为从 `@/config` 导入
- 新增 `onSendFailure` 回调选项：帧发送失败（WebSocket 未就绪）时触发
- 新增 `sendFailCount` ref：暴露给调用方统计丢弃帧数

### `composables/useVideoStream.ts`

- `TARGET_FPS`（20）、`THROTTLED_FPS`（10）、`JPEG_QUALITY`（0.7）从硬编码改为从 `@/config` 导入
- 摄像头约束条件从内联对象改为从 `CAMERA_CONSTRAINTS` 导入

### `composables/useCanvasRenderer.ts`

- `FONT_MONO`、`FONT_OVERLAY`、`CORNER_SIZE`、`panelW` 从硬编码改为从 `@/config` 导入

### `router/index.ts`

- `createWebHistory()` 添加 `BASE_URL` 参数，避免部署在子路径时路由失效
- 现在读取 `import.meta.env.BASE_URL`，与 Vite 部署配置对齐

### `views/Detection.vue`

- 移除启动分析按钮中的 emoji 图标（`🚀`），保持整体 SVG 图标风格统一
- `latencyOk` 阈值从硬编码 `200` 改为从 `LATENCY_THROTTLE_THRESHOLD_MS` 导入
- 延迟进度条最大值从硬编码 `300` 改为从 `LATENCY_BAR_MAX_MS` 导入
- 节流提示阈值从硬编码 `200` 改为从 `LATENCY_THROTTLE_THRESHOLD_MS` 导入
- WebSocket 初始化传入 `onSendFailure` 回调：推流中断时显示警告 Toast
- **新增检测统计**：`classCounts` 记录各类别累计检测次数，`totalDetections` 自动汇总，`analysisDuration` 记录本次分析耗时，`videoName` 记录视频文件名
- **新增保存逻辑**：`autoSave()` 在分析结束时（停止或视频播完）自动调用 `POST /api/history` 保存记录到 SQLite
- **新增保存状态 UI**：FINISHED 浮层中实时显示"正在保存…"、"已保存到历史记录库"或"保存失败"状态；Toast 支持 success 类型（绿色）

### `layouts/MainLayout.vue`

- Logo 图片添加 `@error` 兜底处理：图片加载失败时隐藏并显示渐变色文字兜底（`SK`）
- 解决 Logo 文件（`@/assets/logo/skyline_logo.png`）不存在时页面报错的问题

### 删除 `components/HelloWorld.vue`

- 删除 Vite 初始化残留的未使用组件，保持代码库整洁

### `views/History.vue`（历史记录库）

- **完全重写**，移除所有写死的 mock 数据，改为调用 `GET /api/history` API 获取真实数据
- `onMounted` 时自动加载记录列表；新增刷新按钮手动重新拉取
- 新增加载骨架屏（5 行 pulse 动画）和错误提示横幅
- 删除按钮调用 `DELETE /api/history/{id}`，删除成功后前端直接过滤掉该项
- `video_name`、`duration`、`created_at`、`class_counts` 等字段均从 API 实时获取并格式化显示
- 状态筛选徽章、时长格式化、视频名显示均与后端字段对齐

### `requirements.txt`

- 新增 `sqlalchemy>=2.0.0`、`aiosqlite>=0.20.0` 两个数据库依赖

---

## 2026-03-12

- 初始版本提交
