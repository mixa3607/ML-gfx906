#!/usr/bin/env bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$STRATA_IMAGE" == "" ]; then
  STRATA_IMAGE=docker.io/mixa3607/strata-gfx906
fi

if [ "$STRATA_ROCM_VERSION" == "" ]; then
  STRATA_ROCM_VERSION=7.14
fi

if [ "$STRATA_REPO" == "" ]; then
  STRATA_REPO="https://github.com/Niko1221/Strata.git"
fi
if [ "$STRATA_BRANCH" == "" ]; then
  STRATA_BRANCH="v0.1.41"
fi
if [ "$STRATA_COMMIT" == "" ]; then
  STRATA_COMMIT=""
fi
if [ "$STRATA_PATCH" == "" ]; then
  STRATA_PATCH="gfx906-setup.patch"
fi
if [ "$STRATA_IS_RELEASE" == "" ]; then
  STRATA_IS_RELEASE="0"
fi

# push image
if [ "$STRATA_PUSH" == "" ]; then
  STRATA_PUSH="1"
fi

popd
