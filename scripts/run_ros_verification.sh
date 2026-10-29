#!/usr/bin/env bash
# Run inside the Isaac ROS container. All child processes have private sessions.
set -euo pipefail
set +m

usage() {
  cat <<'USAGE'
Usage: run_ros_verification.sh [--output DIRECTORY] [--seconds N] [--startup-seconds N]
Requires ISAAC_ROS_WS, ROS Lyrical, the official quickstart bag/interface specs,
and isaac_ros_assets/models/yolov8/yolov8s.plan in the container.
Logs are retained in OUTPUT/logs/run.XXXXXXXX even on failure.
USAGE
}
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
output="$script_dir/../reports/ros-$(date -u +%Y%m%dT%H%M%SZ)"
seconds=30
startup_seconds=10
while (($#)); do
  case "$1" in
    --output|--seconds|--startup-seconds)
      (($# >= 2)) || { echo "Missing value for $1" >&2; exit 2; }
      case "$1" in
        --output) output="$2" ;;
        --seconds) seconds="$2" ;;
        --startup-seconds) startup_seconds="$2" ;;
      esac
      shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ "$seconds" =~ ^[1-9][0-9]*$ && "$startup_seconds" =~ ^[0-9]+$ ]] || {
  echo 'Seconds must be a positive integer; startup seconds must be nonnegative.' >&2
  exit 2
}
# Bound arithmetic and ensure a typo cannot run an unattended check for days.
((${#seconds} <= 4 && ${#startup_seconds} <= 3)) || exit 2
seconds=$((10#$seconds))
startup_seconds=$((10#$startup_seconds))
: "${ISAAC_ROS_WS:?Run inside the configured Isaac ROS container with ISAAC_ROS_WS set}"
[[ -r /opt/ros/lyrical/setup.bash ]] || {
  echo 'ROS Lyrical setup missing; run this script inside the Isaac ROS container.' >&2
  exit 1
}
# ROS environment hooks are not guaranteed to support nounset.
set +u
source /opt/ros/lyrical/setup.bash
set -u
for command in ros2 python3 setsid timeout; do
  command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; exit 1; }
done
assets="$ISAAC_ROS_WS/isaac_ros_assets"
engine="$assets/models/yolov8/yolov8s.plan"
specs="$assets/isaac_ros_yolov8/quickstart_interface_specs.json"
bag="$assets/isaac_ros_yolov8/quickstart.bag"
for file in "$engine" "$specs" "$bag/metadata.yaml" "$script_dir/verify_ros.py"; do
  [[ -s "$file" ]] || { echo "Missing or empty required file: $file" >&2; exit 1; }
done
mkdir -p -- "$output/logs"
output="$(cd -- "$output" && pwd)"
logs="$(mktemp -d "$output/logs/run.XXXXXXXX")"
echo "Verification output: $output"
echo "Process logs: $logs"
pids=()
names=()
cleanup() {
  local status=$? pid alive attempt
  trap - EXIT INT TERM
  # Negative PIDs address only the sessions/process groups created below.
  for pid in "${pids[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for attempt in {1..20}; do
    alive=0
    for pid in "${pids[@]}"; do
      if kill -0 -- "-$pid" 2>/dev/null; then alive=1; fi
    done
    ((alive)) || break
    sleep 0.1
  done
  for pid in "${pids[@]}"; do
    kill -KILL -- "-$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
  printf 'exit_code=%s\n' "$status" > "$logs/status.txt"
  if ((status)); then echo "FAIL (exit $status). Logs preserved: $logs" >&2; fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
start() {
  local name=$1
  shift
  # Job control stays disabled so setsid does not fork and $! is the PGID.
  setsid "$@" > "$logs/$name.log" 2>&1 &
  pids+=("$!")
  names+=("$name")
}
check_services() {
  local i rc
  for i in 0 1 2; do
    if ! kill -0 "${pids[$i]}" 2>/dev/null; then
      rc=0
      wait "${pids[$i]}" || rc=$?
      echo "${names[$i]} exited unexpectedly (exit $rc); see $logs/${names[$i]}.log" >&2
      exit 1
    fi
  done
}
start detector ros2 launch isaac_ros_examples isaac_ros_examples.launch.py \
  launch_fragments:=yolov8 "interface_specs_file:=$specs" "engine_file_path:=$engine"
start bag ros2 bag play -l "$bag"
start visualizer ros2 run isaac_ros_yolov8 isaac_ros_yolov8_visualizer.py
for ((elapsed=0; elapsed<startup_seconds; elapsed++)); do
  check_services
  sleep 1
done
check_services
# timeout also bounds recorder shutdown/import hangs beyond its recording window.
start recorder timeout --signal=TERM --kill-after=5s "$((seconds + 15))s" \
  python3 "$script_dir/verify_ros.py" --output "$output" --seconds "$seconds"
recorder=${pids[3]}
while kill -0 "$recorder" 2>/dev/null; do
  check_services
  sleep 1
done
rc=0
wait "$recorder" || rc=$?
case "$rc" in
  0) check_services; echo "PASS: ROS detections and rendered images verified. Report: $output/ros-verification.json" ;;
  124|137) echo "FAIL: recorder timed out after $((seconds + 15)) seconds (plus kill grace). See $logs/recorder.log" >&2; exit "$rc" ;;
  *) echo "FAIL: recorder exited $rc. See $logs/recorder.log" >&2; exit "$rc" ;;
esac
