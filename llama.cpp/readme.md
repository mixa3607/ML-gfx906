# llama.cpp GFX906
LLM inference in C/C++ https://github.com/ggml-org/llama.cpp

## Benchmarks
```shell
export PATH="/app:$PATH"
export LD_LIBRARY_PATH="/app:$LD_LIBRARY_PATH"

MODEL=/root/.cache/huggingface/hub/models--ggml-org--gemma-3n-E4B-it-GGUF/snapshots/ee0f0cb58a4b9d5b48dd55b576db22eeeeecdd7e/gemma-3n-E4B-it-Q8_0.gguf
MODEL=/root/.cache/huggingface/hub/models--unsloth--gemma-3-12b-it-GGUF/snapshots/a5592d885c8a933e824f80d2eeda84db95ad2712/gemma-3-12b-it-Q8_0.gguf
MODEL=/root/.cache/huggingface/hub/models--bartowski--Qwen_Qwen3-14B-GGUF/snapshots/bd080f768a6401c2d5a7fa53a2e50cd8218a9ce2/Qwen_Qwen3-14B-Q4_K_S.gguf
MODEL=/root/.cache/huggingface/hub/models--bartowski--Qwen_Qwen3-14B-GGUF/snapshots/bd080f768a6401c2d5a7fa53a2e50cd8218a9ce2/Qwen_Qwen3-14B-Q4_0.gguf
MODEL=/root/.cache/huggingface/hub/models--bartowski--Qwen_Qwen3-14B-GGUF/snapshots/bd080f768a6401c2d5a7fa53a2e50cd8218a9ce2/Qwen_Qwen3-14B-bf16.gguf
MODEL=/root/.cache/huggingface/hub/models--ggml-org--gemma-3-27b-it-GGUF/snapshots/f94c25afed0072339c5fa3b705a7b4222afe5f62/gemma-3-27b-it-f16-00001-of-00002.gguf

llama-bench --model $MODEL -t 16 --flash-attn 0
```

```
ggml_cuda_init: GGML_CUDA_FORCE_MMQ:    no
ggml_cuda_init: GGML_CUDA_FORCE_CUBLAS: no
ggml_cuda_init: found 2 ROCm devices:
  Device 0: AMD Radeon Graphics, gfx906:sramecc+:xnack- (0x906), VMM: no, Wave Size: 64
  Device 1: AMD Radeon Graphics, gfx906:sramecc+:xnack- (0x906), VMM: no, Wave Size: 64
load_backend: loaded ROCm backend from /app/libggml-hip.so
load_backend: loaded CPU backend from /app/libggml-cpu-haswell.so
```

