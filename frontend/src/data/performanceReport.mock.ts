/**
 * Skyline — 模型评测报告 Mock 数据
 *
 * 用途：支撑 Performance.vue "模型评测结果与案例分析页" 展示
 * 定位：与真实 report.json / train_history.csv 结构对应，支持后续替换
 *
 * 替换说明：
 *  - report.json → 替换 meta / summaryMetrics / classMetrics / scenarios / caseStudies / conclusion
 *  - train_history.csv → 替换 trainingHistory / trainingSummary
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
    sampleImage: string
  }>
  caseStudies: Array<{
    id: string
    title: string
    sceneTag: string
    modelName: string
    summary: string
    videoPath: string
    coverImage: string
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
    modelId: 'yolov8-car-v1',
    modelName: 'YOLOv8s-Car',
    modelType: '闭集目标检测',
    runtime: 'PyTorch (.pt)',
    inputSize: 640,
    datasetName: 'UAV-Car（自建航拍车辆数据集 + VisDrone 补充）',
    testDate: '2026-04-08',
    author: 'Skyline Team',
  },
  summaryMetrics: {
    map50: 0.821,
    map50_95: 0.583,
    precision: 0.770,
    recall: 0.817,
    f1: 0.793,
    fpsInfer: 25.3,
    inferTimeMs: 38.7,
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
      name: '白天城市道路',
      description: '光照充足、视野开阔的城市道路环境，车辆目标尺度适中，背景相对简单',
      performance: 'good',
      sampleImage: '/demo/demo_flight.png',
    },
    {
      name: '夜间低照度',
      description: '夜间或黄昏时段，低照度条件下车辆灯光干扰明显，目标对比度降低',
      performance: 'medium',
      sampleImage: '/demo/night_car.png',
    },
    {
      name: '高空密集小目标',
      description: '无人机高空俯拍视角，车辆目标像素占比小，多目标密集分布场景',
      performance: 'medium',
      sampleImage: '/demo/park_car.png',
    },
    {
      name: '复杂背景 / 遮挡',
      description: '停车场、建筑物遮挡、树木阴影等复杂背景下目标被部分遮挡的检测场景',
      performance: 'weak',
      sampleImage: '/demo/park_car.png',
    },
  ],
  caseStudies: [
    {
      id: 'case-01',
      title: '昼间城区主干道车辆检测',
      sceneTag: '白天城市道路',
      modelName: 'YOLOv8s-Car',
      summary: '模型在昼间城区场景下展现出良好的检测稳定性，mAP@0.5 达到 82.1%，有效区分车辆与背景',
      videoPath: '/demo/demo_flight.mp4',
      coverImage: '/demo/demo_flight.png',
      analysis: {
        sceneDescription: '无人机俯拍城市主干道，包含多车道行驶车辆、行人与骑行者，交通流密集，目标尺度从小到大均有分布',
        modelPerformance: '在昼间城区场景中，YOLOv8s-Car 对车辆目标检测的置信度普遍在 0.8 以上，误检率低，定位框贴合度好',
        strengths: [
          '车辆定位框紧贴车身，无明显漂移',
          '高速行驶车辆仍能保持稳定跟踪检测',
          '密集车流中重叠目标分离良好',
        ],
        limitations: [
          '远距离小目标召回率略有下降',
          '部分被树叶遮挡的车辆出现漏检',
        ],
        whyRepresentative: '该场景是本系统最核心的应用场景之一，昼间城区路况直接决定了系统在主干道巡逻任务中的实际可用性',
      },
    },
    {
      id: 'case-02',
      title: '夜间园区停车场车辆识别',
      sceneTag: '夜间低照度',
      modelName: 'YOLOv8s-Car',
      summary: '夜间低照度环境下检测精度有所下降，但仍满足基本任务需求，漏检主要集中在远距离小目标',
      videoPath: '/demo/night_car.mp4',
      coverImage: '/demo/night_car.png',
      analysis: {
        sceneDescription: '夜间园区停车场环境，车灯与环境光源混合，光照条件复杂，存在强曝光与暗区并存的挑战',
        modelPerformance: '夜间场景下检测置信度整体下降至 0.6~0.75，误检率约 8%，漏检集中在画面边缘区域',
        strengths: [
          '车灯强曝光区域未出现大面积误检',
          '近处停放车辆检测稳定',
          '车尾灯辅助提升了车辆区域激活',
        ],
        limitations: [
          '远距离车辆召回率显著下降',
          '暗区漏检率高于昼间约 15%',
          '部分建筑反光产生误检',
        ],
        whyRepresentative: '夜间场景是无人机常态化巡逻必须覆盖的时段，该案例体现了模型在低照度条件下的鲁棒性边界',
      },
    },
    {
      id: 'case-03',
      title: '园区多目标车辆追踪场景',
      sceneTag: '高空密集小目标',
      modelName: 'YOLOv8s-Car',
      summary: '高空俯拍多目标密集分布场景中，模型对小尺度目标的召回能力存在瓶颈，但核心目标检测准确',
      videoPath: '/demo/park_car.mp4',
      coverImage: '/demo/park_car.png',
      analysis: {
        sceneDescription: '园区停车场高空俯拍视角，车辆密集分布，行人与车辆尺度差异大，部分目标被建筑物或树木遮挡',
        modelPerformance: '大尺度车辆 AP 超过 0.85，但小尺度目标（占画面 < 1%）召回率仅约 0.55，整体 mAP@0.5 仍维持在 0.82',
        strengths: [
          '大尺度车辆检测精度优秀，定位准确',
          '在密集场景中对遮挡目标仍有部分检测能力',
          '误检率控制在 5% 以内',
        ],
        limitations: [
          '高空小目标召回率不足，需数据增强',
          '遮挡场景下漏检明显',
          '多目标重叠时存在框重叠现象',
        ],
        whyRepresentative: '该场景直接对应赛题对"高空密集小目标"检测能力的要求，体现了当前模型的能力边界与后续优化方向',
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
    overallSummary: 'YOLOv8s-Car 在自建航拍车辆数据集上经过 300 epochs 训练，mAP@0.5 达到 82.1%，满足赛题指标要求（mAP ≥ 0.80）。在 RTX 3080 上纯推理 FPS 达 25.3，满足实时处理要求（≥ 25 FPS）。已覆盖白天城区道路、夜间低照度、高空密集小目标、复杂遮挡等典型无人机场景，整体具备在实际航拍巡逻任务中部署的能力。',
    strengths: [
      '昼间城区场景检测精度高，mAP@0.5 达 82.1%',
      '模型推理速度满足实时处理要求（25.3 FPS）',
      '定位精度稳定，误检率控制在合理范围',
      '收敛过程平稳，无明显过拟合迹象',
    ],
    weaknesses: [
      '高空小目标召回率偏低，需增加对应样本',
      '夜间低照度场景漏检率约 15%，需针对性增强',
      '遮挡场景下检测能力下降明显',
    ],
    deploymentReason: '综合评测指标满足赛题基线要求，核心应用场景（昼间城区道路）表现稳定，适合作为系统主模型进行部署演示',
  },
}
