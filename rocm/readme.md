# ROCm GFX906
Open software stack that includes programming models, tools, compilers, libraries, and runtimes for AI and HPC solution development on AMD GPUs.
In 6.4+ gfx906 support was dropped but may be manually compiled.

## Build
Export env vars or use defaults defined in `./env.sh`:
- `ROCM_IMAGE_VER` to ver value from tag https://hub.docker.com/r/rocm/dev-ubuntu-24.04/tags e.g. 7.0/6.4.4
- `ROCM_VERSION` to full version e.g. 7.0.0/6.4.4
- `PATCHED_ROCM_REGISTRY` to your regisry addr

Exec `./build-and-push.rocm.sh`
```bash
$ ./build-and-push.rocm.sh
~/REPOS/mixa3607/llama.cpp-gfx906/rocm ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/llama.cpp ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/comfyui ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/vllm ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
ghcr.io/mixa3607/ml-gfx906/rocm/dev-ubuntu-24.04:6.4.4-complete already in registry. Skip
#0 building with "remote" instance using remote driver
#...............
#14 exporting to image
#14 pushing manifest for ghcr.io/mixa3607/ml-gfx906/rocm/dev-ubuntu-24.04:6.4.4-complete@sha256:7cfb595ab275d842ffe6cded46bcfbf76cf6c7b673022b3bd32dbaa5b10d57b8 5.1s done
#14 pushing layers
#14 pushing layers 0.7s done
#14 pushing manifest for ghcr.io/mixa3607/ml-gfx906/rocm/dev-ubuntu-24.04:6.4.4-9a2bc48-complete@sha256:7cfb595ab275d842ffe6cded46bcfbf76cf6c7b673022b3bd32dbaa5b10d57b8
#14 pushing manifest for ghcr.io/mixa3607/ml-gfx906/rocm/dev-ubuntu-24.04:6.4.4-9a2bc48-complete@sha256:7cfb595ab275d842ffe6cded46bcfbf76cf6c7b673022b3bd32dbaa5b10d57b8 1.0s done
#14 DONE 583.8s
```
