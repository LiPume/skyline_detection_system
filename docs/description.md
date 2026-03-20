# 前端页面样式描述（Skyline）

> 依据当前 `skyline/frontend/src` 的 `Vue/HTML/CSS` 实现整理

---

## 1) 全局基础样式
- 使用 Tailwind 作为原子样式体系：`frontend/src/style.css` 以 `@import "tailwindcss"` 引入基础样式，并对 `*` 做 `box-sizing: border-box` 重置。
- 页面基底为深色石板配色：
  - `html, body`：`overflow: hidden`（避免整体滚动），背景 `#020817`（接近 `slate-950`），文字默认 `#e2e8f0`（`slate-200`）。
- 全局容器 `#app` 占满宽高：`width/height: 100%`，为三栏布局与画布铺满提供稳定的尺寸基准。

---

## 2) 统一布局外观（`MainLayout.vue`）
- 整体为“左侧导航 + 顶部标题栏 + 页面主体”结构：
  - 外层：`flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-200`
  - 左侧：`aside` 固定宽度 `w-56`，背景 `bg-slate-950`，边框 `border-r border-slate-800`
  - 顶部：`header` 高度 `h-16`，半透明 `bg-slate-900/80`，并开启 `backdrop-blur`，底部分隔 `border-b border-slate-800`
- 导航条（Sidebar Nav）：
  - LOGO 区：高度 `h-16`，下边 `border-b border-slate-800`
  - 路由链接：
    - 激活态：`bg-blue-600/20 text-blue-400 border border-blue-600/30`
    - 非激活态：`text-slate-400 hover:bg-slate-800 hover:text-slate-200`
  - Footer：`v1.0.0 · SKYLINE IVAP`，使用 `text-xs text-slate-600`。
- 顶部状态指示：
  - WS/GPU 指示块均为“圆点 + 文本”，容器样式统一：
    - `px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700`
  - 通过“颜色 + 脉冲”表达状态：
    - WS：`connected` 用 `emerald-400`，`connecting` 用 `yellow` 并 `animate-pulse`，`disconnected` 用 `red`。
    - GPU：`isGpuActive` 为真时圆点使用 `blue-400` 并 `animate-pulse`，否则为 `slate-600`。

---

## 3) 智能检测舱（`/detection`，`Detection.vue`）
### 3.1 结构与色彩层级
- 整体画布区 + 右侧控制台的左右分栏布局：
  - 根容器：`relative flex h-full bg-slate-950 overflow-hidden`
  - 左侧“视觉舞台”（`flex-1`）：画布与叠层浮层都在同一 `bg-slate-950` 区域
  - 右侧“AI 控制台”（`aside`）：宽度固定 `w-80 flex-shrink-0`，背景 `bg-slate-900`，分隔线 `border-l border-slate-800`

### 3.2 叠层与动态提示（浮层体系）
- Toast 通知栈（左侧画布上方居中）：
  - 容器：`absolute top-4 left-1/2 -translate-x-1/2 z-50`，并设置 `min-width/max-width` 以限制宽度
  - Toast 样式：`rounded-xl border text-sm backdrop-blur shadow-xl`
  - 错误/警告使用不同语义色：
    - error：`bg-red-950/90 border-red-700/70 text-red-300`
    - warn：`bg-amber-950/90 border-amber-700/70 text-amber-300`
- 状态 Pill（左上角）：
  - 基础外观：`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-mono ...`
  - 根据状态切换不同背景/边框：
    - standby：`text-slate-500 bg-slate-500/10 border-slate-600/40`
    - ready：`text-emerald-400 bg-emerald-500/10 border-emerald-500/40`
    - analyzing：`text-blue-400 bg-blue-500/10 border-blue-500/40`（分析中增加 `animate-pulse` 圆点）
    - finished：`text-cyan-400 bg-cyan-500/10 border-cyan-500/40`
- READY/FINISHED 浮层（画布底部左侧）：
  - READY：`absolute bottom-5 left-5`，使用 `bg-slate-950/85` + `border-emerald-500/30` + `backdrop-blur`
  - FINISHED：`absolute bottom-5 left-5`，使用 `border-cyan-500/30` 并以 `✓` 图标强化完成态
- WebSocket 重连提示（分析尝试时显示）：
  - `v-if="wsStatus !== 'connected' && isAnalyzing"`
  - 背景 `bg-amber-950/85`，边框 `border-amber-700/60`，左上/居中定位并带 `animate-pulse` 小圆点。
- 检测结果计数角标（右上角，仅 analyzing 且有目标时）：
  - `absolute top-4 right-4`，`bg-slate-950/85 border border-blue-500/40`，`text-blue-400 text-xs font-mono`。

