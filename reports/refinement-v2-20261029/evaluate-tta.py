from pathlib import Path
import runpy,sys
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'scripts'))
import centerpose_pucks
load=centerpose_pucks.load_model
def with_tta(*args,**kwargs):
 model=load(*args,**kwargs);model.inference_tta=True;return model
centerpose_pucks.load_model=with_tta
sys.argv=[str(root/'scripts/evaluate_tagged_perception.py')]+sys.argv[1:]
runpy.run_path(sys.argv[0],run_name='__main__')
