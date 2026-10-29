#!/usr/bin/env bash
set -euo pipefail
: "${1:?Usage: build_engine.sh model.onnx model.plan}"
: "${2:?Supply output engine path}"
test -f "$1"
/usr/src/tensorrt/bin/trtexec --onnx="$1" --saveEngine="$2"
test -s "$2"
