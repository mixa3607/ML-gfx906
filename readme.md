# ML software for deprecated SM120 arch

## Prebuild images

### Images

| Name         | About                | Status | Docs                               |
| ------------ | -------------------- | ------ | ---------------------------------- |
| llama.cpp    | llama.cpp images     | OK     | [readme](./llama.cpp/readme.md)    |
| ComfyUI      | ComfyUI images       | OK     | [readme](./comfyui/readme.md)      |
| VLLM         | vLLM images          | OK     | [readme](./vllm/readme.md)      |

| Project   | Image                                                                                                                               |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| vLLM      | `docker.io/mixa3607/vllm-sm120:0.19.1-rocm-6.3.3-aiinfos`                                                                          |
|           | `docker.io/mixa3607/vllm-sm120:0.19.1-rocm-7.2.1-aiinfos`                                                                          |
| --------- | -----------------------------------------------------------                                                                         |
| ComfyUI   | [`docker.io/mixa3607/comfyui-sm120:<ver>-rocm-6.3.3`](https://hub.docker.com/r/mixa3607/comfyui-sm120/tags?name=rocm-6.3.3)\*     |
|           | [`docker.io/mixa3607/comfyui-sm120:<ver>-rocm-7.2.1`](https://hub.docker.com/r/mixa3607/comfyui-sm120/tags?name=rocm-7.2.1)\*     |
| --------- | -----------------------------------------------------------                                                                         |
| llama.cpp | [`docker.io/mixa3607/llama.cpp-sm120:<ver>-rocm-6.3.3`](https://hub.docker.com/r/mixa3607/llama.cpp-sm120/tags?name=rocm-6.3.3)\* |
|           | [`docker.io/mixa3607/llama.cpp-sm120:<ver>-rocm-7.2.1`](https://hub.docker.com/r/mixa3607/llama.cpp-sm120/tags?name=rocm-7.2.1)\* |

> \* llama.cpp and ComfyUI have daily builds. See last tag on dockerhub

# WIP
