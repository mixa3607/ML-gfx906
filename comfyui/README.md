# ComfyUI GFX906

The most powerful and modular diffusion model GUI, API and backend with a graph/nodes interface. https://github.com/comfyanonymous/ComfyUI

## Prebuilt images

- [`docker.io/mixa3607/comfyui-gfx906:<ver>-rocm-6.3.3`](https://hub.docker.com/r/mixa3607/comfyui-gfx906/tags?name=rocm-6.3.3)\*
- [`docker.io/mixa3607/comfyui-gfx906:<ver>-rocm-7.2.1`](https://hub.docker.com/r/mixa3607/comfyui-gfx906/tags?name=rocm-7.2.1)\*

> \* have daily builds. See last tag on Docker Hub.

## Benchmarks

| Tag                                                  | ROCm  | Comfy   | PyTorch | Preset                             | Batch | Time (s) | Notes                           |
| ---------------------------------------------------- | ----- | ------- | ------- | ---------------------------------- | ----- | -------- | ------------------------------- |
| v0.30.0-rocm-7.14                                    | 7.14  | v0.30.0 | v2.13.0 | SD 1.5                             | 1     | 3.5      |                                 |
| v0.30.0-rocm-7.14                                    | 7.14  | v0.30.0 | v2.13.0 | SD 1.5                             | 2     | 6.7      |                                 |
| v0.3.63-torch-v2.7.1-rocm-6.4.4-patch-20251010004720 | 6.4.4 | v0.3.63 | v2.7.1  | SDXL                               | 1     | 33       |                                 |
| v0.3.63-torch-v2.7.1-rocm-6.4.4-patch-20251010004720 | 6.4.4 | v0.3.63 | v2.7.1  | SDXL                               | 2     | 65       |                                 |
| v0.3.63-torch-v2.7.1-rocm-6.4.4-patch-20251010004720 | 6.4.4 | v0.3.63 | v2.7.1  | SD 1.5                             | 1     | 3.8      |                                 |
| v0.3.63-torch-v2.7.1-rocm-6.4.4-patch-20251010004720 | 6.4.4 | v0.3.63 | v2.7.1  | SD 1.5                             | 2     | 7        |                                 |
| v0.3.63-torch-v2.7.1-rocm-6.3.3-patch-20251010004720 | 6.3.3 | v0.3.63 | v2.7.1  | SDXL                               | 1     | 33       |                                 |
| v0.3.63-torch-v2.7.1-rocm-6.3.3-patch-20251010004720 | 6.3.3 | v0.3.63 | v2.7.1  | SDXL                               | 2     | 65       |                                 |
| v0.3.63-torch-v2.7.1-rocm-6.3.3-patch-20251010004720 | 6.3.3 | v0.3.63 | v2.7.1  | SD 1.5                             | 1     | 3.8      |                                 |
| v0.3.63-torch-v2.7.1-rocm-6.3.3-patch-20251010004720 | 6.3.3 | v0.3.63 | v2.7.1  | SD 1.5                             | 2     | 7        |                                 |
| v0.3.66-torch-v2.9.0-rocm-7.0.2-patch-20251023001558 | 7.0.2 | v0.3.63 | v2.7.1  | 03_video_wan2_2_14B_i2v_subgraphed | 1     | 4522     | PowerLimit 200; TdcLimitGfx 160 |
| v0.3.66-torch-v2.9.0-rocm-7.0.2-patch-20251023001558 | 7.0.2 | v0.3.65 | v2.9.0  | video_wan2_2_14B_t2v               | 1     | 1265     | PowerLimit 200; TdcLimitGfx 160 |
| v0.3.66-torch-v2.9.0-rocm-7.0.2-patch-20251023001558 | 7.0.2 | v0.3.65 | v2.9.0  | video_wan2_2_14B_t2v               | 2     | 1762     | PowerLimit 200; TdcLimitGfx 160 |

## Run

### Docker

See https://github.com/hartmark/sd-rocm/blob/main/docker-compose.yml

Persistence (files):
```bash
-e PERSISTENCE_PATH=/data
-v $(pwd)/data:/data
```

Persistence (venv):
```bash
-e VENV_NAME=venv
```

Behavior:
- Creates a Python virtual environment
  - With persistence: `/data/<venv>`
  - Without: `/comfyui/<venv>`

### Kubernetes

Helm chart and samples: [mixa3607 charts](https://github.com/mixa3607/charts)

## Build

See build vars in `./env.sh`. Source a preset, then run the build script:

```bash
$ . preset.v0.19.0-rocm-6.3.3.sh && ./build-and-push.comfyui.sh
```
