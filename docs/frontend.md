# 前端页面样式描述（Skyline）

> 依据当前 `skyline/frontend/src` 的 `Vue/TypeScript` + `Tailwind CSS` 实现整理
> 代码版本对应 2026-04-09，Phase 5+ 后端已完整提供 timing 字段，前端性能面板均为真实数据

---

## 1) 全局基础样式
- 使用 Tailwind 作为原子样式体系：`frontend/src/style.css` 以 `@import "tailwindcss"` 引入基础样式，并对 `*` 做 `box-sizing: border-box` 重置。
- 页面基底为深色石板配色：
  - `html, body`：`overflow: hidden`（避免整体滚动），背景 `#020817`（接近 `slate-950`），文字默认 `#e2e8f0`（`slate-200`）。
- 全局容器 `#app` 占满宽高：`width/height: 100%`，为三栏布局与画布铺满提供稳定的尺寸基准。

---

## 2) 统一布局外观（`MainLayout.vue`）
- 整体为"左侧导航 + 顶部标题栏 + 页面主体"结构：
  - 外层：`flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-200`
  - 左侧：`aside` 固定宽度 `w-56`，背景 `bg-slate-950`，边框 `border-r border-slate-800`
  - 顶部：`header` 高度 `h-16`，半透明 `bg-slate-900/80`，并开启 `backdrop-blur`，底部分隔 `border-b border-slate-800`
- 导航条（Sidebar Nav）：
  - LOGO 区：高度 `h-16`，包含 logo 图片（带 fallback gradient）和"SKYLINE" / "AI VISION"文字
  - 路由链接（RouterLink）：
    - 激活态：`bg-blue-600/20 text-blue-400 border border-blue-600/30`
    - 非激活态：`text-slate-400 hover:bg-slate-800 hover:text-slate-200`
    - 每个链接包含 emoji 图标、中文标题、英文副标题
  - Footer：`v1.0.0 · SKYLINE IVAP`，使用 `text-xs text-slate-600`。
- 顶部状态指示：
  - WS/GPU 指示块均为"圆点 + 文本"，容器样式统一：
    - `px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700`
  - 通过"颜色 + 脉冲"表达状态：
    - WS：`connected` 用 `emerald-400` + "ONLINE"，`connecting` 用 `yellow` + "SYNCING" 并 `animate-pulse`，`disconnected` 用 `red` + "OFFLINE"。
    - GPU：`isGpuActive` 为真时圆点使用 `blue-400` 并 `animate-pulse`，显示 "ACTIVE"，否则为 `slate-600` + "IDLE"。

---

## 3) 首页仪表盘（`/`，`Dashboard.vue`）
### 3.1 页面结构
- 整体可滚动：`h-full overflow-y-auto`，配合固定网格背景
- 网格背景：`fixed inset-0 pointer-events-none z-0`，使用 CSS linear-gradient 创建 48px 间隔的网格线 `rgba(30,41,59,0.3)`
- 内容区：`relative z-10 px-6 py-6 space-y-8 max-w-screen-2xl mx-auto`

### 3.2 Hero 区域
- 顶部装饰线：`flex items-center gap-3`，包含渐变线与脉冲圆点
- 双栏布局：`grid grid-cols-[1fr_1.15fr] gap-6 items-stretch`
- 左侧：版本徽章 + 大标题 + 描述 + 能力标签
  - 版本徽章：`inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/25 text-blue-400 text-xs font-mono`
  - 主标题：使用渐变文字 `bg-gradient-to-r from-blue-400 via-cyan-400 to-blue-400`
  - 能力标签：hover 时显示 `hover:border-cyan-500/50 hover:text-cyan-400`
- 右侧：主视频展示区
  - 四角 HUD 装饰线：`border-l-2 border-t-2 border-cyan-500/40 rounded-tl-lg`
  - 视频区域：`rounded-2xl border border-slate-700/80 bg-slate-900/60`，最小高度 280px
  - 底部状态标签：`bg-red-500/90 text-white`，包含脉冲圆点 + "LIVE DEMO"
  - 视频错误时显示占位图与重试按钮

### 3.3 核心能力区（Core Capabilities）
- 三栏卡片：`grid grid-cols-3 gap-4`
- 卡片样式：`rounded-xl border border-slate-800 bg-slate-900/50 p-5 hover:border-blue-500/40`
- hover 效果：`hover:-translate-y-0.5` 配合 `transition-all duration-200`
- 标签样式：`px-2 py-0.5 rounded text-xs font-mono bg-blue-500/10 border border-blue-500/20 text-blue-400/80`

### 3.4 应用场景区（Application Scenarios）
- 2x2 视频网格：`grid grid-cols-2 gap-4`
- 每个场景卡片：`rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden`
- 视频容器：固定高度 220px，包含四角 HUD 装饰
- hover 效果：`hover:border-blue-500/50 hover:-translate-y-0.5`
- 视频标签：`absolute top-2 right-2 z-10`，样式 `bg-slate-800/85 border border-slate-600/50 text-slate-300 backdrop-blur-sm`
- 底部信息：标题 + 副标题，左侧渐变遮罩 `bg-gradient-to-t from-slate-950/80 via-transparent to-transparent`

### 3.5 功能入口区（Modules）
- 三栏入口卡片：使用 `RouterLink` 组件
- 卡片样式：`rounded-xl border border-slate-800 bg-slate-900/50 p-5`
- hover 效果：
  - `hover:border-emerald-500/50 hover:bg-slate-900/70`
  - `hover:shadow-[0_0_20px_rgba(16,185,129,0.08)]`
  - `hover:-translate-y-0.5`
- 右侧箭头：`group-hover:text-emerald-400 group-hover:translate-x-1`
- 底部进度条：hover 时渐变显示 `group-hover:bg-gradient-to-r group-hover:from-emerald-500/80`

---

## 4) 智能检测舱（`/detection`，`Detection.vue`）
### 4.1 结构与色彩层级
- 整体画布区 + 右侧控制台的左右分栏布局：
  - 根容器：`relative flex h-full bg-slate-950 overflow-hidden`
  - 左侧"视觉舞台"（`flex-1`）：画布与叠层浮层都在同一 `bg-slate-950` 区域
  - 右侧"AI 控制台"（`aside`）：宽度固定 `w-80 flex-shrink-0`，背景 `bg-slate-900`，分隔线 `border-l border-slate-800`

