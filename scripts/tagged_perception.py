"""YOLO shape/color + learned CenterPose center/pose + AprilTag ID/pose.

All outputs are in the calibrated camera optical frame (m, x right/y down/z forward).
Tag-derived object centers remain explicitly separate from CenterPose predictions.
"""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import torch
from functools import lru_cache
from pupil_apriltags import Detector
from ultralytics import YOLO
from centerpose_pucks import load_model, infer

NAMES=['red_cylinder','red_prism','green_cylinder','green_prism']

@lru_cache(maxsize=1)
def tag_detector():
    return Detector(families='tag36h11',nthreads=2,quad_decimate=1.0,refine_edges=1)

def detect_tags(image,K,size=.016):
    detections=tag_detector().detect(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY))
    # Normalize Apriltags3's counter-clockwise native order to the generator's
    # clockwise printed-tag TL/TR/BR/BL convention. Covered by rendered GT audit.
    corners=[t.corners[[1,0,3,2]] for t in detections]
    ids=np.array([t.tag_id for t in detections])
    h=size/2;object_points=np.array([[-h,h,0],[h,h,0],[h,-h,0],[-h,-h,0]],np.float64)
    records=[]
    if len(ids)==0:return records
    for corner,tid in zip(corners,ids.reshape(-1)):
        uv=corner.reshape(4,2).astype(np.float64)
        ok,rvec,tvec=cv2.solvePnP(object_points,uv,K,np.zeros(5),flags=cv2.SOLVEPNP_IPPE_SQUARE)
        if not ok or tvec[2,0]<=0:continue
        rotation=cv2.Rodrigues(rvec)[0]
        proj,_=cv2.projectPoints(object_points,rvec,tvec,K,np.zeros(5))
        records.append(dict(id=int(tid),family='tag36h11',corners_px=uv.tolist(),center_px=uv.mean(0).tolist(),
            tag_center_camera_m=tvec.reshape(3).tolist(),rotation_matrix=rotation.tolist(),
            tag_derived_object_center_camera_m=(tvec.reshape(3)-rotation[:,2]*.03003).tolist(),
            reprojection_error_px=float(np.linalg.norm(proj.reshape(4,2)-uv,axis=1).mean()),
            source='apriltags3_corners_opencv_ippe',tag_size_m=size))
    return records

def combine(image,yolo,centerpose,K,tag_size=.016):
    tags=detect_tags(image,K,tag_size)
    predictions=yolo.predict(image,conf=.25,iou=.45,device=0,verbose=False)[0]
    objects=[]
    for b in predictions.boxes:
        cid=int(b.cls);box=b.xyxy[0].cpu().tolist();color,shape=NAMES[cid].split('_')
        cp=infer(centerpose,image,box,K)
        candidates=[t for t in tags if box[0]<=t['center_px'][0]<=box[2] and box[1]<=t['center_px'][1]<=box[3]]
        # Avoid an ambiguous tag assignment when projected object boxes overlap.
        objects.append(dict(class_id=cid,shape=shape,color=color,yolo_confidence=float(b.conf),bbox_xyxy=box,
            centerpose=cp,apriltag=candidates[0] if len(candidates)==1 else None,
            association_status='candidate_unique' if len(candidates)==1 else ('ambiguous' if candidates else 'tag_not_visible')))
    counts={}
    for obj in objects:
        if obj['apriltag'] is not None:
            tid=obj['apriltag']['id'];counts[tid]=counts.get(tid,0)+1
    for obj in objects:
        if obj['apriltag'] is not None:
            if counts[obj['apriltag']['id']]>1:obj.update(apriltag=None,association_status='ambiguous_shared_tag')
            else:obj['association_status']='matched'
    return dict(frame_id='camera_optical_frame',units='meters',objects=objects,tags=tags)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',type=Path,required=True);p.add_argument('--yolo',required=True)
    p.add_argument('--centerpose',required=True);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();torch.set_num_threads(4)
    meta=json.loads(a.manifest.read_text());i=meta['camera_intrinsics']
    K=np.array([[i['fx'],0,i['cx']],[0,i['fy'],i['cy']],[0,0,1]],np.float64)
    image=cv2.imread(str(a.image))
    result=combine(image,YOLO(a.yolo),load_model(a.centerpose),K,meta['tag_size_m'])
    a.output.mkdir(parents=True,exist_ok=False);(a.output/'perception.json').write_text(json.dumps(result,indent=2))
    for obj in result['objects']:
        x1,y1,x2,y2=map(int,obj['bbox_xyxy']);cv2.rectangle(image,(x1,y1),(x2,y2),(0,255,255),2)
        tag=obj['apriltag'];label=f"{obj['color']} {obj['shape']} tag={tag['id'] if tag else '?'}"
        cv2.putText(image,label,(x1,max(15,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,255,255),1)
        cp=obj['centerpose'];u,v=map(int,cp['center_px']);cv2.circle(image,(u,v),4,(255,0,255),-1)
    cv2.imwrite(str(a.output/'overlay.jpg'),image)

if __name__=='__main__':main()
