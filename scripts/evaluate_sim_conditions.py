"""Evaluate predeclared manifest conditions separately; never train on test data."""
import argparse
import json
from pathlib import Path
import yaml
from ultralytics import YOLO


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--weights', required=True)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--device', default='0')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    config = yaml.safe_load(a.data.read_text())
    root = Path(config['path']).resolve()
    manifest = json.loads((root / 'manifest.json').read_text())
    groups = {}
    for sample in manifest['samples']:
        if sample['split'] == 'test':
            groups.setdefault(sample['condition'], []).append(sample)
    model = YOLO(a.weights)
    report = {'weights': a.weights, 'scope': 'Same held-out test split grouped by predeclared condition', 'conditions': {}}
    for condition, samples in sorted(groups.items()):
        subset = a.output / f'{condition}.txt'
        subset.write_text(''.join(str(root / s['image']) + '\n' for s in samples))
        cfg = dict(config, test=str(subset.resolve()))
        data = a.output / f'{condition}.yaml'
        data.write_text(yaml.safe_dump(cfg))
        m = model.val(data=str(data), split='test', device=a.device, batch=1,
                      workers=0, imgsz=640, plots=False, project=str(a.output), name=condition)
        report['conditions'][condition] = dict(images=len(samples), objects=sum(len(s['boxes']) for s in samples),
            precision=float(m.box.mp), recall=float(m.box.mr), mAP50=float(m.box.map50), mAP50_95=float(m.box.map))
    (a.output / 'conditions.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
