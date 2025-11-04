#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$VLLM_IMAGE" == "" ]; then
  VLLM_IMAGE=docker.io/mixa3607/vllm-gfx906
  #VLLM_IMAGE=registry.arkprojects.space/apps/vllm-gfx906
fi

if [ "$VLLM_PRESET_NAME" == "" ];           then VLLM_PRESET_NAME=default; fi
# vllm git checkpoint
if [ "$VLLM_REPO" == "" ];                  then VLLM_REPO="https://github.com/nlzy/vllm-gfx906.git"; fi
if [ "$VLLM_BRANCH" == "" ];                then VLLM_BRANCH="v0.10.2"; fi
# triton git checkpoint
if [ "$VLLM_TRITON_REPO" == "" ];           then VLLM_TRITON_REPO="https://github.com/nlzy/triton-gfx906.git"; fi
if [ "$VLLM_TRITON_BRANCH" == "" ];         then VLLM_TRITON_BRANCH="v3.4.x"; fi
# rocm version
if [ "$VLLM_ROCM_VERSION" == "" ];          then VLLM_ROCM_VERSION=6.4.4; fi
# torch git checkpoint
if [ "$VLLM_PYTORCH_VERSION" == "" ];       then VLLM_PYTORCH_VERSION="v2.7.1"; fi

popd
