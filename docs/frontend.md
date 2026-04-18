# Skyline 前端实现说明

> 本文档以当前 `skyline/frontend/src` 代码为准，描述真实的页面结构、交互逻辑与数据口径。
> 面向：比赛评委、指导老师、后续维护者

---

## 1. 前端技术栈与目录结构

### 1.1 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 框架 | Vue 3 + TypeScript（严格模式） | Composition API |
| 构建 | Vite + Tailwind CSS v4 | 原子化 CSS，深蓝企业风格 |
| 路由 | Vue Router | SPA 多页面 |
| 视频渲染 | Canvas 2D | BBox 叠加绘制 |
| 通信 | 原生 WebSocket API | 指数退避重连 + 心跳探测 |
| 状态 | 模块级 reactive refs | 无 Pinia/Vuex，轻量共享状态 |

### 1.2 目录职责

```
frontend/src/
├── main.ts                    # 入口
├── App.vue                    # 根组件
├── router/index.ts            # 路由表
├── store/systemStatus.ts      # WS 状态 / GPU 状态共享
├── config/index.ts           # 常量配置（FPS、JPEG质量、阈值）
├── types/skyline.ts         # 共享类型（WebSocket协议、模型能力）
├── api/
│   ├── agent.ts             # Agent 接口：parse-task / generate-report
│   ├── history.ts           # 历史记录接口：列表/详情/保存/补写
│   └── models.ts            # 模型列表与能力接口
├── composables/
│   ├── useWebSocket.ts      # WebSocket 连接、重连、心跳、waitForConnected
│   ├── useVideoStream.ts    # 视频帧捕获、背压推送
│   ├── useCanvasRenderer.ts  # Canvas BBox 渲染
│   ├── useModelConfig.ts     # 模型选择与配置状态
│   ├── useBufferedLocalPlayback.ts
│   └── useDelayedDisplay.ts
├── components/detection/
│   └── TaskAssistantPanel.vue  # 任务助手：自然语言任务解析推荐
├── views/
│   ├── Dashboard.vue        # 首页（demo视频展示）
│   ├── Detection.vue         # 智能检测舱（主功能）
│   ├── History.vue          # 历史记录列表
│   ├── HistoryDetail.vue    # 历史记录详情
│   └── Performance.vue      # 模型评测结果页
└── data/
    ├── performanceReport.mock.ts  # 评测报告 mock 数据
    └── performanceCsvAdapter.ts   # CSV 适配器（训练历史）
```

---

## 2. 页面结构总览

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | Dashboard | 首页 demo 视频展示与功能入口 |
| `/detection` | Detection | 智能检测舱（主功能） |
| `/history` | History | 历史记录列表 |
| `/history/:id` | HistoryDetail | 单次任务详情 + AI 总结 |
| `/performance` | Performance | 模型评测结果与案例分析 |

---

## 3. Detection 页面当前真实链路

### 3.1 分析状态机（6 状态）

```
standby → ready → loading_model → analyzing ↔ paused → finished
         ↑__________________________________|
```

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| `standby` | 初始态，等待加载视频 | 页面加载完成 |
| `ready` | 视频已加载，等待分析 | 文件加载完成（loadeddata 事件） |
| `loading_model` | 首次冷加载模型中 | 点击"启动实时分析"后、后端 model_ready 之前 |
| `analyzing` | 实时分析中 | 收到后端 model_ready 或 inference_result |
| `paused` | 分析已暂停 | 空格暂停或点击暂停按钮 |
| `finished` | 分析结束 | 视频播放完毕 / 手动停止 / 保存 |

### 3.2 模型选择与配置（useModelConfig）

**开放词汇模型（open_vocab）**：
- 模型示例：YOLO-World-V2
- 用户输入：prompt_classes（英文类别词，用逗号分隔）
- 快捷芯片：car/person/drone/truck/motorcycle/boat/backpack
- 支持 prompt_editable=true，可自由编辑类别

**固定类别模型（closed_set）**：
- 模型示例：YOLOv8-Base、YOLOv8-Car、YOLOv8-VisDrone、YOLOv8-Person、YOLOv8-Thermal-Person
- 用户选择：从 supported_classes 中筛选要显示的类别（全选/清空/单选）
- 不支持自定义 prompt

