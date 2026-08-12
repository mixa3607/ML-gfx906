# ML software for deprecated GFX906 arch

![GitHub License](https://img.shields.io/github/license/mixa3607/ML-gfx906?style=flat-square)
[<img src="https://img.shields.io/badge/discord-gfx906-green?style=flat-square">](https://discord.gg/EgsTWBqPr)
[<img src="https://img.shields.io/badge/docs-arkprojects.space%2Fwiki-green?style=flat-square">](https://arkprojects.space/wiki/AMD_GFX906)

## Docs

https://arkprojects.space/wiki/AMD_GFX906

## Prebuild images

> Legacy builds (pre-TheRock) are **no longer supported** starting from the
> `20260802001858` release. If you are stuck on an old build (e.g. `6.3.3`)
> because of issues with the new TheRock builds, please
> [open an issue](https://github.com/mixa3607/ML-gfx906/issues).

### Images

| Name             | About                   | Status                                                                                                                                                       | Docs                                        |
| ---------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------- |
| ROCm             | ROCm patched images     | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/rocm-daily-build.yaml?style=flat-square)          | [readme](./rocm/README.md)                  |
| ROCm RVS         | ROCm Validation Suite   | OK                                                                                                                                                           | [readme](./rocm-validation-suite/README.md) |
| ROCm TB          | ROCm TransferBench      | OK                                                                                                                                                           | [readme](./rocm-transfer-bench/README.md)   |
| AMD Memory Tweak | AMD HBM2 timing tool    | OK                                                                                                                                                           | [readme](./amd-memory-tweak/README.md)      |
| AMD Tuning       | Tool for AMD GPU tuning | OK                                                                                                                                                           | [readme](./amd-tuning/README.md)            |
| ROCm tensile     | gfx906 tensile files    | Deprecated                                                                                                                                                   | [readme](./rocm-tensile/readme.md)          |
| PyTorch          | PyTorch images          | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/pytorch-daily-build.yaml?style=flat-square)       | [readme](./pytorch/README.md)               |
| llama.cpp        | llama.cpp images        | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/llamacpp-ggml-daily-build.yaml?style=flat-square) | [readme](./llama.cpp/README.md)             |
| ComfyUI          | ComfyUI images          | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/comfyui-daily-build.yaml?style=flat-square)       | [readme](./comfyui/README.md)               |
| vLLM             | vLLM images             | Paused                                                                                                                                                       | [readme](./vllm-v2/README.md)               |

### Deps graph

```mermaid
flowchart TD
  ubuntu[docker.io/library/ubuntu] --> rocm[docker.io/mixa3607/rocm-gfx906]
  rocm --> llama[docker.io/mixa3607/llama.cpp-gfx906]
  rocm --> torch[docker.io/mixa3607/pytorch-gfx906]
  torch --> comfyui[docker.io/mixa3607/comfyui-gfx906]
  torch --> vllm[docker.io/mixa3607/vllm-gfx906]
```
