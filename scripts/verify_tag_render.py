"""Check rendered white tag backing against GT geometry; no model inference."""
import argparse,json
from pathlib import Path
import cv2
import numpy as np

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    d=json.loads(a.manifest.read_text());measurements=[]
    # Front-facing unoccluded normal scenes only; RGB neutral light is intentional.
    for s in d['samples']:
        if s['condition']!='normal' or s['negative']:continue
        image=cv2.imread(str(a.manifest.parent/s['image']))
        for pose in s['poses']:
            src=np.array(pose['tag_corners_px'],np.float32)
            dst=np.array([[20,20],[100,20],[100,100],[20,100]],np.float32)
            H=cv2.getPerspectiveTransform(src,dst)
            crop=cv2.warpPerspective(image,H,(120,120))
            # White margin is 10..20 and 100..110; avoid boundary antialiasing.
            ring=np.concatenate([crop[12:17,25:95].reshape(-1,3),crop[103:108,25:95].reshape(-1,3)])
            channel_mean=ring.mean(0);spread=float(channel_mean.max()-channel_mean.min())
            measurements.append(dict(image=s['image'],tag_id=pose['tag_id'],bgr=channel_mean.tolist(),channel_spread=spread))
    # Missing backing exposes strongly red/green object paint and fails neutrality.
    passed=bool(measurements) and np.percentile([m['channel_spread'] for m in measurements],95)<15
    report=dict(passed=bool(passed),samples=len(measurements),p95_channel_spread=float(np.percentile([m['channel_spread'] for m in measurements],95)),scope='Neutral white margin check on unoccluded normal scenes',measurements=measurements)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2));print({k:v for k,v in report.items() if k!='measurements'})
    if not passed:raise SystemExit(1)

if __name__=='__main__':main()
