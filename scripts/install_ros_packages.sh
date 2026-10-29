#!/usr/bin/env bash
# Execute only inside the activated Isaac ROS 5.0 container.
set -euo pipefail
test "${ROS_DISTRO:-}" = lyrical || { echo 'Isaac ROS Lyrical container required'; exit 1; }
sudo apt-get update
sudo apt-get install -y curl jq tar \
  ros-lyrical-isaac-ros-yolov8 \
  ros-lyrical-isaac-ros-dnn-image-encoder \
  ros-lyrical-isaac-ros-tensor-rt \
  ros-lyrical-isaac-ros-examples \
  ros-lyrical-rqt-image-view
sudo apt-get clean
set +u
source /opt/ros/lyrical/setup.bash
set -u
ros2 pkg prefix isaac_ros_yolov8
