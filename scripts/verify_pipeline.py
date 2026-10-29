"""Run GPU examples and retain evidence only from this verification run."""
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def require_file(path):
    path = Path(path)
    if not path.is_file():
        raise RuntimeError(f'Expected output was not produced: {path}')
    return path


def validate_tracking(summary):
    frames = summary.get('frames', 0)
    tracked = summary.get('frames_with_ids', 0)
    if not isinstance(frames, int) or not isinstance(tracked, int) or not 0 < tracked <= frames:
        raise RuntimeError(f'Tracking did not produce valid object IDs: {summary}')
    return summary


def main():
    # Imports are deferred so evidence checks can be tested without a GPU stack.
    import os
    import numpy as np
    import torch
    from ultralytics import YOLO, settings
    from inspect_onnx import inspect
    import onnxruntime as ort

    os.chdir(ROOT)
    settings.update({'datasets_dir': str(ROOT / 'datasets')})
    run_id = uuid.uuid4().hex[:12]
    report = {'run_id': run_id, 'status': 'running'}
    report_path = ROOT / 'reports/verification.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)

    def record(name, value):
        report[name] = value
        report_path.write_text(json.dumps(report, indent=2, default=str))

    def run(*args):
        subprocess.run([sys.executable, *args], check=True, cwd=ROOT)

    record('status', 'running')
    try:
        run('scripts/check_gpu.py')
        record('environment', {'torch': torch.__version__, 'cuda': torch.version.cuda,
                               'gpu': torch.cuda.get_device_name(0)})
        Path('data/demo').mkdir(parents=True, exist_ok=True)
        if not Path('data/demo/bus.jpg').exists():
            urllib.request.urlretrieve('https://raw.githubusercontent.com/ultralytics/assets/main/im/bus.jpg', 'data/demo/bus.jpg')
        model = YOLO('yolov8n.pt')
        result = model.predict('data/demo/bus.jpg', device=0, save=True,
                               project='runs/detect', name=f'install_check_{run_id}')[0]
        if result.boxes is None or len(result.boxes) == 0:
            raise RuntimeError('Bus inference produced no detections')
        record('bus_prediction', {'detections': len(result.boxes), 'output': result.save_dir})
        model.train(data='coco8.yaml', epochs=1, imgsz=640, batch=2, workers=2,
                    device=0, seed=317, project='runs/detect', name=f'install_train_{run_id}')
        require_file(model.trainer.save_dir / 'weights/best.pt')
        record('coco8_train', {'epochs': 1, 'output': model.trainer.save_dir})
        # Keep verification data/config separate from existing user datasets.
        synthetic = Path('data') / f'verification_{run_id}'
        config = synthetic / 'pucks.yaml'
        video = synthetic / 'test.mp4'
        dataset = synthetic / 'dataset'
        run('scripts/make_synthetic.py', '--output', str(dataset),
            '--config', str(config), '--video', str(video))
        run('scripts/validate_labels.py', str(dataset / 'labels'), '--classes', '4')
        name = f'synthetic_pucks_{run_id}'
        run('scripts/train_yolo.py', '--data', str(config), '--epochs', '10', '--batch', '4', '--name', name)
        weights = require_file(Path('runs/detect') / name / 'weights/best.pt')
        model = YOLO(weights)
        metrics = model.val(data=str(config), split='test', device=0,
                            project='runs/detect', name=f'synthetic_test_{run_id}')
        record('synthetic_test', {'weights': weights, 'metrics': metrics.results_dict,
                                 'note': 'Synthetic data only; not real puck accuracy'})
        track_name = f'synthetic_track_{run_id}'
        run('scripts/track_yolo.py', '--weights', str(weights), '--source',
            str(video), '--name', track_name)
        summary = require_file(Path('runs/track') / track_name / 'tracking-summary.json')
        record('synthetic_track', validate_tracking(json.loads(summary.read_text())))
        for name, weight, classes in [('yolov8s', 'yolov8s.pt', 80), ('pucks', str(weights), 4)]:
            run('scripts/export_onnx.py', '--weights', weight, '--output', f'models/{name}.onnx')
            meta = inspect(f'models/{name}.onnx')
            if meta['inputs'][0]['shape'] != [1, 3, 640, 640] or meta['outputs'][0]['shape'] != [1, 4 + classes, 8400]:
                raise RuntimeError(f'Unexpected ONNX dimensions: {meta}')
            x = np.random.default_rng(317).random((1, 3, 640, 640), dtype=np.float32)
            pt = YOLO(weight).model.cpu().eval().float()
            with torch.no_grad():
                y = pt(torch.from_numpy(x))[0].numpy()
            session = ort.InferenceSession(f'models/{name}.onnx', providers=['CPUExecutionProvider'])
            z = session.run(None, {meta['inputs'][0]['name']: x})[0]
            np.testing.assert_allclose(z, y, rtol=1e-3, atol=1e-3)
            record(f'{name}_onnx', dict(meta=meta, max_absolute_error=float(np.max(np.abs(z - y)))))
    except Exception as exc:
        record('error', f'{type(exc).__name__}: {exc}')
        record('status', 'failed')
        raise
    record('status', 'passed')
    print('PASS all available pipeline stages')


if __name__ == '__main__':
    main()
