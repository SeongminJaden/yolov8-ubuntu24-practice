"""Official TAO CenterPose DLA34 architecture with a custom crop training harness.

Predicts geometric center heatmap and ordered 3D cuboid corner projections.
Metric pose comes from predicted corners + calibrated PnP and known dimensions.
This checkpoint is not a drop-in Isaac ROS/TAO exported model.
"""
import argparse
import json
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import cv2
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from third_party.centerpose.centerpose import CenterPose_DLA34

SIZE=128
GRID=32
CORNERS=np.array([[x,y,z] for x in [-.015,.015] for y in [-.015,.015] for z in [-.03,.03]],np.float64)

def make_model():
    return CenterPose_DLA34(SimpleNamespace(down_ratio=4,final_kernel=1,last_level=5,head_conv=64,out_channel=0,use_convGRU=False,use_pretrained=False))

def crop_image(image, box, jitter=None):
    x1,y1,x2,y2=box
    side=max(x2-x1,y2-y1)*1.5
    cx,cy=(x1+x2)/2,(y1+y2)/2
    if jitter is not None:
        cx+=jitter.uniform(-.05,.05)*side;cy+=jitter.uniform(-.05,.05)*side
        side*=jitter.uniform(.9,1.1)
    matrix=np.array([[SIZE/side,0,SIZE/2-cx*SIZE/side],[0,SIZE/side,SIZE/2-cy*SIZE/side]],np.float32)
    crop=cv2.warpAffine(image,matrix,(SIZE,SIZE),borderValue=(114,114,114))
    tensor=torch.from_numpy(cv2.cvtColor(crop,cv2.COLOR_BGR2RGB).transpose(2,0,1).copy()).float()/255
    return tensor,matrix

class Samples(Dataset):
    def __init__(self,manifest,split):
        self.root=manifest.parent;self.split=split;self.items=[]
        data=json.loads(manifest.read_text())
        self.images={}
        for sample in data['samples']:
            if sample['split']!=split:continue
            for pose in sample['poses']:
                boxes=[b for b in sample['boxes'] if b['class_id']==pose['class_id']]
                if boxes:self.items.append((sample['image'],pose,boxes[0]['xyxy']))
        for image,_,_ in self.items:
            if image not in self.images:self.images[image]=cv2.imread(str(self.root/image))
    def __len__(self):return len(self.items)
    def __getitem__(self,index):
        image,pose,box=self.items[index]
        x,m=crop_image(self.images[image],box,random if self.split=='train' else None)
        pts=np.array(pose['projected_cuboid'],np.float32)
        pts=(pts@m[:,:2].T+m[:,2])/4
        ct=pts[0]; ij=np.clip(ct.astype(int),0,GRID-1)
        yy,xx=np.mgrid[:GRID,:GRID]
        heat=np.exp(-((xx-ij[0])**2+(yy-ij[1])**2)/2).astype(np.float32)[None]
        hps=(pts[1:]-ij).reshape(-1).astype(np.float32)
        return x,torch.from_numpy(heat),torch.tensor(ij),torch.from_numpy(hps),torch.tensor(ct-ij,dtype=torch.float32)

def loss_for(out,heat,ij,hps,reg):
    prob=out['hm'].sigmoid().clamp(1e-5,1-1e-5)
    pos=heat.eq(1);neg=heat.lt(1)
    hm=-(torch.log(prob)*(1-prob)**2*pos+torch.log(1-prob)*prob**2*(1-heat)**4*neg).sum()/max(1,len(ij))
    idx=torch.arange(len(ij),device=ij.device)
    pred=out['hps'][idx,:,ij[:,1],ij[:,0]]
    offset=out['reg'][idx,:,ij[:,1],ij[:,0]]
    # Only the heads used by this crop inference path are supervised.
    # A square prism and a cylinder admit at least 90-degree axial symmetry.
    # Minimize a consistent whole-cuboid permutation, never independent corners.
    targets=hps.reshape(-1,8,2)
    variants=[]
    for angle in range(4):
        R=np.array([[np.cos(angle*np.pi/2),-np.sin(angle*np.pi/2),0],[np.sin(angle*np.pi/2),np.cos(angle*np.pi/2),0],[0,0,1]])
        rotated=CORNERS@R.T
        perm=np.linalg.norm(rotated[:,None]-CORNERS[None],axis=-1).argmin(1)
        variants.append(nn.functional.smooth_l1_loss(pred.reshape(-1,8,2),targets[:,perm],reduction='none').mean((1,2)))
    corner_loss=torch.stack(variants,dim=1).min(1).values.mean()
    return hm+corner_loss+nn.functional.l1_loss(offset,reg)