### 4.2 状态机与浮层体系
- 分析状态机（**6 状态**）：`standby | ready | loading_model | analyzing | paused | finished`
- `standby`：画布无视频源，显示 standby 背景动画
- `ready`：视频已加载但未开始分析（视频首帧显示在画布）
- `loading_model`：首次冷加载模型中（点击"启动实时分析"后短暂状态，直到收到后端 `model_ready` 才切换到 `analyzing`）
- `analyzing`：实时分析中（画布显示 REC 指示灯）
- `paused`：分析已暂停，显示暂停统计模态框
- `finished`：本地视频播放完毕或手动停止，显示最终结果与保存状态
- 状态 Pill（左上角）：
  - standby：`text-slate-500 bg-slate-500/10 border-slate-600/40`，标签 "STANDBY"
  - ready：`text-emerald-400 bg-emerald-500/10 border-emerald-500/40`，标签 "ARMED"
  - loading_model：`text-amber-400 bg-amber-500/10 border-amber-500/40`，标签 "WARMING UP"
  - analyzing：`text-blue-400 bg-blue-500/10 border-blue-500/40`（增加 `animate-pulse` 圆点），标签 "ANALYZING"
  - paused：`text-amber-400 bg-amber-500/10 border-amber-500/40`，标签 "PAUSED"
  - finished：`text-cyan-400 bg-cyan-500/10 border-cyan-500/40`，标签 "COMPLETE"
- READY/FINISHED/PAUSED/LOADING_MODEL 浮层（画布底部左侧）：
  - READY：`bg-slate-950/85 border-emerald-500/30 backdrop-blur`，圆点 `animate-pulse`
  - LOADING_MODEL：居中大浮层（画布覆盖），含模型加载提示文字
  - PAUSED：`bg-slate-950/85 border-amber-500/30 backdrop-blur`
  - FINISHED：`bg-slate-950/85 border-cyan-500/30 backdrop-blur`，显示保存状态（saving/saved/error）
- WebSocket 重连提示：`bg-amber-950/85 border-amber-700/60`，带 `animate-pulse` 小圆点
- 检测结果计数角标（右上角，分析中且有检测时）：`bg-slate-950/85 border border-blue-500/40`，`text-blue-400 text-xs font-mono`
- Toast 通知栈（顶部居中）：
  - 容器：`absolute top-4 left-1/2 -translate-x-1/2 z-50`，并设置 `min-width/max-width`
  - Toast 样式：`rounded-xl border text-sm backdrop-blur shadow-xl`
  - error：`bg-red-950/90 border-red-700/70 text-red-300`
  - warn：`bg-amber-950/90 border-amber-700/70 text-amber-300`
  - success：`bg-emerald-950/90 border-emerald-700/70 text-emerald-300`
  - 动画：`TransitionGroup` 实现进入/离开动画

### 4.2.1 模型冷加载提示（Phase 5+）

画布居中显示淡入浮层（`model-hint` transition）：

- 首次点击"启动实时分析"后进入 `loading_model` 状态，显示"首次加载模型中…"
- 若 1 秒后仍处于加载状态，文字变为"模型预热中，首次加载可能需要几秒"
- 收到后端 `StatusMessage(phase="model_ready")` 后，文字变为"模型已就绪"，0.9 秒后自动消失
- 若期间前端切到其他页面，提示保持不消失（由后端控制模型状态）

### 4.2.2 模型就绪后的状态切换逻辑

```
startAnalysis() → 状态 = loading_model → 提示"首次加载模型中…"
收到 model_ready → 状态 = analyzing → 提示"模型已就绪" → 900ms 后隐藏
```

### 4.3 左侧视觉舞台（Canvas + 拖拽区）
- Canvas：
  - 画布在容器内铺满：`<canvas class="w-full h-full block">`
  - 外部套层保持深色底：`<div class="flex-1 relative bg-slate-950">`
- 拖拽上传 Drop Zone（仅在本地未加载且未锁定时显示）：
  - 覆盖层：`absolute inset-0 flex items-center justify-center cursor-pointer`
  - hover/拖拽态：拖拽时容器追加 `bg-blue-950/50`，图标卡片边框从 `border-slate-600 bg-slate-900/60 text-slate-500` 切到
    - `border-blue-400 bg-blue-500/15 text-blue-400` 并带 `scale-105`
  - Drop Zone 内部文字：
    - 主提示：`text-slate-200 text-base font-medium`
    - 辅助：`text-slate-500 text-sm mt-1`

### 4.4 右侧 AI 控制台（表单/按钮/指标）
- 控制台标题区：
  - `px-5 py-4 border-b border-slate-800`
  - 标题：`text-sm font-semibold text-white tracking-wide`
  - 说明：`text-xs text-slate-500 mt-0.5`
- 内容区使用纵向间距：`flex-1 overflow-y-auto px-5 py-4 space-y-5`
- 视频来源选择：
  - 本地文件/实时摄像 两个按钮
  - 选中态：`bg-blue-600/20 border-blue-500/50 text-blue-400`
  - 未选中：`bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600`
  - 已加载视频指示：`bg-emerald-500/8 border border-emerald-500/20 text-emerald-400`
- 模型信息横幅（根据模型类型变化）：
  - 开放词汇模型：`bg-blue-500/10 border-blue-500/30`，标签 "开放词汇"
  - 固定类别模型：`bg-amber-500/10 border-amber-500/30`，标签 "固定类别"
- 表单输入与卡片元素：
  - `select`/`textarea` 默认底色 `bg-slate-800`，边框 `border-slate-700`，圆角 `rounded-lg`
  - 聚焦态：`focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30`
  - 禁用态：`disabled:opacity-40 disabled:cursor-not-allowed`
- 开放词汇模型配置：
  - 快捷类别芯片：`px-2.5 py-1 rounded-full border text-xs`
  - 选中：`border-blue-500/50 bg-blue-500/10 text-blue-400`
  - Prompt 输入框：`textarea` + `font-mono`，显示解析后的类别 chip
- 固定类别模型配置：
  - 提示横幅：`bg-amber-500/5 border border-amber-500/20 text-amber-400`
  - 类别网格：`grid grid-cols-2 gap-1`，支持全选/清空
  - 选中态：`bg-blue-500/20 border border-blue-500/40 text-blue-400`
- CTA 按钮（底部主要操作区）：
  - "启动实时分析" / "重新启动分析"：可执行时为渐变高亮 `bg-gradient-to-r from-blue-600 to-blue-500` + `shadow-lg`
  - 不可执行/禁用：`bg-slate-800 border border-slate-700 text-slate-500 cursor-not-allowed`
  - "暂停分析"：危险语义 `bg-amber-600/20 border border-amber-600/40 text-amber-400`
  - "继续播放"：`bg-emerald-600/20 border border-emerald-600/40 text-emerald-400`
  - "停止分析"：危险语义 `bg-red-950/60 border border-red-700/60 text-red-400`
