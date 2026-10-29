import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from evaluate_sim import audit_splits, ground_truth_counts, latency_summary, metric_summary, split_images


class SimEvaluation(unittest.TestCase):
    def make_splits(self, root):
        splits = {}
        samples = []
        for i, split in enumerate(('train', 'val', 'test')):
            path = root / 'images' / split / 'sample.png'
            path.parent.mkdir(parents=True)
            path.write_bytes(bytes([i]))
            label = root / 'labels' / split / 'sample.txt'
            label.parent.mkdir(parents=True)
            label.write_text('0 .5 .5 .2 .2\n' if i < 2 else '')
            splits[split] = [path]
            samples.append({'image': str(path.relative_to(root)), 'split': split,
                            'session_id': f'{split}_scene'})
        return splits, {'samples': samples}

    def test_disjoint_data_and_sessions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            splits, manifest = self.make_splits(root)
            result = audit_splits(root, splits, manifest)
            self.assertTrue(result['passed'])
            self.assertEqual(result['session_check'], 'checked')
            self.assertEqual(split_images(root, 'images/test'), splits['test'])
            self.assertEqual(ground_truth_counts(splits['test'])[str(splits['test'][0])], 0)
            (root / 'labels/test/sample.txt').unlink()
            with self.assertRaises(ValueError):
                ground_truth_counts(splits['test'])

    def test_duplicate_content_and_session_leakage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            splits, manifest = self.make_splits(root)
            splits['test'][0].write_bytes(splits['train'][0].read_bytes())
            manifest['samples'][2]['session_id'] = 'train_scene'
            result = audit_splits(root, splits, manifest)
            self.assertFalse(result['passed'])
            self.assertEqual(len(result['sha256_cross_split_duplicates']), 1)
            self.assertEqual(len(result['session_cross_split_duplicates']), 1)

    def test_manifest_missing_entry_or_wrong_split(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            splits, manifest = self.make_splits(root)
            manifest['samples'].pop()
            manifest['samples'][0]['split'] = 'val'
            self.assertEqual(len(audit_splits(root, splits, manifest)['manifest_errors']), 2)
            self.assertEqual(audit_splits(root, splits)['session_check'], 'unavailable')

    def test_latency_statistics(self):
        result = latency_summary([.01, .02, .03, .04])
        self.assertAlmostEqual(result['p50_ms'], 25)
        self.assertAlmostEqual(result['p95_ms'], 38.5)
        self.assertAlmostEqual(result['fps'], 40)
        for values in ([], [0], [-1], [float('nan')], [float('inf')]):
            with self.assertRaises(ValueError):
                latency_summary(values)

    def test_metrics_preserve_class_index_mapping(self):
        box = SimpleNamespace(ap_class_index=[0, 3], p=[.1, .2], r=[.3, .4],
                              ap50=[.5, .6], ap=[.7, .8], mp=.15, mr=.35, map50=.55, map=.75)
        result = metric_summary(SimpleNamespace(box=box, names={0: 'red_cylinder', 3: 'green_prism'}))
        self.assertEqual(result['per_class'][1]['class_id'], 3)
        self.assertEqual(result['per_class'][1]['name'], 'green_prism')
        self.assertEqual(result['per_class'][1]['mAP50_95'], .8)
        self.assertEqual(result['mAP50'], .55)

    def test_cli_records_leakage_without_loading_model(self):
        try:
            import yaml
        except ImportError:
            self.skipTest('PyYAML unavailable')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            splits, manifest = self.make_splits(root)
            splits['test'][0].write_bytes(splits['train'][0].read_bytes())
            (root / 'manifest.json').write_text(json.dumps(manifest))
            data = root / 'dataset.yaml'
            data.write_text(yaml.safe_dump(dict(path=str(root), train='images/train', val='images/val', test='images/test')))
            out = root / 'report'
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/evaluate_sim.py'),
                                     '--weights', str(root / 'nonexistent.pt'), '--data', str(data),
                                     '--output', str(out), '--device', 'cpu'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            report = json.loads((out / 'evaluation.json').read_text())
            self.assertEqual(report['status'], 'failed')
            self.assertIn('Dataset integrity failed', report['error'])
            self.assertNotIn('metrics', report)


class SimVideoEvaluation(unittest.TestCase):
    def test_greedy_match_is_one_to_one_and_class_aware(self):
        from evaluate_sim_video import match_boxes
        gt = [{'class_id': 0, 'xyxy': [0, 0, 10, 10]}]
        predictions = [{'class_id': 1, 'xyxy': [0, 0, 10, 10]},
                       {'class_id': 0, 'xyxy': [0, 0, 10, 10]},
                       {'class_id': 0, 'xyxy': [1, 0, 11, 10]}]
        self.assertEqual(match_boxes(gt, predictions), [(0, 1, 1.0)])
        self.assertEqual(match_boxes(gt, [{'class_id': 0, 'xyxy': [20, 20, 30, 30]}]), [])

    def test_id_switch_and_gap_coverage(self):
        from evaluate_sim_video import TrackingCounts
        gt = [{'class_id': 0, 'xyxy': [0, 0, 10, 10]}]
        counts = TrackingCounts()
        for track_id in (1, None, 2, 2):
            predictions = [dict(gt[0], track_id=track_id)] if track_id is not None else []
            counts.update(gt, predictions, 'heldout')
        result = counts.summary()
        self.assertEqual(result['id_switches'], 1)
        self.assertEqual(result['ground_truth_recall'], .75)
        self.assertEqual(result['prediction_precision'], 1)
        self.assertEqual(result['observed_id_coverage'], .75)
        self.assertEqual(result['per_identity']['heldout:0']['observed_ids'], [1, 2])

    def test_no_id_is_not_identity_coverage_and_sessions_are_separate(self):
        from evaluate_sim_video import TrackingCounts
        counts = TrackingCounts()
        gt = [{'class_id': 0, 'xyxy': [0, 0, 10, 10]}]
        counts.update(gt, [dict(gt[0], track_id=None)], 's1')
        counts.update(gt, [dict(gt[0], track_id=1)], 's1')
        counts.update(gt, [dict(gt[0], track_id=9)], 's2')
        self.assertEqual(counts.summary()['id_switches'], 0)
        self.assertAlmostEqual(counts.summary()['observed_id_coverage'], 2/3)
        with self.assertRaises(ValueError):
            counts.update(gt + gt, [], 's1')


if __name__ == '__main__':
    unittest.main()
