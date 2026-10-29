#!/usr/bin/env bash
# Container-side receiver. Start sim/live_ros_camera.py on the host first.
set -euo pipefail
: "${ISAAC_ROS_WS:?Set ISAAC_ROS_WS}"
: "${1:?Usage: run_sim_ros_receiver.sh ENGINE OUTPUT [SECONDS]}"
: "${2:?Output directory required}"
engine=$1
output=$2
seconds=${3:-30}
script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
set +u
source /opt/ros/lyrical/setup.bash
set -u
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-75}
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
mkdir -p "$output"
setsid ros2 launch "$script_dir/../launch/pucks.launch.py" "engine_file_path:=$engine" > "$output/launch.log" 2>&1 &
pid=$!
cleanup() {
  kill -TERM -- "-$pid" 2>/dev/null || true
  sleep 2
  kill -KILL -- "-$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
}
trap cleanup EXIT
sleep 10
kill -0 "$pid"
python3 "$script_dir/verify_ros.py" --output "$output" --seconds "$seconds" --image-topic /pucks/processed_image --detection-topic /pucks/detections
