from pathlib import Path
import json,torch
root=Path('/home/seongmin/Projects/yolov8-ubuntu24-practice');r=root/'reports/refinement-v2-20261029'
b=json.loads((r/'baseline-val/evaluation.json').read_text());best=b;chosen='baseline';rows=[]
for name in ['candidate-val','candidate-tta-val','candidate-tta-fallback-val']:
 c=json.loads((r/name/'evaluation.json').read_text())
 good=(c['centerpose_center_error_mm']['p95']<best['centerpose_center_error_mm']['p95'] and c['centerpose_center_error_mm']['median']<=b['centerpose_center_error_mm']['median'] and c['centerpose_valid_poses']>=b['centerpose_valid_poses'])
 rows.append({'candidate':name,'val_center_mm':c['centerpose_center_error_mm'],'valid_poses':c['centerpose_valid_poses']})
 if good:best=c;chosen=name
base='models/centerpose-sixface-reinforced-20261029/best.pt';candidate='models/centerpose-sixface-v2-20261029/best.pt';selected=base if chosen=='baseline' else candidate
if chosen in ('candidate-tta-val','candidate-tta-fallback-val'):
 ck=torch.load(root/candidate,map_location='cpu',weights_only=False);ck['inference_tta']=True
 selected='models/centerpose-sixface-v2-20261029/best-tta.pt'
 if chosen=='candidate-tta-fallback-val':
  ck['fallback_model']=torch.load(root/base,map_location='cpu',weights_only=False)['model']
  selected='models/centerpose-sixface-v2-20261029/best-tta-fallback.pt'
 torch.save(ck,root/selected)
d={'baseline':base,'selected':selected,'selected_variant':chosen,'baseline_val_center_mm':b['centerpose_center_error_mm'],'baseline_valid':b['centerpose_valid_poses'],'candidates':rows,'selection_rule':'lowest val center P95 with no worse median or valid-pose coverage than baseline; otherwise retain baseline'}
(r/'centerpose-selection.json').write_text(json.dumps(d,indent=2));print(d)
