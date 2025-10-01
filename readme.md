# ML software for deprecated GFX906 arch

## Prebuild images

Packages and status
| Name | Source | OCI registry | app ver | ROCm ver | Status |
| ---- | ------ | ------------ | ------- | -------- | ------ |
| ROCm | [ROCm](https://github.com/ROCm/ROCm), [rocBLAS](https://github.com/ROCm/rocBLAS) | `ghcr.io/mixa3607/ml-gfx906/rocm` | 7.0.0 | 7.0.0 | OK |
| llama.cpp | [llama.cpp](https://github.com/ggml-org/llama.cpp) | `ghcr.io/mixa3607/ml-gfx906/llama` | b6569 | 7.0.0 | OK |
| ComfyUI | [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | `ghcr.io/mixa3607/ml-gfx906/comfyui` | v0.3.60 | 6.4.4 | OK |
| VLLM | [VLLM](https://github.com/nlzy/vllm-gfx906), [triton](https://github.com/nlzy/triton-gfx906) | `ghcr.io/mixa3607/ml-gfx906/vllm` | v0.10.1 + v3.3.0 | 6.3.3 | OK |

## Environment

All software tested on Lenovo RD450X with 256G mem and 2x MI50 32G. For cooling gpus used [AMD Instinct MI50 blower fan adapter (thingiverse)](https://www.thingiverse.com/thing:7153218).

## Docs and benchmarks
See README.md in nested dirs:
- [ROCm](./rocm/readme.md)
- [llama.cpp](./llama.cpp/readme.md)
- [ComfyUI](./comfyui/readme.md)
- [VLLM](./vllm/readme.md)

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
