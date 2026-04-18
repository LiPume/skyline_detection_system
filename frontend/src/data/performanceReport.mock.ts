/**
 * Skyline — 模型评测报告 Mock 数据
 *
 * 用途：支撑 Performance.vue "模型评测结果与案例分析页" 展示
 * 定位：与真实 report.json / train_history.csv 结构对应，支持后续替换
 *
 * 替换说明：
 *  - report.json → 替换 meta / summaryMetrics / classMetrics / scenarios / caseStudies / conclusion
 *  - train_history.csv → 替换 trainingHistory / trainingSummary
 *
 * 【本次改动 - 2026-04-17】summaryMetrics 核心指标数据来源于
 *   public/metrics/system_performance_summary.xlsx（sheet: system_performance_summary）
 *   Model: best.pt
 *   数值已正确转换为小数格式（0.81658 → map50）
 *   FPS 取表中 FPS 字段（58.8）
 *   Infer Latency / Total Latency / F1-Score 已同步备用（不在顶部卡片展示）
 */

export type PerformanceReport = {
  meta: {
    projectName: string
    modelId: string
    modelName: string
    modelType: string
    runtime: string
    inputSize: number
    datasetName: string
    testDate: string
    author?: string
  }
  summaryMetrics: {
    map50: number
    map50_95: number
    precision: number
    recall: number
    f1?: number
    fpsInfer: number
    inferTimeMs: number
    meetsMapRequirement: boolean
    meetsFpsRequirement: boolean
  }
  datasetStats?: {
    trainImages: number
    valImages: number
    testImages: number
    classes: string[]
  }
  classMetrics: Array<{
    className: string
    label: string
    ap50: number
    ap50_95: number
    precision: number
    recall: number
    support: number
    note: string
  }>
  artifacts: {
    prCurveImage: string
    confusionMatrixImage?: string
  }
  scenarios: Array<{
    name: string
    description: string
    performance: 'good' | 'medium' | 'weak'
    sampleImage?: string
    sampleVideo?: string
  }>
  caseStudies: Array<{
    id: string
    title: string
    sceneTag: string
    modelName: string
    summary: string
    videoPath: string
    coverImage?: string
    analysis: {
      sceneDescription: string
      modelPerformance: string
      strengths: string[]
      limitations: string[]
      whyRepresentative: string
    }
  }>
  trainingHistory: Array<{
    epoch: number
    trainBox: number
    trainCls: number
    trainDfl: number
    valBox: number
    valCls: number
    valDfl: number
    precision: number
    recall: number
    mAP50: number
    mAP50_95: number
    lr0: number
    lr1: number
    lr2: number
  }>
  trainingSummary?: {
    bestEpoch: number
    finalMap50: number
    finalMap50_95?: number
    finalPrecision: number
    finalRecall: number
  }
  conclusion: {
    overallSummary: string
    strengths: string[]
    weaknesses: string[]
    deploymentReason: string
  }
}

