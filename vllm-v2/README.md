# vLLM GFX906

Used forks:

- https://github.com/ai-infos/vllm-gfx906-mobydick
- https://github.com/ai-infos/triton-gfx906
- https://github.com/ai-infos/flash-attention-gfx906

## Prebuilt images

- [`docker.io/mixa3607/vllm-gfx906:0.20.1-rocm-6.3.3-aiinfos`](https://hub.docker.com/r/mixa3607/vllm-gfx906/tags)\*
- [`docker.io/mixa3607/vllm-gfx906:0.20.1-rocm-7.2.1-aiinfos`](https://hub.docker.com/r/mixa3607/vllm-gfx906/tags)\*

## Run

## Docker/Kubernetes

https://arkprojects.space/wiki/AMD_GFX906/vllm/run

## Build

See build vars in `./env.sh`. You also may use presets `./preset.*.sh`. Exec `./build-and-push.vllm.sh`:

```bash
$ . preset.0.20.1-rocm-6.3.3-aiinfos.sh
$ ./build-and-push.vllm.sh
```
