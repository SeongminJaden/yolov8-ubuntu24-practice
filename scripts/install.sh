#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv-yolo
.venv-yolo/bin/python -m pip install --no-cache-dir --upgrade pip
.venv-yolo/bin/python -m pip install --no-cache-dir torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu128
.venv-yolo/bin/python -m pip install --no-cache-dir -r requirements-yolo.txt
.venv-yolo/bin/python -m pip check
.venv-yolo/bin/python -m pip freeze > environment-yolo-lock.txt
