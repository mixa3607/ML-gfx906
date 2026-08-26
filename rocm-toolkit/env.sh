#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]}) > /dev/null

if [ "$ROCM_TOOLKIT_IMAGE" == "" ]; then
  ROCM_TOOLKIT_IMAGE="docker.io/mixa3607/rocm-toolkit-gfx906"
fi

if [ "$ROCM_TOOLKIT_PUSH" == "" ]; then
  ROCM_TOOLKIT_PUSH="1"
fi

popd > /dev/null
