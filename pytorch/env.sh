#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

# rocm version
if [ "$TORCH_ROCM_VERSION" == "" ];          then TORCH_ROCM_VERSION=6.3.3; fi
# torch git checkpoint
if [ "$TORCH_PYTORCH_BRANCH" == "" ];        then TORCH_PYTORCH_BRANCH="v2.7.1"; fi
# vision git checkpoint
if [ "$TORCH_PYTORCH_VISION_BRANCH" == "" ]; then TORCH_PYTORCH_VISION_BRANCH="v0.21.0"; fi

# destination image
if [ "$TORCH_IMAGE" == "" ]; then
  TORCH_IMAGE=docker.io/mixa3607/pytorch-gfx906
fi

popd
