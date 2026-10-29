# 실규격 퍽: 형상·색상·중심·AprilTag

처음 실습하는 경우 [단계별 실습](PRACTICE_GUIDE.md)부터 시작하세요. 직접 라벨링한 자료는 [데이터 준비](DATASET_GUIDE.md), 변경할 코드 위치는 [코드 안내](CODE_GUIDE.md)에 정리했습니다.

## 6면 태그 보강 구성

현재 생성기 기본값은 **눕힌 직육면체의 6면 중앙에 같은 ID 태그**, 원기둥은 윗면 태그입니다. 각 물체는 서로 다른 ID를 사용합니다. `--prism-tags top`은 과거의 끝면 한 장 구성을 재현합니다. 아래 과거 v4 평가와 모델은 한 면 태그 자료에서 얻은 결과입니다.

이미지 추론·평가는 manifest의 `prism_tag_mount`를 읽습니다. 실시간에서는 **`--prism-tag-mount six_faces`**를 지정하세요. 같은 물체에서 같은 ID가 여러 번 보이면 가장 큰 영상 면적의 태그를 연결 대표로 선택하고, 전체 검출은 `tags`에 유지합니다. 같은 ID가 여러 물체 상자에 연결되는 경우는 여전히 ambiguous로 거부합니다.

6면 동일 ID는 물체 ID를 알려주지만 어느 면인지는 알려주지 않습니다. 따라서 `tag_derived_object_center_camera_m`는 이 모드에서 null이며 15.03mm/30.03mm 법선 이동 후보를 `object_center_candidates_camera_m`에 제공합니다. 독립적으로 계산된 CenterPose 중심과 태그 자체 위치는 정상 출력합니다. 태그만으로 모호성 없는 중심·자세가 필요하면 면별 ID 또는 별도 면 식별 방법이 필요합니다. 원기둥도 검출 단계에서는 클래스가 알려지지 않으므로 이 모드의 독립 태그 목록은 동일하게 보수적인 후보를 제공합니다.

생성기의 `--seed-base`와 split 수량으로 서로 겹치지 않는 seed 구간을 만듭니다. 별도 생성 실행끼리도 seed 구간을 겹치지 않게 지정하세요. 과거 고정 seed 시작값(1000/3000/5000)은 train 8000에서 val/test와 겹쳤으며 해당 결과는 독립 시험으로 사용할 수 없습니다.

## 물체 및 출력 계약

| 항목 | 규격 / 결과 |
|---|---|
| 직육면체 | 30×30×60mm. 정육면체가 아니라 정사각 단면의 각기둥 |
| 원기둥 | 지름 30mm, 높이 60mm |
| 색상 | 빨강·초록 모두 학습; 어떤 형상이든 두 색 가능 |
| YOLO | red_cylinder / red_prism / green_cylinder / green_prism → shape와 color 별도 출력 |
| CenterPose | 기하학적 물체 중심의 영상 좌표 및 카메라 좌표계 3D 중심·회전 |
| AprilTag | family / id / 코너 영상 좌표 / 태그 중심 3D 위치·회전 |

길이는 출력에서 m, 평가 보고서에서는 mm입니다. 물체 좌표 원점은 기하학적 중심이며 60mm 축이 local Z입니다. 카메라 optical frame은 X 오른쪽, Y 아래쪽, Z 전방입니다. 태그 중심, 물체 기하 중심, YOLO 상자 중심은 서로 다릅니다.

태그 부착 사양은 아직 실물 확인 전이므로 **tag36h11, 검은 경계 16mm, 흰 여백 포함 20mm, 윗면 중앙**을 기본값으로 사용했습니다. 20mm 정사각형의 대각선은 약 28.3mm여서 지름 30mm 윗면에 들어갑니다. 검은 경계 20mm에 흰 여백까지 더하면 원기둥 윗면에서 벗어날 수 있습니다. 실제 인쇄 시 자동 페이지 맞춤을 끄고 검은 경계 크기를 실측해야 합니다. 다른 크기·면으로 부착하면 카메라 PnP의 tag-size와 태그→물체 변환도 변경하세요.

`configs/tagged-pucks.json`은 현재 사양 기록입니다. 실행 파라미터를 자동으로 덮어쓰는 설정 로더는 아닙니다. 물체는 정확한 크기로 생성하며 랜덤 크기 증강을 하지 않습니다. 태그 ID는 장면마다 0–15에서 서로 다르게 선택해 색·형상과 ID의 고정 상관을 없앴습니다. 영상 한 세션에서는 ID가 유지됩니다. 동일 장면에 같은 ID를 중복해서 붙이지 마세요.

인쇄용 [ID 0](../assets/apriltags/tag36h11-0-16mm.svg), [ID 1](../assets/apriltags/tag36h11-1-16mm.svg) SVG를 제공합니다. 다른 ID는 `python scripts/make_apriltag.py --id 2 --output tag2.svg`로 생성하세요. SVG를 실제 크기(100%)로 출력한 뒤 검은 경계를 실측하세요.

## 실행 구성

