# ML software for deprecated GFX906 arch

![GitHub License](https://img.shields.io/github/license/mixa3607/ML-gfx906?style=flat-square)
[<img src="https://img.shields.io/badge/discord-gfx906-green?style=flat-square">](https://discord.gg/ZbXbcqJct)
[<img src="https://img.shields.io/badge/docs-arkprojects.space%2Fwiki-green?style=flat-square">]([https://arkprojects.space/wiki/AMD_GFX906](https://arkprojects.space/wiki/AMD_GFX906))

## Docs
https://arkprojects.space/wiki/AMD_GFX906

## Prebuild images

### Images

| Name         | About                 | Status                                                                                                                                                       | Docs                               |
| ------------ | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------- |
| ROCm         | ROCm patched images   | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/rocm-daily-build.yaml?style=flat-square)          | [readme](./rocm/readme.md)         |
| ROCm RVS     | ROCm Validation Suite | OK                                                                                                                                                           | [readme](./rocm-validation-suite/readme.md)     |
| ROCm tensile | gfx906 tensile files  | Deprecated                                                                                                                                                   | [readme](./rocm-tensile/readme.md) |
| PyTorch      | PyTorch images        | OK                                                                                                                                                           | [readme](./pytorch/readme.md)      |
| llama.cpp    | llama.cpp images      | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/llamacpp-ggml-daily-build.yaml?style=flat-square) | [readme](./llama.cpp/readme.md)    |
| ComfyUI      | ComfyUI images        | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/comfyui-daily-build.yaml?style=flat-square)       | [readme](./comfyui/readme.md)      |
| vLLM         | vLLM images           | OK                                                                                                                                                           | [readme](./vllm-v2/readme.md)      |


### Deps graph

```mermaid
flowchart TD
  ubuntu[docker.io/library/ubuntu] --> rocm[docker.io/mixa3607/rocm-gfx906]
  rocm --> rocm-rvc[docker.io/mixa3607/rvc-gfx906]
  rocm --> llama[docker.io/mixa3607/llama.cpp-gfx906]
  rocm --> torch[docker.io/mixa3607/pytorch-gfx906]
  torch --> comfyui[docker.io/mixa3607/comfyui-gfx906]
  torch --> vllm[docker.io/mixa3607/vllm-gfx906]
```
