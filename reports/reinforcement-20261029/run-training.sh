#!/usr/bin/env bash
set -euo pipefail
cd /home/seongmin/Projects/yolov8-ubuntu24-practice
PY=.venv-yolo/bin/python
REPORT=reports/reinforcement-20261029
$PY "$REPORT/prepare-sixface-data.py"
$PY scripts/centerpose_pucks.py \
  --manifest data/tagged-sixface-mixed-20261029/manifest.json \
  --resume models/centerpose-practice-20261029-143148/best.pt \
  --output models/centerpose-sixface-reinforced-20261029 \
  --epochs 12 --batch 16 --lr 0.00005 > "$REPORT/sixface-centerpose-training.log" 2>&1
$PY "$REPORT/train-sixface-yolo.py" > "$REPORT/sixface-yolo-training.log" 2>&1
$PY scripts/evaluate_tagged_perception.py \
  --manifest data/tagged-sixface-mixed-20261029/manifest.json \
  --yolo runs/detect/tagged-practice-20261029-143148/weights/best.pt \
  --centerpose models/centerpose-practice-20261029-143148/best.pt \
  --output "$REPORT/baseline-sixface" > "$REPORT/baseline-sixface.log" 2>&1
YOLO=$($PY -c 'import json;print(json.load(open("reports/reinforcement-20261029/yolo-selection.json"))["selected"])')
$PY scripts/evaluate_tagged_perception.py \
  --manifest data/tagged-sixface-mixed-20261029/manifest.json \
  --yolo "$YOLO" \
  --centerpose models/centerpose-sixface-reinforced-20261029/best.pt \
  --output "$REPORT/final-sixface" > "$REPORT/final-sixface.log" 2>&1
$PY scripts/tagged_perception.py \
  --image data/tagged-sixface-20261029/images/test/0001.png \
  --manifest data/tagged-sixface-20261029/manifest.json \
  --yolo "$YOLO" --centerpose models/centerpose-sixface-reinforced-20261029/best.pt \
  --output "$REPORT/example"
