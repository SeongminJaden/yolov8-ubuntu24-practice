# Isaac Sim 생성·학습·평가·ROS 실행

실행 환경은 Ubuntu 24.04, RTX 5060 Laptop 8GB, Isaac Sim 6.1.0.0, 별도 YOLO 가상환경, Isaac ROS 5.0 / ROS Lyrical 컨테이너입니다. Sim은 bundled ROS Jazzy를 사용합니다. 실제 실행 결과는 [평가 보고서](../reports/SIM_EVALUATION.md)에 기록합니다. RealSense 연결 방법은 [REALSENSE.md](REALSENSE.md)에 있습니다.

## 1. 데이터 생성

Isaac Sim Python 환경과 YOLO 환경을 분리합니다. 이 장비의 Sim Python은 `/home/seongmin/isaacsim6_venv/bin/python`입니다. 다른 장비에서는 설치된 Isaac Sim Python 실행기로 바꾸세요. NVIDIA [라이선스](https://docs.omniverse.nvidia.com/platform/latest/common/NVIDIA_Omniverse_License_Agreement.html)를 읽고 동의한 경우에만 `OMNI_KIT_ACCEPT_EULA=YES`를 지정합니다.

저장소 루트에서:

```bash
export SIM_PYTHON=/home/seongmin/isaacsim6_venv/bin/python
OMNI_KIT_ACCEPT_EULA=YES "$SIM_PYTHON" sim/generate_dataset.py \
  --output data/isaac-pucks-v1 --train 160 --val 40 --test 80 --video-frames 120
source .venv-yolo/bin/activate
python scripts/validate_labels.py data/isaac-pucks-v1/labels --classes 4
```

기존 출력 디렉터리는 덮어쓰지 않습니다. 재실행 시 새 이름을 사용하세요. 렌더러는 실제 RTX RaytracedLighting이며 RGB와 `bounding_box_2d_tight` 라벨을 저장합니다. 원기둥·각기둥 각각 빨강/초록 4클래스, 테이블, 구형 방해물을 USD로 만듭니다. 정상·어두움·밝음·가림·낮은 카메라 각도 조건을 사용하며 매 11번째 장면은 대상 없는 음성 샘플입니다. 조명 수치 등 정확한 범위는 `sim/generate_dataset.py`에 고정되어 있습니다.

train/val/test는 각각 seed 1000/3000/5000부터 시작하고, 영상은 seed 10000을 씁니다. `manifest.json`에 샘플별 seed·조건·상자·세션을 기록합니다. 시험은 학습과 같은 절차적 장면 분포의 다른 배치이며, 새로운 실물·배경 일반화를 검증하지 않습니다. SHA256 중복과 세션 교차를 검사합니다. 영상은 위치를 수식으로 움직인 120프레임이며 물리 엔진으로 낙하·접촉을 검증하는 예제가 아닙니다.

`scene.usda`는 마지막 장면 스냅샷입니다. Isaac Sim GUI의 File → Open에서 열고 `/World/Camera` 뷰를 선택하면 장면을 볼 수 있습니다. 데이터셋과 영상 생성은 위 Python 스크립트가 수행합니다. GUI에서 연 장면만으로 생성 작업이 자동 재실행되지는 않습니다.

## 2. 학습 및 독립 평가

```bash
python scripts/train_yolo.py --data data/isaac-pucks-v1/dataset.yaml \
  --epochs 50 --batch 4 --device 0 --name isaac_pucks_v1
export SIM_WEIGHTS=runs/detect/isaac_pucks_v1/weights/best.pt
python scripts/evaluate_sim.py --weights "$SIM_WEIGHTS" \
  --data data/isaac-pucks-v1/dataset.yaml --output reports/sim-trained --device 0
python scripts/evaluate_sim_conditions.py --weights "$SIM_WEIGHTS" \
  --data data/isaac-pucks-v1/dataset.yaml --output reports/sim-conditions --device 0
python scripts/evaluate_sim_video.py --weights "$SIM_WEIGHTS" \
  --manifest data/isaac-pucks-v1/manifest.json --output reports/sim-video --device 0
python scripts/export_onnx.py --weights "$SIM_WEIGHTS" --output models/isaac_pucks.onnx
```

기존 `reports/sim-*`가 있으면 새 출력 이름을 사용하세요. 학습 경로 역시 자동 증가할 수 있으므로 콘솔에 출력된 실제 경로를 `SIM_WEIGHTS`로 지정하세요. 평가기는 test만 평가하고 학습·임계값 튜닝을 수행하지 않습니다. precision/recall은 Ultralytics의 최대 F1 지점, 음성 샘플 오검출·영상 추적은 confidence 0.25 기준입니다. 검출 지연시간은 파일 읽기부터 후처리까지, 추적 지연시간은 이미 읽은 배열 입력부터 추적 후처리까지 측정하므로 두 FPS를 직접 비교하지 마세요. 렌더링·ROS·영상 저장 시간은 이 FPS에 포함되지 않습니다.

영상 평가는 클래스별 물체가 하나라는 전제에서 같은 클래스·IoU ≥ 0.5로 대응시킵니다. ID 전환 수와 추적률을 기록하며 표준 MOTChallenge IDF1/HOTA는 계산하지 않습니다. 여러 동일 클래스 물체를 추가하려면 GT instance ID 기반 평가기로 확장해야 합니다.

## 3. 실제 Sim 카메라 → Isaac ROS

먼저 README의 Isaac ROS 설치를 완료합니다. 호스트 공유 폴더와 컨테이너 경로가 대응해야 합니다.

```bash
# 호스트, 본인의 공유 폴더 경로로 설정
export ISAAC_ROS_WS=/absolute/path/to/isaac_ros-dev
mkdir -p "$ISAAC_ROS_WS/practice" "$ISAAC_ROS_WS/isaac_ros_assets/models/pucks"
cp -r scripts launch "$ISAAC_ROS_WS/practice/"
cp models/isaac_pucks.onnx "$ISAAC_ROS_WS/isaac_ros_assets/models/pucks/"
isaac-ros activate
```

컨테이너에서 해당 GPU에 맞춰 엔진을 만듭니다:

```bash
cd /workspaces/isaac_ros-dev
bash practice/scripts/build_engine.sh \
  isaac_ros_assets/models/pucks/isaac_pucks.onnx \
  isaac_ros_assets/models/pucks/isaac_pucks.plan
```

**별도의 깨끗한 호스트 터미널**에서 저장소 루트로 이동하고 Sim을 시작합니다. 이 터미널에서는 컨테이너 Lyrical setup을 source하지 마세요. 스크립트가 Isaac Sim bundled Jazzy 라이브러리와 Fast DDS를 설정합니다.

```bash
OMNI_KIT_ACCEPT_EULA=YES /home/seongmin/isaacsim6_venv/bin/python \
  sim/live_ros_camera.py --scene data/isaac-pucks-v1/scene.usda \
  --seconds 120 --domain 75
```

`NATIVE CAMERA GRAPH READY`가 출력되면 컨테이너 터미널에서:

```bash
export ROS_DOMAIN_ID=75
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
bash /workspaces/isaac_ros-dev/practice/scripts/run_sim_ros_receiver.sh \
  /workspaces/isaac_ros-dev/isaac_ros_assets/models/pucks/isaac_pucks.plan \
  /workspaces/isaac_ros-dev/sim-live-verification 40
```

동시에 다른 컨테이너 터미널에서 카메라 수신도 검사할 수 있습니다:

```bash
source /opt/ros/lyrical/setup.bash
export ROS_DOMAIN_ID=75 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
python3 /workspaces/isaac_ros-dev/practice/scripts/verify_sim_camera.py \
  --output /workspaces/isaac_ros-dev/sim-live-verification --seconds 12
```

640×640 RGB `/pucks/image`, CameraInfo `/pucks/camera_info`가 같은 stamp/frame_id로 발행됩니다. 24mm 초점거리와 20.955mm aperture에서 fx/fy는 약 732.999px입니다. CameraInfo는 USD 카메라에서 native 노드가 생성합니다. 출력은 `/pucks/detections`, `/pucks/processed_image`입니다. 컨테이너는 host networking을 사용합니다. 두 ROS 배포판 간 모든 기능의 호환을 의미하지 않으며 이 이미지·CameraInfo·검출 경로만 실제 검증합니다.

수신 스크립트는 검출 메시지·객체·오버레이 이미지가 모두 있어야 성공합니다. `sim-live-camera.json`의 렌더 루프 완료만으로 ROS 성공을 주장하지 않습니다. 카메라 연결이 안 되면 도메인, host network, 두 터미널의 ROS 환경, `launch.log`를 확인하세요. 동일 domain에서 기존 이미지 발행기는 종료하여 입력이 섞이지 않게 합니다.

## 공식 참고

- [Isaac Sim scene-based synthetic data generation](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/replicator_tutorials/tutorial_replicator_scene_based_sdg.html)
- 설치된 Isaac Sim 6.1의 `isaacsim.ros2.nodes` OGN 스키마 및 카메라 테스트를 기준으로 native camera graph를 구성했습니다.
- Isaac ROS 환경 및 decoder 정수 좌표 변환은 저장소 README를 참고하세요.
