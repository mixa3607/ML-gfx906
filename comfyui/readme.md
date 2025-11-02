# llama.cpp GFX906
The most powerful and modular diffusion model GUI, api and backend with a graph/nodes interface. https://github.com/comfyanonymous/ComfyUI

Recommend use `docker.io/mixa3607/comfyui-gfx906:latest-rocm-6.4.4`

## Benchmarks
| tag                                                  | rocm  | comfy   | pytorch | preset | batch | exec time (sec) | misc |
|------------------------------------------------------|-------|---------|---------|--------|-------|-----------------|------|
| v0.3.63-torch-v2.7.1-rocm-6.4.4-patch-20251010004720 | 6.4.4 | v0.3.63 | v2.7.1  | SDXL   | 1     | 33              |
| v0.3.63-torch-v2.7.1-rocm-6.4.4-patch-20251010004720 | 6.4.4 | v0.3.63 | v2.7.1  | SDXL   | 2     | 65              |
| v0.3.63-torch-v2.7.1-rocm-6.4.4-patch-20251010004720 | 6.4.4 | v0.3.63 | v2.7.1  | SD 1.5 | 1     | 3,8             |
| v0.3.63-torch-v2.7.1-rocm-6.4.4-patch-20251010004720 | 6.4.4 | v0.3.63 | v2.7.1  | SD 1.5 | 2     | 7               |
| v0.3.63-torch-v2.7.1-rocm-6.3.3-patch-20251010004720 | 6.3.3 | v0.3.63 | v2.7.1  | SDXL   | 1     | 33              |
| v0.3.63-torch-v2.7.1-rocm-6.3.3-patch-20251010004720 | 6.3.3 | v0.3.63 | v2.7.1  | SDXL   | 2     | 65              |
| v0.3.63-torch-v2.7.1-rocm-6.3.3-patch-20251010004720 | 6.3.3 | v0.3.63 | v2.7.1  | SD 1.5 | 1     | 3,8             |
| v0.3.63-torch-v2.7.1-rocm-6.3.3-patch-20251010004720 | 6.3.3 | v0.3.63 | v2.7.1  | SD 1.5 | 2     | 7               |
|                                                      | 7.0.2 | v0.3.63 | v2.7.1  | 03_video_wan2_2_14B_i2v_subgraphed | 1     | 4522               | PowerLimit 200; TdcLimitGfx 160 |
|                                                      | 7.0.2 | v0.3.65 | v2.9.0  | video_wan2_2_14B_t2v | 1                   | 1265               | PowerLimit 200; TdcLimitGfx 160 |
|                                                      | 7.0.2 | v0.3.65 | v2.9.0  | video_wan2_2_14B_t2v | 2                   | 1762               | PowerLimit 200; TdcLimitGfx 160 |

## Run
### Docker
See https://github.com/hartmark/sd-rocm/blob/main/docker-compose.yml

### Kubernetes
Helm chart and samples [mixa3607 charts](https://github.com/mixa3607/charts)

## Build
See build vars in `./env.sh`. You also may use presetis `./preset.rocm-*.sh`. Exec `./build-and-push.comfyui.sh`:
```bash
$ . preset.rocm-6.4.4.sh
$ ./build-and-push.comfyui.sh
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
