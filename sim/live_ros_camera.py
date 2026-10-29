"""Render a USD camera and publish RGB/CameraInfo with Isaac Sim's native bridge.

Host Isaac Sim 6.1 Python environment (do not source container ROS Lyrical):
  OMNI_KIT_ACCEPT_EULA=YES /path/to/isaacsim6_venv/bin/python \
    sim/live_ros_camera.py --scene data/isaac-pucks-v1/scene.usda --seconds 90 --domain 75

The renderer is headless RaytracedLighting, 640x640. Native CameraHelper and
CameraInfoHelper share one render product, frame ID and simulation time.
CameraInfo is derived from the USD camera, never a synthetic calibration stub.
Local API/schema checks only until an end-to-end run is recorded: bundled
Jazzy -> container Lyrical DDS interoperability must be verified by a receiver.
No ROS message count or detection success is inferred from rendering updates.
"""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import sysconfig
import time


def configure_bridge_environment(domain):
    """Use bundled Jazzy libraries before the dynamic loader initializes Kit."""
    distro = os.environ.get('ROS_DISTRO', 'jazzy')
    if distro != 'jazzy':
        raise SystemExit('Use a clean host terminal without sourced ROS; this script uses bundled Jazzy.')
    base = Path(sysconfig.get_paths()['purelib']) / 'isaacsim/exts/isaacsim.ros2.core'
    lib = base / 'jazzy/lib'
    if not lib.is_dir():
        raise SystemExit(f'Bundled Isaac Sim Jazzy library directory missing: {lib}')
    os.environ['ROS_DISTRO'] = 'jazzy'
    os.environ['ROS_DOMAIN_ID'] = str(domain)
    os.environ.setdefault('RMW_IMPLEMENTATION', 'rmw_fastrtps_cpp')
    os.environ.setdefault('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')
    existing = os.environ.get('LD_LIBRARY_PATH', '').split(':')
    if str(lib) not in existing:
        os.environ['LD_LIBRARY_PATH'] = ':'.join([str(lib)] + [p for p in existing if p])
        # Setting LD_LIBRARY_PATH after starting Python is insufficient for dlopen.
        os.execv(sys.executable, [sys.executable, *sys.argv])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=90)
    parser.add_argument('--domain', type=int, default=75)
    parser.add_argument('--camera', default='/World/Camera')
    parser.add_argument('--fps', type=float, default=30)
    parser.add_argument('--output', type=Path, default=Path('reports/sim-live-camera.json'))
    args = parser.parse_args()
    if not args.scene.is_file():
        parser.error(f'Scene does not exist: {args.scene}')
    if not (math.isfinite(args.seconds) and args.seconds > 0 and
            math.isfinite(args.fps) and args.fps > 0 and 0 <= args.domain <= 101):
        parser.error('seconds/fps must be positive finite numbers; domain must be 0..101')
    configure_bridge_environment(args.domain)

    from isaacsim import SimulationApp
    app = SimulationApp({'headless': True, 'renderer': 'RaytracedLighting',
                         'width': 640, 'height': 640, 'anti_aliasing': 0, 'multi_gpu': False})
    timeline = None
    report = {'scene': str(args.scene.resolve()), 'camera': args.camera,
              'resolution': [640, 640], 'domain': args.domain,
              'bridge_ros_distro': 'jazzy', 'renderer': 'RaytracedLighting',
              'image_topic': '/pucks/image', 'camera_info_topic': '/pucks/camera_info',
              'receiver_verified': False, 'render_updates': 0}
    try:
        import omni.graph.core as og
        import omni.kit.app
        import omni.timeline
        import omni.usd
        from pxr import Sdf, UsdGeom

        manager = omni.kit.app.get_app().get_extension_manager()
        manager.set_extension_enabled_immediate('isaacsim.ros2.nodes', True)
        app.update()
        if not manager.is_extension_enabled('isaacsim.ros2.core'):
            raise RuntimeError('Native ROS 2 core failed to load; inspect bundled-library startup log')
        context = omni.usd.get_context()
        if not context.open_stage(str(args.scene.resolve())):
            raise RuntimeError('Failed to open USD scene')
        for _ in range(10):
            app.update()
        stage = context.get_stage()
        camera = UsdGeom.Camera(stage.GetPrimAtPath(args.camera))
        if not camera:
            raise RuntimeError(f'USD Camera not found at {args.camera}')
        focal = float(camera.GetFocalLengthAttr().Get())
        horizontal = float(camera.GetHorizontalApertureAttr().Get())
        vertical = float(camera.GetVerticalApertureAttr().Get())
        if min(focal, horizontal, vertical) <= 0:
            raise RuntimeError('Invalid USD camera focal length or aperture')
        report['usd_intrinsics'] = {
            'focal_length': focal, 'horizontal_aperture': horizontal,
            'vertical_aperture': vertical, 'expected_fx': 640*focal/horizontal,
            'expected_fy': 640*focal/vertical,
            'note': 'Expected focal pixels only; native CameraInfo contains full K/P.'}
        # Node names/ports follow the installed 6.1 OGN schemas and camera tests.
        keys = og.Controller.Keys
        values = [('Product.inputs:cameraPrim', [Sdf.Path(args.camera)]),
                  ('Product.inputs:width', 640), ('Product.inputs:height', 640),
                  ('Context.inputs:domain_id', args.domain),
                  ('Context.inputs:useDomainIDEnvVar', False),
                  ('RGB.inputs:type', 'rgb')]
        connections = [('Tick.outputs:tick', 'Product.inputs:execIn')]
        for node, topic in [('RGB', '/pucks/image'), ('Info', '/pucks/camera_info')]:
            values.extend([(f'{node}.inputs:topicName', topic),
                           (f'{node}.inputs:frameId', 'pucks_camera_optical_frame'),
                           (f'{node}.inputs:useSystemTime', False),
                           (f'{node}.inputs:resetSimulationTimeOnStop', True)])
            connections.extend([
                ('Product.outputs:execOut', f'{node}.inputs:execIn'),
                ('Product.outputs:renderProductPath', f'{node}.inputs:renderProductPath'),
                ('Context.outputs:context', f'{node}.inputs:context')])
        og.Controller.edit({'graph_path': '/PucksROS2Graph', 'evaluator_name': 'execution'}, {
            keys.CREATE_NODES: [('Tick', 'omni.graph.action.OnPlaybackTick'),
                                ('Context', 'isaacsim.ros2.bridge.ROS2Context'),
                                ('Product', 'isaacsim.core.nodes.IsaacCreateRenderProduct'),
                                ('RGB', 'isaacsim.ros2.bridge.ROS2CameraHelper'),
                                ('Info', 'isaacsim.ros2.bridge.ROS2CameraInfoHelper')],
            keys.SET_VALUES: values, keys.CONNECT: connections})
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        for _ in range(20):
            app.update()
        print('NATIVE CAMERA GRAPH READY ' + json.dumps(report), flush=True)
        start = time.monotonic()
        while app.is_running() and time.monotonic() - start < args.seconds:
            frame_start = time.monotonic()
            app.update()
            report['render_updates'] += 1
            time.sleep(max(0, 1/args.fps - (time.monotonic()-frame_start)))
        report['elapsed_seconds'] = time.monotonic()-start
        report['status'] = 'render_loop_completed_receiver_validation_required'
    except BaseException as exc:
        report['status'] = 'failed'
        report['error'] = repr(exc)
        raise
    finally:
        if timeline is not None:
            timeline.stop()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2))
        app.close()


if __name__ == '__main__':
    main()
