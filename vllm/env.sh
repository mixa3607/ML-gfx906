#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$PATCHED_VLLM_IMAGE" == "" ]; then
  PATCHED_VLLM_IMAGE=docker.io/mixa3607/vllm-gfx906
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
