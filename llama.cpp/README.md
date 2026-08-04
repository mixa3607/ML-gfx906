# llama.cpp GFX906

LLM inference in C/C++ https://github.com/ggml-org/llama.cpp

## Prebuilt images

- [`docker.io/mixa3607/llama.cpp-gfx906:<ver>-rocm-7.14`](https://hub.docker.com/r/mixa3607/llama.cpp-gfx906/tags?name=rocm-7.14)\*
- [`docker.io/mixa3607/llama.cpp-gfx906:<ver>-rocm-7.14-mxxm`](https://hub.docker.com/r/mixa3607/llama.cpp-gfx906/tags?name=rocm-7.14-mxxm)\*
- [`docker.io/mixa3607/llama.cpp-gfx906:<ver>-rocm-6.3.3`](https://hub.docker.com/r/mixa3607/llama.cpp-gfx906/tags?name=rocm-6.3.3)\*

> \* have daily builds. See last tag on Docker Hub.

Also see [llamacpp-offload-calculator](./llamacpp-offload-calculator/readme.md)

## Docs

http://arkprojects.space/wiki/AMD_GFX906/llamacpp

## Build

See build vars in `./env.sh`. Source a preset, then run the build script:

```bash
$ . preset.b10219-rocm-6.3.3.sh && ./build-and-push.image.sh
```
