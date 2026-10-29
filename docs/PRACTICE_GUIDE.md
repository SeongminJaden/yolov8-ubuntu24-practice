# 처음부터 따라 하는 퍽 인식 실습

현재 장비의 프로젝트는 `/home/seongmin/Projects/yolov8-ubuntu24-practice`입니다. 모든 명령은 특별한 표시가 없으면 이 폴더에서 실행합니다. 먼저 1~3단계로 기존 모델을 사용해 보고, 4단계에서 직접 학습하세요. 실물 자료는 [라벨링·데이터 안내](DATASET_GUIDE.md), 수정 위치는 [코드 안내](CODE_GUIDE.md)를 참고하세요.

현재 생성기는 직육면체를 눕히고 6면에 같은 ID 태그를 붙입니다. 기존 `tagged-pucks-v4` 예제는 한 면 태그 구성입니다. 새 자료의 실시간 실행에는 `--prism-tag-mount six_faces`를 추가하세요. [6면 구성과 중심 모호성](TAGGED_PUCKS.md#6면-태그-보강-구성)을 먼저 확인하세요.

## 0. 무엇을 만드는가

| 기능 | 입력 | 결과 | 학습에 필요한 정답 |
|---|---|---|---|
| YOLO | RGB 영상 | 형상·색상, 사각형, 신뢰도 | 클래스와 2D 상자 |
| CenterPose | YOLO가 찾은 영역 | 중심 픽셀, 카메라 기준 3D 중심·회전 | 중심 및 8개 cuboid 꼭짓점의 영상 투영 |
| AprilTag | RGB 영상, 카메라 K, 태그 실측 크기 | 태그 ID, 태그 위치·회전 | 태그 검출기는 별도 학습하지 않음 |

직육면체는 30×30×60mm, 원기둥은 지름 30×높이 60mm입니다. 물체 중심과 윗면 태그 중심은 다릅니다. YOLO 상자의 중간을 3D 물체 중심으로 사용하지 않습니다. 현재 통합 AprilTag는 CPU Apriltags3, CenterPose는 맞춤 DLA34 crop 모델입니다.

## 1. 터미널과 파일 확인

```bash
cd /home/seongmin/Projects/yolov8-ubuntu24-practice
source .venv-yolo/bin/activate
python scripts/check_gpu.py
python -m unittest discover -s tests -v
ls data/tagged-pucks-v4/manifest.json \
   runs/detect/tagged_pucks_v4/weights/best.pt \
   models/centerpose-pucks-v4/best.pt
```

기대 결과: GPU 확인 성공, 테스트 통과, 세 파일 모두 존재. 이 컴퓨터에는 데이터와 모델이 있지만 **GitHub clone에는 포함되지 않습니다**. 새 컴퓨터는 README의 설치 후 4단계에서 자료와 모델을 생성해야 합니다. Isaac Sim은 별도 환경 `/home/seongmin/isaacsim6_venv`에 설치되어 있습니다. 이미 설치된 장비에서는 매번 `install.sh`를 실행하지 않습니다.

## 2. 한 장에서 세 기능 확인

출력 폴더가 있으면 덮어쓰지 않고 중단합니다. 매번 아래 첫 줄을 다시 실행하면 새 이름을 사용합니다. 같은 초에 재실행하지 마세요.

```bash
OUT="reports/practice-$(date +%Y%m%d-%H%M%S)"
python scripts/tagged_perception.py \
  --image data/tagged-pucks-v4/images/test/0001.png \
  --manifest data/tagged-pucks-v4/manifest.json \
  --yolo runs/detect/tagged_pucks_v4/weights/best.pt \
  --centerpose models/centerpose-pucks-v4/best.pt \
  --output "$OUT"
xdg-open "$OUT/overlay.jpg"
python -m json.tool "$OUT/perception.json"
```

`--image`만 같은 Sim 데이터의 다른 test 이미지로 바꾸어 보세요. 다른 카메라로 찍은 사진을 넣을 때는 그 카메라의 K로 manifest를 준비해야 합니다. 화면의 사각형은 YOLO, 자홍색 점은 CenterPose 중심, `tag=`는 연결된 AprilTag ID입니다. 전체 태그 목록은 JSON의 `tags`, 물체와 연결된 태그는 `objects[].apriltag`입니다.

| JSON 필드 | 읽는 법 |
|---|---|
| `shape`, `color` | `prism`/`cylinder`, `red`/`green` |
| `bbox_xyxy` | 원본 이미지의 왼쪽 위 x,y와 오른쪽 아래 x,y, 단위 px |
| `centerpose.center_px` | 예측 중심의 영상 좌표 |
| `centerpose.center_camera_m` | 카메라 기준 x,y,z, 단위 m; 예: z=0.45는 전방 450mm |
| `centerpose.valid` | 신뢰도·양의 깊이·재투영 오차 검사 결과; 실제 정확도 보장은 아님 |
| `apriltag.id` | 인쇄된 물리 태그 번호 |
| `apriltag.tag_center_camera_m` | 태그 표면 중심의 3D 위치 |
| `apriltag.tag_derived_object_center_camera_m` | 태그 위치와 알려진 부착 변환으로 계산한 물체 중심; CenterPose와 별도 |
| `association_status` | `matched`는 연결됨, `tag_not_visible`은 상자 안에 태그 후보 없음, `ambiguous*`는 대응 불명확 |

카메라 optical 좌표는 X 오른쪽, Y 아래쪽, Z 전방입니다. `apriltag: null`이면 해당 물체의 태그를 사용할 수 없습니다. 로봇 좌표로 바꾸려면 별도의 카메라→로봇 외부 보정이 필요합니다.

## 3. 기존 모델을 평가

시각적으로 잘 보이는 한 장과 전체 정확도는 다릅니다. 다음 두 평가를 따로 확인합니다.

```bash
RUN_ID=$(date +%Y%m%d-%H%M%S)
yolo detect val model=runs/detect/tagged_pucks_v4/weights/best.pt \
  data=data/tagged-pucks-v4/dataset.yaml split=test device=0 \
  project=runs/detect name="practice-eval-$RUN_ID"
python scripts/evaluate_tagged_perception.py \
  --manifest data/tagged-pucks-v4/manifest.json \
  --yolo runs/detect/tagged_pucks_v4/weights/best.pt \
  --centerpose models/centerpose-pucks-v4/best.pt \
  --output "reports/practice-eval-$RUN_ID"
```

YOLO: 클래스별 precision/recall, mAP50, mAP50–95와 오검출 이미지를 확인합니다. 통합 평가: `evaluation.json`의 `ground_truth_objects`, `centerpose_valid_poses`, 중심 오차 median/P95(mm), `tag_id_matches`, `tag_unexpected_ids`, `correct_associations`를 함께 봅니다. 유효한 출력에 한정된 오차가 작아도 미검출이 많으면 좋은 결과가 아닙니다.

회전은 대칭을 고려한 오차와 원래 축 기준 오차를 구분합니다. 원기둥은 축 방향으로 돌려도 형상이 같고 각기둥은 90도 대칭입니다. [기존 평가 결과](../reports/tagged-pucks-v4/RESULTS.md)는 개발 중 재사용한 내부 시험 자료에 대한 결과이며 실제 카메라 성능을 뜻하지 않습니다. 직접 튜닝할 때는 val을 보고, 마지막 확인용 새 test 세션을 따로 남기세요.

## 4. Isaac Sim 자료 생성 → 직접 학습

이 단계는 GPU와 디스크를 사용하며 오래 걸릴 수 있습니다. Sim 렌더와 모델 학습은 차례대로 실행해 GPU 메모리 경쟁을 피하세요. 다음 변수는 **같은 터미널에서** 이어서 사용합니다. 터미널을 바꾸면 실제 생성한 경로로 다시 지정하세요.

```bash
cd /home/seongmin/Projects/yolov8-ubuntu24-practice
RUN_ID=$(date +%Y%m%d-%H%M%S)
DATA="data/tagged-practice-$RUN_ID"
YOLO_NAME="tagged-practice-$RUN_ID"
CP_OUT="models/centerpose-practice-$RUN_ID"

df -h .
OMNI_KIT_ACCEPT_EULA=YES /home/seongmin/isaacsim6_venv/bin/python \
  sim/generate_tagged_pucks.py --output "$DATA" \
  --train 240 --val 60 --test 100 --video-frames 120
```

위 EULA 환경변수는 NVIDIA 라이선스에 동의한 환경에서 사용합니다. 처음에는 `--train 24 --val 8 --test 8 --video-frames 8`로 생성 흐름만 확인해도 됩니다. 소량 자료로 최종 정확도를 판단하지 마세요. 생성 성공 후 `COMPLETE`, `dataset.yaml`, `manifest.json`, `scene.usda`, `images`, `labels`가 생깁니다.

```bash
source .venv-yolo/bin/activate
python scripts/validate_labels.py "$DATA/labels" --classes 4
python scripts/train_yolo.py --data "$DATA/dataset.yaml" \
  --epochs 50 --batch 4 --device 0 --name "$YOLO_NAME"
python scripts/centerpose_pucks.py --manifest "$DATA/manifest.json" \
  --output "$CP_OUT" --epochs 100 --batch 16
```

YOLO가 출력한 실제 저장 경로를 확인하세요. 동일 `--name`이 있으면 `2`, `3` 등이 붙을 수 있습니다. 새 이름을 사용했다면 다음과 같습니다.

```bash
YOLO_WEIGHTS="runs/detect/$YOLO_NAME/weights/best.pt"
yolo detect val model="$YOLO_WEIGHTS" data="$DATA/dataset.yaml" split=test device=0
python scripts/evaluate_tagged_perception.py \
  --manifest "$DATA/manifest.json" --yolo "$YOLO_WEIGHTS" \
  --centerpose "$CP_OUT/best.pt" --output "reports/trained-$RUN_ID"
```

`best.pt`는 검증 자료로 선택한 모델입니다. YOLO `results.csv`/학습 그래프, CenterPose `history.json`의 train_loss와 val_loss를 확인하세요. train만 좋아지고 val이 나빠지면 과적합을 의심합니다. 여기서는 처음부터 다시 학습하므로 기존 모델의 여러 차례 미세조정 이력과 동일하지 않습니다.

기존 CenterPose를 초기값으로 추가 학습하려면 새 output과 `--resume models/centerpose-pucks-v4/best.pt`를 지정합니다. 이 옵션은 가중치만 읽으며 optimizer·epoch 상태를 복원하는 엄밀한 중단 재개가 아닙니다. YOLO 미세조정은 `--model 기존/best.pt`로 시작합니다.

## 5. Sim 카메라를 실시간으로 연결

먼저 현재 장비에 있는 모델·장면으로 시작합니다. 새 모델을 쓸 때는 아래 세 경로를 함께 바꾸세요. 깨끗한 호스트 터미널 두 개를 열고 ROS Lyrical을 source하지 않습니다.

터미널 A — Sim 카메라:

```bash
cd /home/seongmin/Projects/yolov8-ubuntu24-practice
OMNI_KIT_ACCEPT_EULA=YES /home/seongmin/isaacsim6_venv/bin/python \
  sim/live_ros_camera.py --scene data/tagged-pucks-v4/scene.usda \
  --seconds 180 --domain 76 --output "reports/camera-$(date +%Y%m%d-%H%M%S).json"
```

터미널 B — Sim이 로딩되어 영상 발행을 시작한 뒤:

```bash
cd /home/seongmin/Projects/yolov8-ubuntu24-practice
ROS_DOMAIN_ID=76 bash scripts/run_live_tagged.sh \
  --yolo runs/detect/tagged_pucks_v4/weights/best.pt \
  --centerpose models/centerpose-pucks-v4/best.pt \
  --tag-size 0.016 --seconds 60 \
  --output "reports/live-practice-$(date +%Y%m%d-%H%M%S)"
```

B의 출력 폴더에서 `first-rgb.png`, `first-perception.json`, `frames.jsonl`, `live-report.json`을 확인합니다. `passed_all_outputs`는 메시지와 세 기능 출력의 존재 검사입니다. 위치 정확도는 3단계의 GT 평가로 확인합니다. 실시간 결과는 `/pucks/perception`, `/pucks/centerpose/poses`로도 발행됩니다.

이 호스트 통합 경로에는 Docker가 필요하지 않습니다. NVIDIA GPU AprilTag 또는 TensorRT 경로는 [TAGGED_PUCKS.md](TAGGED_PUCKS.md), [README](../README.md)의 별도 컨테이너 실습입니다. 과거 검증 기록이 현재 컨테이너의 존재를 보장하지는 않습니다. 컨테이너를 삭제했다면 다시 준비해야 합니다.

## 6. 내 사진과 라벨로 학습

[DATASET_GUIDE.md](DATASET_GUIDE.md)의 구조로 `data/real-pucks-v1/`에 넣습니다. 먼저 YOLO만 학습·평가하고, 카메라 보정과 pose 정답이 준비되면 CenterPose를 확장하세요. AprilTag는 인쇄·부착 후 크기와 카메라 보정을 설정합니다. RealSense 연결 자체는 [REALSENSE.md](REALSENSE.md)를 따릅니다.

## 7. 자주 막히는 지점

| 증상 | 먼저 확인할 것 |
|---|---|
| `No such file`, 모델 없음 | 프로젝트 루트인지, Git clone만 한 환경인지, 실제 학습 출력 경로인지 |
| `Output exists`, `FileExistsError` | 출력 이름을 새로 지정; 기존 결과를 삭제할 필요 없음 |
| CUDA out of memory | Sim과 학습 동시 실행 중인지 확인, YOLO batch 4→2→1 / CenterPose 16→8→4 |
| 라벨 검사가 PASS인데 학습 오류 | 이미지·라벨 짝과 YAML path, split 폴더 확인; 숫자 검사만으로 파일 대응을 검증하지 않음 |
| 물체 색이 뒤바뀜 | 클래스 ID 순서, 색 증강, RGB/BGR 처리 확인 |
| 태그 ID는 맞는데 거리가 틀림 | 검은 경계 실측 크기, 해상도에 맞는 K, rectification 확인 |
| CenterPose 위치가 틀림 | 실물 크기·K·학습 도메인·코너 순서, `valid`와 재투영 오차 확인 |
| 실시간 paired_frames가 0 | Sim 로딩 완료, 동일 domain 76, timestamp/frame_id/해상도/QoS 확인 |
| 왜곡 입력 오류 | rectified RGB와 일치하는 CameraInfo 사용; D만 0으로 바꾸면 안 됨 |
| 실물 인식이 Sim보다 나쁨 | 실제 촬영 자료 추가, 조명·배경·거리별 평가; threshold만 낮춰 해결하지 않음 |

오늘 처음 시작한다면 1단계 → 2단계 → JSON 읽기까지 진행하세요. 그 다음 전체 평가, 소량 Sim 생성, 본 학습 순서로 확장하면 됩니다.
