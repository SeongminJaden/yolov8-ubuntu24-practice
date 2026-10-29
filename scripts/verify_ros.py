"""Run inside the Isaac ROS container while detector, bag and visualizer are active."""
import argparse
import json
import time
from pathlib import Path

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=30)
    p.add_argument('--image-topic', default='/yolov8_processed_image')
    p.add_argument('--detection-topic')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = rclpy.create_node('yolov8_verification_recorder')
    result = dict(detection_messages=0, detections=0, rendered_images=0,
                  topics={}, first_detections=[])
    bridge = CvBridge()
    subscriptions = []
    detection_topic = None
    image_topic = None

    def detection(msg):
        result['detection_messages'] += 1
        result['detections'] += len(msg.detections)
        if not result['first_detections'] and msg.detections:
            result['first_detections'] = [
                dict(center_x=d.bbox.center.position.x,
                     center_y=d.bbox.center.position.y,
                     width=d.bbox.size_x, height=d.bbox.size_y,
                     hypotheses=[dict(class_id=h.hypothesis.class_id,
                                      score=h.hypothesis.score) for h in d.results])
                for d in msg.detections]

    def image(msg):
        if result['rendered_images'] == 0:
            im = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            if not cv2.imwrite(str(a.output / 'ros-detections.jpg'), im):
                raise RuntimeError('Failed to save rendered image')
        result['rendered_images'] += 1

    start = time.monotonic()
    try:
        while time.monotonic() - start < a.seconds:
            topics = dict(node.get_topic_names_and_types())
            result['topics'] = topics
            if detection_topic is None:
                matches = [n for n,t in topics.items() if 'vision_msgs/msg/Detection2DArray' in t]
                if a.detection_topic:
                    matches = [n for n in matches if n == a.detection_topic]
                if len(matches) > 1:
                    raise RuntimeError(f'Ambiguous detection topics: {matches}')
                if matches:
                    detection_topic = matches[0]
                    subscriptions.append(node.create_subscription(
                        Detection2DArray, detection_topic, detection, qos_profile_sensor_data))
            if image_topic is None and a.image_topic in topics:
                image_topic = a.image_topic
                subscriptions.append(node.create_subscription(Image, image_topic, image, qos_profile_sensor_data))
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        result['elapsed_seconds'] = time.monotonic()-start
        result['detection_topic'] = detection_topic
        (a.output/'ros-verification.json').write_text(json.dumps(result, indent=2))
        node.destroy_node()
        rclpy.shutdown()
    if not all(result[k] > 0 for k in ('detection_messages','detections','rendered_images')):
        raise SystemExit('FAIL: need nonempty detections and rendered images; see report')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
