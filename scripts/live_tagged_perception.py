"""Synchronized live YOLO + custom CenterPose + AprilTag inference on native ROS images.
Run with the YOLO venv and Isaac Sim's bundled Jazzy libraries (see launcher).
"""
import argparse
from collections import OrderedDict
import json
from pathlib import Path
import time
import cv2
import numpy as np
import torch
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image,CameraInfo
from std_msgs.msg import String
from geometry_msgs.msg import PoseArray,Pose
from scipy.spatial.transform import Rotation
from ultralytics import YOLO
from centerpose_pucks import load_model
from tagged_perception import combine

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--yolo',required=True);p.add_argument('--centerpose',required=True)
    p.add_argument('--tag-size',type=float,default=.016);p.add_argument('--seconds',type=float,default=40)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);torch.set_num_threads(4)
    yolo=YOLO(a.yolo);cp=load_model(a.centerpose);rclpy.init();node=rclpy.create_node('tagged_puck_perception')
    publisher=node.create_publisher(String,'/pucks/perception',10)
    pose_pub=node.create_publisher(PoseArray,'/pucks/centerpose/poses',10)
    images=OrderedDict();infos=OrderedDict();counts=dict(paired_frames=0,objects=0,centerpose_valid=0,associated_tags=0)
    def key(m):return (m.header.stamp.sec,m.header.stamp.nanosec,m.header.frame_id)
    def save(cache,m):
        cache[key(m)]=m
        while len(cache)>90:cache.popitem(last=False)
    node.create_subscription(Image,'/pucks/image',lambda m:save(images,m),qos_profile_sensor_data)
    node.create_subscription(CameraInfo,'/pucks/camera_info',lambda m:save(infos,m),qos_profile_sensor_data)
    end=time.monotonic()+a.seconds;last=None
    with (a.output/'frames.jsonl').open('w') as stream:
        while time.monotonic()<end:
            rclpy.spin_once(node,timeout_sec=.01)
            common=images.keys() & infos.keys()
            if not common:continue
            k=max(common)
            if k==last:continue
            last=k;m=images[k];info=infos[k]
            if m.encoding not in ('rgb8','bgr8') or m.width!=info.width or m.height!=info.height:continue
            if any(abs(float(x))>1e-9 for x in info.d):raise RuntimeError('Use rectified RGB + matching CameraInfo; distorted stream is unsupported')
            image=np.frombuffer(m.data,np.uint8).reshape(m.height,m.step)[:,:m.width*3].reshape(m.height,m.width,3).copy()
            if m.encoding=='rgb8':image=cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
            K=np.array(info.k).reshape(3,3);result=combine(image,yolo,cp,K,a.tag_size)
            result.update(frame_id=m.header.frame_id,stamp=dict(sec=m.header.stamp.sec,nanosec=m.header.stamp.nanosec))
            text=json.dumps(result);publisher.publish(String(data=text));stream.write(text+'\n');stream.flush()
            poses=PoseArray();poses.header=m.header
            for obj in result['objects']:
                est=obj['centerpose']
                if est['valid']:
                    pose=Pose();pose.position.x,pose.position.y,pose.position.z=est['center_camera_m']
                    q=Rotation.from_matrix(est['rotation_matrix']).as_quat();pose.orientation.x,pose.orientation.y,pose.orientation.z,pose.orientation.w=map(float,q);poses.poses.append(pose)
            pose_pub.publish(poses)
            counts['paired_frames']+=1;counts['objects']+=len(result['objects']);counts['centerpose_valid']+=len(poses.poses);counts['associated_tags']+=sum(o['apriltag'] is not None for o in result['objects'])
            if counts['paired_frames']==1:
                cv2.imwrite(str(a.output/'first-rgb.png'),image)
                (a.output/'first-perception.json').write_text(json.dumps(result,indent=2))
            images.clear()
    counts['passed_transport']=counts['paired_frames']>0 and counts['objects']>0
    counts['passed_all_outputs']=counts['passed_transport'] and counts['centerpose_valid']>0 and counts['associated_tags']>0
    counts['models']={'yolo':a.yolo,'centerpose':a.centerpose}
    counts['scope']='Transport/output counts, not ground-truth accuracy. CenterPose and tags may be invalid/missing.'
    (a.output/'live-report.json').write_text(json.dumps(counts,indent=2));print(counts)
    node.destroy_node();rclpy.shutdown()
    if not counts['passed_all_outputs']:raise SystemExit(1)

if __name__=='__main__':main()
