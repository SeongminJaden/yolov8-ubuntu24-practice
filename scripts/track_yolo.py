import argparse
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description="ByteTrack IDs are temporary, not physical IDs")
    p.add_argument('--weights', required=True)
    p.add_argument('--source', required=True)
    p.add_argument('--device', default='0')
    p.add_argument('--name', default='track')
    a=p.parse_args()
    from ultralytics import YOLO
    count=tracked=0
    out=None
    for r in YOLO(a.weights).track(source=a.source, device=a.device, tracker='bytetrack.yaml',
            stream=True, save=True, project='runs/track', name=a.name):
        count+=1
        tracked+=int(r.boxes is not None and r.boxes.id is not None)
        out=Path(r.save_dir)
    if count==0: raise RuntimeError('No video frames processed')
    report=dict(frames=count, frames_with_ids=tracked)
    if out:
        out.mkdir(parents=True,exist_ok=True)
        (out/'tracking-summary.json').write_text(json.dumps(report,indent=2))
    print(report)
if __name__=='__main__': main()
