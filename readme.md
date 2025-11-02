# ML software for deprecated GFX906 arch

## Prebuild images
### Images
| Name | Source | Status | Docs |
| ---- | ------ | ------ | ---- |
| ROCm | [ROCm](https://github.com/ROCm/ROCm), [rocBLAS](https://github.com/ROCm/rocBLAS) | OK | [readme](./rocm/readme.md) |
| PyTorch | [torch](https://github.com/pytorch/pytorch), [vision](https://github.com/pytorch/vision), [audio](https://github.com/pytorch/audio) | OK | [readme](./pytorch/readme.md) |
| llama.cpp | [llama.cpp](https://github.com/ggml-org/llama.cpp) | OK | [readme](./llama.cpp/readme.md) |
| ComfyUI | [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | OK | [readme](./comfyui/readme.md) |
| VLLM | [VLLM](https://github.com/nlzy/vllm-gfx906), [triton](https://github.com/nlzy/triton-gfx906) | OK | [readme](./vllm/readme.md) |

### Deps graph
```mermaid
flowchart TD
  rocm-src[docker.io/rocm/dev-ubuntu-24.04] --> rocm[docker.io/mixa3607/rocm-gfx906] 
  rocm --> llama[docker.io/mixa3607/llama.cpp-gfx906]
  rocm --> torch[docker.io/mixa3607/pytorch-gfx906]
  torch --> comfyui[docker.io/mixa3607/comfyui-gfx906]
  torch --> vllm[docker.io/mixa3607/vllm-gfx906]
```

## Perf tuning
Changing smcPPTable/TdcLimitGfx 350 => 150 reduced the hotspot by 10+- degrees with almost no drop in performance in vllm ([table in vllm](./vllm/readme.md#benchmarks))

```console
$ upp -p /sys/class/drm/card${GPU_ID}/device/pp_table set --write smcPPTable/TdcLimitGfx=150
Changing smcPPTable.TdcLimitGfx of type H from 330 to 150 at 0x1fe
Committing changes to '/sys/class/drm/card1/device/pp_table'.
```
<img src="./docs/images/temperatures.png" alt="temperatures" width="400"/>

## Environment
All software tested on Lenovo RD450X with 256G mem and 2x MI50 32G (x16 + x8). For cooling gpus used [AMD Instinct MI50 blower fan adapter (thingiverse)](https://www.thingiverse.com/thing:7153218).

## RVS
```shell
cd /opt/rocm-6.4.1/bin
apt update
apt install -y rocm-validation-suite
echo 'actions:
- name: gst-581Tflops-4K4K8K-rand-bf16
  device: all
  module: gst
  log_interval: 3000
  ramp_interval: 5000
  duration: 15000
  hot_calls: 1000
  copy_matrix: false
  target_stress: 581000
  matrix_size_a: 4864
  matrix_size_b: 4096
  matrix_size_c: 8192
  matrix_init: rand
  data_type: bf16_r
  lda: 8320
  ldb: 8320
  ldc: 4992
  ldd: 4992
  transa: 1
  transb: 0
  alpha: 1
  beta: 0' > ~/gst-581Tflops-4K4K8K-rand-bf16.conf
./rvs -c ~/gst-581Tflops-4K4K8K-rand-bf16.conf
```