**状态字段**：
- `isOpenVocabModel`：当前模型是否为开放词汇
- `isClosedSetModel`：当前模型是否为固定类别
- `targetClasses`：prompt 输入解析后的类别数组
- `selectedClasses`：Set<string>，选中的闭集类别
- `currentCapabilities`：来自后端 /api/models/:id/capabilities 的完整能力描述

### 3.3 视频来源

| 来源 | 行为 |
|------|------|
| 本地文件 | loadFile() → ready → 用户点击"启动实时分析" → loading_model → analyzing |
| 实时摄像 | selectWebcam() → 立即 startPush() → analyzing（无 ready 状态） |

### 3.4 WebSocket 推理链路

```
前端 send(video_frame) → 后端推理 → 前端 receive(inference_result)
```

**发送帧结构**：
```json
{
  "message_type": "video_frame",
  "frame_id": 0,
  "timestamp": 1710345678.123,
  "image_base64": "data:image/jpeg;base64,...",
  "model_id": "YOLO-World-V2",
  "prompt_classes": ["car", "person"],
  "selected_classes": [],
  "selected_model": "YOLO-World-V2",
  "target_classes": ["car", "person"]
}
```

**接收结果结构**（Phase 5+ 完整 timing）：
```json
{
  "message_type": "inference_result",
  "frame_id": 0,
  "timestamp": 1710345678.123,
  "inference_time_ms": 45.2,
  "session_ms": 38.7,
  "preprocess_ms": 3.2,
  "postprocess_ms": 5.1,
  "model_id": "YOLO-World-V2",
  "detections": [
    { "class_name": "car", "confidence": 0.95, "bbox": [x, y, w, h] }
  ]
}
```

**背压机制（useVideoStream）**：
- 最多 1 帧 in-flight（pending = true）
- 收到 inference_result 后 ackFrame() 释放 pending，才发送下一帧
- 超时 1.8s 强制释放（防止后端异常卡死）
- 降级 ACK：pending 超时后若收到 frame_id 更大的结果，强制清理 pending

**自适应 FPS 限流**：
- 端到端延迟 > 250ms → 节流模式（20fps → 5fps）
- 连续 3 帧延迟 < 180ms → 恢复正常

### 3.5 任务助手（TaskAssistantPanel）

**调用接口**：`POST /api/agent/parse-task`
**请求**：`{ user_text: string }`
**响应**：
```json
{
  "intent": "object_detection",
  "recommended_model_id": "YOLO-World-V2",
  "target_classes": ["car", "person"],
  "report_required": false,
  "reason": "推荐使用开放词汇模型...",
  "confidence": "high"
}
```

**交互流程**：
1. 用户输入自然语言描述（如"帮我检测视频中的汽车和行人"）
2. 点击"理解任务"，加载状态展示 3 个阶段提示
3. 展示推荐结果（模型 / 确信度 / 类别 / 原因）
4. 点击"应用到当前配置"，写入模型和类别选择
5. **不会自动启动检测**，需用户手动点击"启动实时分析"

### 3.6 检测完成态摘要

**触发条件**：`analysisState === 'finished'`

**数据来源**：全部来自 Detection.vue 已有状态

| 字段 | 来源 |
|------|------|
| modelId | selectedModelId |
| modelLabel | currentCapabilities?.display_name |
| targetClasses | targetClasses（开放词汇）或 selectedClasses（闭集） |
| totalDetectionEvents | totalDetections 累计 |
| detectedClassCount | 类别去重数 |
| classCounts | 按次数降序排列 |
| maxFrameDetections | 单帧最大检测数 |
| durationSec | analysisDuration |
| summaryText | 本地规则生成（单类/多类/无检测） |
| sceneEvidence | buildSceneEvidence() 启发式计算 |

**sceneEvidence 约束说明**：
- laneDensityHint 当前全为 0（无逐帧坐标数据）
- 拥堵判断：frameCrowdingHigh（maxDet>=15 && vehicleRatio>=0.7）
- 高速推断：highwayRatio>=0.85 && vehicleRatio>=0.7

### 3.7 AI 短报告（手动触发）

**触发方式**：用户在完成态点击"生成 AI 短报告"按钮