def load_model(path,device='cuda'):
    ck=torch.load(path,map_location=device,weights_only=False)
    model=make_model().to(device);model.load_state_dict(ck['model']);model.eval()
    return model

@torch.inference_mode()
def infer(model,image,box,K,device='cuda'):
    x,m=crop_image(image,box)
    out=model(x[None].to(device))[0]
    heat=out['hm'][0,0].sigmoid();flat=int(heat.argmax());y,x=divmod(flat,GRID)
    score=float(heat[y,x]);ij=np.array([x,y],np.float32)
    ct=(ij+out['reg'][0,:,y,x].cpu().numpy())*4
    corners=(out['hps'][0,:,y,x].cpu().numpy().reshape(8,2)+ij)*4
    inv=cv2.invertAffineTransform(m)
    pixels=corners@inv[:,:2].T+inv[:,2];center_px=ct@inv[:,:2].T+inv[:,2]
    ok,rvec,tvec=cv2.solvePnP(CORNERS,pixels.astype(np.float64),K,np.zeros(5),flags=cv2.SOLVEPNP_EPNP)
    result=dict(source='centerpose_dla34_custom_crop',confidence=score,center_px=center_px.tolist(),corners_px=pixels.tolist(),valid=False)
    if ok:
        rvec,tvec=cv2.solvePnPRefineLM(CORNERS,pixels.astype(np.float64),K,np.zeros(5),rvec,tvec)
        reproj,_=cv2.projectPoints(CORNERS,rvec,tvec,K,np.zeros(5))
        error=float(np.linalg.norm(reproj.reshape(-1,2)-pixels,axis=1).mean())
        valid=bool(tvec[2,0]>0 and np.isfinite(tvec).all() and error<10 and score>=.25)
        result.update(valid=valid,center_camera_m=tvec.reshape(3).tolist(),rotation_matrix=cv2.Rodrigues(rvec)[0].tolist(),reprojection_error_px=error)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--resume',type=Path);p.add_argument('--epochs',type=int,default=40);p.add_argument('--batch',type=int,default=16)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(4);torch.manual_seed(317);np.random.seed(317);random.seed(317)
    model=load_model(a.resume) if a.resume else make_model().cuda();opt=torch.optim.Adam(model.parameters(),lr=.0005)
    train=DataLoader(Samples(a.manifest,'train'),batch_size=a.batch,shuffle=True,num_workers=0)
    val=DataLoader(Samples(a.manifest,'val'),batch_size=a.batch,num_workers=0)
    best=float('inf');history=[]
    for epoch in range(a.epochs):
        model.train();total=0
        for batch in train:
            x,heat,ij,hps,reg=[v.cuda() for v in batch]
            out=model(x)[0];loss=loss_for(out,heat,ij,hps,reg)
            opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),10);opt.step();total+=float(loss.detach())
        model.eval();vtotal=0
        with torch.no_grad():
            for batch in val:
                x,heat,ij,hps,reg=[v.cuda() for v in batch];vtotal+=float(loss_for(model(x)[0],heat,ij,hps,reg))
        row=dict(epoch=epoch+1,train_loss=total/len(train),val_loss=vtotal/len(val));history.append(row);print(row,flush=True)
        if row['val_loss']<best:
            best=row['val_loss'];torch.save(dict(model=model.state_dict(),epoch=epoch+1,scope='Custom crop harness; hm/hps/reg supervised, other heads unused',dimensions_m=[.03,.03,.06]),a.output/'best.pt')
        (a.output/'history.json').write_text(json.dumps(history,indent=2))

if __name__=='__main__':main()
