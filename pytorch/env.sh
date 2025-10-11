#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

# rocm version
if [ "$TORCH_ROCM_VERSION" == "" ];  then TORCH_ROCM_VERSION=6.3.3; fi
# torch git checkpoint
if [ "$TORCH_VERSION" == "" ];       then TORCH_VERSION="v2.7.1"; fi
# vision git checkpoint
if [ "$TORCH_VISION_BRANCH" == "" ]; then TORCH_VISION_VERSION="v0.21.0"; fi

# destination image
if [ "$TORCH_IMAGE" == "" ]; then
  TORCH_IMAGE=docker.io/mixa3607/pytorch-gfx906
fi

popd
