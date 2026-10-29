"""Mission invariants, including all official count/code combinations."""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('mission',Path(__file__).resolve().parents[1]/'scripts/randomize_mission.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class MissionTests(unittest.TestCase):
    def test_all_count_code_combinations(self):
        self.assertEqual(len(m.COUNTS),25)
        for triple in m.COUNTS:
            for code in m.CODES:
                e=m.episode(42,triple,code);self.assertTrue(m.validate(e))
                values=[e['counts'][c] for c in e['destination_groups'].values()]
                self.assertEqual(values,sorted(triple,reverse=m.CODES[code]))
    def test_ties_keep_ryg_even_descending(self):
        for code in m.CODES:
            self.assertEqual(list(m.episode(0,(4,4,4),code)['destination_groups'].values()),list('RYG'))
    def test_reproducible_and_varied(self):
        self.assertEqual(m.episode(10),m.episode(10))
        self.assertNotEqual(m.episode(10),m.episode(11))
    def test_many_poses(self):
        for mode in ['official','augmentation']:
            for seed in range(1000):
                e=m.episode(seed,pose_mode=mode,jitter_mm=0 if mode=='official' else 3)
                self.assertTrue(m.validate(e))
                if mode=='official':self.assertTrue(all(p['position_mm'][2]==100 and p['euler_xyz_deg'][:2]==[0,0] for p in e['pucks']))
    def test_impossible_inventory(self):
        ps=[dict(id=i,shape='prism',color='red') for i in range(12)]
        self.assertEqual(list(m.solve(ps,dict(R=4,Y=4,G=4))),[])
    def test_dice_geometry(self):
        for n,points in m.DICE.items():
            self.assertEqual(len(set(points)),n)
            self.assertTrue(all(abs(x)<=60 and abs(y)<=60 for x,y in points))
        self.assertEqual(m.DICE[2],[(-60,60),(60,-60)])

if __name__=='__main__':unittest.main()