- 性能监控卡片：
  - 延迟卡片：`bg-slate-800/60 rounded-lg p-3 border border-slate-700/50`
  - 进度条表达节流状态：`h-1.5 bg-slate-700 overflow-hidden`
  - 推理耗时与吞吐量：`grid grid-cols-2 gap-2`
- 网络控制：
  - 两个并排按钮：`flex gap-2`，每个 `flex-1 py-2 rounded-lg border text-xs font-medium`
  - hover 的强调色分别落在红/蓝语义上，并由 `disabled:opacity-35` 控制禁用反馈

### 4.5 右侧 AI 控制台（表单/按钮/指标）

控制台标题区：
- `px-5 py-4 border-b border-slate-800`
- 标题：`text-sm font-semibold text-white tracking-wide`
- 说明：`text-xs text-slate-500 mt-0.5`

内容区使用纵向间距：`flex-1 overflow-y-auto px-5 py-4 space-y-5`

视频来源选择：
- 本地文件/实时摄像 两个按钮
- 选中态：`bg-blue-600/20 border-blue-500/50 text-blue-400`
- 未选中：`bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600`
- 已加载视频指示：`bg-emerald-500/8 border border-emerald-500/20 text-emerald-400`（显示"视频已就绪"，带"更换"/"重置"按钮）

模型信息横幅（根据模型类型变化）：
- 开放词汇模型：`bg-blue-500/10 border-blue-500/30`，标签 "开放词汇"
- 固定类别模型：`bg-amber-500/10 border-amber-500/30`，标签 "固定类别"

表单输入与卡片元素：
- `select`/`textarea` 默认底色 `bg-slate-800`，边框 `border-slate-700`，圆角 `rounded-lg`
- 聚焦态：`focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30`
- 禁用态：`disabled:opacity-40 disabled:cursor-not-allowed`

开放词汇模型配置：
- 快捷类别芯片：`px-2.5 py-1 rounded-full border text-xs`
- 选中：`border-blue-500/50 bg-blue-500/10 text-blue-400`
- Prompt 输入框：`textarea` + `font-mono`，显示解析后的类别 chip

固定类别模型配置：
- 提示横幅：`bg-amber-500/5 border border-amber-500/20 text-amber-400`
- 类别网格：`grid grid-cols-2 gap-1`，支持全选/清空
- 选中态：`bg-blue-500/20 border border-blue-500/40 text-blue-400`

CTA 按钮（底部主要操作区）：
- "启动实时分析" / "重新启动分析"：可执行时为渐变高亮 `bg-gradient-to-r from-blue-600 to-blue-500` + `shadow-lg`
- 不可执行/禁用：`bg-slate-800 border border-slate-700 text-slate-500 cursor-not-allowed`
- "暂停分析"：危险语义 `bg-amber-600/20 border border-amber-600/40 text-amber-400`
- "继续播放"：`bg-emerald-600/20 border border-emerald-600/40 text-emerald-400`
- "停止分析"：危险语义 `bg-red-950/60 border border-red-700/60 text-red-400`
- "暂停"和"继续播放"并排显示（grid col-span-2）

性能监控卡片：
- 延迟卡片：`bg-slate-800/60 rounded-lg p-3 border border-slate-700/50`，带进度条颜色指示（绿色 ≤ LATENCY_THROTTLE_THRESHOLD_MS，否则红色）
- 推理耗时与吞吐量：`grid grid-cols-4 gap-2`

网络控制：
- 两个并排按钮：`flex gap-2`，每个 `flex-1 py-2 rounded-lg border text-xs font-medium`
- hover 的强调色分别落在红/蓝语义上，并由 `disabled:opacity-35` 控制禁用反馈

### 4.6 暂停对话框（Modal）
- 使用 `<Teleport to="body">` 渲染
- 遮罩：`bg-black/80 backdrop-blur-sm`
- 内容：`max-w-md mx-4 bg-slate-900 rounded-2xl border border-slate-700`
- 统计数据卡片：`grid grid-cols-3 gap-4 text-center`
  - 检测次数：`text-blue-400`
  - 目标类别：`text-emerald-400`
  - 当前帧目标：`text-amber-400`
- 操作按钮：继续播放（绿色渐变）、保存到历史记录库（蓝色边框）
- 键盘提示：`text-slate-600 text-xs`，`<kbd>` 标签样式

### 4.7 任务助手（TaskAssistantPanel，Phase 1 Agent）

#### 4.7.1 位置与定位
- 位于右侧 AI 控制台**最顶部**，在视频来源选择之上
- 组件路径：`components/detection/TaskAssistantPanel.vue`
- 定位：自然语言任务输入 → AI 解析 → 推荐结果展示

#### 4.7.2 交互流程（三阶段）
1. **输入阶段**：用户输入自然语言任务描述，按"理解任务"按钮（或 `Ctrl+Enter`）
2. **加载阶段**：显示阶段性 loading 提示，3 个阶段轮换（1200ms 切换一次）：
   - "正在理解你的任务"
   - "正在匹配可用模型与类别"
   - "正在生成推荐方案"
   - 超过 8 秒后额外提示"智能解析较慢，你也可以稍后直接手动配置"
3. **结果展示阶段**：推荐结果展示（模型、确信度、类别、原因、报告建议）

#### 4.7.3 推荐结果展示内容
| 字段 | 说明 |
|------|------|
| 推荐模型 | `recommended_model_id`，以高亮文本展示 |
| 确信度 | `high`（绿色）/ `medium`（黄色）/ `low`（灰色）三种状态 |
| 推荐类别 | 蓝色 chip 展示，支持多个 |
| 报告建议 | 若 `report_required=true`，显示"建议生成检测报告"徽章 |
| 推荐原因 | 带背景色的原因说明文本 |
| 应用按钮 | "**应用到当前配置**"按钮，点击后触发 `apply-recommendation` 事件 |

#### 4.7.4 边界与限制
- 任务助手**不修改现有表单状态**，仅展示推荐结果
- 推荐结果需用户主动点击"应用到当前配置"才会写入当前配置
- 解析失败时显示错误提示，用户可继续手动配置
- 调用后端 `POST /api/agent/parse-task` 接口，依赖 Agent API Key 配置

