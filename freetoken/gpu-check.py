import json
import os

import torch
import torch.distributed as dist


rank = int(os.environ.get("LOCAL_RANK", "0"))
distributed = "RANK" in os.environ
if distributed:
    torch.cuda.set_device(rank)
    dist.init_process_group("nccl")
    value = torch.tensor([rank + 1.0], device="cuda")
    dist.all_reduce(value)
    torch.cuda.synchronize()
    assert value.item() == 10, value
    print(json.dumps({"rank": rank, "rccl_all_reduce": value.item()}), flush=True)
    dist.destroy_process_group()
else:
    count = torch.cuda.device_count()
    assert count == 4, count
    print(json.dumps({"torch": torch.__version__, "hip": torch.version.hip, "gpu_count": count}))
    for index in range(count):
        with torch.cuda.device(index):
            torch.manual_seed(0)
            a = torch.randn(128, 128, dtype=torch.float16)
            expected = a.float() @ a.float().T
            actual = a.cuda() @ a.cuda().T
            torch.cuda.synchronize()
            torch.testing.assert_close(actual.cpu().float(), expected, rtol=1e-2, atol=0.1)
            props = torch.cuda.get_device_properties(index)
            print(json.dumps({"gpu": index, "name": props.name, "arch": props.gcnArchName, "vram": props.total_memory, "fp16_matmul": "pass"}))
