#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$PATCHED_VLLM_REGISTRY" == "" ]; then
  PATCHED_VLLM_REGISTRY=ghcr.io/mixa3607/ml-gfx906/vllm
  #PATCHED_VLLM_REGISTRY=registry.arkprojects.space/apps/vllm
fi

if [ "$VLLM_ROCM_VERSION" == "" ]; then
  VLLM_ROCM_VERSION=6.3.3
fi

if [ "$VLLM_GIT_REF" == "" ]; then
  VLLM_GIT_REF="$(git_get_current_tag submodules/vllm-gfx906)"
fi
if [ "$VLLM_GIT_REF" == "" ]; then
  VLLM_GIT_REF="$(git_get_current_sha submodules/vllm-gfx906)"
fi

if [ "$TRITON_GIT_REF" == "" ]; then
  TRITON_GIT_REF="$(git_get_current_tag submodules/triton-gfx906)"
fi
if [ "$TRITON_GIT_REF" == "" ]; then
  TRITON_GIT_REF="$(git_get_current_sha submodules/triton-gfx906)"
fi

popd