### 4.8 推荐结果应用到当前配置

#### 4.8.1 handleApplyRecommendation 回调逻辑
当用户点击"应用到当前配置"按钮时，`Detection.vue` 中的 `handleApplyRecommendation` 执行以下操作：

**第一步：切换模型**
- 调用 `selectModel(rec.recommended_model_id, postLoadAction)`
- 在 `postLoadAction` 回调中根据模型类型写入类别配置

**第二步：开放词汇模型（open_vocab）**
- 直接将 `promptInput` 覆盖为 `rec.target_classes.join(', ')`

**第三步：闭集模型（closed_set）**
- 清空现有选中状态
- 按推荐类别覆盖（仅保留模型支持的类别）
- 调用 `selectedClasses.value = new Set(matched)`

**重要：不会自动启动检测**
- 应用推荐配置后，用户需手动点击"启动实时分析"
- 任务助手仅负责配置建议，不涉及检测启动

### 4.9 完成态摘要层（Detection Summary）

#### 4.9.1 触发条件
- 仅在 `analysisState === 'finished'` 时有值
- 由 `detectionSummary` computed 属性驱动

#### 4.9.2 数据来源
全部来自 `Detection.vue` 已有状态，不新建独立数据源：

| 字段 | 来源 |
|------|------|
| `modelId` | `selectedModelId` |
| `modelLabel` | `currentCapabilities?.display_name` |
| `targetClasses` | `targetClasses`（开放词汇）或 `selectedClasses`（闭集） |
| `totalDetectionEvents` | `totalDetections` |
| `detectedClassCount` | `sorted classCounts.length` |
| `classCounts` | 按次数降序排列的类别统计 |
| `maxFrameDetections` | `maxFrameDetections` |
| `durationSec` | `analysisDuration`（有值时） |
| `summaryText` | 本地规则生成的结论文本 |

#### 4.9.3 UI 展示位置
- 画布左下角 FINISHED 浮层中
- 在状态横幅（保存状态）下方
- 包含：主数据行（检测次数/类别数/最大帧数）、类别分布条、本地结论

#### 4.9.4 本地结论规则（summaryText）
| 条件 | 结论文本 |
|------|---------|
| `totalEvents === 0` | "未检测到任何目标" |
| `classNum === 1` | "仅检测到 {class}，共 {count} 次" |
| `classNum > 1` | "检测到 {n} 类目标，{top} 最多（{count} 次）" |

### 4.10 AI 短报告（手动触发）

#### 4.10.1 触发方式
- **手动触发**，非自动触发
- 用户在完成态摘要层中点击"**生成 AI 短报告**"按钮
- 触发 `triggerGenerateReport()` 函数

#### 4.10.2 报告状态机（reportState）
| 状态 | 触发条件 | UI 行为 |
|------|---------|---------|
| `idle` | 初始状态 | 显示"生成 AI 短报告"按钮 |
| `generating` | 点击按钮后 | 显示 loading 动画 + "正在生成 AI 报告…" |
| `done` | 报告生成成功 | 展示报告文本区域 |
| `error` | 报告生成失败 | 显示错误 toast，保留重试按钮 |

#### 4.10.3 生成后流程
1. 后端返回 `reportText`
2. `reportText.value` 写入本地状态
3. **若存在历史记录 ID**（`currentHistoryId !== null`），自动调用 `patchHistoryExtraData` 补写：
   - `short_report: resp.reportText`
   - `detection_summary: detectionSummary.value`（同步写入）
4. 补写失败不影响页面展示（warn 日志）

#### 4.10.4 AI 短报告展示位置
- 画布左下角 FINISHED 浮层底部
- 在本地结论文本下方
- 使用蓝色主题样式：`bg-blue-500/5 border-blue-500/20`

### 4.11 autoSave 与历史记录写入

#### 4.11.1 保存时机
- 视频播放完毕（`video.ended` 事件）
- 用户手动停止分析（`stopAnalysis()`）
- 用户从暂停对话框保存（`saveAndFinish()`）

#### 4.11.2 保存数据口径
| 字段 | 说明 |
|------|------|
| `video_name` | 从文件或摄像头提取 |
| `duration` | `analysisDuration`（秒） |
| `detection_model` | `buildModelConfig()` 当前配置 |
| `class_counts` | 当前 `classCounts` 对象 |
| `total_detections` | 累计检测次数 |
| `extra_data` | `detection_summary`（有值时写入） |

> **注意**：`short_report` 在保存时**不会**立即写入 `extra_data`，而是在 AI 报告生成成功后通过 `patchHistoryExtraData` 补写。这是为了避免用户未生成报告时 `extra_data` 中存在空字段。

---

## 5) 历史记录库（`/history`，`History.vue`）
### 5.1 页面容器
- 根容器：`h-full bg-slate-950 flex flex-col overflow-hidden`
- 顶部标题区：
  - `px-8 py-6 flex-shrink-0 border-b border-slate-800`
  - 主标题：`text-lg font-semibold text-white`
  - 子标题：`text-sm text-slate-500 mt-0.5`
  - 右侧刷新按钮：`px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-400`
- 错误横幅：`mx-8 mt-4 px-4 py-3 rounded-lg bg-red-950/70 border border-red-700/60 text-red-300`

### 5.2 表格与行样式
- 加载骨架屏：`v-if="isLoading"` 时显示 5 个脉冲占位 `animate-pulse`
- 表格外层卡片：
  - `rounded-xl border border-slate-800 overflow-hidden bg-slate-900/50`
  - Header：`grid` 布局，并带 `bg-slate-900` + `border-b border-slate-800`
  - 列宽：`grid-cols-[56px_1fr_120px_180px_100px_100px_180px]`
  - 表头文字：`text-xs font-medium text-slate-500 tracking-wider uppercase`
- 每行使用 `grid` 对齐列宽，并通过 hover 提升可读性：
  - `hover:bg-slate-800/40`
  - 行分隔：除最后一行外使用 `border-b border-slate-800/60`
- 单元格内部细节：
  - 序号占位格：`w-10 h-8 rounded-md bg-slate-800 border border-slate-700 text-slate-600 text-xs font-mono`
  - 类别标签（chips）颜色来自 `classColorMap`
  - 状态标签（status pill）：
    - completed：`bg-emerald-500/10 border border-emerald-500/25 text-emerald-400`
    - failed：`bg-red-500/10 border border-red-500/25 text-red-400`