| rocm  | llama.cpp | model                                |       size |     params | backend    | ngl |            test |                  t/s |
| ----- | --------- | ------------------------------------ | ---------: | ---------: | ---------- | --: | --------------: | -------------------: |
| 6.3.4 | 982e3472  | gemma3n E4B Q8_0                     |   6.84 GiB |     6.87 B | ROCm       |  99 |           pp512 |        483.29 ± 0.68 |
| 6.3.4 | 982e3472  | gemma3n E4B Q8_0                     |   6.84 GiB |     6.87 B | ROCm       |  99 |           tg128 |         33.48 ± 0.43 |
| 6.3.4 | 982e3472  | gemma3 12B Q8_0                      |  11.64 GiB |    11.77 B | ROCm       |  99 |           pp512 |        246.66 ± 0.07 |
| 6.3.4 | 982e3472  | gemma3 12B Q8_0                      |  11.64 GiB |    11.77 B | ROCm       |  99 |           tg128 |         28.41 ± 0.12 |
| 6.3.4 | 982e3472  | qwen3 14B Q4_K - Small               |   7.98 GiB |    14.77 B | ROCm       |  99 |           pp512 |        242.34 ± 0.15 |
| 6.3.4 | 982e3472  | qwen3 14B Q4_K - Small               |   7.98 GiB |    14.77 B | ROCm       |  99 |           tg128 |         35.87 ± 0.15 |
| 6.3.4 | 982e3472  | qwen3 14B Q4_0                       |   7.95 GiB |    14.77 B | ROCm       |  99 |           pp512 |        574.13 ± 0.28 |
| 6.3.4 | 982e3472  | qwen3 14B Q4_0                       |   7.95 GiB |    14.77 B | ROCm       |  99 |           tg128 |         39.02 ± 0.23 |
| 6.3.4 | 982e3472  | qwen3 14B BF16                       |  27.51 GiB |    14.77 B | ROCm       |  99 |           pp512 |        118.01 ± 0.24 |
| 6.3.4 | 982e3472  | qwen3 14B BF16                       |  27.51 GiB |    14.77 B | ROCm       |  99 |           tg128 |         19.33 ± 0.08 |
| 6.3.4 | 982e3472  | gemma3 27B F16                       |  50.31 GiB |    27.01 B | ROCm       |  99 |           pp512 |        236.51 ± 0.14 |
| 6.3.4 | 982e3472  | gemma3 27B F16                       |  50.31 GiB |    27.01 B | ROCm       |  99 |           tg128 |         10.37 ± 0.04 |
| 6.3.4 | 982e3472  | llama4 17Bx16E (Scout) Q3_K - Medium |  48.19 GiB |   107.77 B | ROCm       |  99 |           pp512 |        160.50 ± 0.81 |
| 6.3.4 | 982e3472  | llama4 17Bx16E (Scout) Q3_K - Medium |  48.19 GiB |   107.77 B | ROCm       |  99 |           tg128 |         22.75 ± 0.07 |
| 6.4.1 | 982e3472  | gemma3n E4B Q8_0                     |   6.84 GiB |     6.87 B | ROCm       |  99 |           pp512 |        606.83 ± 0.97 |
| 6.4.1 | 982e3472  | gemma3n E4B Q8_0                     |   6.84 GiB |     6.87 B | ROCm       |  99 |           tg128 |         33.36 ± 0.23 |
| 6.4.1 | 982e3472  | gemma3 12B Q8_0                      |  11.64 GiB |    11.77 B | ROCm       |  99 |           pp512 |        329.70 ± 0.30 |
| 6.4.1 | 982e3472  | gemma3 12B Q8_0                      |  11.64 GiB |    11.77 B | ROCm       |  99 |           tg128 |         28.58 ± 0.15 |
| 6.4.1 | 982e3472  | qwen3 14B Q4_K - Small               |   7.98 GiB |    14.77 B | ROCm       |  99 |           pp512 |        286.58 ± 0.15 |
| 6.4.1 | 982e3472  | qwen3 14B Q4_K - Small               |   7.98 GiB |    14.77 B | ROCm       |  99 |           tg128 |         36.48 ± 0.11 |
| 6.4.1 | 982e3472  | qwen3 14B Q4_0                       |   7.95 GiB |    14.77 B | ROCm       |  99 |           pp512 |        570.15 ± 0.23 |
| 6.4.1 | 982e3472  | qwen3 14B Q4_0                       |   7.95 GiB |    14.77 B | ROCm       |  99 |           tg128 |         38.94 ± 0.16 |
| 6.4.1 | 982e3472  | qwen3 14B BF16                       |  27.51 GiB |    14.77 B | ROCm       |  99 |           pp512 |        119.03 ± 0.31 |
| 6.4.1 | 982e3472  | qwen3 14B BF16                       |  27.51 GiB |    14.77 B | ROCm       |  99 |           tg128 |         19.46 ± 0.10 |
| 6.4.1 | 982e3472  | gemma3 27B F16                       |  50.31 GiB |    27.01 B | ROCm       |  99 |           pp512 |        238.38 ± 0.26 |
| 6.4.1 | 982e3472  | gemma3 27B F16                       |  50.31 GiB |    27.01 B | ROCm       |  99 |           tg128 |         10.41 ± 0.03 |
| 6.4.1 | 982e3472  | llama4 17Bx16E (Scout) Q3_K - Medium |  48.19 GiB |   107.77 B | ROCm       |  99 |           pp512 |        190.52 ± 0.84 |
| 6.4.1 | 982e3472  | llama4 17Bx16E (Scout) Q3_K - Medium |  48.19 GiB |   107.77 B | ROCm       |  99 |           tg128 |         22.96 ± 0.10 |


## Run
### Docker
See https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md + https://github.com/ROCm/vllm/blob/main/docs/deployment/docker.md

### Kubernetes
Helm chart and samples [mixa3607 charts](https://github.com/mixa3607/charts)

## Build
Export env vars or use defaults defined in `./env.sh`:
- `LLAMA_ROCM_VERSION` to required ROCm ver (For `build-and-push.rocm.sh` only)
- `PATCHED_LLAMA_REGISTRY` to your regisry addr

Exec `./build-and-push.rocm.sh` or `./build-and-push.vulkan.sh`
```bash
$ ./build-and-push.rocm.sh
~/REPOS/mixa3607/llama.cpp-gfx906/rocm ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/llama.cpp ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/comfyui ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/vllm ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
#0 building with "remote" instance using remote driver
#...............
#14 DONE 583.8s
```
