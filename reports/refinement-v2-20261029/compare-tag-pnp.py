from pathlib import Path
import sys,json,time
import numpy as np,cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import tagged_perception as tp
root=Path(__file__).resolve().parents[2];mr=root/'data/tagged-sixface-20261029';m=json.loads((mr/'manifest.json').read_text());i=m['camera_intrinsics'];K=np.array([[i['fx'],0,i['cx']],[0,i['fy'],i['cy']],[0,0,1.]])
original=tp.tag_detector();reports=[]
class Refined:
 def detect(self,gray):
  tags=original.detect(gray)
  for t in tags:
   before=t.corners.copy();corners=before.astype(np.float32).reshape(-1,1,2)
   cv2.cornerSubPix(gray,corners,(window,window),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,30,.001))
   if np.linalg.norm(corners.reshape(4,2)-before,axis=1).max()<2:
    t.corners[:]=corners.reshape(4,2)
  return tags
solve=cv2.solvePnP
for window in (0,1):
 def refined_solve(*args,**kwargs):
  ok,r,t=solve(*args,**kwargs)
  if ok and window:
   r,t=cv2.solvePnPRefineLM(args[0],args[1],args[2],args[3],r,t)
  return ok,r,t
 cv2.solvePnP=refined_solve
 errors=[];matches=total=wrong=0
 for s in m['samples']:
  if s['split']!='val':continue
  tags=tp.detect_tags(cv2.imread(str(mr/s['image'])),K,prism_tag_mount='six_faces')
  total+=len(s['poses']);wrong+=sum(t['id'] not in {p['tag_id'] for p in s['poses']} for t in tags)
  for p in s['poses']:
   found=[t for t in tags if t['id']==p['tag_id']]
   if not found:continue
   matches+=1;t=max(found,key=lambda t:abs(cv2.contourArea(np.array(t['corners_px'],np.float32))))
   f=min(p['tag_faces'],key=lambda f:np.linalg.norm(np.array(f['tag_corners_px'])-t['corners_px']))
   errors.append(1000*np.linalg.norm(np.array(t['tag_center_camera_m'])-np.mean(f['tag_corners_camera_m'],axis=0)))
 r=dict(window=window,total=total,matches=matches,unexpected_ids=wrong,median_mm=float(np.median(errors)),p95_mm=float(np.percentile(errors,95)));reports.append(r);print(r,flush=True)
 (root/'reports/refinement-v2-20261029/tag-pnp-validation.json').write_text(json.dumps(reports,indent=2))
