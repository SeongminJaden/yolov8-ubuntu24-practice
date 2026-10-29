import torch
import torchvision
from torchvision.ops import nms
print(torch.__version__, torchvision.__version__, torch.version.cuda)
assert torch.cuda.is_available()
x = torch.rand(64, 64, device="cuda")
assert torch.isfinite(x @ x).all()
b = torch.tensor([[0,0,10,10],[1,1,9,9]], dtype=torch.float32, device="cuda")
s = torch.tensor([.9,.8], device="cuda")
assert nms(b,s,.5).tolist() == [0]
print("PASS GPU + NMS:", torch.cuda.get_device_name(0))
