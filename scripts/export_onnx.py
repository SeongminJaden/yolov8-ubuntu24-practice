import argparse
from pathlib import Path
import shutil
from ultralytics import YOLO
from inspect_onnx import inspect

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--weights',default='yolov8s.pt')
    p.add_argument('--output',default='models/yolov8s.onnx')
    a=p.parse_args()
    result=YOLO(a.weights).export(format='onnx',imgsz=640,batch=1,dynamic=False,nms=False,simplify=False,opset=17)
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    if Path(result).resolve()!=out.resolve(): shutil.copy2(result,out)
    print(inspect(out))
