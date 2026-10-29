import argparse
import math
from pathlib import Path

def validate_line(line, classes):
    if not isinstance(classes, int) or isinstance(classes, bool) or classes <= 0:
        raise ValueError('classes must be a positive integer')
    parts=line.split()
    if len(parts)!=5: raise ValueError('expected class x y w h')
    c,x,y,w,h=map(float,parts)
    if not all(math.isfinite(v) for v in (c,x,y,w,h)): raise ValueError('nonfinite value')
    if not c.is_integer() or not 0<=c<classes: raise ValueError('invalid class')
    if not (0<=x<=1 and 0<=y<=1 and 0<w<=1 and 0<h<=1): raise ValueError('invalid normalized box')
    if min(x-w/2,y-h/2)<-1e-6 or max(x+w/2,y+h/2)>1+1e-6: raise ValueError('box outside image')
    return int(c),x,y,w,h

def main():
    p=argparse.ArgumentParser()
    p.add_argument('path',type=Path)
    p.add_argument('--kind',choices=['yolo'],default='yolo')
    p.add_argument('--classes',type=int,default=4)
    a=p.parse_args()
    if a.classes <= 0: p.error('--classes must be positive')
    files=[a.path] if a.path.is_file() and a.path.suffix == '.txt' else sorted(a.path.rglob('*.txt'))
    if not files: p.error('No label files')
    errors=[]
    for f in files:
        for n,line in enumerate(f.read_text().splitlines(),1):
            if not line.strip(): continue
            try: validate_line(line,a.classes)
            except ValueError as e: errors.append(f'{f}:{n}: {e}')
    if errors: raise SystemExit('\n'.join(errors))
    print(f'PASS: {len(files)} label files (empty files represent background)')
if __name__=='__main__': main()
