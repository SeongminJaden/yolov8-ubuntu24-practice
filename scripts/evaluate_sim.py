"""Evaluate a held-out Isaac Sim YOLO dataset without invented quality thresholds."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}


def split_images(root, entry):
    entries = entry if isinstance(entry, list) else [entry]
    found = []
    for item in entries:
        path = Path(item)
        if not path.is_absolute():
            path = root / path
        if path.is_dir():
            found.extend(p.resolve() for p in path.rglob('*') if p.suffix.lower() in IMAGE_SUFFIXES)
        elif path.suffix.lower() == '.txt' and path.is_file():
            for line in path.read_text().splitlines():
                if line.strip():
                    image = Path(line.strip())
                    found.append((image if image.is_absolute() else path.parent / image).resolve())
        else:
            found.append(path.resolve())
    if not found:
        raise ValueError('Dataset split has no images')
    for path in found:
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError(f'Missing or unsupported image: {path}')
    if len(found) != len(set(found)):
        raise ValueError('Repeated image path within a split')
    return sorted(found)


def audit_splits(root, splits, manifest=None):
    """Check byte-identical cross-split images and generation session reuse."""
    hashes = {}
    for split, images in splits.items():
        for path in images:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes.setdefault(digest, []).append({'split': split, 'image': str(path)})
    duplicates = [items for items in hashes.values() if len({x['split'] for x in items}) > 1]
    result = {'sha256_cross_split_duplicates': duplicates,
              'image_counts': {key: len(value) for key, value in splits.items()},
              'session_check': 'unavailable', 'session_cross_split_duplicates': [],
              'manifest_errors': []}
    if manifest is not None:
        result['session_check'] = 'checked'
        records = manifest.get('samples')
        if not isinstance(records, list):
            raise ValueError('manifest.json must contain a samples list')
        mapping, sessions = {}, {}
        for item in records:
            if not isinstance(item, dict) or not all(item.get(k) for k in ('image', 'split', 'session_id')):
                result['manifest_errors'].append('Sample missing image, split, or session_id')
                continue
            path = (root / item['image']).resolve()
            if path in mapping:
                result['manifest_errors'].append(f'Duplicate manifest image: {path}')
            mapping[path] = item
        for split, images in splits.items():
            for path in images:
                item = mapping.get(path.resolve())
                if item is None or item['split'] != split:
                    result['manifest_errors'].append(f'Missing or mismatched manifest split: {path}')
                    continue
                sessions.setdefault(str(item['session_id']), set()).add(split)
        result['session_cross_split_duplicates'] = [
            {'session_id': key, 'splits': sorted(value)}
            for key, value in sorted(sessions.items()) if len(value) > 1]
    result['passed'] = not (duplicates or result['session_cross_split_duplicates'] or result['manifest_errors'])
    return result



def ground_truth_counts(images):
    """Require explicit labels, including empty files for negative images."""
    counts = {}
    for image in images:
        parts = list(image.parts)
        if 'images' not in parts:
            raise ValueError(f'Expected images/labels dataset layout: {image}')
        index = len(parts) - 1 - parts[::-1].index('images')
        parts[index] = 'labels'
        label = Path(*parts).with_suffix('.txt')
        if not label.is_file():
            raise ValueError(f'Missing label (negative images need an empty file): {label}')
        counts[str(image)] = sum(bool(line.strip()) for line in label.read_text().splitlines())
    return counts


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def latency_summary(seconds):
    if not seconds or any(not math.isfinite(x) or x <= 0 for x in seconds):
        raise ValueError('Latency samples must be finite and positive')
    return {'count': len(seconds), 'p50_ms': 1000 * percentile(seconds, .5),
            'p95_ms': 1000 * percentile(seconds, .95),
            'mean_ms': 1000 * sum(seconds) / len(seconds),
            'fps': len(seconds) / sum(seconds)}


def metric_summary(metrics):
    box = metrics.box
    names = metrics.names
    classes = []
    for i, class_id in enumerate(box.ap_class_index):
        class_id = int(class_id)
        classes.append({'class_id': class_id, 'name': names[class_id],
                        'precision': float(box.p[i]), 'recall': float(box.r[i]),
                        'mAP50': float(box.ap50[i]), 'mAP50_95': float(box.ap[i])})
    return {'precision': float(box.mp), 'recall': float(box.mr),
            'mAP50': float(box.map50), 'mAP50_95': float(box.map),
            'per_class': classes,
            'note': 'Per-class values are reported only for evaluated ground-truth classes.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--weights', required=True, type=Path)
    parser.add_argument('--data', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New report directory')
    parser.add_argument('--device', default='0')
    args = parser.parse_args()
    import yaml
    config = yaml.safe_load(args.data.read_text())
    root = Path(config['path'])
    if not root.is_absolute():
        parser.error('dataset.yaml path must be absolute')
    splits = {split: split_images(root, config[split]) for split in ('train', 'val', 'test')}
    manifest_path = root / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    audit = audit_splits(root, splits, manifest)
    ground_truth = ground_truth_counts(splits['test'])
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'weights': str(args.weights.resolve()),
              'data': str(args.data.resolve()), 'device': args.device, 'integrity': audit,
              'scope': 'Rendered simulation test split; not evidence of real-camera accuracy.'}
    report_path = args.output / 'evaluation.json'

    def save():
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False))

    save()
    try:
        if not audit['passed']:
            raise ValueError('Dataset integrity failed; inspect evaluation.json')
        from ultralytics import YOLO
        import torch
        import cv2
        model = YOLO(str(args.weights))
        metrics = model.val(data=str(args.data.resolve()), split='test', device=args.device,
                            imgsz=640, batch=1, workers=0, project=str(args.output.resolve()),
                            name='validation', plots=True)
        report['metrics'] = metric_summary(metrics)
        save()
        # Use the same file-input prediction API for warmup and timing. CUDA sync
        # includes all pending GPU work; plotting/disk output is outside timing.
        def sync():
            parameter = next(model.model.parameters())
            if parameter.is_cuda:
                torch.cuda.synchronize(parameter.device)

        warmup = 3
        for _ in range(warmup):
            model.predict(str(splits['test'][0]), device=args.device, imgsz=640, conf=0.25, verbose=False)
        sync()
        seconds, predictions = [], []
        samples = args.output / 'sample_predictions'
        samples.mkdir()
        for i, path in enumerate(splits['test']):
            sync()
            start = time.perf_counter()
            result = model.predict(str(path), device=args.device, imgsz=640, conf=0.25, verbose=False)[0]
            sync()
            seconds.append(time.perf_counter() - start)
            predictions.append({'image': str(path), 'detections': len(result.boxes),
                                'ground_truth_objects': ground_truth[str(path)],
                                'class_ids': result.boxes.cls.int().cpu().tolist()})
            if i < 6 and not cv2.imwrite(str(samples / f'{i:04}_{path.stem}.jpg'), result.plot()):
                raise RuntimeError('Could not save prediction image')
        report['latency'] = dict(latency_summary(seconds), warmup_frames_excluded=warmup,
                                 scope='Sequential file-input predict wall time including decode, preprocess, inference and postprocess; excluding plotting and saving.',
                                 prediction_confidence=0.25, samples_seconds=seconds)
        report['predictions'] = predictions
        report['counts'] = {'test_images': len(predictions),
                            'detections': sum(x['detections'] for x in predictions),
                            'ground_truth_objects': sum(ground_truth.values()),
                            'negative_images': sum(count == 0 for count in ground_truth.values()),
                            'negative_images_with_false_positives': sum(x['ground_truth_objects'] == 0 and x['detections'] > 0 for x in predictions),
                            'images_with_detections': sum(x['detections'] > 0 for x in predictions)}
        report['status'] = 'completed'
        save()
    except Exception as exc:
        report['status'] = 'failed'
        report['error'] = f'{type(exc).__name__}: {exc}'
        save()
        raise
    print(report_path)


if __name__ == '__main__':
    main()
