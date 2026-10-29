"""Seeded, solvable mission episodes. Standard library only unless --usd is used."""
import argparse
import itertools
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
STARTS = [(1468,950),(3670,3152),(2936,5354),(734,5354),(2202,5354),(3670,3886)]
GOALS = [(3670,950),(2202,3700),(3670,5354)]
COUNTS = [(r,y,12-r-y) for r in range(1,7) for y in range(1,7) if 1 <= 12-r-y <= 6]
DICE = {1:[(0,0)],2:[(-60,60),(60,-60)],3:[(-60,60),(0,0),(60,-60)],
        4:[(-60,60),(60,60),(-60,-60),(60,-60)],
        5:[(-60,60),(60,60),(0,0),(-60,-60),(60,-60)],
        6:[(x,y) for x in (-60,60) for y in (-60,0,60)]}
CODES = {'P2-01':False,'P2-02':True,'P2-03':False,'P2-04':True}

def solve(pucks, counts):
    """Enumerate feasible Y subsets; remaining colors uniquely define R/G."""
    for shape in ('prism','cylinder'):
        eligible = [p for p in pucks if p['shape'] == shape]
        for subset in itertools.combinations(eligible, counts['Y']):
            yids = {p['id'] for p in subset}
            rest = [p for p in pucks if p['id'] not in yids]
            r = [p['id'] for p in rest if p['color']=='red']
            g = [p['id'] for p in rest if p['color']=='green']
            if len(r)==counts['R'] and len(g)==counts['G']:
                yield {'R':r,'Y':sorted(yids),'G':g}

