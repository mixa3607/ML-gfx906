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
if [ "$PATCHED_ROCM_REGISTRY" == "" ]; then
  PATCHED_ROCM_REGISTRY=ghcr.io/mixa3607/ml-gfx906/rocm
  #PATCHED_ROCM_REGISTRY=registry.arkprojects.space/ghcrio-proxy/mixa3607/ml-gfx906/rocm
fi

popd