- 操作按钮组：
  - 查看数据：`bg-slate-800 border border-slate-700`，hover `border-blue-600 text-blue-400`
  - 下载 JSON：`bg-slate-800`，hover `border-purple-600 text-purple-400`
  - 下载视频：`bg-slate-800`，hover `border-emerald-600 text-emerald-400`
  - 在线播放：`bg-slate-800`，hover `border-cyan-600 text-cyan-400`
  - 删除：`bg-slate-800`，hover `border-red-600 text-red-400`

### 5.3 空态
- 当 `records.length === 0 && !errorMsg` 时，使用居中空态：
  - `flex flex-col items-center justify-center py-20 text-slate-600`
  - 搭配图标与 `text-sm` 文本提示 `暂无历史记录`
  - 辅助提示：`text-xs text-slate-700 mt-1`

### 5.4 视频预览弹窗
- 使用 `<Teleport to="body">` + `Transition name="modal"`
- 遮罩：`bg-black/80 backdrop-blur-sm`
- 内容：`max-w-4xl mx-4 bg-slate-900 rounded-2xl border border-slate-700`
- 视频播放器：`aspect-video bg-black`，controls + autoplay
- 模态框动画：进入/离开 `transition: all 0.25s ease`

---

## 6) 历史详情页（`/history/:id`，`HistoryDetail.vue`）
### 6.1 页面头部
- 返回按钮：`p-2 rounded-lg bg-slate-800 border border-slate-700`
- 操作按钮：下载 JSON（紫色）、下载视频（绿色）

### 6.2 概览卡片
- 四栏网格：`grid grid-cols-4 gap-4`
- 每个卡片：`bg-slate-900 rounded-xl border border-slate-800 p-5`
  - 图标：`p-2 rounded-lg bg-{color}-500/15`
  - 标签：`text-xs text-slate-500 uppercase tracking-wider`
- 视频信息卡：蓝色图标，显示文件名和时长
- 模型信息卡：紫色图标，显示模型名称和类型
- 总检测数卡：绿色图标，显示总检测数（大字体）
- 分析时间卡：橙色图标，显示创建时间

### 6.3 检测类别统计
- 横向条形图：`flex items-center gap-4`
- 类别标签：`px-3 py-1 rounded-lg border text-sm font-mono min-w-[100px]`
- 进度条：`flex-1 h-8 bg-slate-800 rounded-lg overflow-hidden`
- 数量显示：`text-white font-mono font-bold`

### 6.4 AI 智能总结展示（extra_data 驱动的 AI 报告）
- **触发条件**：`record.metadata` 中存在 `short_report` 字段且非空
- 展示位置：在派生指标卡片行之后，本次任务结论摘要之前
- 样式：`bg-gradient-to-br from-slate-900 to-slate-900/80 rounded-xl border border-blue-500/25 p-5`
- 内容：由 `extraData?.short_report` 驱动，展示 AI 生成的中文分析报告
- 若历史记录在生成 AI 报告前保存，则该区域不展示（`hasShortReport === false`）
- `detection_summary` 字段同样从 `extra_data` 中读取，用于数据完整性校验

### 6.5 JSON 数据预览
- 代码块：`bg-slate-950 rounded-lg p-4 font-mono text-xs overflow-x-auto max-h-80`
- 下载按钮：`bg-slate-800 border border-slate-700`，hover `border-purple-600 text-purple-400`

### 6.5 数据结构说明
- 双栏网格：`grid grid-cols-2 gap-4`
- 每个字段卡片：`bg-slate-800/50 rounded-lg p-3`
- 字段名：使用对应语义色（`text-blue-400`、`text-emerald-400` 等），`font-mono`
- 说明：`text-slate-500 text-xs mt-1`

---

## 7) 模型评估页（`/performance`，`Performance.vue`）
### 7.1 页面容器与布局
- 根容器：`h-full bg-slate-950 flex flex-col overflow-hidden`
- 顶部标题区：`px-8 py-5 flex-shrink-0 border-b border-slate-800`
  - 主标题 `text-base font-semibold text-white`，子标题 `text-xs text-slate-500`
  - 右侧按钮：导出报告（outline）、查看测试报告（蓝色填充）
- Tab 导航：`px-8 pt-4 pb-0`
  - 容器：`flex gap-1 bg-slate-900/60 p-1 rounded-xl w-fit border border-slate-800`
  - 四个 Tab：总览、训练过程、标准评测、类别分析

### 7.2 总览 Tab（Overview）
- 顶部指标卡网格：`grid grid-cols-6 gap-4`
  - mAP@0.5：`text-3xl text-blue-400`，进度条 `bg-blue-500`
  - mAP@0.5:0.95：条件颜色（≥0.5 绿色，否则黄色）
  - Precision/Recall：条件颜色（≥0.75 绿色，否则黄色）
  - FPS：`text-cyan-400`，说明 "实时处理"
  - 推理耗时：`text-amber-400`，说明 "单帧平均"
- 两列布局（模型配置 + 训练摘要）：
  - 卡片：`rounded-xl border border-slate-800 bg-slate-900/50 p-5`
  - 左侧色条：4px 圆角 `w-1 h-4 rounded-full`
  - 双栏配置列表：`grid grid-cols-2 gap-x-6 gap-y-3`
- 评测摘要卡片：
  - 四栏数据：`grid grid-cols-4 gap-4`
  - 状态标签：`bg-emerald-500/15 border border-emerald-500/25 text-emerald-400`
- 类别 AP 排名：
  - 横向条形图 + 排名数字
  - 颜色条件：≥75% 绿色，≥50% 黄色，<50% 红色

### 7.3 训练过程 Tab（Train）
- 说明区 + 图例：`flex items-center justify-between`
- 损失收敛曲线卡片：
  - SVG 图表：支持平滑曲线（`buildSmoothPath`）和面积填充（`buildAreaPath`）
  - 网格线：`stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"`
  - 训练曲线：蓝色 `#3b82f6`，验证曲线：琥珀色 `#f59e0b` + 虚线
  - 图例行：`grid grid-cols-6 gap-3`
- 精度演进曲线：
  - 多指标：`Precision`(蓝) / `Recall`(青) / `mAP@0.5`(绿) / `mAP@0.5:0.95`(蓝绿虚线)
  - 最佳轮次标记：垂直虚线 + `★ E{epoch}` 标签
- 学习率曲线 + 最佳轮次摘要：
  - 三栏布局（lr曲线占2列，摘要卡占1列）
  - LR 曲线：`pg0`(青) / `pg1`(蓝) / `pg2`(靛蓝)
  - 摘要卡：显示最佳轮次各项指标

