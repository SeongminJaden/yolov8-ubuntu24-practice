"""Optional NVIDIA GPU AprilTag path on the same calibrated Sim/RealSense topics."""
from launch import LaunchDescription
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

def generate_launch_description():
    node=ComposableNode(package='isaac_ros_apriltag',plugin='nvidia::isaac_ros::apriltag::AprilTagNode',name='puck_apriltag',parameters=[{'size':.016,'max_tags':64,'tile_size':4}],remappings=[('image','/pucks/image'),('camera_info','/pucks/camera_info'),('tag_detections','/pucks/apriltag_detections')])
    return LaunchDescription([ComposableNodeContainer(name='puck_apriltag_container',namespace='',package='rclcpp_components',executable='component_container_mt',composable_node_descriptions=[node],output='screen')])
