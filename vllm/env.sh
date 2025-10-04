#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$VLLM_IMAGE" == "" ]; then
  VLLM_IMAGE=docker.io/mixa3607/vllm-gfx906
  #VLLM_IMAGE=registry.arkprojects.space/apps/vllm-gfx906
fi

if [ "$VLLM_PRESET_NAME" == "" ];           then VLLM_PRESET_NAME=default; fi
if [ "$VLLM_BRANCH" == "" ];                then VLLM_BRANCH="v0.10.2"; fi
if [ "$VLLM_TRITON_BRANCH" == "" ];         then VLLM_TRITON_BRANCH="v3.4.x"; fi
if [ "$VLLM_ROCM_VERSION" == "" ];          then VLLM_ROCM_VERSION=6.4.4; fi
if [ "$VLLM_PYTORCH_REPO" == "" ];          then VLLM_PYTORCH_REPO="https://github.com/pytorch/pytorch.git"; fi
if [ "$VLLM_PYTORCH_BRANCH" == "" ];        then VLLM_PYTORCH_BRANCH="v2.7.1"; fi
if [ "$VLLM_PYTORCH_VISION_REPO" == "" ];   then VLLM_PYTORCH_VISION_REPO="https://github.com/pytorch/vision.git"; fi
if [ "$VLLM_PYTORCH_VISION_BRANCH" == "" ]; then VLLM_PYTORCH_VISION_BRANCH="v0.21.0"; fi

popd
