import argparse
import json
import onnx

def inspect(path):
    m=onnx.load(path)
    onnx.checker.check_model(m)
    def info(v):
        return dict(name=v.name,shape=[d.dim_value if d.HasField('dim_value') else d.dim_param for d in v.type.tensor_type.shape.dim])
    return dict(inputs=[info(v) for v in m.graph.input],outputs=[info(v) for v in m.graph.output])
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('model'); a=p.parse_args()
    print(json.dumps(inspect(a.model),indent=2))