### 7.4 标准评测 Tab（Eval）
- PR 曲线展示区：
  - `rounded-xl border border-slate-800 bg-slate-900/50`
  - 图片展示：`max-w-2xl rounded-lg overflow-hidden`，支持 `@error` 处理
  - 失败占位：显示 "PR 曲线预留区" + 重试按钮
- AP 详细数据表格：
  - 表头：`px-5 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider`
  - 单元格：带颜色编码的 AP 值
  - 达标状态：≥75% 显示 "达标"（绿色），否则 "待优化"（黄色）
- 整体评测结论：
  - 四栏指标卡 + 评测场景描述
  - 结论文本：`p-4 rounded-lg bg-slate-800/30 border border-slate-700/50`

### 7.5 类别分析 Tab（Class）
- 类别 AP@0.5 排行：
  - 排名样式：🥇 金色 / 🥈 银色 / 🥉 铜色 / 普通灰色
  - 条形图 + 数值
  - AP@0.5:0.95 分隔区域（半透明）
- 类别样本统计：
  - 五栏网格：`grid grid-cols-5 gap-4`
  - 样本量比例条：`h-1 bg-slate-700 rounded-full`
- 类别表现分析卡：
  - 条件边框/背景：`emerald/yellow/red` 根据 AP 值
  - 类别徽章：首字母缩写 + 背景色
  - P/R/AP 三栏数据
  - 备注文本：对应语义色边框/背景

### 7.6 当前状态（数据层）

**所有数据均为硬编码内联 mock 数据**，无任何真实 API 调用：

- 训练历史：`trainHistory` ref 包含 25 条 epoch 关键节点数据（1/2/3/.../300），来自 `yolo_car_results.csv` 解析结果
- 评测数据：`summaryMetrics`、`evaluationResult`、`classMetrics` 均为 Vue ref 内的硬编码值
- PR 曲线：使用静态图片 `/metrics/pr_curve.png`，带 `@error` fallback 占位符
- 无训练数据存储管道，无评测结果回填机制，无真实 API 连接

---

## 8) 组件/原型说明
### SkylineDashboard.vue
- 项目中仍包含一个 `SkylineDashboard.vue`，其样式使用 `scoped` 的"霓虹荧光（neon）+ Courier 字体风格"而非当前页面的 Tailwind 风格。
- 当前路由页面主要由 `Dashboard.vue`、`Detection.vue`、`History.vue`、`HistoryDetail.vue`、`Performance.vue` 构成；该文件可视为历史原型/备用实现，因此其样式体系与本页文档的 Tailwind 规范相互独立。

### MainLayout.vue
- 当前应用的主布局组件，包含侧边栏导航、顶部状态栏和内容区域
- 使用 Vue Router 的 `<RouterView />` 渲染子路由页面

### 状态管理（`store/systemStatus.ts`）
- `wsStatus`：WebSocket 连接状态（`connected` | `connecting` | `disconnected`）
- `isGpuActive`：GPU 是否处于活跃状态
- 状态在 Detection.vue 中被监听并同步更新

### API 层（`api/history.ts`）
- `listHistory()`：获取历史记录列表
- `getHistory(id)`：获取单条历史记录详情
- `deleteHistory(id)`：删除历史记录
- `saveDetection()`：保存检测结果
- `getVideoUrl(id)`：获取视频下载 URL
- `getDataUrl(id)`：获取 JSON 数据 URL

---

## 9) 性能指标体系（Phase 5+）

### 9.1 前端性能指标展示总览

前端右侧性能区分为三类：

| 层级 | 分类 | 展示性质 | 示例 |
|------|------|----------|------|
| 第1层 | 主展示指标 | 正式展示，比赛/答辩必须保留 | 后端处理耗时、纯推理耗时、后端处理 FPS、纯推理 FPS |
| 第2层 | 工程 / 实时指标 | 正式展示，系统实时展示建议保留 | 发送节奏、结果返回节奏、算法全流程耗时/ FPS |
| 第3层 | 链路诊断指标 | 调试辅助，开发/排查阶段保留 | 前端编码耗时、前端消息处理、链路额外开销、Pending 诊断 |

### 9.2 前端当前使用的统一字段协议

#### WebSocket 接收字段（后端 → 前端）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `inference_time_ms` | `number` | 后端单帧总处理耗时（_blocking_inference 整体） |
| `session_ms` | `number\|null` | 纯模型 forward 耗时（ONNX: session.run / PT: Results.speed["inference"]） |
| `preprocess_ms` | `number\|null` | 预处理耗时（ONNX: decode_ms + _preprocess / PT: decode_ms + Results.speed["preprocess"]） |
| `postprocess_ms` | `number\|null` | 后处理耗时（ONNX: _postprocess / PT: Results.speed["postprocess"]） |
| `model_id` | `string` | 本次推理使用的模型 ID（Phase 5+ 冷加载状态通知用） |

> **Phase 5+ 变化**：后端已完整实现所有 timing 字段（inference_time_ms / session_ms / preprocess_ms / postprocess_ms / model_id），前端不再显示 "--" 占位，所有指标均为真实数据。

#### 前端派生字段

| 字段名 | 类型 | 计算公式 | 说明 |
|--------|------|----------|------|
| `backendProcessMs` | `ref<number\|null>` | `= inference_time_ms` | 后端处理耗时（直接赋值） |
| `sessionMs` | `ref<number\|null>` | `= session_ms` | 纯推理耗时（直接赋值） |
| `preprocessMs` | `ref<number\|null>` | `= preprocess_ms` | 预处理耗时（直接赋值） |
| `postprocessMs` | `ref<number\|null>` | `= postprocess_ms` | 后处理耗时（直接赋值） |
| `algoProcessMs` | `computed<number\|null>` | `preprocessMs + sessionMs + postprocessMs` | 算法全流程耗时（三段之和，三个值均非 null 时计算） |
| `fpsBackend` | `computed<number\|null>` | `1000 / backendProcessMs` | 后端处理 FPS |
| `fpsInfer` | `computed<number\|null>` | `1000 / sessionMs` | 纯推理 FPS |
| `fpsAlgo` | `computed<number\|null>` | `1000 / algoProcessMs` | 算法全流程 FPS |
| `frontendSendIntervalMs` | `ref<number\|null>` | 相邻两次 send 间隔 | 发送节奏 |
| `fpsSend` | `computed<number\|null>` | `1000 / frontendSendIntervalMs` | 发送节奏 FPS |
| `resultIntervalMs` | `ref<number\|null>` | 相邻两次 inference_result 到达间隔 | 结果返回节奏 |
| `fpsResult` | `computed<number\|null>` | `1000 / resultIntervalMs` | 结果返回 FPS |
| `endToEndLatencyMs` | `ref<number\|null>` | `(Date.now() / 1000 - timestamp) * 1000` | 端到端延迟 |
| `frontendEncodeMs` | `ref<number\|null>` | CanvasEncoder 回调传入 | 前端编码耗时（useVideoStream.ts onEncode 回调） |
| `frontendRenderMs` | `ref<number\|null>` | `performance.now() - resultNow` | 前端消息处理耗时 |
| `pipelineExtraMs` | `computed<number\|null>` | `endToEndLatencyMs - backendProcessMs` | 链路额外开销 |

