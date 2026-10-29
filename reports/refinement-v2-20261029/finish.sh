#!/usr/bin/env bash
set -euo pipefail
cd /home/seongmin/Projects/yolov8-ubuntu24-practice
PY=.venv-yolo/bin/python
R=reports/refinement-v2-20261029
$PY scripts/evaluate_tagged_perception.py --manifest data/tagged-sixface-v2-mixed-20261029/validation-manifest.json \
 --yolo runs/detect/tagged-sixface-reinforced-20261029/weights/best.pt \
 --centerpose models/centerpose-sixface-v2-20261029/best.pt --output "$R/candidate-val" > "$R/candidate-val.log" 2>&1
$PY "$R/evaluate-tta.py" --manifest data/tagged-sixface-v2-mixed-20261029/validation-manifest.json \
 --yolo runs/detect/tagged-sixface-reinforced-20261029/weights/best.pt \
 --centerpose models/centerpose-sixface-v2-20261029/best.pt --output "$R/candidate-tta-val" > "$R/candidate-tta-val.log" 2>&1
$PY "$R/evaluate-tta-fallback.py" --manifest data/tagged-sixface-v2-mixed-20261029/validation-manifest.json \
 --yolo runs/detect/tagged-sixface-reinforced-20261029/weights/best.pt \
 --centerpose models/centerpose-sixface-v2-20261029/best.pt --output "$R/candidate-tta-fallback-val" > "$R/candidate-tta-fallback-val.log" 2>&1
$PY "$R/select-centerpose.py"
$PY "$R/train-yolo.py" > "$R/yolo-training.log" 2>&1
$PY scripts/evaluate_tagged_perception.py --manifest data/tagged-sixface-v2-mixed-20261029/manifest.json \
 --yolo runs/detect/tagged-sixface-reinforced-20261029/weights/best.pt \
 --centerpose models/centerpose-sixface-reinforced-20261029/best.pt --output "$R/baseline-test" > "$R/baseline-test.log" 2>&1
YOLO=$($PY -c 'import json;print(json.load(open("reports/refinement-v2-20261029/yolo-selection.json"))["selected"])')
CP=$($PY -c 'import json;print(json.load(open("reports/refinement-v2-20261029/centerpose-selection.json"))["selected"])')
$PY scripts/evaluate_tagged_perception.py --manifest data/tagged-sixface-v2-mixed-20261029/manifest.json \
 --yolo "$YOLO" --centerpose "$CP" --output "$R/final-test" > "$R/final-test.log" 2>&1
$PY scripts/tagged_perception.py --image data/tagged-sixface-v2-20261029/images/test/0001.png \
 --manifest data/tagged-sixface-v2-20261029/manifest.json --yolo "$YOLO" --centerpose "$CP" --output "$R/example"
