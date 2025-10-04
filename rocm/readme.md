# ROCm GFX906
Open software stack that includes programming models, tools, compilers, libraries, and runtimes for AI and HPC solution development on AMD GPUs.
In 6.4+ gfx906 support was dropped but may be manually compiled.

At this moment rebuild:
- rccl
- rocblas+tensile

## Build
Export env vars or use defaults defined in `./env.sh`:
- `ROCM_IMAGE_VER` to ver value from tag https://hub.docker.com/r/rocm/dev-ubuntu-24.04/tags e.g. 7.0/6.4.4
- `ROCM_VERSION` to full version e.g. 7.0.0/6.4.4
- `PATCHED_ROCM_REGISTRY` to your regisry addr

Exec `./build-and-push.rocm.sh`
```bash
$ . preset.rocm-7.0.0.sh
$ ./build-and-push.rocm.sh
~/REPOS/mixa3607/llama.cpp-gfx906/rocm ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/llama.cpp ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/comfyui ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/vllm ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
#0 building with "remote" instance using remote driver

#1 [internal] load build definition from rocm.Dockerfile
#1 transferring dockerfile: 4.95kB done
#1 DONE 0.0s

#2 [auth] dockerio-proxy/rocm/dev-ubuntu-24.04:pull rocm/dev-ubuntu-24.04:pull token for registry.arkprojects.space
#2 DONE 0.0s

#3 [internal] load metadata for docker.io/rocm/dev-ubuntu-24.04:7.0-complete
#3 DONE 1.8s

#4 [internal] load .dockerignore
#4 transferring context: 2B done
#...............
#24 exporting to image
#24 pushing layers 6.5s done
#24 pushing manifest for docker.io/mixa3607/rocm-gfx906:7.0.0-20251005035204-complete@sha256:00532f62462e80d51e48b021afb7875af53164455c84dc28b24eb29d39aa0005
#24 pushing manifest for docker.io/mixa3607/rocm-gfx906:7.0.0-20251005035204-complete@sha256:00532f62462e80d51e48b021afb7875af53164455c84dc28b24eb29d39aa0005 3.3s done
#24 pushing layers 2.0s done
#24 pushing manifest for docker.io/mixa3607/rocm-gfx906:7.0.0-complete@sha256:00532f62462e80d51e48b021afb7875af53164455c84dc28b24eb29d39aa0005
#24 pushing manifest for docker.io/mixa3607/rocm-gfx906:7.0.0-complete@sha256:00532f62462e80d51e48b021afb7875af53164455c84dc28b24eb29d39aa0005 2.2s done
#24 DONE 17.6s
```