**调用接口**：`POST /api/agent/generate-report`
**请求**：
```json
{
  "modelId": "YOLO-World-V2",
  "modelLabel": "YOLO-World V2",
  "targetClasses": ["car", "person"],
  "totalDetectionEvents": 1234,
  "detectedClassCount": 2,
  "classCounts": [{"className": "car", "count": 800}, {"className": "person", "count": 434}],
  "maxFrameDetections": 45,
  "durationSec": 62.5,
  "summaryText": "检测到 2 类目标，car 最多（800 次）",
  "taskIntent": "交通/车辆场景分析",
  "sceneEvidence": { ... }
}
```
**响应**：`{ "reportText": "本次检测..." }`

**补写流程**（检测完成后）：
1. autoSave() 保存记录（含 detection_summary）
2. 用户点击"生成 AI 短报告"
3. generateReport() 获取 reportText
4. patchHistoryExtraData() 补写 short_report + detection_summary

### 3.8 自动保存（autoSave）

**触发时机**：
- 视频播放完毕（video.ended 事件）
- 手动停止（stopAnalysis）
- 暂停对话框保存（saveAndFinish）

**保存数据**：
```json
{
  "video_name": "xxx.mp4",
  "duration": 62.5,
  "detection_model": { model_id, display_name, model_type, prompt_classes, selected_classes },
  "class_counts": { "car": 800, "person": 434 },
  "total_detections": 1234,
  "extra_data": {
    "detection_summary": { ... }
  }
}
```

**注意**：`short_report` 在保存时**不写入**，在 AI 报告生成成功后通过 patchHistoryExtraData 补写。

---

## 4. History / HistoryDetail 页面

### 4.1 History 页面

**功能**：历史记录列表展示

**API**：
- `GET /api/history?limit=100` → 列表
- `DELETE /api/history/:id` → 删除
- `GET /api/history/:id/video` → 视频下载
- `GET /api/history/:id/data` → JSON 下载

**口径说明**：
- "检测次数" = 逐帧检测事件累计，不是独立目标数
- 同一目标连续多帧被重复检测时，每帧均计入

### 4.2 HistoryDetail 页面

**功能**：单次任务完整数据查看

**展示内容**：
- 视频信息 / 模型信息 / 总检测数 / 分析时间
- 派生指标：主导类别、检测事件频率、类别覆盖
- AI 智能总结（extra_data.short_report）
- 类别统计条形图
- 模型配置详情（model_type / prompt_classes / selected_classes）
- 原始归档数据 JSON

---

## 5. Performance 页面当前定位

### 5.1 数据来源说明

| 模块 | 数据来源 | 说明 |
|------|----------|------|
| 顶部核心指标（mAP/Precision/Recall/FPS） | performanceReport.mock.ts | 来自 system_performance_summary.xlsx |
| 训练历史摘要 | yolo_final_results.csv | 真实训练过程数据 |
| PR 曲线 | PerformancePrCurve.vue + pr_curve_plot_data_VisDrone.csv | 真实 PR 曲线数据 |
| 场景鲁棒性分析 | performanceReport.mock.ts | mock 展示数据 |
| 典型案例 | performanceReport.mock.ts | mock 展示数据 |

**重要说明**：
- 顶部 mAP@0.5 / mAP@0.5:0.95 / Precision / Recall / FPS 来自赛题 Drone-Vehicle 数据集评测结果
- 训练历史曲线（mAP50/precision/recall 演进）来自 yolo_final_results.csv
- 场景分析和案例分析为展示增强，非真实推理数据

### 5.2 页面结构（单页滚动，5 个纵向模块）

1. **评测总览**：顶部指标卡 + 模型配置 + 评测结论
2. **标准评测结果**：PR 曲线 + AP 排名 + 详细数据表
3. **场景鲁棒性分析**：4 类场景（白天城区 / 夜间低照度 / 高空密集小目标 / 复杂背景）
4. **典型案例分析**：3 个案例卡片，点击弹出详情模态框
5. **轻量训练摘要**：精度演进曲线（SVG）+ 最佳轮次标记

---

## 6. 关键 composables 概览

### 6.1 useWebSocket

| 功能 | 说明 |
|------|------|
| connect/disconnect | 连接/断开 |
| send | 发送帧（失败返回 false，递增 sendFailCount） |
| forceReconnect | 强制重连（visibility 恢复时调用） |
| waitForConnected | 等待连接建立（Promise，Detection.vue 恢复逻辑依赖） |
| 心跳 | 15s ping / 20s 超时 |
| 重连 | 指数退避（1s→2s→...→30s 上限） |