### 3.3 左侧视觉舞台（Canvas + 拖拽区）
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

### 3.4 右侧 AI 控制台（表单/按钮/指标）
- 控制台标题区：
  - `px-5 py-4 border-b border-slate-800`
  - 标题：`text-sm font-semibold text-white tracking-wide`
  - 说明：`text-xs text-slate-500 mt-0.5`
- 内容区使用纵向间距：`flex-1 overflow-y-auto px-5 py-4 space-y-5`。
- 表单输入与卡片元素统一风格（整体倾向“深底 + 细边框 + 圆角”）：
  - `select`/`textarea` 默认底色 `bg-slate-800`，边框 `border-slate-700`，圆角 `rounded-lg`
  - 聚焦态：`focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30`
  - 禁用态：`disabled:opacity-40 disabled:cursor-not-allowed`。
- CTA 按钮（底部主要操作区）：
  - “启动分析”：可执行时为渐变高亮 `bg-gradient-to-r from-blue-600 to-blue-500` + `shadow-lg`
  - 不可执行/禁用：`bg-slate-800 border border-slate-700 text-slate-500 cursor-not-allowed`
  - “停止分析”：危险语义 `bg-red-950/60 border border-red-700/60 text-red-400`，hover 时强化边框/底色并允许 `active:scale-[0.98]`
- 性能监控卡片：
  - 延迟卡片：`bg-slate-800/60 rounded-lg p-3 border border-slate-700/50`，并以进度条 `h-1.5 bg-slate-700 overflow-hidden` 表达节流/压力状态。
  - 推理耗时与吞吐量：`grid grid-cols-2 gap-2`，每个指标同样使用深色卡片与强调色（如 `text-blue-400` / `text-emerald-400`）。
- 网络控制：
  - 两个并排按钮：`flex gap-2`，每个 `flex-1 py-2 rounded-lg border text-xs font-medium`
  - hover 的强调色分别落在红/蓝语义上，并由 `disabled:opacity-35` 控制禁用反馈。

---

## 4) 历史记录库（`/history`，`History.vue`）
### 4.1 页面容器
- 根容器：`h-full bg-slate-950 flex flex-col overflow-hidden`。
- 顶部标题区：
  - `px-8 py-6 flex-shrink-0 border-b border-slate-800`
  - 主标题：`text-lg font-semibold text-white`
  - 子标题：`text-sm text-slate-500 mt-0.5`
- 搜索/筛选（当前为占位 UI）：
  - 搜索框样式：`px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-500`
  - 筛选按钮样式：`px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-400 hover:border-slate-600`

### 4.2 表格与行样式
- 表格外层卡片：
  - `rounded-xl border border-slate-800 overflow-hidden bg-slate-900/50`
  - Header：`grid` 布局，并带 `bg-slate-900` + `border-b border-slate-800`
  - 表头文字统一为：`text-xs font-medium text-slate-500 tracking-wider uppercase`
- 每行使用 `grid` 对齐列宽，并通过 hover 提升可读性：
  - `hover:bg-slate-800/40`
  - 行分隔：除最后一行外使用 `border-b border-slate-800/60`
- 单元格内部细节：
  - 序号占位格：`w-10 h-8 rounded-md bg-slate-800 border border-slate-700 text-slate-600 text-xs font-mono`
  - 类别标签（chips）颜色来自 `classColorMap`，统一表现为：深底半透明 + 对应颜色边框/文字（例如 `car` 用 yellow 语义等）。
  - 状态标签（status pill）：
    - 统一为绿色语义：`bg-emerald-500/10 border border-emerald-500/25 text-emerald-400`
    - 含小圆点装饰：`w-1.5 h-1.5 rounded-full bg-emerald-400`
  - 操作按钮：`bg-slate-800 border border-slate-700 text-slate-300 hover:border-blue-600 hover:text-blue-400`

### 4.3 空态
- 当 `records.length === 0` 时，使用居中空态：
  - `flex flex-col items-center justify-center py-20 text-slate-600`
  - 搭配图标与 `text-sm` 文本提示 `暂无历史记录`。

---

## 5) 组件/原型说明（`SkylineDashboard.vue`）
- 项目中仍包含一个 `SkylineDashboard.vue`，其样式使用 `scoped` 的“霓虹荧光（neon）+ Courier 字体风格”而非当前页面的 Tailwind 风格。
- 当前路由页面主要由 `Detection.vue` 与 `History.vue` 构成；该文件可视为历史原型/备用实现，因此其样式体系与本页文档的 Tailwind 规范相互独立。
