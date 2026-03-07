# VLLM GFX906

Used forks:

- https://github.com/tomylin890/vllm-gfx906
- https://github.com/nlzy/vllm-gfx906
- https://github.com/nlzy/triton-gfx906

## Run

## DockerHub images

> ghcr.io registry is deprecated. Use https://hub.docker.com/r/mixa3607/vllm-gfx906 instead

Vers compatibility table:
| ROCm | PyTorch | vLLM | triton | model | text | images | misc |
| ----- | ------- | ------ | ------ | ------------------------------------ | ---- | ------ | ---- |
| 6.3.3 | 2.7.1 | 0.10.2 | 3.3.0 | gaunernst/gemma-3-27b-it-qat-autoawq | ✅️ | ✅️ | ok |
| 6.4.4 | 2.7.1 | 0.10.2 | 3.3.0 | gaunernst/gemma-3-27b-it-qat-autoawq | ✅️ | ⛔ | requests with images throw exception |
| 6.3.3 | 2.8.0 | 0.11.0 | 3.4.0 | gaunernst/gemma-3-27b-it-qat-autoawq | ✅️ | ✅️ | ok |
| 6.3.3 | 2.8.0 | 0.11.0 | 3.4.0 | QuantTrio/Qwen3-VL-32B-Instruct-AWQ | ✅️ | ✅️ | ok |
| 6.4.4 | 2.8.0 | 0.11.0 | 3.4.0 | gaunernst/gemma-3-27b-it-qat-autoawq | ⛔ | ⛔ | all requests throw exception |
| 6.3.3 | 2.8.0 | 0.11.2 | 3.4.0 | gaunernst/gemma-3-27b-it-qat-autoawq | ✅️ | ✅️ | ok |
| 6.3.3 | 2.9.0 | 0.12.0 | 3.5.0 | gaunernst/gemma-3-27b-it-qat-autoawq | ✅️ | ✅️ | ok |

Recommend use `docker.io/mixa3607/vllm-gfx906:0.12.0-rocm-6.3.3`

## Docker/Kubernetes

https://arkprojects.space/wiki/AMD_GFX906/vllm/run

## Build

See build vars in `./env.sh`. You also may use presetis `./preset.*.sh`. Exec `./build-and-push.vllm.sh`:

```bash
$ . preset.0.11.0-rocm-6.3.3.sh
$ ./build-and-push.vllm.sh
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
