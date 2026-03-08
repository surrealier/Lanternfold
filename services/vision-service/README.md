# Vision Service Boundary

The MVP uses a deterministic detector inside `services/api-gateway/app/main.py`.
This directory is reserved for extraction into a dedicated inference service with ONNX, TensorRT, or OpenVINO later.