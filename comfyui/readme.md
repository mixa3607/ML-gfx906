# llama.cpp GFX906
The most powerful and modular diffusion model GUI, api and backend with a graph/nodes interface. https://github.com/comfyanonymous/ComfyUI

## Run
### Docker
See https://github.com/hartmark/sd-rocm/blob/main/docker-compose.yml

### Kubernetes
Helm chart and samples [mixa3607 charts](https://github.com/mixa3607/charts)

## Build
Export env vars or use defaults defined in `./env.sh`:
- `COMFYUI_ROCM_VERSION` to required ROCm ver
- `PATCHED_COMFYUI_REGISTRY` to your regisry addr

Exec `./build-and-push.comfyui.sh`
```bash
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
