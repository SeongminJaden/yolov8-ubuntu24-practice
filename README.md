# Ubuntu 24.04 YOLOv8 학습 실습

[원문 설치 가이드](https://velog.io/@roboticsmaster/Ubuntu-24.04-YOLOv8-실습-설치-가이드)의 학습 흐름을 실행 가능한 스크립트로 새로 구현했습니다. 원문에서 언급한 배포 ZIP은 제공되지 않았으므로 그 ZIP의 코드나 12개 테스트를 복제한 저장소가 아닙니다.

## 설치

Ubuntu 24.04 / Python 3.12 / NVIDIA GPU 기준입니다. Python venv와 시스템 라이브러리가 준비된 상태에서:

```bash
bash scripts/install.sh
source .venv-yolo/bin/activate
python scripts/check_gpu.py
```

가이드 조합은 PyTorch 2.9.1 + torchvision 0.24.1 (cu128)입니다. **이 장비의 실제 검증은 디스크 부족으로 기존 Isaac Sim 환경의 torch 2.11.0+cu130 / torchvision 0.26.0을 별도 venv에서 필요한 의존성만 심볼릭 링크로 참조했습니다.** 따라서 고정 버전 설치를 검증했다고 볼 수 없습니다. 기존 환경은 수정하지 않았습니다. `.venv-yolo`는 로컬 의존 경로를 포함하므로 Git에 넣지 않습니다. 새 장비는 설치 스크립트로 독립 환경을 만드세요.

## 전체 학습 예제

```bash
python -m unittest discover -s tests -v
python scripts/make_synthetic.py
python scripts/validate_labels.py data/synthetic-pucks/labels --kind yolo --classes 4
python scripts/verify_pipeline.py
```

검증 스크립트는 공개 버스 이미지 검출, COCO8 1 epoch 학습, 합성 퍽 10 epoch 학습, 별도 test 평가, ByteTrack 영상 추적, COCO YOLOv8s 및 퍽 ONNX 변환, ONNX Runtime와 PyTorch의 출력 수치 비교를 수행합니다. 결과는 `reports/verification.json`, 상세 로그는 실행 시 리다이렉션할 수 있습니다. GPU와 인터넷 연결이 필요합니다. 결과 디렉터리는 Ultralytics가 자동 증가시킵니다. 합성 데이터 생성기는 기존 데이터가 있으면 중단합니다.

합성 퍽은 빨강/초록 원과 사각형으로 만든 **코드 흐름 확인용** 자료입니다. 원은 cylinder, 사각형은 prism을 대신하는 단순 도형이며 실제 물체 인식 성능을 증명하지 않습니다. train/val/test는 서로 다른 seed로 생성합니다. 실제 사진은 촬영 세션 단위로 분리해야 합니다.

## 실제 퍽 데이터 학습

`data/yolo/images/{train,val,test}`와 같은 구조의 `labels` 디렉터리를 준비하고, `configs/pucks.yaml`을 복사한 `configs/pucks-local.yaml`의 `path`를 데이터 절대 경로로 지정합니다. 이미지와 라벨 파일의 stem은 같아야 합니다. 클래스 순서는 red_cylinder, red_prism, green_cylinder, green_prism입니다. 라벨 검사기는 행의 숫자·범위·상자 경계를 검사합니다. 이미지 누락·촬영 세션 누출은 별도로 점검해야 합니다.

```bash
python scripts/validate_labels.py data/yolo/labels --classes 4
python scripts/train_yolo.py --data configs/pucks-local.yaml --epochs 50 --batch 4 --device 0
# 아래 경로는 콘솔에서 확인한 실제 출력 경로로 변경
export YOLO_WEIGHTS=runs/detect/pucks/weights/best.pt
yolo detect val model="$YOLO_WEIGHTS" data=configs/pucks-local.yaml split=test device=0
python scripts/track_yolo.py --weights "$YOLO_WEIGHTS" --source data/test.mp4 --device 0
python scripts/export_onnx.py --weights "$YOLO_WEIGHTS" --output models/pucks.onnx
python scripts/inspect_onnx.py models/pucks.onnx
```

기본 학습은 YOLOv8n, 640, seed 317, hue 증강 0입니다. ByteTrack ID는 일시적 번호이고 물리적 ID나 6D 자세가 아닙니다. 실영상·실제 퍽 데이터가 없어 실제 데이터 학습과 평가를 완료했다고 주장하지 않습니다.

## Isaac ROS / TensorRT

이 장비에서는 디스크 여유 부족(시작 시 약 2GB), Docker socket 접근 불가, 비대화형 sudo 불가로 **설치 및 실행 미검증**입니다. 기존 Docker/ROS 설치를 덮어쓰지 않았습니다. 원문 7~9절에 따라 충분한 공간에서 Isaac ROS 5.0 컨테이너와 공식 자산을 준비한 후 아래를 실행합니다.

```bash
# 활성화된 Lyrical 컨테이너 안에서
bash scripts/ros_preflight.sh
bash scripts/build_engine.sh "$ISAAC_ROS_WS/isaac_ros_assets/models/yolov8/yolov8s.onnx" "$ISAAC_ROS_WS/isaac_ros_assets/models/yolov8/yolov8s.plan"
# 각각 별도 활성화된 컨테이너 터미널에서
bash scripts/run_ros.sh detect
bash scripts/run_ros.sh bag
bash scripts/run_ros.sh overlay
bash scripts/run_ros.sh view
```

자체 4클래스 모델은 기본 80클래스 launch에 바로 연결하지 않습니다. 실제 binding, 클래스 수, 전처리와 좌표 복원을 확인한 뒤 launch/decoder를 맞춰야 합니다. 엔진은 대상 GPU에서 생성합니다.

## 파일과 검증 증거

- `scripts/`: 설치, GPU/NMS 확인, 학습, 추적, 라벨 검사, 합성 자료, ONNX 검사 및 ROS 실행 도구
- `tests/`: 잘못된 라벨을 거부하는 회귀 테스트
- `reports/`: 실제 실행 기록과 완료된 단계의 수치
- `data/`, `datasets/`, `runs/`, `models/`: 재생성 가능한 로컬 산출물, Git 제외

공식 API 참고: [학습](https://docs.ultralytics.com/modes/train/), [추적](https://docs.ultralytics.com/modes/track/), [ONNX export](https://docs.ultralytics.com/modes/export/). 모델은 YOLOv8을 명시합니다. 외부 모델·데이터·패키지는 각각의 라이선스가 적용됩니다.
