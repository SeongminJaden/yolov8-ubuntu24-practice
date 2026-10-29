# 실행 상태 — 2026-10-29

실행 장비: Ubuntu 24.04 x86_64, RTX 5060 Laptop GPU, driver 595.99.02.

| 단계 | 상태 | 증거 / 제한 |
|---|---|---|
| 가이드 고정 torch/cu128 신규 설치 | 완료 | 독립 venv: torch 2.9.1+cu128 / torchvision 0.24.1+cu128 |
| Ultralytics 8.3.221 및 ONNX 1.17.0 | 완료 | environment-observed.txt |
| GPU 계산 + CUDA NMS | 통과 | pipeline-guide.log |
| pip 의존성 검사 | 통과 | pip-check.txt |
| 공개 이미지 검출 | 통과 | 버스·사람 포함 6개 검출; 이미지 육안 확인 |
| COCO8 1 epoch | 통과 | best.pt, last.pt, results.csv 생성 |
| 퍽 예제 구현 | 완료 | 학습·라벨 검사·추적·ONNX 스크립트 |
| 합성 4클래스 10 epoch / test | 통과 | verification.json; 실제 퍽 성능 아님 |
| ByteTrack | 통과 | 30프레임 처리 및 ID 출력 |
| YOLOv8s / 퍽 ONNX | 통과 | 출력 [1,84,8400] / [1,8,8400] |
| ONNX Runtime vs PyTorch | 통과 | 같은 난수 입력, rtol=1e-3 / atol=1e-3 |
| 실제 퍽 사진 학습·영상 평가 | 미실행 | 원본 데이터와 영상 필요 |
| 원문 배포 ZIP의 12개 테스트 | 미실행 | ZIP 미제공; 자체 라벨 회귀 테스트 2개(오류 사례 8개) 실행 |
| Isaac ROS 컨테이너 GPU | 통과 | Docker 모드, Lyrical, RTX 5060 확인 |
| TensorRT / ROS 검출 | 설치 중 | 의존 패키지 다운로드; 엔진·검출 미검증 |
| GitHub | 공개 저장소 생성 | SeongminJaden/yolov8-ubuntu24-practice |

Ubuntu 파티션을 174.2GiB로 확장한 후 가이드의 고정 버전 환경을 새로 설치하고 전체 학습 파이프라인을 재검증했습니다. `pipeline.log`는 이전 cu130 실행 기록이고 `pipeline-guide.log`가 현재 고정 버전 검증입니다. 현재 venv는 기존 Isaac Sim 환경을 참조하지 않습니다.
