"""Measure detection and identity continuity on held-out rendered video frames."""
import argparse
import json
from pathlib import Path
import time

from evaluate_sim import latency_summary


def iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def match_boxes(ground_truth, predictions, threshold=0.5):
    candidates = []
    for gi, gt in enumerate(ground_truth):
        for pi, prediction in enumerate(predictions):
            overlap = iou(gt['xyxy'], prediction['xyxy'])
            if gt['class_id'] == prediction['class_id'] and overlap >= threshold:
                candidates.append((overlap, gi, pi))
    used_gt, used_predictions, matches = set(), set(), []
    for overlap, gi, pi in sorted(candidates, key=lambda x: (-x[0], x[1], x[2])):
        if gi not in used_gt and pi not in used_predictions:
            matches.append((gi, pi, overlap))
            used_gt.add(gi)
            used_predictions.add(pi)
    return matches


class TrackingCounts:
    def __init__(self):
        self.gt_count = self.prediction_count = self.matches = self.matches_with_ids = 0
        self.switches = 0
        self.last_ids = {}
        self.ids_by_identity = {}
        self.gt_by_identity = {}
        self.matched_by_identity = {}

    def update(self, gt, predictions, session):
        # This dataset has exactly one physical object per class in each session.
        classes = [box['class_id'] for box in gt]
        if len(classes) != len(set(classes)):
            raise ValueError('Class-based physical identities require at most one GT object per class')
        self.gt_count += len(gt)
        self.prediction_count += len(predictions)
        for box in gt:
            key = f"{session}:{box['class_id']}"
            self.gt_by_identity[key] = self.gt_by_identity.get(key, 0) + 1
        matches = match_boxes(gt, predictions)
        self.matches += len(matches)
        for gi, pi, _ in matches:
            identity = f"{session}:{gt[gi]['class_id']}"
            track_id = predictions[pi].get('track_id')
            if track_id is None:
                continue
            self.matches_with_ids += 1
            if identity in self.last_ids and self.last_ids[identity] != track_id:
                self.switches += 1
            self.last_ids[identity] = track_id
            self.ids_by_identity.setdefault(identity, set()).add(track_id)
            self.matched_by_identity[identity] = self.matched_by_identity.get(identity, 0) + 1
        return matches

    def summary(self):
        return {'ground_truth_instances': self.gt_count, 'predicted_instances': self.prediction_count,
                'matched_instances': self.matches, 'matched_instances_with_ids': self.matches_with_ids,
                'ground_truth_recall': self.matches / self.gt_count if self.gt_count else None,
                'prediction_precision': self.matches / self.prediction_count if self.prediction_count else None,
                'id_switches': self.switches,
                'observed_id_coverage': self.matches_with_ids / self.gt_count if self.gt_count else None,
                'per_identity': {key: {'ground_truth_frames': count,
                                      'matched_frames_with_id': self.matched_by_identity.get(key, 0),
                                      'observed_ids': sorted(self.ids_by_identity.get(key, set())),
                                      'id_coverage': self.matched_by_identity.get(key, 0) / count}
                                 for key, count in sorted(self.gt_by_identity.items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--device', default='0')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    frames = manifest['video']
    if not frames:
        parser.error('No video frames in manifest')
    # Preserve the generated sequence and reject ambiguous order or split leakage.
    sequence = [(item['session_id'], int(item['frame'])) for item in frames]
    if len(sequence) != len(set(sequence)):
        parser.error('Duplicate session/frame entries')
    sessions = {item['session_id'] for item in frames}
    sample_sessions = {item['session_id'] for item in manifest.get('samples', [])}
    if sessions & sample_sessions:
        parser.error('Video sessions overlap image dataset sessions')
    last_frame = {}
    closed_sessions = set()
    current_session = None
    for item in frames:
        session = item['session_id']
        if current_session != session:
            if session in closed_sessions:
                parser.error('Video session frames must be contiguous')
            if current_session is not None:
                closed_sessions.add(current_session)
            current_session = session
        if int(item['frame']) <= last_frame.get(session, -1):
            parser.error('Frame indices must increase within each session')
        last_frame[session] = int(item['frame'])
    args.output.mkdir(parents=True, exist_ok=False)
    report_path = args.output / 'video-evaluation.json'
    report = {'status': 'running', 'manifest': str(args.manifest.resolve()),
              'weights': str(args.weights.resolve()), 'device': args.device,
              'matching': 'Greedy descending IoU >= 0.5, same class, one-to-one',
              'identity_assumption': 'One stable physical object per class per session. ID switches compare successive matched IDs, including across detection gaps. Not standard MOTChallenge IDF1/HOTA.',
              'scope': 'Rendered held-out video only; throughput measures tracking, not Isaac Sim rendering.',
              'confidence': 0.25, 'frames': []}

    def save():
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False))

    save()
    writer = None
    try:
        import cv2
        import torch
        from ultralytics import YOLO
        model = YOLO(str(args.weights))
        counts = TrackingCounts()
        latencies = []
        current_session = None
        excluded = 0
        for index, item in enumerate(frames):
            path = args.manifest.parent / item['image']
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError(f'Cannot decode frame: {path}')
            session = item['session_id']
            if current_session != session:
                # Reset tracking state at genuine session boundaries, and warm the
                # prediction network without feeding future frames to the tracker.
                if current_session is not None:
                    model = YOLO(str(args.weights))
                for _ in range(3):
                    model.predict(image, device=args.device, imgsz=640, conf=.25, verbose=False)
                current_session = session
                session_index = 0

            def sync():
                parameter = next(model.model.parameters())
                if parameter.is_cuda:
                    torch.cuda.synchronize(parameter.device)

            sync()
            started = time.perf_counter()
            result = model.track(image, persist=True, tracker='bytetrack.yaml', conf=.25,
                                 device=args.device, imgsz=640, verbose=False)[0]
            sync()
            seconds = time.perf_counter() - started
            # Tracker initialization consumes extra time; retain its accuracy data
            # while excluding the first 3 tracker frames from steady-state latency.
            if session_index >= 3:
                latencies.append(seconds)
            else:
                excluded += 1
            session_index += 1
            predictions = []
            boxes = result.boxes
            if boxes is not None:
                ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(boxes)
                predictions = [{'class_id': int(c), 'xyxy': xyxy, 'track_id': track_id}
                               for c, xyxy, track_id in zip(boxes.cls.cpu().tolist(), boxes.xyxy.cpu().tolist(), ids)]
            matches = counts.update(item['boxes'], predictions, session)
            report['frames'].append({'frame': item['frame'], 'session_id': session,
                                     'latency_seconds': seconds, 'predictions': predictions,
                                     'matches': [{'ground_truth_index': gi, 'prediction_index': pi, 'iou': overlap}
                                                 for gi, pi, overlap in matches]})
            annotated = result.plot()
            if index == 0:
                fps = float(manifest.get('video_fps', 30))
                writer = cv2.VideoWriter(str(args.output / 'annotated.mp4'), cv2.VideoWriter_fourcc(*'mp4v'),
                                         fps, (image.shape[1], image.shape[0]))
                report['annotated_video'] = 'annotated.mp4' if writer.isOpened() else None
                report['video_playback_fps'] = fps
            if writer is not None and writer.isOpened():
                writer.write(annotated)
            elif index < 6:
                if not cv2.imwrite(str(args.output / f'frame_{index:04}.jpg'), annotated):
                    raise RuntimeError('Cannot write annotated frame')
        report['metrics'] = counts.summary()
        report['latency'] = dict(latency_summary(latencies), warmup_tracking_frames_excluded=excluded,
                                 scope='NumPy-input model.track wall time including preprocess/inference/tracking/postprocess, excluding frame read, plotting and encoding.') if latencies else {'count': 0, 'warmup_tracking_frames_excluded': excluded, 'note': 'No steady-state frames available'}
        report['status'] = 'completed'
        save()
    except Exception as exc:
        report['status'] = 'failed'
        report['error'] = f'{type(exc).__name__}: {exc}'
        save()
        raise
    finally:
        if writer is not None:
            writer.release()
    print(report_path)


if __name__ == '__main__':
    main()
