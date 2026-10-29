"""Compose mission assets over the supplied maze without modifying its source layers."""
import json
import os
import random
import math
from pathlib import Path


def build_scene(episode, maze, output, offset, layout="initial"):
    from pxr import Usd, UsdGeom, UsdShade, UsdLux, UsdPhysics, UsdSemantics, Gf, Sdf
    from reportlab.graphics.barcode.code128 import Code128
    s=Usd.Stage.CreateNew(str(output.resolve()))
    UsdGeom.SetStageMetersPerUnit(s,1); UsdGeom.SetStageUpAxis(s,'Z')
    s.SetTimeCodesPerSecond(24);s.SetStartTimeCode(0);s.SetEndTimeCode(26*24)
    world=UsdGeom.Xform.Define(s,'/World'); s.SetDefaultPrim(world.GetPrim())
    # Keep source relative and preserve all internal references and collision geometry.
    base=UsdGeom.Xform.Define(s,'/World/Maze')
    base.GetPrim().GetReferences().AddReference(os.path.relpath(maze,output.parent))
    root=UsdGeom.Xform.Define(s,'/World/Mission')
    root.AddTranslateOp().Set(Gf.Vec3d(offset[0]/1000,offset[1]/1000,0))
    prefix='/World/Mission'
    def mat(name,color,rough=.4,metal=0):
        m=UsdShade.Material.Define(s,prefix+'/Materials/'+name)
        sh=UsdShade.Shader.Define(s,str(m.GetPath())+'/Shader');sh.CreateIdAttr('UsdPreviewSurface')
        for n,t,v in [('diffuseColor',Sdf.ValueTypeNames.Color3f,Gf.Vec3f(*color)),('roughness',Sdf.ValueTypeNames.Float,rough),('metallic',Sdf.ValueTypeNames.Float,metal)]: sh.CreateInput(n,t).Set(v)
        m.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(),'surface')
        return m,sh
    white,_=mat('White',(.9,.9,.9));black,_=mat('Black',(.003,.003,.003))
    red,_=mat('Red',(.65,.012,.015));green,_=mat('Green',(.012,.45,.025))
    floor,_=mat('Floor',(.21,.23,.25),.65);metal,_=mat('Aluminum',(.55,.58,.6),.25,.9)
    glass=UsdShade.Material.Define(s,prefix+'/Materials/Acrylic')
    sh=UsdShade.Shader.Define(s,str(glass.GetPath())+'/Shader')
    sh.SetSourceAsset('OmniGlass.mdl','mdl');sh.SetSourceAssetSubIdentifier('OmniGlass','mdl')
    sh.CreateInput('glass_ior',Sdf.ValueTypeNames.Float).Set(episode['acrylic']['ior'])
    sh.CreateInput('frosting_roughness',Sdf.ValueTypeNames.Float).Set(episode['acrylic']['roughness'])
    sh.CreateInput('thin_walled',Sdf.ValueTypeNames.Bool).Set(False)
    sh.CreateInput('glass_color',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.98,.995,1))
    sh.CreateOutput('out',Sdf.ValueTypeNames.Token)
    for kind in ('surface','volume','displacement'): glass.CreateOutput('mdl:'+kind,Sdf.ValueTypeNames.Token).ConnectToSource(sh.ConnectableAPI(),'out')
    for p in list(s.Traverse()):
        if p.IsA(UsdGeom.Mesh) and '/wall/geo' in str(p.GetPath()):
            UsdShade.MaterialBindingAPI.Apply(p).Bind(glass, bindingStrength=UsdShade.Tokens.strongerThanDescendants)
        elif p.IsA(UsdGeom.Mesh) and '/profile/geo' in str(p.GetPath()):
            UsdShade.MaterialBindingAPI.Apply(p).Bind(metal, bindingStrength=UsdShade.Tokens.strongerThanDescendants)
    def cube(path,pos,size,material,collision=False):
        g=UsdGeom.Cube.Define(s,path);g.CreateSizeAttr(1)
        g.AddTranslateOp().Set(Gf.Vec3d(*pos));g.AddScaleOp().Set(Gf.Vec3f(*size))
        UsdShade.MaterialBindingAPI.Apply(g.GetPrim()).Bind(material)
        if collision: UsdPhysics.CollisionAPI.Apply(g.GetPrim())
        return g
    cube(prefix+'/Floor',(2.202,3.152,-.025),(4.65,6.6,.05),floor,True)
    def cylinder(path,radius,height,axis='Z'):
        count=96
        def orient(v):return (v[2],v[0],v[1]) if axis=='X' else v
        points=[orient((radius*math.cos(2*math.pi*i/count),radius*math.sin(2*math.pi*i/count),z)) for z in (-height/2,height/2) for i in range(count)]
        indices=[];normals=[];counts=[]
        for i in range(count):
            j=(i+1)%count;indices.extend([i,j,j+count,i+count]);counts.append(4)
            for k in [i,j,j,i]:normals.append(orient((math.cos(2*math.pi*k/count),math.sin(2*math.pi*k/count),0)))
        indices.extend(reversed(range(count)));counts.append(count);normals.extend([orient((0,0,-1))]*count)
        indices.extend(range(count,count*2));counts.append(count);normals.extend([orient((0,0,1))]*count)
        mesh=UsdGeom.Mesh.Define(s,path);mesh.CreatePointsAttr(points);mesh.CreateFaceVertexCountsAttr(counts);mesh.CreateFaceVertexIndicesAttr(indices)
        mesh.CreateSubdivisionSchemeAttr('none');mesh.CreateNormalsAttr(normals);mesh.SetNormalsInterpolation('faceVarying')
        return mesh
    from randomize_mission import STARTS,GOALS
    for i,(x,y) in enumerate(STARTS+[GOALS[0],GOALS[2]]):
        cube(prefix+f'/Boxes/Small{i}',(x/1000,y/1000,.035),(.205,.205,.07),white,True)
    # L2 lies in north half of platform; center Y=3500 mm is an explicit assumption.
    for i,(dx,dy) in enumerate([(x,y) for x in (-.205,.205) for y in (-.205,.205)]):
        cube(prefix+f'/Boxes/Central{i}',(2.202+dx,3.5+dy,.035),(.410,.410,.07),white,True)
    patterns=json.loads((Path(__file__).resolve().parents[1]/'configs/tags/tag36h11.json').read_text())
    def tag(path,ident,size,pos,normal):
        t=UsdGeom.Xform.Define(s,path)
        t.AddTransformOp().Set(Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0,0,1),Gf.Vec3d(*normal)))*Gf.Matrix4d().SetTranslate(Gf.Vec3d(*pos)))
        cube(path+'/Paper',(0,0,-.000015),(size*1.25,size*1.25,.00002),white)
        for row,pixels in enumerate(patterns[str(ident)]):
            for col,value in enumerate(pixels):
                if value==0:
                    cube(path+f'/b{row}_{col}',(-size/2+(col+.5)*size/8,size/2-(row+.5)*size/8,0),(size/8,size/8,.00001),black)
    for p in episode['pucks']:
        path=prefix+f'/Pucks/Puck{p["id"]:02d}'
        obj=UsdGeom.Xform.Define(s,path)
        target=next(t for t in episode['targets'] if t['id']==p['id'])
        position=p['position_mm'] if layout=='initial' else target['position_mm']
        angles=p['euler_xyz_deg'] if layout=='initial' else [0,0,target['yaw_deg']]
        obj.AddTranslateOp().Set(Gf.Vec3d(*(v/1000 for v in position)))
        obj.AddRotateXYZOp().Set(Gf.Vec3f(*angles))
        obj.GetPrim().CreateAttribute('mission:tagId',Sdf.ValueTypeNames.Int).Set(p['id'])
        obj.GetPrim().CreateAttribute('mission:class',Sdf.ValueTypeNames.String).Set(p['color']+'_'+p['shape'])
        UsdSemantics.LabelsAPI.Apply(obj.GetPrim(),'class').CreateLabelsAttr([p['color']+'_'+p['shape']])
        m=red if p['color']=='red' else green
        if p['shape']=='prism': body=cube(path+'/Body',(0,0,0),(.03,.03,.06),m,True)
        else:
            body=cylinder(path+'/Body',.015,.06)
            UsdShade.MaterialBindingAPI.Apply(body.GetPrim()).Bind(m);UsdPhysics.CollisionAPI.Apply(body.GetPrim())
        faces=[((0,0,1),.03)]
        if p['shape']=='prism': faces += [((0,0,-1),.03),((1,0,0),.015),((-1,0,0),.015),((0,1,0),.015),((0,-1,0),.015)]
        for i,(normal,dist) in enumerate(faces):tag(path+f'/Tag{i}',p['id'],.016,tuple(v*(dist+.00005) for v in normal),normal)
    # Destination tags on approach-facing vertical box surfaces, center height 35 mm.
    for i,(pos,normal) in enumerate([((3.56745,.95,.035),(-1,0,0)),((2.202,3.91005,.035),(0,1,0)),((3.67,5.25145,.035),(0,-1,0))]):
        tag(prefix+f'/LocationTag{i+1}',12+i,.048,pos,normal)
    # Device dimensions were not specified: editable assumptions in meters.
    cube(prefix+'/Signal/Post',(.08,.95,.2),(.025,.025,.4),metal,True)
    cube(prefix+'/Signal/Body',(.08,.95,.45),(.08,.13,.34),black,True)
    for color,z,rgb in [('R',.55,(1,0,0)),('Y',.45,(1,.6,0)),('G',.35,(0,1,0))]:
        m,sh=mat('LED_'+color,tuple(.04*v for v in rgb),.2)
        led=cylinder(prefix+'/Signal/'+color,.038,.008,'X');led.AddTranslateOp().Set(Gf.Vec3d(.125,.95,z));UsdShade.MaterialBindingAPI.Apply(led.GetPrim()).Bind(m)
        emit=sh.CreateInput('emissiveColor',Sdf.ValueTypeNames.Color3f)
        for frame in range(625):
            t=frame/24;index=int(t//2)
            on=index<12 and t%2<1 and episode['signal_sequence'][index]==color
            emit.Set(Gf.Vec3f(*(v*12 if on else 0 for v in rgb)),frame)
    # Actual Code128 geometry, including mandatory quiet zones; +X facing.
    code=Code128(episode['barcode']);code.validate();code.encode();pattern=code.decompose()
    widths=[ord(c.lower())-ord('a')+1 for c in pattern]
    unit=.16/(sum(widths)+20)
    carrier=UsdGeom.Xform.Define(s,prefix+'/Barcode')
    carrier.AddTransformOp().Set(Gf.Matrix4d(0,1,0,0, 0,0,1,0, 1,0,0,0, .08,.65,.45,1))
    cube(prefix+'/Barcode/Paper',(0,0,-.0001),(.18,.10,.0001),white)
    x=-.08+10*unit
    for i,(c,w) in enumerate(zip(pattern,widths)):
        if c.isupper():cube(prefix+f'/Barcode/Bar{i}',(x+w*unit/2,0,0),(w*unit,.075,.00002),black)
        x+=w*unit
    dome=UsdLux.DomeLight.Define(s,prefix+'/Ambient');dome.CreateIntensityAttr(180)
    for i,(x,y) in enumerate([(1,1.4),(3.4,1.4),(1,4.8),(3.4,4.8)]):
        light=UsdLux.RectLight.Define(s,prefix+f'/CeilingLight{i}');light.AddTranslateOp().Set(Gf.Vec3d(x,y,2.8));light.CreateWidthAttr(1.2);light.CreateHeightAttr(.35);light.CreateIntensityAttr(episode['lighting']['intensity']);light.CreateEnableColorTemperatureAttr(True);light.CreateColorTemperatureAttr(episode['lighting']['temperature_k'])
    def camera(name,eye,target,focal):
        cam=UsdGeom.Camera.Define(s,prefix+'/Cameras/'+name)
        cam.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye),Gf.Vec3d(*target),Gf.Vec3d(0,0,1)).GetInverse());cam.CreateFocalLengthAttr(focal);cam.CreateClippingRangeAttr(Gf.Vec2f(.005,100))
    camera('Overview',(9,-8,11),(2.202,3.152,0),35)
    camera('Signal',(.734,.8,.45),(.08,.8,.45),20)
    rng=random.Random(episode['seed']+9000000)
    for i,(x,y) in enumerate(STARTS,1):
        eye=(x/1000+rng.uniform(.17,.25),y/1000-rng.uniform(.22,.30),rng.uniform(.27,.38))
        camera('Pucks'+str(i),eye,(x/1000,y/1000,.10),35)
        if i==1:camera('Pucks',eye,(x/1000,y/1000,.10),35)
    for i,(x,y) in enumerate(GOALS,1):
        camera('L'+str(i),(x/1000+.2,y/1000-.3,.42),(x/1000,y/1000,.10),28)
    from pxr import UsdRender
    settings=UsdRender.Settings.Define(s,'/Render/Settings');settings.CreateResolutionAttr(Gf.Vec2i(3840,2160))
    product=UsdRender.Product.Define(s,'/Render/Product');product.CreateResolutionAttr(Gf.Vec2i(3840,2160));product.CreateCameraRel().SetTargets([prefix+'/Cameras/Overview']);settings.CreateProductsRel().SetTargets([product.GetPath()])
    s.GetRootLayer().customLayerData={'seed':episode['seed'],'alignment':'Assumed PDF translation; source mesh preserved','central_platform_y_mm':3500,'robot_present':False}
    s.GetRootLayer().Save()
