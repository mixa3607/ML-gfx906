# ML software for deprecated GFX906 arch

![GitHub License](https://img.shields.io/github/license/mixa3607/ML-gfx906?style=flat-square)
[<img src="https://img.shields.io/badge/discord-gfx906-green?style=flat-square">](https://discord.gg/EgsTWBqPr)
[<img src="https://img.shields.io/badge/docs-arkprojects.space%2Fwiki-green?style=flat-square">](https://arkprojects.space/wiki/AMD_GFX906)

## Docs

> Legacy builds (pre-TheRock) are **no longer supported** starting from the
> `20260802001858` release. If you are stuck on an old build (e.g. `6.3.3`)
> because of issues with the new TheRock builds, please
> [open an issue](https://github.com/mixa3607/ML-gfx906/issues).

https://arkprojects.space/wiki/AMD_GFX906

### Add the repository (Ubuntu 24.04)

```bash
sudo apt-get update
sudo apt-get install ca-certificates curl -y
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://s3.arkprojects.space/apt-gfx906/ubuntu/gpg -o /etc/apt/keyrings/apt-gfx906.asc
sudo chmod a+r /etc/apt/keyrings/apt-gfx906.asc
sudo tee /etc/apt/sources.list.d/gfx906.sources <<EOF
Types: deb
URIs: https://s3.arkprojects.space/apt-gfx906/ubuntu
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: main
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/apt-gfx906.asc
EOF
sudo apt-get update
```

### Subprojects

| Name                  | About                   | Artefacts    | Status                                                                                                                                                             | Docs                                        |
| --------------------- | ----------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------- |
| ROCm                  | ROCm bulds              | deb, image   | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/rocm-daily-build.yaml?style=flat-square)                | [readme](./rocm/README.md)                  |
| ROCm Validation Suite | ROCm Validation Suite   | deb          | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/rocm-validation-suite-deb-build.yaml?style=flat-square) | [readme](./rocm-validation-suite/README.md) |
| ROCm TransferBench    | ROCm TransferBench      | deb          | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/rocm-transfer-bench-deb-build.yaml?style=flat-square)   | [readme](./rocm-transfer-bench/README.md)   |
| AMD Memory Tweak      | AMD HBM2 timing tool    | deb          | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/amd-memory-tweak-deb-build.yaml?style=flat-square)      | [readme](./amd-memory-tweak/README.md)      |
| AMD Tuning            | Tool for AMD GPU tuning | deb          | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/amd-tuning-deb-build.yaml?style=flat-square)            | [readme](./amd-tuning/README.md)            |
| PyTorch               | PyTorch                 | wheel, image | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/pytorch-daily-build.yaml?style=flat-square)             | [readme](./pytorch/README.md)               |
| llama.cpp             | llama.cpp               | image        | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/llamacpp-ggml-daily-build.yaml?style=flat-square)       | [readme](./llama.cpp/README.md)             |
| ComfyUI               | ComfyUI                 | image        | ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/mixa3607/ML-gfx906/comfyui-daily-build.yaml?style=flat-square)             | [readme](./comfyui/README.md)               |
| ROCm Bandwidth Test   | ROCm Bandwidth Test     | deb          | Paused                                                                                                                                                             | [readme](./rocm-bandwidth-test/README.md)   |
| vLLM                  | vLLM                    | image        | Paused                                                                                                                                                             | [readme](./vllm-v2/README.md)               |
| ROCm tensile          | gfx906 tensile files    | files        | Deprecated                                                                                                                                                         | [readme](./rocm-tensile/readme.md)          |

### Deps graph

```mermaid
flowchart TD
  ubuntu[docker.io/library/ubuntu] --> rocm[docker.io/mixa3607/rocm-gfx906]
  rocm --> llama[docker.io/mixa3607/llama.cpp-gfx906]
  rocm --> torch[docker.io/mixa3607/pytorch-gfx906]
  torch --> comfyui[docker.io/mixa3607/comfyui-gfx906]
  torch --> vllm[docker.io/mixa3607/vllm-gfx906]
```
