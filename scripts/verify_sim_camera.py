"""Receive native Sim RGB/CameraInfo and check calibration and timestamp pairing."""
import argparse
import json
import time
from pathlib import Path
import cv2
import numpy as np
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, CameraInfo


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=15)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = rclpy.create_node('verify_native_sim_camera')
    images, infos = {}, {}
    calibration = {}
    def key(m):
        return (m.header.stamp.sec, m.header.stamp.nanosec, m.header.frame_id)
    def rgb(m):
        images[key(m)] = [m.width, m.height, m.encoding]
        if len(images) == 1:
            pixels = np.frombuffer(m.data, np.uint8).reshape(m.height, m.step)[:, :m.width*3].reshape(m.height,m.width,3)
            if m.encoding == 'rgb8':
                pixels = cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)
            elif m.encoding != 'bgr8':
                raise ValueError(m.encoding)
            cv2.imwrite(str(a.output/'native-rgb.png'), pixels)
    def info(m):
        infos[key(m)] = [m.width, m.height]
        calibration.update(k=list(m.k), p=list(m.p), distortion_model=m.distortion_model, d=list(m.d))
    node.create_subscription(Image, '/pucks/image', rgb, qos_profile_sensor_data)
    node.create_subscription(CameraInfo, '/pucks/camera_info', info, qos_profile_sensor_data)
    end = time.monotonic()+a.seconds
    while time.monotonic()<end:
        rclpy.spin_once(node, timeout_sec=.1)
    paired = images.keys() & infos.keys()
    expected=640*24/20.955
    passed = bool(paired) and all(v[:2]==[640,640] for v in images.values()) and all(v==[640,640] for v in infos.values()) and abs(calibration['k'][0]-expected)<.01 and abs(calibration['k'][4]-expected)<.01
    report=dict(passed=bool(passed),image_messages=len(images),camera_info_messages=len(infos),same_stamp_and_frame_pairs=len(paired),calibration=calibration,expected_focal_pixels=expected,domain=75)
    (a.output/'camera-verification.json').write_text(json.dumps(report,indent=2))
    node.destroy_node(); rclpy.shutdown()
    print(report)
    if not passed: raise SystemExit(1)


if __name__ == '__main__':
    main()
