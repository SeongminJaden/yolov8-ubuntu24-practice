#!/usr/bin/env bash
set -euo pipefail
: "${ISAAC_ROS_WS:?Activate Isaac ROS container first}"
set +u
source /opt/ros/lyrical/setup.bash
set -u
a="$ISAAC_ROS_WS/isaac_ros_assets"
case "${1:-}" in
 detect) ros2 launch isaac_ros_examples isaac_ros_examples.launch.py launch_fragments:=yolov8 interface_specs_file:="$a/isaac_ros_yolov8/quickstart_interface_specs.json" engine_file_path:="$a/models/yolov8/yolov8s.plan" ;;
 bag) ros2 bag play -l "$a/isaac_ros_yolov8/quickstart.bag" ;;
 overlay) ros2 run isaac_ros_yolov8 isaac_ros_yolov8_visualizer.py ;;
 view) ros2 run rqt_image_view rqt_image_view /yolov8_processed_image ;;
 *) echo 'Usage: run_ros.sh detect|bag|overlay|view'; exit 2 ;;
esac
