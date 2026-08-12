#!/bin/bash

pushd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null

if [ "$RBT_VERSION" = "" ]; then
  RBT_VERSION="master"
fi
if [ "$RBT_PUSH" = "" ]; then
  RBT_PUSH="0"
fi

popd > /dev/null
