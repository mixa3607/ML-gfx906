#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$PATCHED_COMFYUI_REGISTRY" == "" ]; then
  PATCHED_COMFYUI_REGISTRY=ghcr.io/mixa3607/ml-gfx906/comfyui
  #PATCHED_COMFYUI_REGISTRY=registry.arkprojects.space/apps
fi

if [ "$COMFYUI_GIT_REF" == "" ]; then
  COMFYUI_GIT_REF="$(cd submodules/ComfyUI; git tag --points-at HEAD)"
fi
if [ "$COMFYUI_GIT_REF" == "" ]; then
  COMFYUI_GIT_REF="$(cd submodules/ComfyUI; git rev-parse --short HEAD)"
fi

popd
