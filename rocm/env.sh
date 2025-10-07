#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

# value from tag https://hub.docker.com/r/rocm/dev-ubuntu-24.04/tags e.g. 7.0/6.4.4
if [ "$ROCM_VERSION" == "" ]; then
  ROCM_VERSION=6.3.3
fi
if [ "$ROCM_IMAGE_VER" == "" ]; then
  ROCM_IMAGE_VER=6.3.3
fi

# target arch
if [ "$ROCM_ARCH" == "" ]; then
  ROCM_ARCH=gfx906
fi

# source image
if [ "$BASE_ROCM_IMAGE" == "" ]; then
  BASE_ROCM_IMAGE=docker.io/rocm/dev-ubuntu-24.04
fi

# destination image
if [ "$PATCHED_ROCM_IMAGE" == "" ]; then
  PATCHED_ROCM_IMAGE=docker.io/mixa3607/rocm-gfx906
  #PATCHED_ROCM_IMAGE=registry.arkprojects.space/apps/rocm-gfx906
fi

popd
