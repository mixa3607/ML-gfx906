# llama.cpp GFX906

LLM inference in C/C++ https://github.com/ggml-org/llama.cpp

Recommend use `docker.io/mixa3607/llama.cpp-gfx906:7.2.3-complete`

Also see [llamacpp-offload-calculator](./llamacpp-offload-calculator/readme.md)

## Docs

http://arkprojects.space/wiki/AMD_GFX906/llamacpp

## Build

See build vars in `./env.sh`

```bash
$ . preset.b9180-rocm-7.2.3.sh && ./build-and-push.rocm.sh
~/REPOS/mixa3607/ML-gfx906/llama.cpp ~/REPOS/mixa3607/ML-gfx906/llama.cpp
~/REPOS/mixa3607/ML-gfx906/llama.cpp
~/REPOS/mixa3607/ML-gfx906/rocm ~/REPOS/mixa3607/ML-gfx906/llama.cpp
~/REPOS/mixa3607/ML-gfx906/llama.cpp
#0 building with "remote" instance using remote driver
#...............
#14 DONE 583.8s
```
