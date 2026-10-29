from pathlib import Path
import json,copy,yaml
root=Path('/home/seongmin/Projects/yolov8-ubuntu24-practice');old=root/'data/tagged-sixface-mixed-20261029';new=root/'data/tagged-sixface-v2-20261029';out=root/'data/tagged-sixface-v2-mixed-20261029';out.mkdir()
a=json.loads((old/'manifest.json').read_text());b=json.loads((new/'manifest.json').read_text());m=copy.deepcopy(b);m['samples']=[]
for src,samples in [(old,[s for s in a['samples'] if s['split']!='test']),(new,b['samples'])]:
 for s in samples:
  t=copy.deepcopy(s);t['image']=str(src/s['image']);m['samples'].append(t)
for split in ('train','val','test'):
 (out/f'{split}.txt').write_text('\n'.join(s['image'] for s in m['samples'] if s['split']==split)+'\n')
(out/'manifest.json').write_text(json.dumps(m,indent=2));(out/'dataset.yaml').write_text(yaml.safe_dump(dict(path=str(out),train='train.txt',val='val.txt',test='test.txt',names=dict(enumerate(m['classes'])))))
val=copy.deepcopy(m)
for s in val['samples']:s['split']='test' if s['split']=='val' else 'unused'
(out/'validation-manifest.json').write_text(json.dumps(val,indent=2))
sets={sp:{s['seed'] for s in m['samples'] if s['split']==sp} for sp in ('train','val','test')}
assert not sets['train']&sets['val'] and not sets['train']&sets['test'] and not sets['val']&sets['test']
report={'images':{sp:len(v) for sp,v in sets.items()},'overlap':0,'new_seed_range':[500000,501099],'scope':'Old test is excluded from further training; fresh test not used for selection.'}
(root/'reports/refinement-v2-20261029/split-audit.json').write_text(json.dumps(report,indent=2));print(report)
