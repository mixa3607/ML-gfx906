#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$COMFYUI_IMAGE" == "" ]; then
  COMFYUI_IMAGE=docker.io/mixa3607/comfyui-gfx906
fi

if [ "$COMFYUI_BASE_IMAGE" == "" ]; then
  COMFYUI_BASE_IMAGE="docker.io/library/ubuntu:24.04"
fi

if [ "$COMFYUI_ROCM_VERSION" == "" ]; then
  COMFYUI_ROCM_VERSION="6.4.4"
fi

if [ "$COMFYUI_GIT_REF" == "" ]; then
  COMFYUI_GIT_REF="$(git_get_current_tag submodules/ComfyUI)"
fi
if [ "$COMFYUI_GIT_REF" == "" ]; then
  COMFYUI_GIT_REF="$(git_get_current_sha submodules/ComfyUI)"
fi

popd
