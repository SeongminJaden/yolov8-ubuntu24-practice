"""Render generated episodes in one Isaac Sim process, with RGB and YOLO boxes."""
import argparse
import json
from pathlib import Path

NAMES=['red_cylinder','red_prism','green_cylinder','green_prism']

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('scene',type=Path,help='scene.usda or episode batch directory')
    p.add_argument('--output',type=Path,default=Path('work/mission-render'))
    p.add_argument('--camera',default='Overview',help='Comma-separated cameras: Overview,Signal,Pucks1..6,L1..3')
    p.add_argument('--width',type=int,default=3840);p.add_argument('--height',type=int,default=2160)
    p.add_argument('--frame',type=int,default=0,help='24 fps signal timeline')
    p.add_argument('--gui',action='store_true')
    a=p.parse_args()
    scenes=[a.scene] if a.scene.is_file() else sorted(a.scene.glob('episode-*/scene.usda'))
    if not scenes:p.error('No scene.usda files found')
    if a.output.exists():p.error('Output exists; use a fresh output directory')
    if a.width<1 or a.height<1:p.error('Positive image dimensions required')
    from isaacsim import SimulationApp
    app=SimulationApp({'headless':not a.gui,'renderer':'RaytracedLighting','width':1280,'height':720,'multi_gpu':False})
    try:
        import omni.usd
        import omni.replicator.core as rep
        import omni.timeline
        import carb
        import numpy as np
        from PIL import Image
        a.output.mkdir(parents=True)
        samples=[]
        settings=carb.settings.get_settings();settings.set('/rtx/translucency/enabled',True);settings.set('/rtx/reflections/enabled',True)
        settings.set('/rtx/post/histogram/enabled',False)
        for scene in scenes:
            omni.usd.get_context().open_stage(str(scene.resolve()))
            for _ in range(30):app.update()
            rp=rep.create.render_product('/World/Mission/Cameras/'+a.camera.split(',')[0],(a.width,a.height))
            rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach([rp])
            bbox=rep.AnnotatorRegistry.get_annotator('bounding_box_2d_tight');bbox.attach([rp])
            for name in a.camera.split(','):
                path='/World/Mission/Cameras/'+name
                if not omni.usd.get_context().get_stage().GetPrimAtPath(path):raise ValueError('Unknown camera '+name)
                omni.timeline.get_timeline_interface().set_current_time(a.frame/24)
                rp.hydra_texture.set_camera_path(path)
                for _ in range(30):app.update()
                rep.orchestrator.step(rt_subframes=16,delta_time=0)
                arr=np.asarray(rgb.get_data())
                if arr.size==0:raise RuntimeError('No render output')
                stem=scene.parent.name+'-'+name
                dest=a.output/'images'/f'{stem}.png';dest.parent.mkdir(exist_ok=True)
                Image.fromarray(arr).save(dest)
                data=bbox.get_data();lines=[]
                for row in data['data']:
                    labels=data['info']['idToLabels'];label=labels.get(str(int(row['semanticId'])),{}).get('class','')
                    if label not in NAMES:continue
                    x1,y1,x2,y2=[float(row[k]) for k in ['x_min','y_min','x_max','y_max']]
                    x1=max(0,min(a.width,x1));x2=max(0,min(a.width,x2));y1=max(0,min(a.height,y1));y2=max(0,min(a.height,y2))
                    if x2<=x1 or y2<=y1:continue
                    lines.append(f'{NAMES.index(label)} {(x1+x2)/2/a.width:.8f} {(y1+y2)/2/a.height:.8f} {(x2-x1)/a.width:.8f} {(y2-y1)/a.height:.8f}')
                ld=a.output/'labels';ld.mkdir(exist_ok=True);(ld/(stem+'.txt')).write_text('\n'.join(lines)+ ('\n' if lines else ''))
                samples.append(dict(image=str(dest.relative_to(a.output)),objects=len(lines),scene=str(scene.resolve()),camera=name,frame=a.frame))
                print('RENDER_SAVED',dest.resolve(),arr.shape,'boxes',len(lines),flush=True)
            rgb.detach([rp]);bbox.detach([rp]);rp.destroy()
            for _ in range(10):app.update()
        (a.output/'manifest.json').write_text(json.dumps(dict(classes=NAMES,samples=samples,annotation='RTX bounding_box_2d_tight',scope='Synthetic images; no robot task execution'),indent=2)+'\n')
        if a.gui:
            from omni.kit.viewport.utility import get_active_viewport
            get_active_viewport().set_active_camera(path)
            while app.is_running():app.update()
    finally:app.close()

if __name__=='__main__':main()
