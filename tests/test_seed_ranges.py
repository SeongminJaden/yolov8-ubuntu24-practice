import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('generator',Path(__file__).resolve().parents[1]/'sim/generate_tagged_pucks.py')
generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(generator)

class SeedRangesTests(unittest.TestCase):
    def test_large_training_split_does_not_overlap_validation_or_test(self):
        ranges=generator.split_seed_ranges(8000,1000,1000,300000)
        seeds=[set(range(base,base+count)) for _,count,base in ranges]
        self.assertEqual(len(set.union(*seeds)),10000)
        self.assertFalse(seeds[0]&seeds[1] or seeds[0]&seeds[2] or seeds[1]&seeds[2])
    def test_negative_count_rejected(self):
        with self.assertRaises(ValueError):generator.split_seed_ranges(-1,10,10,0)
