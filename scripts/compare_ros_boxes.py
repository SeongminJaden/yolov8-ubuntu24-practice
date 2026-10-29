"""Compare ROS decoded boxes against PyTorch on the same square 640x640 image."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


def iou(a,b):
    left=np.maximum(a[:2],b[:2]);right=np.minimum(a[2:],b[2:])
    area=float(np.maximum(right-left,0).prod())
    union=float((a[2:]-a[:2]).prod()+(b[2:]-b[:2]).prod()-area)
    return area/union if union>0 else 0.0


def decoder_rect(box):
    # release-5.0 yolov8_decoder_node.cpp constructs cv::Rect<int> from float
    # left/top/width/height, then reconstructs center and size from those ints.
    x,y=np.trunc(box[:2])
    w,h=np.trunc(box[2:]-box[:2])
    return np.array([x,y,x+w,y+h])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--weights',required=True)
    p.add_argument('--image',required=True)
    p.add_argument('--ros-report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    im=cv2.imread(a.image)
    if im is None: p.error('Cannot read image')
    im=cv2.resize(im,(640,640))
    r=YOLO(a.weights).predict(im,imgsz=640,conf=.25,iou=.45,device='cpu',verbose=False)[0]
    actual=json.loads(a.ros_report.read_text())['first_detections']
    matches=[];used=set()
    for box,cls in zip(r.boxes.xyxy.numpy(),r.boxes.cls.numpy()):
        candidates=[]
        for j,d in enumerate(actual):
            if j in used or not d['hypotheses']: continue
            h=max(d['hypotheses'],key=lambda x:x['score'])
            if int(h['class_id'])!=int(cls):continue
            x,y,w,h=d['center_x'],d['center_y'],d['width'],d['height']
            coords=np.array([x-w/2,y-h/2,x+w/2,y+h/2])
            candidates.append((iou(decoder_rect(box),coords),j,iou(box,coords)))
        score,j,raw_iou=max(candidates,default=(0.0,-1,0.0))
        if j>=0:used.add(j)
        matches.append(dict(class_id=int(cls),decoder_adjusted_iou=score,float_reference_iou=raw_iou))
    passed=bool(matches) and len(actual)==len(matches) and all(m['decoder_adjusted_iou']>=.99 for m in matches)
    report=dict(passed=passed,pytorch_boxes=len(matches),ros_boxes=len(actual),matches=matches,minimum_decoder_adjusted_iou=.99,reference="release-5.0 cv::Rect<int> truncation")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2))
    print(report)
    if not passed:raise SystemExit('Decoded ROS boxes did not match PyTorch')


if __name__=='__main__': main()
