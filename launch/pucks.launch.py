"""Isaac ROS 5 / ROS Lyrical inference for the four-class synthetic puck model.

Requires an existing TensorRT engine with images [1,3,640,640] -> output0
[1,8,8400] (raw YOLO output, no embedded NMS). Publish synchronized 640x640
RGB images and CameraInfo on /pucks/image and /pucks/camera_info. Boxes use
640x640 image coordinates. This demonstration does not calibrate a real camera.
"""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, OpaqueFunction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
from launch_ros.parameter_descriptions import ParameterValue


CLASS_NAMES = {0: 'red_cylinder', 1: 'red_prism', 2: 'green_cylinder', 3: 'green_prism'}


def require_engine(context):
    engine = Path(LaunchConfiguration('engine_file_path').perform(context))
    if not engine.is_file() or engine.stat().st_size == 0:
        raise RuntimeError(f'Build the four-class TensorRT engine first: {engine}')
    return []


def generate_launch_description():
    encoder_share = Path(get_package_share_directory('isaac_ros_dnn_image_encoder'))
    yolov8_share = Path(get_package_share_directory('isaac_ros_yolov8'))
    encoder = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(encoder_share / 'launch/dnn_image_encoder.launch.py')),
        launch_arguments={
            'input_image_width': '640', 'input_image_height': '640',
            'network_image_width': '640', 'network_image_height': '640',
            'image_mean': '[0.0, 0.0, 0.0]', 'image_stddev': '[1.0, 1.0, 1.0]',
            'input_encoding': 'rgb8', 'encoding_desired': 'rgb8',
            'tensor_name': 'input_tensor', 'final_tensor_name': 'input_tensor',
            'attach_to_shared_component_container': 'True',
            'component_container_name': '/pucks_container',
            'dnn_image_encoder_namespace': 'pucks_encoder',
            'image_input_topic': '/pucks/image',
            'camera_info_input_topic': '/pucks/camera_info',
            'tensor_output_topic': '/pucks/encoded_tensor',
        }.items(),
    )
    inference = ComposableNode(
        name='pucks_tensor_rt', package='isaac_ros_tensor_rt',
        plugin='nvidia::isaac_ros::dnn_inference::TensorRTNode',
        parameters=[{
            'model_file_path': '',
            'engine_file_path': ParameterValue(LaunchConfiguration('engine_file_path'), value_type=str),
            'input_tensor_names': ['input_tensor'], 'input_binding_names': ['images'],
            'output_tensor_names': ['output_tensor'], 'output_binding_names': ['output0'],
            'force_engine_update': False, 'verbose': False,
        }],
        # TensorRTNode receives on tensor_pub and publishes on tensor_sub.
        remappings=[('tensor_pub', '/pucks/encoded_tensor'),
                    ('tensor_sub', '/pucks/inference_tensor')],
    )
    decoder = ComposableNode(
        name='pucks_decoder', package='isaac_ros_yolov8',
        plugin='nvidia::isaac_ros::yolov8::YoloV8DecoderNode',
        parameters=[{
            'num_classes': 4, 'tensor_name': 'output_tensor',
            'confidence_threshold': ParameterValue(LaunchConfiguration('confidence_threshold'), value_type=float),
            'nms_threshold': 0.45,
        }],
        remappings=[('tensor_sub', '/pucks/inference_tensor'),
                    ('detections_output', '/pucks/detections')],
    )
    container = ComposableNodeContainer(
        name='pucks_container', namespace='', package='rclcpp_components',
        executable='component_container_mt', composable_node_descriptions=[inference, decoder],
        output='screen',
    )
    # Reuse the installed visualizer implementation with the training class map.
    # Its default COCO labels would incorrectly call class 0 "person".
    visualizer_path = yolov8_share / 'scripts/isaac_ros_yolov8_visualizer.py'
    visualizer_code = (
        'import importlib.util; '
        f's=importlib.util.spec_from_file_location("puck_visualizer", {str(visualizer_path)!r}); '
        'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
        f'm.names={CLASS_NAMES!r}; m.main()'
    )
    visualizer = ExecuteProcess(
        cmd=['python3', '-c', visualizer_code, '--ros-args',
             '-r', '__node:=pucks_visualizer',
             '-r', 'detections_output:=/pucks/detections',
             '-r', '/yolov8_encoder/resize/image:=/pucks_encoder/resize/image',
             '-r', 'yolov8_processed_image:=/pucks/processed_image'],
        condition=IfCondition(LaunchConfiguration('visualize')), output='screen',
    )
    return LaunchDescription([
        DeclareLaunchArgument('engine_file_path', description='Absolute path to the four-class 640x640 engine'),
        DeclareLaunchArgument('confidence_threshold', default_value='0.25'),
        DeclareLaunchArgument('visualize', default_value='True'),
        OpaqueFunction(function=require_engine), container, encoder, visualizer,
    ])
