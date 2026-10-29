from pathlib import Path
import sys,json,time
import numpy as np,cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from tagged_perception import detect_tags
root=Path(__file__).resolve().parents[2];mroot=root/'data/tagged-sixface-20261029';m=json.loads((mroot/'manifest.json').read_text());i=m['camera_intrinsics'];K=np.array([[i['fx'],0,i['cx']],[0,i['fy'],i['cy']],[0,0,1.]])
reports=[]
for scale in (1,2,3):
 errors=[];matches=total=wrong=0;start=time.monotonic()
 for s in m['samples']:
  if s['split']!='val':continue
  image=cv2.imread(str(mroot/s['image']));scaled=image if scale==1 else cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
  ks=K.copy();ks[:2]*=scale
  tags=detect_tags(scaled,ks,prism_tag_mount='six_faces')
  for t in tags:t['corners_px']=(np.array(t['corners_px'])/scale).tolist()
  total+=len(s['poses']);wrong+=sum(t['id'] not in {p['tag_id'] for p in s['poses']} for t in tags)
  for p in s['poses']:
   found=[t for t in tags if t['id']==p['tag_id']]
   if not found:continue
   matches+=1;t=max(found,key=lambda t:abs(cv2.contourArea(np.array(t['corners_px'],np.float32))))
   face=min(p['tag_faces'],key=lambda f:np.linalg.norm(np.array(f['tag_corners_px'])-t['corners_px']))
   errors.append(1000*np.linalg.norm(np.array(t['tag_center_camera_m'])-np.mean(face['tag_corners_camera_m'],axis=0)))
 report=dict(scale=scale,total=total,matches=matches,unexpected_ids=wrong,median_mm=float(np.median(errors)),p95_mm=float(np.percentile(errors,95)),seconds=time.monotonic()-start)
 reports.append(report);print(report,flush=True)
 (root/'reports/refinement-v2-20261029/tag-scale-validation.json').write_text(json.dumps(reports,indent=2))
