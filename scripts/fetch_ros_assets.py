"""Download pinned Isaac ROS 5.0.0 sample assets into an explicit workspace."""
import argparse
import tarfile
import tempfile
import urllib.request
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('workspace', type=Path)
    a = p.parse_args()
    out = a.workspace.resolve() / 'isaac_ros_assets'
    target = out / 'isaac_ros_yolov8'
    if target.exists():
        raise SystemExit(f'Refusing to overwrite existing assets: {target}')
    out.mkdir(parents=True, exist_ok=True)
    version = '5.0.0'
    url = ('https://api.ngc.nvidia.com/v2/resources/nvidia/isaac/'
           f'isaac_ros_yolov8_assets/versions/{version}/files/quickstart.tar.gz')
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / 'quickstart.tar.gz'
        urllib.request.urlretrieve(url, archive)
        with tarfile.open(archive) as tar:
            tar.extractall(out, filter='data')
    assert (target / 'quickstart_interface_specs.json').is_file()
    assert (target / 'quickstart.bag/metadata.yaml').is_file()
    (out / 'yolov8-assets-version.txt').write_text(version + '\n')
    print(target)


if __name__ == '__main__':
    main()