`tagged_perception.py`는 한 RGB 이미지에 YOLO, CenterPose, Apriltags3 detector (pupil-apriltags) + OpenCV PnP를 실행합니다. CenterPose는 NVIDIA TAO의 **실제 DLA34 아키텍처**를 사용하며 저장소의 `third_party/centerpose`에 원본 commit과 라이선스를 기록했습니다. 퍽 YOLO ROI를 128px로 자르고, 학습된 중심 heatmap·중심 offset·8개 cuboid 꼭짓점을 예측한 뒤 알려진 30×30×60mm 경계 상자로 PnP를 풉니다.

이것은 **맞춤 crop 학습/추론 경로**입니다. TAO CLI 학습을 실행한 결과나 Isaac ROS CenterPose 기본 decoder에 그대로 넣을 수 있는 모델이 아닙니다. hm/hps/reg head만 학습하며 다른 head는 사용하지 않습니다. 초기 40 epoch 뒤 형상의 90도 축 대칭을 고려하는 일관된 꼭짓점 순열 손실로 60 epoch를 추가 학습하고, 흰 여백 렌더를 수정한 데이터에서 30 epoch 미세조정했습니다. 태그로 계산한 물체 중심을 CenterPose 결과에 넣지 않습니다.

원기둥은 연속 축 대칭, 각기둥은 90도 축 대칭을 갖습니다. 표면 태그 없이 형상만으로 고유한 축 회전각을 결정할 수 없습니다. 태그가 보이면 태그 방향을 별도로 사용할 수 있습니다. CenterPose 회전 오차는 원래 축 기준과 대칭을 고려한 값을 구분해서 해석해야 합니다.

## 재현 명령

기존 디렉터리는 덮어쓰지 않으므로 재실행 때 새로운 출력 이름을 지정하세요. Isaac Sim 라이선스에 동의한 환경에서 저장소 루트 기준:

```bash
OMNI_KIT_ACCEPT_EULA=YES /home/seongmin/isaacsim6_venv/bin/python \
  sim/generate_tagged_pucks.py --output data/tagged-pucks-v4 \
  --train 240 --val 60 --test 100 --video-frames 120
source .venv-yolo/bin/activate
python -m pip install -r requirements-pose.txt
python scripts/train_yolo.py --data data/tagged-pucks-v4/dataset.yaml \
  --epochs 50 --batch 4 --device 0 --name tagged_pucks_v4
python scripts/centerpose_pucks.py --manifest data/tagged-pucks-v4/manifest.json \
  --output models/centerpose-pucks-sym-new --epochs 100 --batch 16
```

현재 최종 코드는 처음부터 대칭 손실을 사용합니다. 저장된 실험은 초기 40 + 대칭 손실 60 + 흰 여백 수정 데이터 30 epoch의 이력을 사용했습니다. YOLO 역시 초기 50 + 수정 데이터 30 epoch입니다. 위 명령은 수정 데이터에서 처음부터 학습하는 방법으로, 동일 학습 이력을 재현하지 않습니다. 저장된 실험의 체크포인트 선택·평가 근거는 [결과](../reports/tagged-pucks-v4/RESULTS.md)를 참고하세요. checkpoint는 `.pt`이며 로컬 모델 폴더에 있습니다. 학습 중 best는 val loss로 선택하고 test로 선택하지 않습니다.

```bash
python scripts/tagged_perception.py \
  --image data/tagged-pucks-v4/images/test/0001.png \
  --manifest data/tagged-pucks-v4/manifest.json \
  --yolo runs/detect/tagged_pucks_v4/weights/best.pt \
  --centerpose models/centerpose-pucks-v4/best.pt \
  --output reports/tagged-example-new
python scripts/evaluate_tagged_perception.py \
  --manifest data/tagged-pucks-v4/manifest.json \
  --yolo runs/detect/tagged_pucks_v4/weights/best.pt \
  --centerpose models/centerpose-pucks-v4/best.pt \
  --output reports/tagged-evaluation-new
```

단일 이미지 추론은 manifest에서 카메라 내부 파라미터와 태그 크기만 읽습니다. 정답 pose/ID는 추론에 사용하지 않습니다. 전체 평가는 별도의 test 라벨로 오차를 계산합니다. 입력은 왜곡이 제거된 RGB와 그 RGB에 맞는 K여야 합니다.

## 실시간 Sim 카메라 입력

첫 번째 호스트 터미널:

```bash
OMNI_KIT_ACCEPT_EULA=YES /home/seongmin/isaacsim6_venv/bin/python \
  sim/live_ros_camera.py --scene data/tagged-pucks-v4/scene.usda \
  --seconds 120 --domain 76 --output reports/tagged-camera-new.json
```

다른 호스트 터미널에서:

```bash
ROS_DOMAIN_ID=76 bash scripts/run_live_tagged.sh \
  --yolo runs/detect/tagged_pucks_v4/weights/best.pt \
  --centerpose models/centerpose-pucks-v4/best.pt \
  --seconds 60 --output reports/tagged-live-new
```

