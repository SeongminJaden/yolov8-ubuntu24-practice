"""Publish a square test image and matching CameraInfo for ROS decoder checks."""
import argparse
import cv2
import rclpy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CameraInfo


def main():
    p = argparse.ArgumentParser()
    p.add_argument('image')
    p.add_argument('--image-topic', default='/image_rect')
    p.add_argument('--camera-topic', default='/camera_info_rect')
    a = p.parse_args()
    im = cv2.imread(a.image)
    if im is None:
        raise SystemExit(f'Cannot read image: {a.image}')
    im = cv2.resize(im, (640,640))
    rclpy.init()
    node = rclpy.create_node('puck_test_image_publisher')
    images = node.create_publisher(Image, a.image_topic, 10)
    cameras = node.create_publisher(CameraInfo, a.camera_topic, 10)
    bridge = CvBridge()
    def tick():
        msg = bridge.cv2_to_imgmsg(cv2.cvtColor(im,cv2.COLOR_BGR2RGB),encoding='rgb8')
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.header.frame_id = 'test_camera'
        info = CameraInfo()
        info.header = msg.header
        info.width = info.height = 640
        info.distortion_model = 'plumb_bob'
        info.d = [0.0]*5
        info.k = [640.0,0.0,320.0,0.0,640.0,320.0,0.0,0.0,1.0]
        info.r = [1.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0]
        info.p = [640.0,0.0,320.0,0.0,0.0,640.0,320.0,0.0,0.0,0.0,1.0,0.0]
        cameras.publish(info)
        images.publish(msg)
    node.create_timer(0.1,tick)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()


if __name__ == '__main__':
    main()
