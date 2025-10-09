# PyTorch GFX906
Tensors and Dynamic neural networks in Python with strong GPU acceleration.

Packages:
- torch
- torchvision

Recommend use `docker.io/mixa3607/pytorch-gfx906:v2.7.1-rocm-6.3.3`

## Build
See build vars in `./env.sh`. You also may use presetis `./preset.*.sh`. Exec `./build-and-push.torch.sh`:
```bash
$ . preset.torch-2.7.1-rocm-6.3.3.sh
$ ./build-and-push.torch.sh
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
