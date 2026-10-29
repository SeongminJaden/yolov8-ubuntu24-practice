# RealSense 실물 카메라 연결 안내

**상태: 실장비 미연결·미검증.** 이 문서는 나중에 카메라를 연결할 때 실행할 절차입니다. 현재 저장소의 합성 이미지/Isaac Sim 결과는 실물 RealSense 인식 정확도나 USB 안정성을 검증한 결과가 아닙니다. 기준 환경은 Ubuntu 24.04, Isaac ROS 5.0, ROS Lyrical입니다.

## 1. 모델과 드라이버 조합 확인

카메라 모델명부터 확인하세요. [NVIDIA release-5.0 RealSense 설정](https://nvidia-isaac-ros.github.io/v/release-5.0/getting_started/sensors/realsense_setup.html)은 D455·D435i 지원과 D415 미지원을 명시하고, 그 예제 환경에 firmware 5.16.0.1 / librealsense v2.56.3 / realsense-ros r/4.56.3 조합을 요구합니다. **모델이 아직 지정되지 않았으므로 이 문서가 모든 RealSense 모델에 해당 firmware를 설치하라는 뜻은 아닙니다.** 모델·현재 firmware·지원 목록을 확인한 뒤 해당 모델의 공식 절차를 따르세요. D405 등 다른 모델은 스트림 파라미터와 지원 조건이 다를 수 있습니다.

호스트에서 카메라를 연결하기 전에 udev 규칙을 설치합니다. 저장소 루트에서 실행합니다.

```bash
mkdir -p work/realsense-setup
curl -fL https://raw.githubusercontent.com/realsenseai/librealsense/v2.56.3/config/99-realsense-libusb.rules \
  -o work/realsense-setup/99-realsense-libusb.rules
sudo install -m 0644 work/realsense-setup/99-realsense-libusb.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

기존 `~/.config/isaac-ros-cli/config.yaml` 설정에 아래 항목을 **병합**합니다. 파일 전체를 덮어쓰지 말고 기존 image keys와 mounts를 보존하세요.

```yaml
docker:
  image:
    additional_image_keys:
      - realsense
```

USB 3 포트와 데이터 케이블로 연결한 뒤 호스트에서 실행합니다. 실행 중 학습·ROS 작업은 먼저 정상 종료하세요. 새 이미지에 저장소 스크립트와 엔진이 보이도록 README의 workspace bind mount 구성을 유지합니다.

```bash
lsusb
lsusb -t
isaac-ros activate --build-local
```

첫 빌드 이후에는 `isaac-ros activate`를 사용합니다. 컨테이너에서 확인합니다.

```bash
source /opt/ros/lyrical/setup.bash
rs-enumerate-devices
ros2 pkg prefix realsense2_camera
```

출력에서 모델, serial, firmware, USB 연결 속도, 지원 color profile을 기록합니다. `realsense-viewer`로 확인했다면 ROS 카메라 노드를 시작하기 전에 스트리밍을 종료합니다.

### USB 장치 전달 확인

호스트에서는 보이는데 컨테이너에서는 보이지 않는다면 드라이버 재설치보다 장치 전달부터 확인합니다. 실제 컨테이너 이름으로 바꾸세요.

```bash
docker inspect isaac_ros_dev_container \
  --format 'privileged={{.HostConfig.Privileged}} devices={{json .HostConfig.Devices}} rules={{json .HostConfig.DeviceCgroupRules}} mounts={{json .Mounts}}'
docker exec isaac_ros_dev_container ls -l /dev/bus/usb
```

Isaac ROS CLI의 RealSense 이미지 구성과 카메라를 연결한 상태에서 새로 활성화하는 공식 경로를 우선 사용합니다. 직접 Docker를 구성한다면 RSUSB backend에는 `/dev/bus/usb` bind mount와 USB 문자 장치 접근 권한이 필요합니다. 대표적인 `docker run` 옵션은 `--mount type=bind,src=/dev/bus/usb,dst=/dev/bus/usb` 및 `--device-cgroup-rule='c 189:* rmw'`입니다. 이 두 옵션만으로 전체 Isaac ROS 컨테이너 구성이 끝나는 것은 아닙니다. GPU, workspace, DDS 네트워크 및 호스트 udev 사용자 권한도 유지해야 합니다. UVC backend라면 해당 `/dev/video*` 장치도 전달해야 합니다. 실행 중인 컨테이너에 `docker exec`로 장치를 추가할 수 없으므로 실행 구성을 바꾼 뒤 재생성합니다. 무작정 모든 장치를 `chmod 777`로 바꾸지 마세요.

## 2. 카메라만 실행하고 실제 토픽 확인

아래 예시는 일반 RGB 스트림이 있는 모델의 출발점입니다. `640x480x30`이 지원되는지 `rs-enumerate-devices`로 먼저 확인하세요. 모델별 파라미터는 [RealSense ROS 공식 문서](https://github.com/realsenseai/realsense-ros/tree/r/4.56.3)와 설치된 launch 도움말을 기준으로 합니다.

모든 터미널에서 같은 환경을 사용합니다. 여기서는 같은 컴퓨터의 컨테이너 내부 통신을 전제로 합니다.

```bash
source /opt/ros/lyrical/setup.bash
export ROS_DOMAIN_ID=74
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 launch realsense2_camera rs_launch.py --show-args
```

카메라 터미널:

```bash
ros2 launch realsense2_camera rs_launch.py \
  camera_namespace:=camera camera_name:=camera \
  enable_color:=true enable_depth:=false \
  rgb_camera.color_profile:=640x480x30
```

다른 터미널에서:

```bash
ros2 topic list -t
ros2 node list
ros2 topic info /camera/camera/color/image_raw -v
ros2 topic echo /camera/camera/color/camera_info --once
ros2 topic hz /camera/camera/color/image_raw
```

`/camera/camera/color/image_raw`와 `/camera/camera/color/camera_info`는 위 namespace/name의 예시입니다. 실제 발견된 이름을 사용하세요. 이미지 width/height/encoding, CameraInfo width/height/K/P, frame_id, timestamp와 QoS를 확인합니다. 카메라 인식만 성공하고 영상 Hz가 0이면 USB profile·권한·다른 프로세스의 카메라 점유부터 점검합니다.

## 3. 공식 COCO 데모와 퍽 모델은 별도 경로

먼저 카메라 연결 자체를 확인하려면 [공식 YOLOv8 RealSense quickstart](https://nvidia-isaac-ros.github.io/v/release-5.0/repositories_and_packages/isaac_ros_object_detection/isaac_ros_yolov8/index.html#run-launch-file)를 사용할 수 있습니다. 위에서 따로 켠 카메라 노드는 종료한 뒤 실행합니다. 이 launch가 카메라도 시작합니다.

```bash
sudo apt-get update
sudo apt-get install -y ros-lyrical-isaac-ros-examples ros-lyrical-isaac-ros-realsense
ros2 launch isaac_ros_examples isaac_ros_examples.launch.py \
  launch_fragments:=realsense_mono_rect,yolov8 \
  engine_file_path:="$ISAAC_ROS_WS/isaac_ros_assets/models/yolov8/yolov8s.plan"
```

별도 터미널:

```bash
ros2 run isaac_ros_yolov8 isaac_ros_yolov8_visualizer.py
```

이 경로는 COCO 80클래스 `yolov8s.plan`용입니다. 4클래스 퍽 엔진을 그대로 끼우면 decoder 클래스 수와 시각화 이름이 맞지 않습니다. 퍽 모델에는 다음 절차와 저장소의 `launch/pucks.launch.py`를 사용합니다.

## 4. 퍽 입력 계약과 해상도 변환

현재 퍽 launch는 다음 입력을 고정적으로 받습니다.

| 항목 | 값 |
| --- | --- |
| 이미지 | `/pucks/image`, `sensor_msgs/msg/Image`, RGB8, 640×640 |
| 보정 정보 | `/pucks/camera_info`, `sensor_msgs/msg/CameraInfo`, 640×640 |
| 동기화 | 두 메시지가 같은 timestamp와 optical frame_id 사용 |
| engine | `images [1,3,640,640]` → `output0 [1,8,8400]`, raw YOLO, NMS 미포함 |
| 클래스 순서 | red_cylinder, red_prism, green_cylinder, green_prism |
| 출력 | `/pucks/detections`, `/pucks/processed_image` |

**640×480 영상을 이름만 remap해서 넣으면 안 됩니다.** 실제 픽셀을 640×640으로 바꾸고 CameraInfo도 함께 변환해야 합니다. `scripts/publish_test_image.py`의 가상 CameraInfo는 파일 입력 smoke test용이므로 실카메라 보정을 대신하지 못합니다.

다음 adapter는 RGB raw 영상을 비등방 resize하는 최소 연결 예시입니다. 가로세로 비율이 바뀌므로 실제 모델 성능 평가에는 학습 때의 전처리와 일치하는지 확인해야 합니다. letterbox를 사용하려면 픽셀 padding과 K/P의 주점 이동, 원본 좌표 역변환을 함께 구현해야 합니다. 현재 예시에 letterbox나 왜곡 보정은 없습니다.

원본 크기 W×H에서 `sx=640/W`, `sy=640/H`입니다. OpenCV resize의 픽셀 중심 규약에 맞춰 affine 행렬 A를 적용합니다.

```text
A = [[sx, 0, (sx-1)/2], [0, sy, (sy-1)/2], [0, 0, 1]]
K_new = A @ K_old
P_new = A @ P_old
```

D와 R, distortion_model은 그대로 유지합니다. 아래 코드는 binning/ROI가 활성화된 입력을 거부하므로 해당 기능이 있으면 먼저 실제 유효 영상의 calibration을 정규화해야 합니다. raw 왜곡을 제거하려면 rectification과 그에 맞는 CameraInfo를 upstream에서 제공하세요.

컨테이너의 저장소 루트에서 아래 파일을 생성합니다. **예시 코드이며 실카메라 실행은 아직 하지 않았습니다.**

```bash
mkdir -p work
cat > work/realsense_square.py <<'PY'
import copy
import os
import cv2
import numpy as np
import rclpy
import message_filters
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, CameraInfo

class SquareInput(Node):
    def __init__(self):
        super().__init__('realsense_square_input')
        self.bridge = CvBridge()
        self.images = self.create_publisher(Image, '/pucks/image', 10)
        self.infos = self.create_publisher(CameraInfo, '/pucks/camera_info', 10)
        self.image_sub = message_filters.Subscriber(
            self, Image, os.environ.get('RS_IMAGE', '/camera/camera/color/image_raw'),
            qos_profile=qos_profile_sensor_data)
        self.info_sub = message_filters.Subscriber(
            self, CameraInfo, os.environ.get('RS_INFO', '/camera/camera/color/camera_info'),
            qos_profile=qos_profile_sensor_data)
        self.sync = message_filters.TimeSynchronizer([self.image_sub, self.info_sub], 20)
        self.sync.registerCallback(self.convert)

    def convert(self, image, info):
        if (image.width, image.height) != (info.width, info.height):
            raise RuntimeError('Image and CameraInfo dimensions differ')
        if image.header.frame_id != info.header.frame_id:
            raise RuntimeError('Image and CameraInfo optical frames differ')
        if info.k[0] <= 0 or info.k[4] <= 0:
            raise RuntimeError('Missing valid camera calibration')
        if (info.binning_x > 1 or info.binning_y > 1 or
                info.roi.x_offset or info.roi.y_offset or info.roi.width or info.roi.height):
            raise RuntimeError('Normalize ROI/binning calibration before this adapter')
        rgb = self.bridge.imgmsg_to_cv2(image, desired_encoding='rgb8')
        rgb = cv2.resize(rgb, (640, 640), interpolation=cv2.INTER_LINEAR)
        out = self.bridge.cv2_to_imgmsg(rgb, encoding='rgb8')
        out.header = copy.deepcopy(image.header)
        ci = copy.deepcopy(info)
        sx, sy = 640 / image.width, 640 / image.height
        a = np.array([[sx, 0, (sx-1)/2], [0, sy, (sy-1)/2], [0, 0, 1]])
        ci.k = (a @ np.array(info.k).reshape(3, 3)).ravel().tolist()
        ci.p = (a @ np.array(info.p).reshape(3, 4)).ravel().tolist()
        ci.width = ci.height = 640
        ci.header = copy.deepcopy(out.header)
        self.infos.publish(ci)
        self.images.publish(out)

rclpy.init()
node = SquareInput()
try:
    rclpy.spin(node)
except KeyboardInterrupt:
    pass
finally:
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
PY
python3 work/realsense_square.py
```

다른 namespace에서는 실제 토픽에 맞춰 실행합니다.

```bash
RS_IMAGE=/my_camera/color/image_raw RS_INFO=/my_camera/color/camera_info \
  python3 work/realsense_square.py
```

CameraInfo가 이미지와 같은 시각으로 도착하지 않으면 TimeSynchronizer는 발행하지 않습니다. 원본 timestamp와 QoS부터 확인하세요. 시각을 무시하고 다른 profile의 오래된 CameraInfo를 결합하면 안 됩니다.

## 5. 실물 퍽 추론과 기록

2절의 카메라 노드, 4절의 adapter를 실행한 상태에서 동일 ROS_DOMAIN_ID의 다른 터미널에서 시작합니다. 공식 COCO 카메라 launch와 동시에 실행하지 않습니다.

```bash
ros2 launch ./launch/pucks.launch.py \
  engine_file_path:="$ISAAC_ROS_WS/isaac_ros_assets/models/pucks/pucks.plan"
```

다른 터미널에서 입력과 결과를 확인합니다.

```bash
ros2 topic hz /pucks/image
ros2 topic echo /pucks/camera_info --once
python3 scripts/verify_ros.py --output "$ISAAC_ROS_WS/realsense-verification" \
  --seconds 30 --image-topic /pucks/processed_image --detection-topic /pucks/detections
```

검증기가 통과하려면 실제 검출과 시각화 프레임이 있어야 합니다. 영상은 정상인데 실물 퍽을 못 찾는 경우는 실제 데이터와 학습 데이터의 차이일 수 있습니다. confidence threshold만 낮춰 성공으로 처리하지 말고 조명·거리·배경·노출·색·시점을 포함한 실물 데이터로 평가하세요. 모델 weight와 ONNX/engine을 바꿀 때는 같은 클래스 순서를 유지하고 대상 GPU에서 engine을 재생성합니다.

현재 검출 상자는 640×640 영상 좌표입니다. 원본 영상 좌표로 돌릴 때는 위 affine의 역행렬을 적용합니다. 2D 상자만으로 실제 거리·로봇 좌표·6D 자세가 나오지 않습니다. 깊이 기반 위치가 필요하면 depth-to-color alignment, depth 단위, optical frame과 로봇 extrinsic calibration을 별도로 검증해야 합니다.

실장비 평가 기록에는 모델/firmware/SDK/wrapper 버전, 원본 profile·전처리, engine 식별값, 촬영 세션별 train/val/test 분리, 클래스별 precision/recall/mAP, 오검출 이미지와 처리율을 남깁니다. 단일 이미지 반복 publisher 또는 ROS 메시지 개수는 정확도 지표가 아닙니다.
