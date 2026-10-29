from pathlib import Path
import json
from ultralytics import YOLO
root=Path('/home/seongmin/Projects/yolov8-ubuntu24-practice');r=root/'reports/refinement-v2-20261029'
data=str(root/'data/tagged-sixface-v2-mixed-20261029/dataset.yaml');base=str(root/'runs/detect/tagged-sixface-reinforced-20261029/weights/best.pt')
b=YOLO(base).val(data=data,split='val',device=0,batch=4,project=str(root/'runs/detect'),name='sixface-v2-baseline-val',plots=False)
YOLO(base).train(data=data,epochs=6,batch=4,imgsz=640,device=0,workers=2,seed=317,hsv_h=0,hsv_s=.2,hsv_v=.2,lr0=.00005,optimizer='AdamW',cos_lr=True,project=str(root/'runs/detect'),name='tagged-sixface-v2-20261029',exist_ok=False)
candidate=str(root/'runs/detect/tagged-sixface-v2-20261029/weights/best.pt')
c=YOLO(candidate).val(data=data,split='val',device=0,batch=4,project=str(root/'runs/detect'),name='sixface-v2-candidate-val',plots=False)
d={'baseline':base,'candidate':candidate,'baseline_val_map5095':float(b.box.map),'candidate_val_map5095':float(c.box.map),'selected':candidate if c.box.map>b.box.map else base,'selection_rule':'higher val mAP50-95; retain baseline on ties'}
(r/'yolo-selection.json').write_text(json.dumps(d,indent=2));print(d)
