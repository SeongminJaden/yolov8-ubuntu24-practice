from pathlib import Path
import json,random,copy,yaml
root=Path('/home/seongmin/Projects/yolov8-ubuntu24-practice')
old=root/'data/tagged-test';new=root/'data/tagged-sixface-20261029';out=root/'data/tagged-sixface-mixed-20261029'
a=json.loads((old/'manifest.json').read_text());b=json.loads((new/'manifest.json').read_text());out.mkdir()
rng=random.Random(317);chosen=rng.sample([s for s in a['samples'] if s['split']=='train'],400)
m=copy.deepcopy(b);m['samples']=[]
for src,samples in [(old,chosen),(new,b['samples'])]:
 for s in samples:
  t=copy.deepcopy(s);t['image']=str(src/s['image']);m['samples'].append(t)
for split in ['train','val','test']:
 (out/f'{split}.txt').write_text('\n'.join(s['image'] for s in m['samples'] if s['split']==split)+'\n')
(out/'manifest.json').write_text(json.dumps(m,indent=2))
(out/'dataset.yaml').write_text(yaml.safe_dump(dict(path=str(out),train='train.txt',val='val.txt',test='test.txt',names=dict(enumerate(a['classes'])))))
val=copy.deepcopy(m)
for s in val['samples']:s['split']='test' if s['split']=='val' else 'unused'
(out/'validation-manifest.json').write_text(json.dumps(val,indent=2))
seeds={sp:{s['seed'] for s in m['samples'] if s['split']==sp} for sp in ['train','val','test']}
assert not seeds['train']&seeds['val'] and not seeds['train']&seeds['test'] and not seeds['val']&seeds['test']
print({sp:len([s for s in m['samples'] if s['split']==sp]) for sp in seeds})
