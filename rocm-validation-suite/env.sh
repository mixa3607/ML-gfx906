#!/usr/bin/env bash

pushd $(dirname ${BASH_SOURCE[0]})

# ROCmValidationSuite git tag/branch to build
if [ "$RVS_VERSION" == "" ]; then
  RVS_VERSION="main"
fi
# push result
if [ "$RVS_PUSH" == "" ]; then
  RVS_PUSH="0"
fi

popd
