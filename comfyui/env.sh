#!/usr/bin/env bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$COMFYUI_IMAGE" == "" ]; then
  COMFYUI_IMAGE="docker.io/mixa3607/comfyui-gfx906"
fi

if [ "$COMFYUI_TORCH_IMAGE" == "" ]; then
  COMFYUI_TORCH_IMAGE="docker.io/mixa3607/pytorch-gfx906"
fi
if [ "$COMFYUI_ROCM_VERSION" == "" ]; then
  COMFYUI_ROCM_VERSION="6.3.3"
fi
if [ "$COMFYUI_PYTORCH_VERSION" == "" ]; then
  COMFYUI_PYTORCH_VERSION="2.7.1"
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

# push image
if [ "$COMFYUI_PUSH" == "" ]; then
  COMFYUI_PUSH="1"
fi

if [ "$COMFYUI_IS_RELEASE" == "" ]; then
  COMFYUI_IS_RELEASE="0"
fi

popd