launcher는 YOLO venv에 Isaac Sim bundled Jazzy의 rclpy·공유 라이브러리를 연결합니다. Sim 설치 위치가 다르면 `SIM_VENV`를 지정하세요. ROS Lyrical을 source한 터미널과 혼용하지 마세요. 컨테이너를 재설치하거나 Torch를 컨테이너에 복사할 필요가 없습니다.

- 입력 `/pucks/image` + `/pucks/camera_info`: stamp·frame_id가 같은 쌍만 추론합니다.
- 출력 `/pucks/perception` (`std_msgs/String` JSON): stamp, frame_id, shape, color, YOLO bbox/confidence, CenterPose, AprilTag, association_status.
- 출력 `/pucks/centerpose/poses` (`geometry_msgs/PoseArray`): 유효 CenterPose 위치·회전. 개체 식별은 JSON을 함께 사용하세요.
- 로컬 `frames.jsonl`과 `live-report.json`: 실제 처리 프레임과 결과 기록. 수신 개수는 정확도 지표가 아닙니다.

태그 중심이 한 YOLO 상자 안에 있고 다른 물체와 중복 대응하지 않을 때만 연결합니다. 가림·여러 후보·중복 대응은 null/ambiguous로 반환합니다. 태그가 없어도 YOLO/CenterPose는 실행합니다. 잘못된 과거 태그 ID를 새 물체에 유지하지 않습니다. `centerpose.valid`는 수치·깊이·재투영 검사 통과를 뜻하며 실제 3D 정확도 보증이 아닙니다.

## Isaac ROS 패키지와 RealSense

이 장비의 Isaac ROS 컨테이너에 CenterPose·AprilTag 5.0 패키지를 설치했습니다. **이번 통합 경로의 AprilTag 구현은 Apriltags3 CPU + OpenCV PnP이며 NVIDIA CUDA AprilTag 성능 검증과 다릅니다.** `launch/tagged_apriltag.launch.py`는 동일 토픽에 연결하는 별도 GPU 경로 예제로, 실행 검증 여부는 결과 보고서를 따릅니다. 기본 CenterPose 신발 모델은 퍽 학습 모델로 쓸 수 없습니다.

RealSense 연결 후에는 [REALSENSE.md](REALSENSE.md)를 따라 카메라를 연결하고, rectified RGB와 같은 해상도의 실제 CameraInfo를 `/pucks/image`, `/pucks/camera_info`로 전달하세요. 이 통합 노드는 왜곡이 남은 입력을 거부합니다. Sim K를 실물 카메라에 복사하지 마세요. 실제 크기·태그 부착 변환·RGB/depth 정렬을 측정하고 새 촬영 세션으로 평가해야 합니다.

태그의 local Z가 표면 바깥쪽일 때, 윗면 중앙의 물체 중심은 `p_object = p_tag - R_tag[:,2] × 0.03003m`입니다. 0.03mm는 시뮬레이션 표면 분리를 위한 값이며 실제 스티커 두께/부착 위치로 바꿔야 합니다. 실물 카메라가 로봇 기준 좌표를 출력하려면 별도의 camera→robot 외부 보정이 필요합니다.

## 참고

- [NVIDIA CenterPose 학습과 데이터](https://docs.nvidia.com/tao/tao-toolkit/latest/text/cv_finetuning/pytorch/centerpose/centerpose.html)
- [Isaac ROS CenterPose](https://nvidia-isaac-ros.github.io/repositories_and_packages/isaac_ros_pose_estimation/isaac_ros_centerpose/index.html)
- [Isaac ROS AprilTag](https://nvidia-isaac-ros.github.io/repositories_and_packages/isaac_ros_apriltag/isaac_ros_apriltag/index.html)

AprilTag CPU detector: [pupil-apriltags 공식 저장소](https://github.com/pupil-labs/apriltags). 검증 세트에서 기존 OpenCV detector보다 ID 검출률이 높아 최종 경로로 선택했습니다.

### NVIDIA GPU AprilTag 경로 재실행

컨테이너에서 추가 패키지를 설치하고, 저장소의 `scripts`와 `launch`를 공유 workspace의 `practice`로 복사한 상태에서 다음을 실행합니다. 호스트 Sim·통합 노드도 같은 domain 76에서 실행 중이어야 합니다.

```bash
sudo apt-get update
sudo apt-get install -y ros-lyrical-isaac-ros-centerpose ros-lyrical-isaac-ros-apriltag
source /opt/ros/lyrical/setup.bash
export ROS_DOMAIN_ID=76 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 launch /workspaces/isaac_ros-dev/practice/launch/tagged_apriltag.launch.py
```

다른 컨테이너 터미널에서 같은 ROS 환경을 설정하고:

```bash
python3 /workspaces/isaac_ros-dev/practice/scripts/verify_tagged_topics.py \
  --output /workspaces/isaac_ros-dev/tagged-topic-verification.json --seconds 40
```

이 경로는 NVIDIA CUDA AprilTag와 통합 JSON 메시지의 실제 수신을 확인합니다. 호스트 통합 노드는 CPU Apriltags3 결과를 사용하며 GPU 태그 결과를 대신 혼합하지 않습니다. 두 경로의 정확도·지연시간은 별도로 평가해야 합니다.
