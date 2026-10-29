"""Run actual GPU inference/training/export; keep JSON evidence per completed stage."""
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import numpy as np
import torch
from ultralytics import YOLO, settings
from inspect_onnx import inspect

root=Path.cwd()
settings.update({'datasets_dir':str(root/'datasets')})
report={}
def record(name,value):
    report[name]=value
    Path('reports/verification.json').write_text(json.dumps(report,indent=2,default=str))
def run(*args): subprocess.run([sys.executable,*args],check=True)
run('scripts/check_gpu.py')
record('environment',{'torch':torch.__version__,'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0)})
Path('data/demo').mkdir(parents=True,exist_ok=True)
if not Path('data/demo/bus.jpg').exists():
    urllib.request.urlretrieve('https://raw.githubusercontent.com/ultralytics/assets/main/im/bus.jpg','data/demo/bus.jpg')
m=YOLO('yolov8n.pt')
r=m.predict('data/demo/bus.jpg',device=0,save=True,project='runs/detect',name='install_check')[0]
assert len(r.boxes)>0
record('bus_prediction',{'detections':len(r.boxes),'output':r.save_dir})
m.train(data='coco8.yaml',epochs=1,imgsz=640,batch=2,workers=2,device=0,project='runs/detect',name='install_train')
assert (m.trainer.save_dir/'weights/best.pt').is_file()
record('coco8_train',{'epochs':1,'output':m.trainer.save_dir})
run('scripts/train_yolo.py','--epochs','10','--batch','4','--name','synthetic_pucks')
# Find the actual output rather than silently assuming a suffix.
weights=max(Path('runs/detect').glob('synthetic_pucks*/weights/best.pt'),key=lambda p:p.stat().st_mtime)
m=YOLO(weights)
metrics=m.val(data='configs/pucks-local.yaml',split='test',device=0,project='runs/detect',name='synthetic_test')
record('synthetic_test',{'weights':weights,'metrics':metrics.results_dict,'note':'Synthetic data only; not real puck accuracy'})
run('scripts/track_yolo.py','--weights',str(weights),'--source','data/test.mp4','--name','synthetic_track')
record('synthetic_track',json.loads(max(Path('runs/track').glob('synthetic_track*/tracking-summary.json'),key=lambda p:p.stat().st_mtime).read_text()))
for name,weight,classes in [('yolov8s','yolov8s.pt',80),('pucks',str(weights),4)]:
    run('scripts/export_onnx.py','--weights',weight,'--output',f'models/{name}.onnx')
    meta=inspect(f'models/{name}.onnx')
    assert meta['inputs'][0]['shape']==[1,3,640,640]
    assert meta['outputs'][0]['shape']==[1,4+classes,8400]
    import onnxruntime as ort
    x=np.random.default_rng(317).random((1,3,640,640),dtype=np.float32)
    pt=YOLO(weight).model.eval().float()
    with torch.no_grad(): y=pt(torch.from_numpy(x))[0].numpy()
    session=ort.InferenceSession(f'models/{name}.onnx',providers=['CPUExecutionProvider'])
    z=session.run(None,{'images':x})[0]
    np.testing.assert_allclose(z,y,rtol=1e-3,atol=1e-3)
    record(f'{name}_onnx',dict(meta=meta,max_absolute_error=float(np.max(np.abs(z-y)))))
print('PASS all available pipeline stages')
