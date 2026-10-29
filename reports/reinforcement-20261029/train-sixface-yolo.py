from pathlib import Path
import json
from ultralytics import YOLO
root=Path('/home/seongmin/Projects/yolov8-ubuntu24-practice')
r=root/'reports/reinforcement-20261029'
data=str(root/'data/tagged-sixface-mixed-20261029/dataset.yaml')
base=str(root/'runs/detect/tagged-practice-20261029-143148/weights/best.pt')
b=YOLO(base).val(data=data,split='val',device=0,batch=4,project=str(root/'runs/detect'),name='sixface-baseline-val',plots=False)
YOLO(base).train(data=data,epochs=8,batch=4,imgsz=640,device=0,workers=2,seed=317,hsv_h=0,hsv_s=.2,hsv_v=.2,lr0=.0001,optimizer='AdamW',project=str(root/'runs/detect'),name='tagged-sixface-reinforced-20261029',exist_ok=False)
candidate=str(root/'runs/detect/tagged-sixface-reinforced-20261029/weights/best.pt')
c=YOLO(candidate).val(data=data,split='val',device=0,batch=4,project=str(root/'runs/detect'),name='sixface-candidate-val',plots=False)
selection={'baseline':base,'candidate':candidate,'baseline_val_map5095':float(b.box.map),'candidate_val_map5095':float(c.box.map),'selected':candidate if c.box.map>b.box.map else base,'selection_rule':'higher validation mAP50-95; retain baseline on ties'}
(r/'yolo-selection.json').write_text(json.dumps(selection,indent=2));print(selection)
