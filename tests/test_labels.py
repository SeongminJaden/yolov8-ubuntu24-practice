import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from validate_labels import validate_line
class Labels(unittest.TestCase):
    def test_valid(self): self.assertEqual(validate_line('3 .5 .5 .2 .2',4)[0],3)
    def test_invalid(self):
        for text in ['4 .5 .5 .2 .2','-1 .5 .5 .2 .2','1.5 .5 .5 .2 .2','0 nan .5 .2 .2','0 .5 .5 0 .2','0 .05 .5 .2 .2','0 .5 .5 .2','0 .5 .5 2 .2']:
            with self.subTest(text=text),self.assertRaises(ValueError): validate_line(text,4)
if __name__=='__main__': unittest.main()
