"""Generate fixed 30x30x60 mm / diameter30x60 mm tagged pucks and pose GT.
Requires the separate Isaac Sim Python environment and accepted NVIDIA EULA.
"""
import argparse
import json
from pathlib import Path
import math
import random
import time

NAMES=['red_cylinder','red_prism','green_cylinder','green_prism']

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--train',type=int,default=160)
    p.add_argument('--val',type=int,default=40)
    p.add_argument('--test',type=int,default=80)
    p.add_argument('--video-frames',type=int,default=120)
    p.add_argument('--tag-size',type=float,default=.016)
    p.add_argument('--tag-patterns',type=Path,default=Path(__file__).resolve().parents[1]/'configs/tags/tag36h11.json')
    a=p.parse_args()
    out=a.output.resolve()
    if not 0 < a.tag_size <= .01697: p.error('Tag plus white margin must fit a diameter 30mm top')
    patterns=json.loads(a.tag_patterns.read_text())
    if out.exists():raise SystemExit('Refusing to overwrite dataset')
    from isaacsim import SimulationApp
    app=SimulationApp({'headless':True,'renderer':'RaytracedLighting','width':640,'height':640,
                       'anti_aliasing':0,'multi_gpu':False})
    try:
        import omni.usd
        import omni.replicator.core as rep
        import numpy as np
        from PIL import Image
        from pxr import UsdGeom,UsdLux,UsdShade,UsdSemantics,Gf,Sdf
        stage=omni.usd.get_context().get_stage()
        UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage,1.0)
        UsdGeom.Xform.Define(stage,'/World')
        def material(path,color):
            m=UsdShade.Material.Define(stage,path)
            sh=UsdShade.Shader.Define(stage,path+'/Shader');sh.CreateIdAttr('UsdPreviewSurface')
            sh.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
            sh.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.55)
            m.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(),'surface')
            return m,sh
        ground=UsdGeom.Cube.Define(stage,'/World/Table');ground.CreateSizeAttr(1)
        ground.AddTransformOp().Set(Gf.Matrix4d().SetScale(Gf.Vec3d(1.8,1.5,.025))*Gf.Matrix4d().SetTranslate(Gf.Vec3d(0,0,-.0125)))
        table_mat,table_sh=material('/World/TableMaterial',(.25,.25,.24))
        UsdShade.MaterialBindingAPI.Apply(ground.GetPrim()).Bind(table_mat)
        targets=[]
        tags=[]
        black,_=material('/World/TagBlack',(.001,.001,.001))
        white,_=material('/World/TagWhite',(.95,.95,.95))
        def tile(path, bounds, mat):
            x1,y1,x2,y2,z=bounds
            mesh=UsdGeom.Mesh.Define(stage,path)
            mesh.CreatePointsAttr([Gf.Vec3f(x1,y1,z),Gf.Vec3f(x2,y1,z),Gf.Vec3f(x2,y2,z),Gf.Vec3f(x1,y2,z)])
            mesh.CreateFaceVertexCountsAttr([4]);mesh.CreateFaceVertexIndicesAttr([0,1,2,3])
            mesh.CreateDoubleSidedAttr(True)
            UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)
        for c in range(4):
            tag=UsdGeom.Xform.Define(stage,f'/World/Tag{c}')
            top=a.tag_size*1.25/2
            tile(f'/World/Tag{c}/White',(-top,-top,top,top,.03002),white)
            for row,pixels in enumerate(patterns[str(c)]):
                for col,pixel in enumerate(pixels):
                    x=-a.tag_size/2+col*a.tag_size/8
                    y=a.tag_size/2-(row+1)*a.tag_size/8
                    tile(f'/World/Tag{c}/Pixel{row}_{col}',(x,y,x+a.tag_size/8,y+a.tag_size/8,.03003),black)
            tags.append((tag,tag.AddTransformOp()))
        for c,name in enumerate(NAMES):
            path='/World/'+name
            if c%2==0:
                g=UsdGeom.Cylinder.Define(stage,path);g.CreateRadiusAttr(.015);g.CreateHeightAttr(.060);g.CreateAxisAttr('Z')
            else:
                g=UsdGeom.Cube.Define(stage,path);g.CreateSizeAttr(1);g.AddScaleOp().Set(Gf.Vec3f(.030,.030,.060))
            # Matrix transform avoids translate scaling through preceding scale ops.
            xf=UsdGeom.Xformable(g);xf.ClearXformOpOrder()
            op=xf.AddTransformOp()
            mat,shader=material('/World/Mat'+str(c),(.7,.025,.02) if c<2 else (.025,.5,.035))
            UsdShade.MaterialBindingAPI.Apply(g.GetPrim()).Bind(mat)
            UsdSemantics.LabelsAPI.Apply(g.GetPrim(),'class').CreateLabelsAttr([name])
            targets.append((g,op))
        distractors=[]
        for j in range(2):
            g=UsdGeom.Sphere.Define(stage,f'/World/Distractor{j}');g.CreateRadiusAttr(.045)
            op=g.AddTranslateOp();m,_=material(f'/World/DistractorMat{j}',(.03,.08,.4) if j==0 else (.4,.35,.25))
            UsdShade.MaterialBindingAPI.Apply(g.GetPrim()).Bind(m);distractors.append((g,op))
        dome=UsdLux.DomeLight.Define(stage,'/World/Dome');dome.CreateIntensityAttr(700)
        sun=UsdLux.DistantLight.Define(stage,'/World/Sun');sun.CreateIntensityAttr(1800)
        sun.AddRotateXYZOp().Set(Gf.Vec3f(20,-30,25));sun.CreateAngleAttr(8)
        camera=UsdGeom.Camera.Define(stage,'/World/Camera');camera.CreateFocalLengthAttr(24)
        camera.CreateHorizontalApertureAttr(20.955);camera.CreateVerticalApertureAttr(20.955)
        camera.CreateClippingRangeAttr(Gf.Vec2f(.01,100));camop=camera.AddTransformOp()
        rp=rep.create.render_product('/World/Camera',(640,640))
        rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach([rp])
        bbox=rep.AnnotatorRegistry.get_annotator('bounding_box_2d_tight');bbox.attach([rp])
        manifest={'source':'isaac_sim','isaac_sim_version':'6.1.0.0','resolution':[640,640],
                  'classes':NAMES,'dimensions_m':[.03,.03,.06],'tag_family':'tag36h11','tag_size_m':a.tag_size,'tag_ids':list(range(16)),'camera_intrinsics':{'fx':640*24/20.955,'fy':640*24/20.955,'cx':320,'cy':320},'annotation':'RTX bounding_box_2d_tight','samples':[], 'video':[]}
        out.mkdir(parents=True)
        def set_pose(c,x,y,yaw,scale=1):
            g,op=targets[c]
            size=(.030,.030,.060) if c%2 else (1,1,1)
            m=Gf.Matrix4d().SetScale(Gf.Vec3d(*size))
            m=m*Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0,0,1),yaw))
            m=m*Gf.Matrix4d().SetTranslate(Gf.Vec3d(x,y,.03))
            op.Set(m)
            tags[c][1].Set(Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0,0,1),yaw))*Gf.Matrix4d().SetTranslate(Gf.Vec3d(x,y,.03)))
        def setup(seed,condition,negative=False,phase=None):
            rng=random.Random(seed)
            tag_ids=rng.sample(range(16),4)
            for c,tid in enumerate(tag_ids):
                for row,pixels in enumerate(patterns[str(tid)]):
                    for col,pixel in enumerate(pixels):
                        prim=UsdGeom.Imageable(stage.GetPrimAtPath(f'/World/Tag{c}/Pixel{row}_{col}'))
                        prim.GetVisibilityAttr().Set(UsdGeom.Tokens.inherited) if pixel==0 else prim.GetVisibilityAttr().Set(UsdGeom.Tokens.invisible)
                tags[c][0].GetPrim().CreateAttribute('tag_id',Sdf.ValueTypeNames.Int).Set(tid)
            for c,(g,op) in enumerate(targets):
                UsdGeom.Imageable(g.GetPrim()).GetVisibilityAttr().Set(UsdGeom.Tokens.invisible) if negative else UsdGeom.Imageable(g.GetPrim()).GetVisibilityAttr().Set(UsdGeom.Tokens.inherited)
            for tag,_ in tags:
                UsdGeom.Imageable(tag.GetPrim()).GetVisibilityAttr().Set(UsdGeom.Tokens.invisible) if negative else UsdGeom.Imageable(tag.GetPrim()).GetVisibilityAttr().Set(UsdGeom.Tokens.inherited)
            points=[(-.055,-.05),(.055,-.05),(-.055,.05),(.055,.05)]
            rng.shuffle(points)
            for c,(x,y) in enumerate(points):
                x+=rng.uniform(-.012,.012);y+=rng.uniform(-.012,.012)
                if phase is not None:x+=.008*math.sin(phase+c)
                if condition=='occlusion' and c==1:x,y=points[0][0]+.022,points[0][1]+.015
                set_pose(c,x,y,rng.uniform(-90,90),1.0)
            height=.23 if condition=='low_angle' else rng.uniform(.30,.40)
            eye=Gf.Vec3d(rng.uniform(-.04,.04),-.20,height)
            camop.Set(Gf.Matrix4d().SetLookAt(eye,Gf.Vec3d(0,0,.03),Gf.Vec3d(0,0,1)).GetInverse())
            intensity={'dark':120,'bright':1400}.get(condition,rng.uniform(400,850))
            dome.GetIntensityAttr().Set(intensity);sun.GetIntensityAttr().Set(intensity*2)
            shade=rng.uniform(.12,.45);table_sh.GetInput('diffuseColor').Set(Gf.Vec3f(shade,shade*.95,shade*.9))
            for g,op in distractors:op.Set(Gf.Vec3d(rng.uniform(-.5,.5),rng.uniform(-.35,.35),.04))
        def capture():
            rep.orchestrator.step(rt_subframes=4)
            pixels=np.asarray(rgb.get_data())
            if pixels.shape[:2]!=(640,640):raise RuntimeError(f'Unexpected RGB shape {pixels.shape}')
            data=bbox.get_data();rows=[];boxes=[]
            ids=data['info']['idToLabels']
            for row in data['data']:
                label=ids.get(str(int(row['semanticId'])),ids.get(int(row['semanticId']),{})).get('class','')
                if label not in NAMES:continue
                x1,y1,x2,y2=[float(row[k]) for k in ['x_min','y_min','x_max','y_max']]
                x1,y1=max(0,x1),max(0,y1);x2,y2=min(640,x2),min(640,y2)
                if x2-x1<2 or y2-y1<2:continue
                c=NAMES.index(label)
                rows.append(f'{c} {(x1+x2)/1280:.8f} {(y1+y2)/1280:.8f} {(x2-x1)/640:.8f} {(y2-y1)/640:.8f}')
                boxes.append({'class_id':c,'xyxy':[x1,y1,x2,y2]})
            poses=[]
            world_to_cam=camop.Get().GetInverse()
            focal=640*24/20.955
            def optical(point):
                q=world_to_cam.Transform(Gf.Vec3d(*point))
                return [q[0],-q[1],-q[2]]
            def project(q):return [320+focal*q[0]/q[2],320+focal*q[1]/q[2]]
            for c,(_,op) in enumerate(tags):
                if UsdGeom.Imageable(targets[c][0].GetPrim()).ComputeVisibility()=='invisible':continue
                m=op.Get()
                corners=[[x,y,z] for x in [-.015,.015] for y in [-.015,.015] for z in [-.03,.03]]
                pts=[optical(m.Transform(Gf.Vec3d(*p))) for p in [[0,0,0]]+corners]
                h=a.tag_size/2
                tc=[optical(m.Transform(Gf.Vec3d(x,y,.03003))) for x,y in [(-h,h),(h,h),(h,-h),(-h,-h)]]
                poses.append(dict(class_id=c,tag_id=tags[c][0].GetPrim().GetAttribute('tag_id').Get(),center_camera_m=pts[0],cuboid_camera_m=pts,projected_cuboid=[project(q) for q in pts],tag_corners_camera_m=tc,tag_corners_px=[project(q) for q in tc]))
            return pixels[:,:,:3],rows,boxes,poses
        setup(317,'normal')
        for _ in range(10):app.update()
        for split,count,base in [('train',a.train,1000),('val',a.val,3000),('test',a.test,5000)]:
            (out/'images'/split).mkdir(parents=True);(out/'labels'/split).mkdir(parents=True)
            for i in range(count):
                condition=['normal','dark','bright','occlusion','low_angle'][i%5]
                negative=i%11==0;seed=base+i
                setup(seed,condition,negative)
                pixels,labels,boxes,poses=capture()
                if not negative and not labels:raise RuntimeError(f'No renderer labels: {split} {i}')
                image=f'images/{split}/{i:04}.png'
                Image.fromarray(pixels).save(out/image)
                (out/'labels'/split/f'{i:04}.txt').write_text('\n'.join(labels)+'\n' if labels else '')
                manifest['samples'].append(dict(image=image,split=split,session_id=f'{split}_scene_{seed}',seed=seed,condition=condition,negative=negative,boxes=boxes,poses=poses))
                print(f'RENDER {split} {i+1}/{count} labels={len(labels)}',flush=True)
        if a.video_frames:
            (out/'video').mkdir()
            for i in range(a.video_frames):
                setup(10000,'normal',phase=i*.05)
                pixels,labels,boxes,poses=capture();name=f'video/{i:04}.png'
                Image.fromarray(pixels).save(out/name)
                manifest['video'].append(dict(image=name,frame=i,session_id='video_scene_10000',boxes=boxes,poses=poses))
        stage.GetRootLayer().Export(str(out/'scene.usda'))
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
        import yaml
        (out/'dataset.yaml').write_text(yaml.safe_dump(dict(path=str(out),train='images/train',val='images/val',test='images/test',names=dict(enumerate(NAMES))),sort_keys=False))
        (out/'COMPLETE').write_text('Renderer generation completed\n')
        print('DATASET COMPLETE',out,flush=True)
    except BaseException:
        import traceback
        traceback.print_exc()
        raise
    finally:
        app.close()

if __name__=='__main__':main()
