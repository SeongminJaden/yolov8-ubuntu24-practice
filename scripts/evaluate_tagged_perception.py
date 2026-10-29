"""Held-out evaluation, keeping model predictions separate from renderer truth."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from centerpose_pucks import load_model, infer
from tagged_perception import combine,detect_tags

def iou(a,b):
    lo=np.maximum(a[:2],b[:2]);hi=np.minimum(a[2:],b[2:]);inter=np.maximum(hi-lo,0).prod()
    return float(inter/max(1e-12,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter))

def stats(values):
    return {'count':len(values),'median':float(np.median(values)) if values else None,'p95':float(np.percentile(values,95)) if values else None}

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--yolo',required=True);p.add_argument('--centerpose',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);torch.set_num_threads(4)
    meta=json.loads(a.manifest.read_text());i=meta['camera_intrinsics'];root=a.manifest.parent
    K=np.array([[i['fx'],0,i['cx']],[0,i['fy'],i['cy']],[0,0,1]],np.float64)
    yolo=YOLO(a.yolo);cp=load_model(a.centerpose)
    center_mm=[];center_px=[];tag_mm=[];tag_object_mm=[];rotation_deg=[];rotation_sym_deg=[];cylinder_axis_deg=[]
    total=matched=valid=tag_total=tag_matched=tag_wrong=associations=association_correct=0
    rows=[]
    for s in meta['samples']:
        if s['split']!='test':continue
        image=cv2.imread(str(root/s['image']));result=combine(image,yolo,cp,K,meta['tag_size_m'],meta.get('prism_tag_mount','top'))
        total+=len(s['poses']);tag_total+=len(s['poses'])
        for truth in s['poses']:
            # One object per class in this dataset; no inference uses this truth.
            gtbox=next((b['xyxy'] for b in s['boxes'] if b['class_id']==truth['class_id']),None)
            candidates=[o for o in result['objects'] if o['class_id']==truth['class_id'] and gtbox is not None and iou(o['bbox_xyxy'],gtbox)>=.5]
            if len(candidates)==1:
                obj=candidates[0];matched+=1;pose=obj['centerpose']
                center_px.append(np.linalg.norm(np.array(pose['center_px'])-truth['projected_cuboid'][0]))
                if pose['valid']:
                    valid+=1;center_mm.append(1000*np.linalg.norm(np.array(pose['center_camera_m'])-truth['center_camera_m']))
                    cub=np.array(truth['cuboid_camera_m'][1:]);R=np.column_stack(((cub[4]-cub[0])/.03,(cub[2]-cub[0])/.03,(cub[1]-cub[0])/.06))
                    Rhat=np.array(pose['rotation_matrix']);angle=np.arccos(np.clip((np.trace(R.T@Rhat)-1)/2,-1,1));rotation_deg.append(np.degrees(angle))
                    equivalents=[]
                    for quarter in range(4):
                        a90=quarter*np.pi/2;S=np.array([[np.cos(a90),-np.sin(a90),0],[np.sin(a90),np.cos(a90),0],[0,0,1]])
                        equivalents.append(np.degrees(np.arccos(np.clip((np.trace((R@S).T@Rhat)-1)/2,-1,1))))
                    rotation_sym_deg.append(min(equivalents))
                    if truth['class_id']%2==0:cylinder_axis_deg.append(np.degrees(np.arccos(np.clip(R[:,2]@Rhat[:,2],-1,1))))
                if obj['apriltag']:
                    associations+=1;association_correct+=obj['apriltag']['id']==truth['tag_id']
            tags=[t for t in result['tags'] if t['id']==truth['tag_id']]
            if tags:
                tag_matched+=1
                tag=max(tags,key=lambda t:abs(cv2.contourArea(np.array(t['corners_px'],np.float32))))
                faces=truth.get('tag_faces',[truth])
                face=min(faces,key=lambda f:np.linalg.norm(np.array(f['tag_corners_px'])-tag['corners_px']))
                tag_mm.append(1000*np.linalg.norm(np.array(tag['tag_center_camera_m'])-np.mean(face['tag_corners_camera_m'],axis=0)))
                if tag['tag_derived_object_center_camera_m'] is not None:
                    tag_object_mm.append(1000*np.linalg.norm(np.array(tag['tag_derived_object_center_camera_m'])-truth['center_camera_m']))
        tag_wrong+=sum(t['id'] not in [g['tag_id'] for g in s['poses']] for t in result['tags'])
        rows.append(dict(image=s['image'],condition=s['condition'],prediction=result))
    report=dict(ground_truth_objects=total,yolo_unique_class_matches=matched,centerpose_valid_poses=valid,
        centerpose_center_error_mm=stats(center_mm),centerpose_center_error_px=stats(center_px),centerpose_rotation_error_deg=stats(rotation_deg),centerpose_rotation_modulo90_error_deg=stats(rotation_sym_deg),cylinder_axis_error_deg=stats(cylinder_axis_deg),
        tag_ground_truth=tag_total,tag_id_matches=tag_matched,tag_unexpected_ids=tag_wrong,tag_position_error_mm=stats(tag_mm),
        tag_derived_object_center_error_mm=stats(tag_object_mm),associations=associations,correct_associations=association_correct,
        test_images=sum(s['split']=='test' for s in meta['samples']),scope='Procedural test images; pose error conditional on valid model outputs; independence depends on dataset provenance; no real-camera claim',frames=rows)
    (a.output/'evaluation.json').write_text(json.dumps(report,indent=2));print({k:v for k,v in report.items() if k!='frames'})

if __name__=='__main__':main()
