#!/bin/bash

pushd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null

if [ "${AMD_TUNING_VERSION:-}" = "" ]; then
  AMD_TUNING_VERSION="0.0.0"
fi
if [ "${AMD_TUNING_PUSH:-}" = "" ]; then
  AMD_TUNING_PUSH="0"
fi
if [ "${AMD_TUNING_BASE_IMAGE:-}" = "" ]; then
  AMD_TUNING_BASE_IMAGE="docker.io/library/ubuntu:24.04"
fi

popd > /dev/null
