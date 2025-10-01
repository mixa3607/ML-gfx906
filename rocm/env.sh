#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$ROCM_VERSION" == "" ]; then
  ROCM_VERSION=7.0.0
fi
if [ "$ROCM_IMAGE_VER" == "" ]; then
  ROCM_IMAGE_VER=7.0
fi

if [ "$ROCM_ARCH" == "" ]; then
  ROCM_ARCH=gfx906
fi

if [ "$BASE_ROCM_REGISTRY" == "" ]; then
  BASE_ROCM_REGISTRY=docker.io
fi
if [ "$PATCHED_ROCM_IMAGE" == "" ]; then
  PATCHED_ROCM_IMAGE=docker.io/mixa3607/rocm-gfx906
fi

popd
