#!/usr/bin/env bash

pushd $(dirname ${BASH_SOURCE[0]})

# TransferBench git tag/branch to build
if [ "$TB_VERSION" == "" ]; then
  TB_VERSION="main"
fi
# push result
if [ "$TB_PUSH" == "" ]; then
  TB_PUSH="0"
fi

popd