> `fpsBackend`、`fpsInfer`、`fpsAlgo`、`fpsSend`、`fpsResult` 计算中，当分母为 0 或 null 时返回 null。

### 9.3 前端展示指标定义

#### 正式指标：必须长期保留

以下指标直接支撑比赛、工程、实时三类指标体系，**禁止删除或隐藏**：

##### 比赛硬指标（Phase 5 核心）

| 指标名称 | 来源 | 计算公式 | 用途 |
|----------|------|----------|------|
| **纯推理耗时** | `session_ms` | `sessionMs` | 比赛硬指标口径 |
| **纯推理 FPS** | `session_ms` | `1000 / sessionMs` | 比赛硬指标口径 |
| **算法全流程耗时** | 三段之和 | `preprocessMs + sessionMs + postprocessMs` | 比赛参考口径 |
| **算法全流程 FPS** | 三段之和 | `1000 / (preprocessMs + sessionMs + postprocessMs)` | 比赛参考口径 |

##### 工程与系统指标

| 指标名称 | 来源 | 计算公式 | 用途 |
|----------|------|----------|------|
| **后端处理耗时** | `inference_time_ms` | `backendProcessMs` | 后端整帧处理能力 |
| **后端处理 FPS** | `inference_time_ms` | `1000 / inference_time_ms` | 后端吞吐量 |
| **端到端延迟** | websocket timestamp | `(Date.now() / 1000 - timestamp) * 1000` | 系统实时性 |
| **发送节奏** | 前端测速 | 相邻两次 send 间隔 | 前端发送稳定性 |
| **发送节奏 FPS** | 前端测速 | `1000 / frontendSendIntervalMs` | 前端发送速率 |
| **结果返回节奏** | 前端测速 | 相邻两次 inference_result 到达间隔 | 后端响应稳定性 |
| **结果返回 FPS** | 前端测速 | `1000 / resultIntervalMs` | 后端响应速率 |

#### 调试指标：后续可隐藏/删除

以下指标属于调试辅助，**建议在正式展示时隐藏或降级**：

| 指标名称 | 来源 | 定位 | 建议处理 |
|----------|------|------|----------|
| **前端编码耗时** (`frontendEncodeMs`) | useVideoStream onEncode 回调 | 前端 canvas → base64 JPEG 编码耗时 | 开发阶段保留，正式页面可折叠或隐藏 |
| **前端消息处理** (`frontendRenderMs`) | `performance.now()` 差值 | 前端收到 ws 消息到写入 state 的耗时 | 开发阶段保留，正式页面可折叠或隐藏 |
| **链路额外开销** (`pipelineExtraMs`) | `endToEndLatencyMs - backendProcessMs` | 端到端 - 后端耗时 | **严禁对外表述为"纯网络延迟"**。包含队列等待、网络传输、前端处理等 |
| **Pending 诊断** | useVideoStream 内部状态 | pending / pendingFrameId / pendingAgeMs | 临时调试区展示，限 3 秒刷新 |

### 9.4 文案口径警告

以下混淆**必须避免**：

| 混淆 | 正确口径 |
|------|----------|
| `inference_time_ms` = 纯推理耗时 | `inference_time_ms` = 后端总耗时，`session_ms` = 纯推理耗时 |
| `backendProcessMs` = `sessionMs` | `backendProcessMs` 来源于 `inference_time_ms`，`sessionMs` 来源于 `session_ms` |
| `fpsBackend` = `fpsInfer` | `fpsBackend = 1000 / inference_time_ms`，`fpsInfer = 1000 / session_ms` |
| `endToEndLatencyMs` = 取帧到渲染完成 | `endToEndLatencyMs = t(收到结果) - t(发送帧)`，不含前端渲染 |
| `frontendRenderMs` = 浏览器真实渲染耗时 | 仅是 ws 消息到 state 写入的差值，不含 DOM 渲染 |
| `pipelineExtraMs` = 纯网络延迟 | 包含队列等待 + 网络传输 + 前端处理，不能简化为"网络延迟" |

---

## 10) useWebSocket.ts 当前真实行为

### 10.1 连接与重连

- **connect()**：新建 WebSocket，若已有 OPEN 或 CONNECTING socket 则直接返回（防止重复连接）
- **指数退避重连**：首次延迟 1000ms，之后每次翻倍，上限 30000ms（WS_MAX_RECONNECT_DELAY_MS）
- **连接超时**：3 秒内 onopen 未触发，自动关闭并重连（单次，不走指数退避）
- **manualDisconnect**（disconnect()）：设置 `manualDisconnect=true`，不再自动重连
- **visibility 重连**：页面变为 visible 时，若 socket 不健康（断开或异常），立即强制重连（`isRecovering` 防止并发）

### 10.2 心跳机制

- 心跳间隔 15s（`HEARTBEAT_INTERVAL_MS`），每轮发送 `__heartbeat_ping__`
- 发送后启动 20s 超时计时器（`HEARTBEAT_TIMEOUT_MS`），若超时未收到 pong 则关闭 socket
- 收到 `__heartbeat_pong__` 或 `__heartbeat_ping__` 均刷新 `lastPongTime`

### 10.3 waitForConnected()

返回 Promise，若已连接则立即 resolve；若未连接则注册一次性的 `pendingConnectedResolve`，onopen 时调用 resolve。Detection.vue 的 visibility 恢复逻辑依赖此方法。

### 10.4 sendFailCount

send() 失败时（socket 未 OPEN）递增，供诊断使用。

### 10.5 onUnmounted

组件销毁时移除 visibilitychange 监听并调用 disconnect()。

---

## 11) useVideoStream.ts 当前真实行为

### 11.1 背压机制（单帧 in-flight）

