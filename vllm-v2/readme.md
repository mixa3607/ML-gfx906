# VLLM GFX906

Used forks:

- https://github.com/ai-infos/vllm-gfx906-mobydick
- https://github.com/ai-infos/triton-gfx906
- https://github.com/ai-infos/flash-attention-gfx906

## Run

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
