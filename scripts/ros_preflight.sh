#!/usr/bin/env bash
set -euo pipefail
: "${ISAAC_ROS_WS:?Set ISAAC_ROS_WS to the activated container workspace}"
test "${ROS_DISTRO:-}" = lyrical || { echo 'Activate Isaac ROS 5.0 Lyrical container first'; exit 1; }
set +u
source /opt/ros/lyrical/setup.bash
set -u
nvidia-smi
ros2 pkg prefix isaac_ros_yolov8
ros2 pkg prefix isaac_ros_examples
test -x /usr/src/tensorrt/bin/trtexec
test -f "$ISAAC_ROS_WS/isaac_ros_assets/isaac_ros_yolov8/quickstart_interface_specs.json"
test -d "$ISAAC_ROS_WS/isaac_ros_assets/isaac_ros_yolov8/quickstart.bag"
