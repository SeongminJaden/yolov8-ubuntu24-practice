# 실행 상태 — 2026-10-29

Ubuntu 24.04 x86_64, RTX 5060 Laptop GPU 8GB, driver 595.99.02에서 실행했습니다. 파티션 확장 후 가이드 고정 버전을 독립 가상환경에 설치했습니다.

| 단계 | 상태 | 증거 |
|---|---|---|
| 고정 Python 환경 | 통과 | torch 2.9.1+cu128 / torchvision 0.24.1+cu128 / Ultralytics 8.3.221 |
| GPU 연산·CUDA NMS·pip check | 통과 | pipeline-guide.log, pip-check.txt |
| 공개 이미지 검출 | 통과 | 버스·사람 등 6개 검출 |
| COCO8 1 epoch | 통과 | coco8-training-results.csv |
| 합성 퍽 10 epoch / test | 통과 | synthetic-training-results.csv, verification.json |
| ByteTrack | 통과 | 30프레임 모두 추적 ID 출력 |
| YOLOv8s 및 퍽 ONNX | 통과 | [1,84,8400] / [1,8,8400], PyTorch 수치 비교 |
| CPU 회귀 테스트 | 통과 | 7개, 일반 실행과 python -O 모두 통과 |
| Isaac ROS 컨테이너·GPU | 통과 | ROS Lyrical, Isaac ROS 5.0.0 |
| TensorRT 엔진 2개 | 통과 | TensorRT 10.16.1.11, FP32/noTF32 |
| TensorRT vs ONNX Runtime | 통과 | yolov8s-trt-comparison.json, pucks-trt-comparison.json |
| 공식 ROS rosbag 검출 | 통과 | 30초, 검출 메시지 271개, 객체 2710개, 이미지 65개 |
| 4클래스 퍽 ROS 검출 | 통과 | 20초, 검출 메시지 195개, 객체 780개, 이미지 11개 |
| 퍽 PyTorch vs ROS 좌표 | 통과 | 디코더 정수 변환 기준 4개 상자 모두 IoU 1.0 |
| GitHub 공개 저장소 | 업로드 | https://github.com/SeongminJaden/yolov8-ubuntu24-practice |
| 실제 퍽 사진·실영상 평가 | 미실행 | 실제 데이터 미제공. 합성 검증으로 대체했다고 주장하지 않음 |
| 원문 ZIP의 코드·12개 테스트 | 미실행 | ZIP 미제공. 별도 구현 및 자체 테스트 사용 |

합성 test mAP50은 0.995이며 실제 물체 성능이 아닙니다. GUI의 RQT 창 대신 동일 결과 토픽의 이미지를 저장하고 육안 확인했습니다. ROS·추적 테스트는 반복 스트림의 동작 확인이며 메시지 수를 정확도 지표로 사용하지 않습니다.

`pipeline.log`는 이전 cu130 환경 기록이고 `pipeline-guide.log`가 현재 고정 버전 실행 기록입니다. 현재 `.venv-yolo`는 기존 Isaac Sim 환경을 참조하지 않습니다.

기본 TF32 엔진의 엄격한 수치 비교는 실패해 noTF32로 재생성했습니다. 기준을 완화하지 않았으며 `precision-note.json`에 기록했습니다. 퍽 ROS 상자는 NVIDIA decoder의 `cv::Rect<int>` 절삭 때문에 소수점 PyTorch 상자와 1~2px 차이가 납니다. 공식 소스와 같은 변환을 적용하면 정확히 일치하며, 변환 전 IoU도 보고서에 남겼습니다.

모델 가중치·ONNX·TensorRT 엔진·데이터는 대용량 로컬 산출물로 Git에서 제외했습니다. README 명령으로 재생성할 수 있습니다. TensorRT 엔진은 대상 GPU에서 다시 생성해야 합니다.
