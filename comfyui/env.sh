#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$PATCHED_COMFYUI_REGISTRY" == "" ]; then
  PATCHED_COMFYUI_REGISTRY=ghcr.io/mixa3607/ml-gfx906/comfyui
  #PATCHED_COMFYUI_REGISTRY=registry.arkprojects.space/apps
fi

if [ "$COMFYUI_GIT_REF" == "" ]; then
  COMFYUI_GIT_REF="$(git_get_current_tag submodules/ComfyUI)"
fi
if [ "$COMFYUI_GIT_REF" == "" ]; then
  COMFYUI_GIT_REF="$(git_get_current_sha submodules/ComfyUI)"
fi

popd
