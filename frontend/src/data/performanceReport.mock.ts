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
  trainingHistory: [
    { epoch: 1,    trainBox: 3.7513, trainCls: 3.1819, trainDfl: 2.6552,  valBox: 1.3445,  valCls: 1.6503,  valDfl: 1.5234,  precision: 0.40228, recall: 0.12524, mAP50: 0.14902, mAP50_95: 0.06782, lr0: 0.070013, lr1: 0.0033319, lr2: 0.0033319 },
    { epoch: 2,    trainBox: 1.2723, trainCls: 1.5159, trainDfl: 1.3870,   valBox: 0.87866, valCls: 1.1854,  valDfl: 1.2253,  precision: 0.25755, recall: 0.34154, mAP50: 0.27992, mAP50_95: 0.14896, lr0: 0.039991, lr1: 0.0066432, lr2: 0.0066432 },
    { epoch: 3,    trainBox: 1.0811, trainCls: 1.2483, trainDfl: 1.2517,   valBox: 0.85706, valCls: 1.0030,  valDfl: 1.1662,  precision: 0.35850, recall: 0.36023, mAP50: 0.33365, mAP50_95: 0.18770, lr0: 0.0099473, lr1: 0.0099325, lr2: 0.0099325 },
    { epoch: 4,    trainBox: 1.0287, trainCls: 1.1096, trainDfl: 1.1867,   valBox: 0.84920, valCls: 0.89137, valDfl: 1.1310,  precision: 0.42409, recall: 0.42684, mAP50: 0.40131, mAP50_95: 0.23186, lr0: 0.009901, lr1: 0.009901, lr2: 0.009901 },
    { epoch: 5,    trainBox: 1.0343, trainCls: 1.0363, trainDfl: 1.1560,   valBox: 0.87599, valCls: 0.84592, valDfl: 1.1115,  precision: 0.44647, recall: 0.49543, mAP50: 0.45896, mAP50_95: 0.26739, lr0: 0.009901, lr1: 0.009901, lr2: 0.009901 },
    { epoch: 6,    trainBox: 1.0447, trainCls: 0.97641, trainDfl: 1.1320,  valBox: 0.92003, valCls: 0.80660, valDfl: 1.1004,  precision: 0.50286, recall: 0.51031, mAP50: 0.49487, mAP50_95: 0.29866, lr0: 0.009868, lr1: 0.009868, lr2: 0.009868 },
    { epoch: 7,    trainBox: 1.0698, trainCls: 0.93544, trainDfl: 1.1129,  valBox: 0.93178, valCls: 0.77396, valDfl: 1.0786,  precision: 0.55557, recall: 0.51739, mAP50: 0.52366, mAP50_95: 0.32551, lr0: 0.009835, lr1: 0.009835, lr2: 0.009835 },
    { epoch: 8,    trainBox: 1.1035, trainCls: 0.91395, trainDfl: 1.1035,  valBox: 0.97868, valCls: 0.75956, valDfl: 1.0745,  precision: 0.53287, recall: 0.54041, mAP50: 0.53216, mAP50_95: 0.33345, lr0: 0.009802, lr1: 0.009802, lr2: 0.009802 },
    { epoch: 9,    trainBox: 1.1343, trainCls: 0.89317, trainDfl: 1.0921,  valBox: 1.0121,  valCls: 0.74617, valDfl: 1.0624,  precision: 0.58025, recall: 0.56472, mAP50: 0.56969, mAP50_95: 0.35958, lr0: 0.009769, lr1: 0.009769, lr2: 0.009769 },
    { epoch: 10,   trainBox: 1.1719, trainCls: 0.88053, trainDfl: 1.0821,  valBox: 1.0369,  valCls: 0.72956, valDfl: 1.0513,  precision: 0.59519, recall: 0.55896, mAP50: 0.57883, mAP50_95: 0.36904, lr0: 0.009736, lr1: 0.009736, lr2: 0.009736 },
    { epoch: 15,   trainBox: 1.2823, trainCls: 0.81923, trainDfl: 1.0522,  valBox: 1.1494,  valCls: 0.67968, valDfl: 1.0298,  precision: 0.64740, recall: 0.62535, mAP50: 0.63873, mAP50_95: 0.41869, lr0: 0.009571, lr1: 0.009571, lr2: 0.009571 },
    { epoch: 20,   trainBox: 1.3170, trainCls: 0.78392, trainDfl: 1.0404,  valBox: 1.1871,  valCls: 0.64025, valDfl: 1.0172,  precision: 0.68754, recall: 0.65899, mAP50: 0.68259, mAP50_95: 0.45094, lr0: 0.009406, lr1: 0.009406, lr2: 0.009406 },
    { epoch: 30,   trainBox: 1.3038, trainCls: 0.73664, trainDfl: 1.0232,  valBox: 1.2063,  valCls: 0.59901, valDfl: 1.0065,  precision: 0.71002, recall: 0.70094, mAP50: 0.71487, mAP50_95: 0.48613, lr0: 0.009076, lr1: 0.009076, lr2: 0.009076 },
    { epoch: 40,   trainBox: 1.2780, trainCls: 0.70602, trainDfl: 1.0111,  valBox: 1.2016,  valCls: 0.57769, valDfl: 0.99862, precision: 0.73605, recall: 0.71487, mAP50: 0.74265, mAP50_95: 0.51281, lr0: 0.008746, lr1: 0.008746, lr2: 0.008746 },
    { epoch: 50,   trainBox: 1.2739, trainCls: 0.68844, trainDfl: 1.0084,  valBox: 1.2004,  valCls: 0.56710, valDfl: 0.99605, precision: 0.74526, recall: 0.72692, mAP50: 0.75397, mAP50_95: 0.52020, lr0: 0.008482, lr1: 0.008482, lr2: 0.008482 },
    { epoch: 60,   trainBox: 1.2749, trainCls: 0.67480, trainDfl: 1.0064,  valBox: 1.2000,  valCls: 0.55892, valDfl: 0.99444, precision: 0.75020, recall: 0.72980, mAP50: 0.75980, mAP50_95: 0.52500, lr0: 0.008218, lr1: 0.008218, lr2: 0.008218 },
    { epoch: 80,   trainBox: 1.2530, trainCls: 0.64060, trainDfl: 0.99760, valBox: 1.1980,  valCls: 0.54360, valDfl: 0.99130, precision: 0.76000, recall: 0.74000, mAP50: 0.77000, mAP50_95: 0.53500, lr0: 0.007690, lr1: 0.007690, lr2: 0.007690 },
    { epoch: 100,  trainBox: 1.2290, trainCls: 0.60330, trainDfl: 0.98640, valBox: 1.1970,  valCls: 0.53080, valDfl: 0.98890, precision: 0.76500, recall: 0.74800, mAP50: 0.77600, mAP50_95: 0.54200, lr0: 0.007162, lr1: 0.007162, lr2: 0.007162 },
    { epoch: 120,  trainBox: 1.2000, trainCls: 0.56700, trainDfl: 0.97500, valBox: 1.1960,  valCls: 0.52000, valDfl: 0.98700, precision: 0.76800, recall: 0.75500, mAP50: 0.78000, mAP50_95: 0.54900, lr0: 0.006634, lr1: 0.006634, lr2: 0.006634 },
    { epoch: 150,  trainBox: 1.1600, trainCls: 0.53000, trainDfl: 0.96000, valBox: 1.1940,  valCls: 0.51000, valDfl: 0.98400, precision: 0.77000, recall: 0.76000, mAP50: 0.78500, mAP50_95: 0.55500, lr0: 0.006106, lr1: 0.006106, lr2: 0.006106 },
    { epoch: 180,  trainBox: 1.1200, trainCls: 0.51000, trainDfl: 0.95000, valBox: 1.1920,  valCls: 0.50200, valDfl: 0.98200, precision: 0.77200, recall: 0.76300, mAP50: 0.78800, mAP50_95: 0.56000, lr0: 0.005578, lr1: 0.005578, lr2: 0.005578 },
    { epoch: 200,  trainBox: 1.1000, trainCls: 0.50000, trainDfl: 0.94200, valBox: 1.1910,  valCls: 0.49700, valDfl: 0.98100, precision: 0.77300, recall: 0.76500, mAP50: 0.79000, mAP50_95: 0.56400, lr0: 0.005050, lr1: 0.005050, lr2: 0.005050 },
    { epoch: 220,  trainBox: 1.0850, trainCls: 0.49200, trainDfl: 0.93800, valBox: 1.1905,  valCls: 0.49300, valDfl: 0.98050, precision: 0.77400, recall: 0.76600, mAP50: 0.79200, mAP50_95: 0.56700, lr0: 0.004522, lr1: 0.004522, lr2: 0.004522 },
    { epoch: 240,  trainBox: 1.0720, trainCls: 0.48800, trainDfl: 0.93550, valBox: 1.1900,  valCls: 0.49000, valDfl: 0.98000, precision: 0.77450, recall: 0.76700, mAP50: 0.79350, mAP50_95: 0.56950, lr0: 0.003994, lr1: 0.003994, lr2: 0.003994 },
    { epoch: 252,  trainBox: 1.0670, trainCls: 0.48600, trainDfl: 0.93450, valBox: 1.1898,  valCls: 0.48900, valDfl: 0.97980, precision: 0.77480, recall: 0.76750, mAP50: 0.79400, mAP50_95: 0.57000, lr0: 0.003802, lr1: 0.003802, lr2: 0.003802 },
    { epoch: 260,  trainBox: 1.0630, trainCls: 0.48400, trainDfl: 0.93400, valBox: 1.1895,  valCls: 0.48850, valDfl: 0.97970, precision: 0.77450, recall: 0.76700, mAP50: 0.79350, mAP50_95: 0.56980, lr0: 0.003606, lr1: 0.003606, lr2: 0.003606 },
    { epoch: 280,  trainBox: 1.0570, trainCls: 0.48000, trainDfl: 0.93300, valBox: 1.1890,  valCls: 0.48700, valDfl: 0.97950, precision: 0.77400, recall: 0.76650, mAP50: 0.79300, mAP50_95: 0.56920, lr0: 0.003078, lr1: 0.003078, lr2: 0.003078 },
    { epoch: 300,  trainBox: 1.0542, trainCls: 0.48624, trainDfl: 0.93322, valBox: 1.2338,  valCls: 0.50926, valDfl: 0.97925, precision: 0.77300, recall: 0.76700, mAP50: 0.79200, mAP50_95: 0.56900, lr0: 0.001750, lr1: 0.001750, lr2: 0.001750 },
  ],
  trainingSummary: {
    bestEpoch: 252,
    finalMap50: 0.792,
    finalMap50_95: 0.569,
    finalPrecision: 0.773,
    finalRecall: 0.767,
  },
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
