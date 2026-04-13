#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$COMFYUI_IMAGE" == "" ]; then
  COMFYUI_IMAGE="docker.io/mixa3607/comfyui-sm100"
fi

if [ "$COMFYUI_TORCH_IMAGE" == "" ]; then
  COMFYUI_TORCH_IMAGE="docker.io/pytorch/pytorch"
fi
if [ "$COMFYUI_CUDA_VERSION" == "" ]; then
  COMFYUI_CUDA_VERSION="13.0-cudnn9"
fi
if [ "$COMFYUI_PYTORCH_VERSION" == "" ]; then
  COMFYUI_PYTORCH_VERSION="v2.7.1"
fi

if [ "$COMFYUI_REPO" == "" ]; then
  COMFYUI_REPO="https://github.com/Comfy-Org/ComfyUI.git"
fi
if [ "$COMFYUI_BRANCH" == "" ]; then
  COMFYUI_BRANCH="master"
fi
if [ "$COMFYUI_COMMIT" == "" ]; then
  COMFYUI_COMMIT=""
fi

popd
