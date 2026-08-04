#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

# value from tag https://github.com/ROCm/TheRock/tags therock-<VERSION>
if [ "$ROCM_VERSION" == "" ]; then
  ROCM_VERSION=7.14
fi

if [ "$ROCM_ARCH" == "" ]; then
  ROCM_ARCH=gfx906
fi

if [ "$ROCM_BUILD" == "" ]; then
  ROCM_BUILD=$ROCM_VERSION.0-$ROCM_ARCH+$REPO_GIT_REF
fi

# base image
if [ "$ROCM_BASE_IMAGE" == "" ]; then
  ROCM_BASE_IMAGE="docker.io/library/ubuntu:24.04"
fi

# destination image
if [ "$ROCM_IMAGE" == "" ]; then
  ROCM_IMAGE=docker.io/mixa3607/rocm-gfx906
fi

# push image
if [ "$ROCM_PUSH" == "" ]; then
  ROCM_PUSH="1"
fi

popd
