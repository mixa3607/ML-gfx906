#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$COMFYUI_IMAGE" == "" ]; then
  COMFYUI_IMAGE=docker.io/mixa3607/comfyui-gfx906
fi

if [ "$COMFYUI_TORCH_IMAGE" == "" ]; then
  COMFYUI_TORCH_IMAGE="docker.io/mixa3607/pytorch-gfx906"
fi
if [ "$COMFYUI_ROCM_VERSION" == "" ]; then
  COMFYUI_ROCM_VERSION="6.3.3"
fi
if [ "$COMFYUI_PYTORCH_VERSION" == "" ]; then
  COMFYUI_PYTORCH_VERSION="v2.7.1"
fi

if [ "$COMFYUI_GIT_REF" == "" ]; then
  COMFYUI_GIT_REF="$(git_get_current_tag submodules/ComfyUI)"
fi
if [ "$COMFYUI_GIT_REF" == "" ]; then
  COMFYUI_GIT_REF="$(git_get_current_sha submodules/ComfyUI)"
fi

popd
