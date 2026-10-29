"""CPU-only regression checks for trustworthy pipeline evidence."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_pipeline import require_file, validate_tracking


class Verification(unittest.TestCase):
    def test_missing_current_artifact_cannot_use_old_run(self):
        with tempfile.TemporaryDirectory() as folder:
            old = Path(folder) / 'old/weights/best.pt'
            old.parent.mkdir(parents=True)
            old.touch()
            with self.assertRaises(RuntimeError):
                require_file(Path(folder) / 'current/weights/best.pt')
            self.assertEqual(require_file(old), old)

    def test_tracking_requires_ids_in_processed_frames(self):
        for summary in [{}, {'frames': 10, 'frames_with_ids': 0},
                        {'frames': 0, 'frames_with_ids': 1},
                        {'frames': 10, 'frames_with_ids': 11},
                        {'frames': '10', 'frames_with_ids': 1}]:
            with self.subTest(summary=summary), self.assertRaises(RuntimeError):
                validate_tracking(summary)
        self.assertEqual(validate_tracking({'frames': 10, 'frames_with_ids': 2})['frames'], 10)

    def test_single_label_file_is_validated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'labels.txt'
            path.write_text('0 .5 .5 .2 .2\n')
            command = [sys.executable, str(ROOT / 'scripts/validate_labels.py'), str(path)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            path.write_text('9 .5 .5 .2 .2\n')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('invalid class', result.stderr)

    def test_empty_background_still_rejects_invalid_class_count(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'empty.txt').touch()
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_labels.py'),
                                     folder, '--classes', '0'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('--classes must be positive', result.stderr)


@unittest.skipUnless(all(importlib.util.find_spec(name) for name in ('cv2', 'numpy', 'yaml')),
                     'Synthetic generator dependencies are not installed')
class SyntheticOutputs(unittest.TestCase):
    def test_isolated_outputs_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            config = base / 'custom/config.yaml'
            video = base / 'custom/clip.mp4'
            dataset = base / 'dataset'
            command = [sys.executable, str(ROOT / 'scripts/make_synthetic.py'),
                       '--output', str(dataset), '--config', str(config), '--video', str(video)]
            result = subprocess.run(command, cwd=base, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(list(dataset.rglob('*.jpg'))), 72)
            self.assertEqual(len(list(dataset.rglob('*.txt'))), 72)
            self.assertGreater(video.stat().st_size, 0)
            self.assertIn(str(dataset), config.read_text())
            old_config = config.read_bytes()
            # A different dataset must still not overwrite an existing config/video.
            command[command.index('--output') + 1] = str(base / 'fresh-dataset')
            result = subprocess.run(command, cwd=base, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((base / 'fresh-dataset').exists())
            self.assertEqual(config.read_bytes(), old_config)


if __name__ == '__main__':
    unittest.main()
