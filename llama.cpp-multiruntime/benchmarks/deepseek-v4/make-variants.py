#!/usr/bin/env python3
"""Derive placement experiments from the captured stock server command."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
baseline = json.loads((root / "baseline.json").read_text())


def save(name, overrides):
    command = baseline.copy()
    command[command.index("--device") + 1] = "ROCm0,ROCm1,ROCm2,ROCm3,CUDA0,CUDA1"
    command[command.index("--tensor-split") + 1] = "25,25,25,25,0,0"
    index = command.index("--override-tensor") + 1
    command[index] = ",".join(overrides + [command[index]])
    (root / f"{name}.json").write_text(json.dumps(command, indent=2) + "\n")


# First match wins: CUDA overrides must precede the stock CPU overrides.
save("cpu-experts-to-cuda", [
    r"^blk\.(0|1|2|3|4|5)\.ffn_(up|down)_exps\.weight$=CUDA0",
    r"^blk\.(11|12|13|14|15|16)\.ffn_(up|down)_exps\.weight$=CUDA1",
])
save("router-to-cuda", [
    r"^blk\.([0-9]|1[0-9]|20)\.ffn_gate_inp\.weight$=CUDA0",
    r"^blk\.(2[1-9]|3[0-9]|4[0-2])\.ffn_gate_inp\.weight$=CUDA1",
])
save("dense-to-cuda", [
    r"^blk\.([0-9]|1[0-9]|20)\.(?!ffn_(up|gate|down)_exps\.).*=CUDA0",
    r"^blk\.(2[1-9]|3[0-9]|4[0-2])\.(?!ffn_(up|gate|down)_exps\.).*=CUDA1",
    r"^output.*=CUDA1",
])

small_batch = baseline.copy()
small_batch[small_batch.index("--ubatch-size") + 1] = "512"
(root / "baseline-ub512.json").write_text(json.dumps(small_batch, indent=2) + "\n")

all_gpu = small_batch.copy()
index = all_gpu.index("--override-tensor")
del all_gpu[index:index + 2]
all_gpu[all_gpu.index("--device") + 1] = "CUDA0,CUDA1,ROCm0,ROCm1,ROCm2,ROCm3"
all_gpu[all_gpu.index("--tensor-split") + 1] = "4,4,9,9,9,9"
(root / "all-gpu-ub512.json").write_text(json.dumps(all_gpu, indent=2) + "\n")

# An explicit output override preserves its placement and disables pipeline
# parallelism in llama_context, reducing scheduler buffer allocations.
all_gpu_headroom = all_gpu + [
    "--override-tensor", r"^output\.weight$=ROCm3",
    "--mmproj-device", "ROCm3",
]
(root / "all-gpu-headroom.json").write_text(json.dumps(all_gpu_headroom, indent=2) + "\n")

dense_aligned = baseline.copy()
dense_aligned[dense_aligned.index("--device") + 1] = "CUDA0,CUDA1,ROCm0,ROCm1,ROCm2,ROCm3"
dense_aligned[dense_aligned.index("--tensor-split") + 1] = "22,22,0,0,0,0"
index = dense_aligned.index("--override-tensor") + 1
dense_aligned[index] += "," + ",".join([
    r"^blk\.([0-9]|10)\.ffn_(up|gate|down)_exps\.weight$=ROCm0",
    r"^blk\.(1[1-9]|2[01])\.ffn_(up|gate|down)_exps\.weight$=ROCm1",
    r"^blk\.(2[2-9]|3[0-2])\.ffn_(up|gate|down)_exps\.weight$=ROCm2",
    r"^blk\.(3[3-9]|4[0-2])\.ffn_(up|gate|down)_exps\.weight$=ROCm3",
])
(root / "dense-cuda-aligned.json").write_text(json.dumps(dense_aligned, indent=2) + "\n")

# Within the CUDA free-memory constraint: rescue some CPU expert pairs onto
# ROCm, which has spare memory once layers/KV moved to CUDA.
redistributed = dense_aligned.copy()
index = redistributed.index("--override-tensor") + 1
redistributed[index] = ",".join([
    r"^blk\.(0|1|2)\.ffn_(up|down)_exps\.weight$=ROCm0",
    r"^blk\.(11|12|13)\.ffn_(up|down)_exps\.weight$=ROCm1",
    r"^blk\.(22|23|24)\.ffn_(up|down)_exps\.weight$=ROCm2",
    r"^blk\.(33|34|35)\.ffn_(up|down)_exps\.weight$=ROCm3",
    redistributed[index],
])
redistributed += ["--mmproj-device", "ROCm3"]
(root / "dense-cuda-redistributed.json").write_text(json.dumps(redistributed, indent=2) + "\n")

redistributed_plus = dense_aligned.copy()
index = redistributed_plus.index("--override-tensor") + 1
redistributed_plus[index] = ",".join([
    r"^blk\.(0|1|2)\.ffn_(up|down)_exps\.weight$=ROCm0",
    r"^blk\.(11|12|13)\.ffn_(up|down)_exps\.weight$=ROCm1",
    r"^blk\.(22|23|24)\.ffn_(up|down)_exps\.weight$=ROCm2",
    r"^blk\.(33|34|35)\.ffn_(up|down)_exps\.weight$=ROCm3",
    r"^blk\.3\.ffn_(up|down)_exps\.weight$=ROCm0",
    r"^blk\.14\.ffn_(up|down)_exps\.weight$=ROCm1",
    r"^blk\.25\.ffn_(up|down)_exps\.weight$=ROCm2",
    r"^blk\.36\.ffn_(up|down)_exps\.weight$=ROCm3",
    redistributed_plus[index],
])
redistributed_plus += ["--mmproj-device", "ROCm3"]
(root / "dense-cuda-redistributed-plus.json").write_text(json.dumps(redistributed_plus, indent=2) + "\n")