def episode(seed, triple=None, barcode=None, pose_mode='official', jitter_mm=0):
    rng = random.Random(seed)
    r,y,g = triple or rng.choice(COUNTS)
    if (r,y,g) not in COUNTS: raise ValueError('R/Y/G must each be 1..6 and sum to 12')
    counts = dict(zip('RYG',(r,y,g)))
    barcode = barcode or rng.choice(list(CODES))
    yshape = rng.choice(['prism','cylinder'])
    specs = [('red',rng.choice(['prism','cylinder'])) for _ in range(r)]
    specs += [(rng.choice(['red','green']),yshape) for _ in range(y)]
    specs += [('green',rng.choice(['prism','cylinder'])) for _ in range(g)]
    rng.shuffle(specs)
    # IDs do not encode color, shape, group, or starting box.
    ids = list(range(12)); rng.shuffle(ids)
    pucks=[]
    for i,(color,shape) in enumerate(specs):
        x,b_y = STARTS[i//2]; x += (-40,40)[i%2]
        yaw = rng.uniform(-180,180)
        roll = rng.choice([0,90,180,270]) if pose_mode=='augmentation' and shape=='prism' else 0
        pitch = rng.choice([0,90]) if pose_mode=='augmentation' and shape=='cylinder' else 0
        # Stable face-supported poses only; no floating tilted cuboids.
        half_height = 15 if roll in (90,270) or pitch==90 else 30
        pos=[x+rng.uniform(-jitter_mm,jitter_mm), b_y+rng.uniform(-jitter_mm,jitter_mm),70+half_height]
        pucks.append(dict(id=ids[i],color=color,shape=shape,start_box=i//2+1,
                          position_mm=pos,euler_xyz_deg=[roll,pitch,yaw]))
    solution = next(solve(pucks,counts))
    order=sorted('RYG',key=lambda c: -counts[c] if CODES[barcode] else counts[c])
    targets=[]
    for loc,(xy,group) in enumerate(zip(GOALS,order),1):
        chosen=solution[group][:]; rng.shuffle(chosen)
        for puck_id,(dx,dy) in zip(chosen,DICE[counts[group]]):
            targets.append(dict(id=puck_id,location=f'L{loc}',group=group,
                                position_mm=[xy[0]+dx,xy[1]+dy,100],yaw_deg=rng.uniform(-180,180)))
    sequence=list('R'*r+'Y'*y+'G'*g); rng.shuffle(sequence)
    return dict(schema_version=1,seed=seed,pose_mode=pose_mode,
        official_compliant=pose_mode=='official' and jitter_mm==0,
        coordinate_frame='PDF lower-left post center, millimeters, Z up',
        barcode=barcode,counts=counts,signal_sequence=''.join(sequence),
        signal_timing=dict(on_seconds=1,between_off_seconds=1,final_off_seconds=3,duration_seconds=26),
        destination_groups=dict(zip(['L1','L2','L3'],order)),pucks=pucks,targets=targets,
        lighting=dict(intensity=rng.uniform(700,1400),temperature_k=rng.uniform(4000,6500)),
        acrylic=dict(ior=1.491,roughness=rng.uniform(.015,.06)),
        notes=['Ground-truth placement plan, not robot execution or measured placement.',
               'Augmentation poses/jitter are outside official mission rules.'])

def validate(e):
    assert e['barcode'] in CODES
    ps=e['pucks']; assert len(ps)==12 and {p['id'] for p in ps}==set(range(12))
    assert tuple(e['counts'][c] for c in 'RYG') in COUNTS
    assert len(e['signal_sequence'])==12
    assert all(e['signal_sequence'].count(c)==e['counts'][c] for c in 'RYG')
    assert len(e['targets'])==12 and {t['id'] for t in e['targets']}==set(range(12))
    byid={p['id']:p for p in ps}
    for loc,group in e['destination_groups'].items():
        ts=[t for t in e['targets'] if t['location']==loc]
        assert len(ts)==e['counts'][group]
        assert all(t['group']==group for t in ts)
        gx,gy=GOALS[int(loc[1:])-1]
        assert {(t['position_mm'][0]-gx,t['position_mm'][1]-gy) for t in ts}==set(DICE[len(ts)])
        chosen=[byid[t['id']] for t in ts]
        if group in 'RG': assert all(p['color']=={'R':'red','G':'green'}[group] for p in chosen)
        else: assert len({p['shape'] for p in chosen})==1
    if e['official_compliant']:
        assert e['pose_mode']=='official'
        assert all(p['position_mm'][2]==100 and p['euler_xyz_deg'][:2]==[0,0] for p in ps)
    for a,b in itertools.combinations(ps,2):
        if a['start_box']==b['start_box']:
            # Bounding spheres in XY, conservative for every allowed resting orientation.
            assert math.dist(a['position_mm'][:2],b['position_mm'][:2])>2*math.sqrt(30**2+15**2)
    return True

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--seed',type=int,default=1000000)
    ap.add_argument('--episodes',type=int,default=100)
    ap.add_argument('--all-combinations',action='store_true',help='All ordered R/Y/G counts times four barcodes (100 episodes)')
    ap.add_argument('--pose-mode',choices=['official','augmentation'],default='official')
    ap.add_argument('--jitter-mm',type=float,default=0,help='0..3 mm; nonzero is augmentation')
    ap.add_argument('--layout',choices=['initial','solution'],default='initial',help='Render initial inventory or solved dice placement')
    ap.add_argument('--usd',action='store_true',help='Requires Isaac Sim Python / pxr')
    ap.add_argument('--maze',type=Path,default=ROOT/'work/mission-inputs/maze/maze.usda')
    ap.add_argument('--map-offset-mm',type=float,nargs=2,default=[-2202,-3152],help='PDF origin in imported maze coordinates; verify against CAD')
    a=ap.parse_args()
    if a.episodes<1 or not 0<=a.jitter_mm<=3: ap.error('episodes >=1 and jitter 0..3 required')
    if a.output.exists(): ap.error('Output exists; use a fresh output directory')
    if a.usd and not a.maze.is_file(): ap.error('Extract maze.zip and set --maze first')
    combos=list(itertools.product(COUNTS,CODES)) if a.all_combinations else [(None,None)]*a.episodes
    if a.usd:
        sys.path.insert(0,str(ROOT/'sim'))
        from mission_scene import build_scene
    a.output.mkdir(parents=True)
    for i,(counts,code) in enumerate(combos):
        e=episode(a.seed+i,counts,code,a.pose_mode,a.jitter_mm); validate(e)
        d=a.output/f'episode-{i:05d}';d.mkdir()
        (d/'mission.json').write_text(json.dumps(e,indent=2)+'\n')
        if a.usd: build_scene(e,a.maze.resolve(),d/'scene.usda',a.map_offset_mm,a.layout)
    (a.output/'index.json').write_text(json.dumps(dict(seed=a.seed,episodes=len(combos),
        pose_mode=a.pose_mode,layout=a.layout,map_offset_mm=a.map_offset_mm,maze=str(a.maze.resolve()),
        map_alignment_status='assumed centered PDF frame; inspect before robot navigation'),indent=2)+'\n')
    print(f'Created and validated {len(combos)} episodes in {a.output}')

if __name__=='__main__': main()
