"""Evaluate AprilTag ID and metric position against rendered held-out truth."""
import argparse,json
from pathlib import Path
import cv2
import numpy as np
from tagged_perception import detect_tags

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Output exists')
    d=json.loads(a.manifest.read_text());i=d['camera_intrinsics'];K=np.array([[i['fx'],0,i['cx']],[0,i['fy'],i['cy']],[0,0,1.]])
    conditions={};errors=[];rows=[];wrong=0
    for s in d['samples']:
        if s['split']!='test':continue
        tags=detect_tags(cv2.imread(str(a.manifest.parent/s['image'])),K,d['tag_size_m'])
        c=conditions.setdefault(s['condition'],dict(ground_truth=0,matched=0));c['ground_truth']+=len(s['poses'])
        wrong+=sum(t['id'] not in [g['tag_id'] for g in s['poses']] for t in tags)
        for g in s['poses']:
            matches=[t for t in tags if t['id']==g['tag_id']]
            if len(matches)==1:
                c['matched']+=1
                errors.append(float(1000*np.linalg.norm(np.array(matches[0]['tag_center_camera_m'])-np.mean(g['tag_corners_camera_m'],axis=0))))
        rows.append(dict(image=s['image'],tags=tags))
    report=dict(conditions=conditions,unexpected_ids=wrong,matched=sum(c['matched'] for c in conditions.values()),ground_truth=sum(c['ground_truth'] for c in conditions.values()),position_error_mm_median=float(np.median(errors)) if errors else None,position_error_mm_p95=float(np.percentile(errors,95)) if errors else None,frames=rows)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2));print({k:v for k,v in report.items() if k!='frames'})

if __name__=='__main__':main()
