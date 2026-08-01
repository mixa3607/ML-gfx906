#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

# value from tag https://github.com/ROCm/TheRock/tags therock-<VERSION>
if [ "$ROCM_THEROCK_VERSION" == "" ]; then
  ROCM_THEROCK_VERSION=7.14
fi

# target arch
if [ "$ROCM_ARCH" == "" ]; then
  ROCM_ARCH=gfx906
fi

# base image
if [ "$ROCM_BASE_IMAGE" == "" ]; then
  ROCM_BASE_IMAGE="docker.io/library/ubuntu:24.04"
fi

# destination image
if [ "$ROCM_IMAGE" == "" ]; then
  ROCM_IMAGE=docker.io/mixa3607/rocm-gfx906
fi

popd
