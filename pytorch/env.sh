#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

# rocm version
if [ "$TORCH_ROCM_VERSION" == "" ];    then TORCH_ROCM_VERSION="7.14"; fi
# torch git checkpoint
if [ "$TORCH_VERSION" == "" ];         then TORCH_VERSION="v2.13.0"; fi
# destination image
if [ "$TORCH_IMAGE" == "" ];           then TORCH_IMAGE="docker.io/mixa3607/pytorch-gfx906"; fi
# push result
if [ "$TORCH_PUSH" == "" ];            then TORCH_PUSH="1"; fi
# packages source
if [ "$TORCH_PACKAGES_SOURCE" == "" ]; then TORCH_PACKAGES_SOURCE="fetch"; fi

popd
