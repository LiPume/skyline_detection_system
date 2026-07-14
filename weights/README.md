# 模型权重说明

权重是运行实时推理的必要条件，但不会随本仓库分发：其中包含大体积二进制文件，部分为项目训练产物或受上游模型许可约束。仓库保留了完整的运行时路径和文件名约定，以便归档恢复。

| 模型 ID | 期望路径 | 运行时 | 获取方式 |
| --- | --- | --- | --- |
| `YOLO-World-V2` | `weights/yolov8m-worldv2.pt` | PyTorch | 第一次使用 Ultralytics 时可按其官方机制下载；也可手动放入该路径。 |
| `YOLOv8-VisDrone` | `weights/VisDrone/yolov8x_visdrone_best.onnx` | ONNX Runtime | 项目训练产物；请从项目归档或联系作者获取。 |
| `YOLOv8-Person` | `weights/person_only/best_person.onnx` | ONNX Runtime | 项目训练产物；请从项目归档或联系作者获取。 |

后端会依据 `backend/models/registry.py` 中的 `RUNTIME_CONFIG` 查找上述文件。模型缺失时，模型列表接口仍可访问，但选择对应模型进行推理会失败并返回缺失权重信息。

为避免误用，请同时保留模型来源、训练数据许可和模型文件校验信息；第三方模型须遵守其各自许可证。
