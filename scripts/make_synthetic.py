"""Synthetic colored shapes for pipeline verification, not real puck accuracy."""
import random
from pathlib import Path
import cv2
import numpy as np
import yaml

def frame(rng):
    im=np.full((320,320,3),rng.randint(170,240),np.uint8)
    labels=[]
    for c,(ox,oy) in enumerate([(0,0),(160,0),(0,160),(160,160)]):
        x=ox+rng.randint(35,120); y=oy+rng.randint(35,120); r=rng.randint(15,28)
        color=(30,30,rng.randint(170,245)) if c<2 else (30,rng.randint(120,210),30)
        if c%2==0: cv2.circle(im,(x,y),r,color,-1)
        else: cv2.rectangle(im,(x-r,y-r),(x+r,y+r),color,-1)
        labels.append(f'{c} {x/320} {y/320} {2*r/320} {2*r/320}')
    return im,labels

def main():
    root=Path('data/synthetic-pucks').resolve()
    if root.exists(): raise SystemExit('Output already exists; use a fresh directory')
    for split,n,seed in [('train',48,317),('val',12,318),('test',12,319)]:
        rng=random.Random(seed)
        for sub in ['images','labels']: (root/sub/split).mkdir(parents=True)
        for i in range(n):
            im,labels=frame(rng)
            assert cv2.imwrite(str(root/'images'/split/f'{i:04}.jpg'),im)
            (root/'labels'/split/f'{i:04}.txt').write_text('\n'.join(labels)+'\n')
    cfg=yaml.safe_load(Path('configs/pucks.yaml').read_text());cfg['path']=str(root)
    Path('configs/pucks-local.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False))
    writer=cv2.VideoWriter('data/test.mp4',cv2.VideoWriter_fourcc(*'mp4v'),10,(320,320))
    if not writer.isOpened(): raise RuntimeError('Video writer unavailable')
    im,_=frame(random.Random(320))
    for i in range(30): writer.write(cv2.warpAffine(im,np.float32([[1,0,i/3],[0,1,0]]),(320,320),borderMode=cv2.BORDER_REFLECT))
    writer.release()
    print(root)
if __name__=='__main__': main()
