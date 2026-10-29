#!/usr/bin/env bash
set -euo pipefail
: "${SIM_VENV:=/home/seongmin/isaacsim6_venv}"
base="$SIM_VENV/lib/python3.12/site-packages/isaacsim/exts/isaacsim.ros2.core/jazzy"
test -d "$base/lib"
export LD_LIBRARY_PATH="$base/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$base/rclpy${PYTHONPATH:+:$PYTHONPATH}"
export ROS_DISTRO=jazzy ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-75}
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
exec "$root/.venv-yolo/bin/python" "$root/scripts/live_tagged_perception.py" "$@"
