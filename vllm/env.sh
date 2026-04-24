#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$VLLM_IMAGE" == "" ]; then
  VLLM_IMAGE="docker.io/mixa3607/vllm-gfx906"
fi

if [ "$VLLM_PRESET_NAME" == "" ];           then VLLM_PRESET_NAME=default; fi
# vllm git checkpoint
if [ "$VLLM_REPO" == "" ];                  then VLLM_REPO="https://github.com/ai-infos/vllm-gfx906-mobydick.git"; fi
if [ "$VLLM_BRANCH" == "" ];                then VLLM_BRANCH="main"; fi
if [ "$VLLM_PATCH" == "" ];                 then VLLM_PATCH="empty.patch"; fi
# triton git checkpoint
if [ "$VLLM_TRITON_REPO" == "" ];           then VLLM_TRITON_REPO="https://github.com/ai-infos/triton-gfx906.git"; fi
if [ "$VLLM_TRITON_BRANCH" == "" ];         then VLLM_TRITON_BRANCH="v3.5.1+gfx906"; fi
if [ "$VLLM_TRITON_PATCH" == "" ];          then VLLM_TRITON_PATCH="empty.patch"; fi
# fa git checkpoint
if [ "$VLLM_FA_REPO" == "" ];               then VLLM_FA_REPO="https://github.com/ai-infos/flash-attention-gfx906.git"; fi
if [ "$VLLM_FA_BRANCH" == "" ];             then VLLM_FA_BRANCH="gfx906/v2.8.3.x"; fi
if [ "$VLLM_FA_PATCH" == "" ];              then VLLM_FA_PATCH="empty.patch"; fi
# rocm version
if [ "$VLLM_ROCM_VERSION" == "" ];          then VLLM_ROCM_VERSION=6.3.3; fi
# torch git checkpoint
if [ "$VLLM_PYTORCH_VERSION" == "" ];       then VLLM_PYTORCH_VERSION="v2.10.0"; fi

popd
