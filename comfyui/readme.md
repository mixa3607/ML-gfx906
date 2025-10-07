# llama.cpp GFX906
The most powerful and modular diffusion model GUI, api and backend with a graph/nodes interface. https://github.com/comfyanonymous/ComfyUI

Recommend use `docker.io/mixa3607/comfyui-gfx906:latest-rocm-6.4.4`

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
