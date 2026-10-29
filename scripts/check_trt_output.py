"""Prepare a shared FP32 input or compare trtexec --exportOutput with ONNX Runtime.

Run this with the host YOLO venv. Run trtexec separately inside the GPU container.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--onnx', type=Path)
    p.add_argument('--trt-output', type=Path)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    if a.prepare:
        if a.input.exists():
            p.error('Input already exists; refusing overwrite')
        a.input.parent.mkdir(parents=True, exist_ok=True)
        np.random.default_rng(317).random((1,3,640,640),dtype=np.float32).tofile(a.input)
        return
    if not all((a.onnx,a.trt_output,a.report)):
        p.error('--onnx, --trt-output and --report are required for comparison')
    x = np.fromfile(a.input,dtype=np.float32).reshape(1,3,640,640)
    session = ort.InferenceSession(str(a.onnx),providers=['CPUExecutionProvider'])
    name = session.get_outputs()[0].name
    expected = session.run([name],{session.get_inputs()[0].name:x})[0]
    exported = json.loads(a.trt_output.read_text())
    record = next(r for r in exported if r['name']==name)
    actual = np.asarray(record['values'],dtype=np.float32).reshape(expected.shape)
    error = np.abs(actual-expected)
    # FP32 TensorRT kernels can differ slightly from ONNX Runtime's CPU kernels.
    close = bool(np.allclose(actual,expected,rtol=1e-3,atol=1e-2))
    result = dict(passed=close,shape=list(expected.shape),max_absolute_error=float(error.max()),
                  mean_absolute_error=float(error.mean()),rtol=1e-3,atol=1e-2)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,indent=2))
    print(result)
    if not close:
        raise SystemExit('TensorRT and ONNX Runtime outputs differ beyond tolerance')


if __name__ == '__main__':
    main()