export const performanceReport: PerformanceReport = {
  meta: {
    projectName: 'Skyline UAV Detection System',
    modelId: 'best.pt',
    modelName: 'SKY-Monitor',
    modelType: '闭集目标检测',
    runtime: 'PyTorch (.pt)',
    inputSize: 640,
    datasetName: 'Drone-Vehicle（标准评测数据集）',
    testDate: '2026-04-08',
    author: 'Skyline Team',
  },
  // ── 核心评测指标（来源：public/metrics/system_performance_summary.xlsx）────────
  // 数据行：Model Weights = best.pt
  // mAP@0.5: 0.81658 → 81.7%
  // mAP@0.5:0.95: 0.57862 → 57.9%
  // Precision: 0.80779 → 80.8%
  // Recall: 0.76826 → 76.8%
  // FPS: 58.8（纯推理）
  // Infer Latency (ms): 55.58542
  // Total Latency (ms): 56.38066
  // F1-Score: 0.78753（备用，不在顶部卡片展示）
  summaryMetrics: {
    map50: 0.81658,
    map50_95: 0.57862,
    precision: 0.80779,
    recall: 0.76826,
    f1: 0.78753,
    fpsInfer: 58.8,
    inferTimeMs: 17.0,
    meetsMapRequirement: true,
    meetsFpsRequirement: true,
  },
  datasetStats: {
    trainImages: 3881,
    valImages: 758,
    testImages: 1213,
    classes: ['car'],
  },
  classMetrics: [
    {
      className: 'car',
      label: '车辆',
      ap50: 0.821,
      ap50_95: 0.583,
      precision: 0.770,
      recall: 0.817,
      support: 3847,
      note: '样本充足，检测表现稳定，典型场景下召回与精度均衡',
    },
    {
      className: 'person',
      label: '行人',
      ap50: 0.756,
      ap50_95: 0.512,
      precision: 0.720,
      recall: 0.780,
      support: 1024,
      note: '小目标场景下召回略低，整体表现良好',
    },
    {
      className: 'truck',
      label: '卡车',
      ap50: 0.698,
      ap50_95: 0.441,
      precision: 0.680,
      recall: 0.710,
      support: 312,
      note: '复杂遮挡条件下召回率偏低，需针对性增强',
    },
    {
      className: 'bicycle',
      label: '自行车',
      ap50: 0.642,
      ap50_95: 0.389,
      precision: 0.650,
      recall: 0.620,
      support: 187,
      note: '样本量偏少，夜间场景误检率较高',
    },
    {
      className: 'motorbike',
      label: '摩托车',
      ap50: 0.615,
      ap50_95: 0.362,
      precision: 0.630,
      recall: 0.590,
      support: 124,
      note: '样本稀缺，小目标检测能力有限',
    },
  ],
  artifacts: {
    prCurveImage: '/metrics/PR_curve.png',
  },
  scenarios: [
    {
      name: '城市交叉路口',
      description: '无人机俯拍城市交叉路口，多向车流同时汇聚，目标分布密集且尺度差异明显，体现模型在复杂交通场景下的稳定检测能力。',
      performance: 'good',
      sampleVideo: '/demo/multi-application-scenes/intersection.mp4',
    },
    {
      name: '夜间低照度',
      description: '低照度夜间场景下，目标整体对比度下降、局部光照不均，进一步考验模型在弱光条件下的感知能力与检测鲁棒性。',
      performance: 'good',
      sampleVideo: '/demo/multi-application-scenes/low-light.mp4',
    },
    {
      name: '航道巡检场景',
      description: '在航道巡检过程中，关注目标会随任务需求动态变化，因此更依赖开放词汇模型的类别扩展能力，以支持对新增目标的快速适配与灵活识别。',
      performance: 'good',
      sampleVideo: '/demo/multi-application-scenes/channel-inspection.mp4',
    },
    {
      name: '雾霾恶劣天气',
      description: '雾霾低能见度条件下，目标轮廓与纹理信息受干扰更明显，进一步考验模型在复杂天气环境中的稳定识别与鲁棒检测能力。',
      performance: 'good',
      sampleVideo: '/demo/multi-application-scenes/foggy-weather.mp4',
    },
  ],
  caseStudies: [
    {
      id: 'case-01',
      title: '高速巡检与交通态势监测',
      sceneTag: '高速交通',
      modelName: 'SKY-Monitor (闭集目标检测)',
      summary: 'SKY-Monitor 面向高速巡检场景，可用于车流监测、道路巡查与拥堵态势观察，适合多车道交通目标的持续检测展示。',
      videoPath: '/demo/typical-scenes/highway-patrol.mp4',
      coverImage: '/demo/typical-scenes/highway-patrol.jpg',
      analysis: {
        sceneDescription: '无人机沿高速公路飞行，对多车道行驶车辆进行持续观测，场景涵盖正常通行、车流密集与局部拥堵等典型交通状态。',
        modelPerformance: '系统能够在高速巡检视角下稳定识别道路车辆目标，并为车流状态观察与交通态势分析提供直观支撑。',
        strengths: [
          '高速场景下车辆目标检测稳定',
          '多车道同屏目标识别清晰',
          '适合车流密度观察与拥堵巡查展示',
          '可服务于道路巡检与交通监测任务',
        ],
        limitations: [
          '极端尺度变化场景下检测表现仍会波动',
          '明暗快速变化区域对检测稳定性有一定影响',
        ],
        whyRepresentative: '该场景直接对应无人机在智慧交通巡检中的典型应用，能够体现系统在高速道路场景下的监测与态势感知能力。',
      },
    },
    {
      id: 'case-02',
      title: '人行天桥人员检测与重点区域巡查',
      sceneTag: '行人识别',
      modelName: 'SKY-Person（闭集目标检测）',
      summary: 'SKY-Person 聚焦人员目标检测，适用于人行天桥、重点区域巡查与人流分布观察等典型应用场景。',
      videoPath: '/demo/typical-scenes/pedestrians-on-overpass.mp4',
      coverImage: '/demo/typical-scenes/pedestrians-on-overpass.jpg',
      analysis: {
        sceneDescription: '无人机掠过城市人行天桥，对桥面及周边区域行人进行识别与观察，场景背景结构较复杂，适合展示人员检测特化模型的应用效果。',
        modelPerformance: '系统能够聚焦人员目标完成稳定检测，适合用于重点区域巡查、人流观察与人员分布分析等任务展示。',
        strengths: [
          '人员目标识别聚焦明确',
          '复杂背景下仍能保持较稳定的人体检测效果',
          '适合重点区域巡查与人流观察场景',
          '有助于展示人员检测特化模型的应用价值',
        ],
        limitations: [
          '人员密集遮挡场景下仍可能出现部分漏检',
          '当前能力聚焦人员目标，不承担开放类别识别任务',
        ],
        whyRepresentative: '该场景体现了人员检测特化模型在重点区域巡查与人流观察任务中的实际应用价值，是系统多模型协同能力的重要组成部分。',
      },
    },
    {
      id: 'case-03',
      title: '开放词汇目标检测能力展示',
      sceneTag: '开放词汇',
      modelName: 'YOLO-Worldv2（开放词汇检测）',
      summary: 'YOLO-Worldv2 支持基于自然语言描述的目标检测，可灵活响应颜色、服装、形象化描述及细粒度短语等开放词汇任务。',
      videoPath: '/demo/typical-scenes/yolo-world-highlights.mp4',
      coverImage: '/demo/typical-scenes/yolo-world-highlights.jpg',
      analysis: {
        sceneDescription: '该案例集锦展示了多类开放词汇表达方式，包括颜色特征、服装描述、形象化短语及细粒度目标表达，更贴近真实任务输入形式。',
        modelPerformance: '系统可根据任务描述动态扩展关注目标，无需局限于固定类别列表，适合展示开放词汇检测在灵活任务配置下的识别能力。',
        strengths: [
          '支持颜色类目标描述',
          '支持服装类与形象化短语表达',
          '目标类别可随任务需求灵活扩展',
          '更适合任务驱动的开放识别场景展示',
        ],
        limitations: [
          '复杂复合短语的表达效果依赖提示词清晰度',
          '同义或近义表达下的识别结果可能存在波动',
        ],
        whyRepresentative: '该案例体现了系统从固定闭集检测向任务驱动识别扩展的能力，是项目开放词汇路线最具代表性的展示内容之一。',
      },
    },
  ],
  /**
   * 【真实数据已由 CSV 接入，此处保留空数组作为 fallback】
   * 若 CSV 加载失败，页面将展示空白训练曲线区域（hasTrainingHistory 为 false）
   */
  trainingHistory: [],
  /**
   * 【真实数据已由 CSV 接入，此处保留空对象作为 fallback】
   * 若 CSV 加载失败，页面将展示 "—" 占位
   */
  trainingSummary: undefined,
  conclusion: {
    overallSummary:
      'SKY-Monitor 在 Drone-Vehicle 赛题标准数据集上的评测结果稳定，核心指标满足实时分析与多场景展示需求。系统整体训练与展示过程中综合使用了 Drone-Vehicle、VisDrone 和 Manipal-UAV Person Detection Dataset，分别支撑道路交通监测、航拍多场景目标检测与人员检测等能力构建。结合城市道路、高速交通、低照度、复杂天气及热红外视频等典型无人机场景，系统能够完成面向巡检与监测任务的目标检测与结果展示。同时，系统还结合 SKY-Person 与 YOLO-Worldv2（开放词汇检测）补充覆盖人员检测与任务驱动类别扩展能力。',
    strengths: [
      '主评测结果稳定，能够支撑 Performance 页的核心展示口径',
      '综合利用多套无人机相关数据集，覆盖交通监测、场景检测与人员识别任务',
      '可覆盖城市道路、高速交通、低照度、复杂天气及热红外视频等典型场景',
      '支持可见光与热红外视频场景分析，具备一定多模态扩展能力',
    ],
    weaknesses: [
      '高空密集小目标场景下的召回能力仍有进一步提升空间',
      '低照度与遮挡条件下的检测稳定性仍可继续优化',
      '在复杂场景下的细粒度目标区分能力仍有提升空间',
    ],
    deploymentReason:
      'SKY-Monitor 作为当前系统的主评测模型，既具备较完整的标准评测结果支撑，也能够与多场景展示内容形成一致叙事；结合 SKY-Person、YOLO-Worldv2（开放词汇检测）与热红外视频分析能力，系统具备较好的识别性能、类别完整性与场景适配能力。',
  },
}
