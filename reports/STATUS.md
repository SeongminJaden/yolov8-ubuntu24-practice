# 실행 상태 — 2026-10-29

실행 장비: Ubuntu 24.04 x86_64, RTX 5060 Laptop GPU, driver 595.99.02.

| 단계 | 상태 | 증거 / 제한 |
|---|---|---|
| 가이드 고정 torch/cu128 신규 설치 | 미완료 | 디스크 부족. 기존 cu130 torch를 읽기 전용 심볼릭 링크로 재사용 |
| Ultralytics 8.3.221 및 ONNX 1.17.0 | 완료 | environment-observed.txt |
| GPU 계산 + CUDA NMS | 통과 | pipeline.log |
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
| Isaac ROS 컨테이너 / TensorRT | 미실행 | 디스크, Docker socket 권한, sudo 제약 |
| GitHub 업로드 | 미완료 | GitHub 인증 및 대상 계정 미확인 |

환경을 정리한 뒤 전체 검증을 재실행했습니다. 기존 Isaac Sim 패키지를 변경하지 않고 YOLO에 필요한 의존성만 링크했습니다. 로컬 venv는 기존 파일 경로에 의존합니다. 새 장비에서 scripts/install.sh로 만드는 독립 환경과 구분해야 합니다.