- `pending`：当前是否有帧正在等待 inference_result（最多 1 帧）
- `pendingFrameId`：正在等待的那帧 frame_id（用于 ACK 对齐，防止乱序释放）
- 发送帧后立即置 `pending=true`，收到匹配的 inference_result 后 `ackFrame(frame_id)` 释放
- **超时兜底**：1.8s 未收到 ACK，`onPendingTimeout()` 强制释放 pending（防止后端异常导致永久卡死）
- **降级 ACK**：若 pending 已超时且收到 frame_id 更大的结果帧，强制清理 pending 一次，防止长视频跑久后因一帧之差永久卡死

### 11.2 自适应 FPS 限流

- `HIGH_LATENCY_THRESHOLD = 150ms`：端到端延迟超过此值进入节流模式
- `LOW_LATENCY_RECOVERY = 100ms` + `RECOVERY_THRESHOLD = 3`：连续 3 帧低于此值，退出节流模式
- 节流模式：发送频率从 `VIDEO_TARGET_FPS`（默认 20）降至 `VIDEO_THROTTLED_FPS`（默认 5）

### 11.3 限频日志

每 3 秒最多打印同类日志一次（`LOG_INTERVAL_MS = 3000`），防止刷屏。

### 11.4 来源管理

| 方法 | 行为 |
|------|------|
| `loadFile(file)` | 创建 Blob URL，video.loop=false（需要 ended 事件触发 finished），触发 hasVideo=true |
| `selectWebcam()` | getUserMedia，await video.play()，立即 startPush()（无 ready 状态，直接 analyzing） |
| `resetVideo()` | 停止推流、清理 pending、释放摄像头/Blob URL，重置 hasVideo=false |
| `stopPush()` | 清理推流定时器，清除 pending，isPlaying=false |
| `startPush()` | 重置连续高延迟计数，从 tick() 开始循环（tick 内调度自身） |

### 11.5 诊断导出

`pending`、`pendingFrameId`、`pendingAgeMs` 均以 `computed` ref 形式导出，供 Detection.vue 调试面板展示。

---

## 12) useCanvasRenderer.ts 当前真实行为

### 12.1 三态渲染

| hasVideo | isPlaying | 渲染内容 |
|----------|-----------|----------|
| false | — | Standby 屏幕（网格 + 扫描线动画 + 脉冲文字 + 角括号装饰） |
| true | false | 视频当前帧（无 BBox，READY 或 FINISHED 状态） |
| true | true | 视频当前帧 + BBox 叠加层 + 检测摘要浮层 + REC 指示灯 |

### 12.2 BBox 绘制

- 按 `class_name` 查 `CLASS_COLORS` 调色板，���匹配用 `DEFAULT_DETECTION_COLOR = #00ff88`
- 半透明填充 + 边框（2px）+ 角 tick 线 + 标签 chip（深色背景，白色文字）
- 标签 chip 自适应位置（bbox 顶部放不下则移到 bbox 内部下方）

### 12.3 检测摘要浮层

左下角半透明面板，显示 `CLASS: COUNT` 统计（BBox 绘制前触发）。

---

## 13) 当前 API 层

### 13.1 api/history.ts

| 方法 | 端点 | 说明 |
|------|------|------|
| `saveDetection(payload)` | POST `/api/history` | 保存检测记录（包含 extra_data） |
| `listHistory({page, limit, status})` | GET `/api/history` | 分页查询历史记录 |
| `getHistory(id)` | GET `/api/history/{id}` | 获取单条记录详情 |
| `deleteHistory(id)` | DELETE `/api/history/{id}` | 删除记录 |
| `getVideoUrl(id)` | GET `/api/history/{id}/video` | 获取视频下载 URL（`FileResponse`） |
| `getDataUrl(id)` | GET `/api/history/{id}/data` | 获取 JSON 下载 URL（`StreamingResponse`） |
| `patchHistoryExtraData(id, extraData)` | PATCH `/api/history/{id}/extra-data` | **合并写入** extra_data 字段（用于 AI 报告补写） |

> **`patchHistoryExtraData` 语义**：顶层 key merge（`Object.assign` 行为），请求中传入的字段直接覆盖已有值。用于 AI 短报告生成成功后，将 `short_report` 和 `detection_summary` 补写入历史记录的 `extra_data` 字段。

### 13.2 api/agent.ts

| 方法 | 端点 | 说明 |
|------|------|------|
| `parseTask(userText)` | POST `/api/agent/parse-task` | 自然语言任务解析，返回结构化推荐 |
| `generateReport(payload)` | POST `/api/agent/generate-report` | 基于检测摘要生成 AI 短报告 |

#### parseTask 请求/响应
```
请求：{ user_text: string }
响应：{
  intent: string,
  recommended_model_id: string,
  target_classes: string[],
  report_required: boolean,
  reason: string,
  confidence: "high" | "medium" | "low"
}
```

#### generateReport 请求/响应
```
请求：{
  modelId, modelLabel, targetClasses, totalDetectionEvents,
  detectedClassCount, classCounts, maxFrameDetections,
  durationSec, summaryText, taskPrompt?
}
响应：{ reportText: string }
```

### 13.3 types/skyline.ts

关键类型：VideoFrame、InferenceResult（含完整 timing 字段 + model_id）、Detection、ErrorMessage、ModelStatusMessage、ServerMessage、ModelConfig、ModelCapabilities、HistoryRecord（与 api/history.ts 共用）。

---

## 14) 当前状态管理

### 14.1 store/systemStatus.ts

模块级 reactive refs（无需 Pinia/Vuex）：

| 变量 | 类型 | 写入方 | 读取方 |
|------|------|--------|--------|
| `wsStatus` | `'connected' \| 'connecting' \| 'disconnected'` | useWebSocket | MainLayout 头部指示灯 |
| `isGpuActive` | `boolean` | Detection.vue（`watch(isAnalyzing, v => isGpuActive.value = v)`） | MainLayout 头部指示灯 |

### 14.2 Detection.vue 的 onMounted 健康检查

页面加载时若 ws 未连接，调用 connect() 建立连接，确保 header 指示灯及时更新到 ONLINE。首次加载模型时提示"首次加载模型中…"（Phase 5+）。

### 14.3 History.vue 与 HistoryDetail.vue 的数据口径

- **"检测事件次数"**：逐帧检测框累计次数，不代表视频中出现的独立目标数量
- **检测事件频率** = `total_detections / duration`
- **类别覆盖** = 实际检测到类别数 / 配置类别数
