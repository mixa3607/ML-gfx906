#!/bin/bash

pushd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null

if [ "${AMT_VERSION:-}" = "" ]; then
  AMT_VERSION="0.1.9.1"
fi
if [ "${AMT_PUSH:-}" = "" ]; then
  AMT_PUSH="0"
fi
if [ "${AMT_BASE_IMAGE:-}" = "" ]; then
  AMT_BASE_IMAGE="docker.io/library/ubuntu:24.04"
fi

popd > /dev/null
