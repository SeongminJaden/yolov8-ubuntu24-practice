"""Container-side check of combined JSON and NVIDIA GPU AprilTag ROS outputs."""
import argparse
import json
from pathlib import Path
import time
import rclpy
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import String
from isaac_ros_apriltag_interfaces.msg import AprilTagDetectionArray

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=float,default=40)
    a=p.parse_args();rclpy.init();n=rclpy.create_node('verify_tagged_topics')
    data={'perception_messages':0,'gpu_tag_messages':0,'gpu_tag_objects':0}
    def combined(m):
        data['perception_messages']+=1
        if 'first_perception' not in data:data['first_perception']=json.loads(m.data)
    def tags(m):
        data['gpu_tag_messages']+=1;data['gpu_tag_objects']+=len(m.detections)
        if m.detections and 'first_gpu_tags' not in data:
            data['first_gpu_tags']=[{'id':t.id,'position':[t.pose.pose.pose.position.x,t.pose.pose.pose.position.y,t.pose.pose.pose.position.z]} for t in m.detections]
    n.create_subscription(String,'/pucks/perception',combined,10)
    n.create_subscription(AprilTagDetectionArray,'/pucks/apriltag_detections',tags,qos_profile_sensor_data)
    end=time.monotonic()+a.seconds
    while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.1)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(data,indent=2));print(data)
    n.destroy_node();rclpy.shutdown()
    if min(data['perception_messages'],data['gpu_tag_objects'])<=0:raise SystemExit(1)

if __name__=='__main__':main()