### 6.2 useVideoStream

| 功能 | 说明 |
|------|------|
| loadFile | 加载本地文件（不自动播放） |
| selectWebcam | 连接摄像头（立即 startPush） |
| startPush/stopPush | 开始/停止推流 |
| resetVideo | 重置到 standby 态 |
| ackFrame | 背压释放（等待 inference_result 后调用） |

### 6.3 useCanvasRenderer

| 状态 | hasVideo | isPlaying | 渲染内容 |
|------|----------|-----------|----------|
| STANDBY | false | — | 网格背景动画 |
| READY | true | false | 视频首帧（无 BBox） |
| ANALYZING | true | true | 视频帧 + BBox + 检测摘要 |
| FINISHED | true | false | 视频末帧 + 最终 BBox |

### 6.4 useModelConfig

| 导出 | 说明 |
|------|------|
| modelList | /api/models 返回的模型列表 |
| selectedModelId | 当前选中模型 ID |
| currentCapabilities | 当前模型完整能力（/api/models/:id/capabilities） |
| promptInput / targetClasses | 开放词汇 prompt 及解析结果 |
| selectedClasses | Set<string>，闭集选中类别 |
| isOpenVocabModel / isClosedSetModel | 当前模型类型判断 |
| selectModel | 切换模型（异步加载 capabilities） |
| buildModelConfig | 构建保存用的模型配置对象 |

---

## 7. 前后端主要数据交互边界

### 7.1 WebSocket（推理）

| 方向 | 内容 |
|------|------|
| 前端 → 后端 | video_frame（帧数据 + 模型配置） |
| 后端 → 前端 | inference_result（含 timing）+ status（model_loading/model_ready） |

### 7.2 REST API

| 接口 | 方向 | 用途 |
|------|------|------|
| `GET /api/models` | 前端获取 | 模型列表下拉 |
| `GET /api/models/:id/capabilities` | 前端获取 | 模型能力详情 |
| `POST /api/agent/parse-task` | 前端调用 | 任务助手解析 |
| `POST /api/agent/generate-report` | 前端调用 | AI 短报告生成 |
| `POST /api/history` | 前端调用 | 保存检测记录 |
| `GET /api/history` | 前端获取 | 历史记录列表 |
| `GET /api/history/:id` | 前端获取 | 历史记录详情 |
| `DELETE /api/history/:id` | 前端调用 | 删除记录 |
| `PATCH /api/history/:id/extra-data` | 前端调用 | AI 报告补写 |
| `GET /api/history/:id/video` | 前端获取 | 视频下载 |
| `GET /api/history/:id/data` | 前端获取 | JSON 导出 |

---

## 8. 已知实现约束

### 8.1 稳定主链路

- Detection 状态机 + WebSocket 推送 + Canvas 渲染链路：**稳定主链路**
- autoSave + patchHistoryExtraData 补写：**稳定**
- useWebSocket 心跳 + 指数退避重连：**稳定**
- useVideoStream 背压机制：**稳定**

### 8.2 展示增强模块

- Performance 页面场景分析 + 典型案例：**展示增强**，数据来源于 mock
- sceneEvidence 车道密度判断（laneDensityHint）：**全为 0**，依赖逐帧坐标数据
- sceneEvidence 拥堵/高速推断：**启发式规则**，非精确计算

### 8.3 当前未实现功能

- 无逐帧目标追踪（无 MOT）
- 无视频上传存储（video_path 由前端写入，后端不处理视频文件）
- 无 TensorRT 运行时（registry 预留，未实现）
- 无 OpenVINO 运行时（registry 预留，未实现）
- Agent 服务依赖 AGENT_API_KEY 环境变量（SiliconFlow API）
- Performance 页面部分模块（场景分析/典型案例）仍为 mock 数据，非实时推理数据

### 8.4 口径说明

- "检测次数" = 逐帧检测事件累计（重复检测同一目标多次计入）
- "推理耗时" 显示 "--" 的情况：
  - session_ms / preprocess_ms / postprocess_ms 为 null 时
  - 后端未返回对应字段时
- endToEndLatencyMs = 收到结果时间 - 发送帧时间（不含前端渲染）
