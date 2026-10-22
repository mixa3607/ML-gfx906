#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/build-common.sh
source ../.build/logger.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${MAYA_IMAGE:="docker.io/mixa3607/maya-gfx906"}"
: "${MAYA_ROCM_VERSION:="10.1"}"
: "${MAYA_BASE_IMAGE:="docker.io/mixa3607/rocm-gfx906:${MAYA_ROCM_VERSION}-complete"}"
: "${MAYA_REPO:="https://github.com/mw00/project-maya.git"}"
: "${MAYA_BRANCH:="v1.1.21"}"
: "${MAYA_COMMIT="451f9cb6a21ea65673bdde2e57b4a670ae2b8859"}"
: "${MAYA_BUILD_JOBS:="4"}"
: "${MAYA_CMAKE_HIP_FLAGS:=""}"
: "${MAYA_CCACHE_MAXSIZE:="2G"}"
: "${MAYA_PATCH:="gfx906.patch"}"
: "${MAYA_PUSH:="1"}"
: "${MAYA_IS_RELEASE:="0"}"
: "${MAYA_PRESET_NAME:="${MAYA_BRANCH}-rocm-${MAYA_ROCM_VERSION}"}"
: "${MAYA_IMAGE_TAG:="${MAYA_PRESET_NAME}-${REPO_GIT_REF}$([ "$MAYA_IS_RELEASE" = 1 ] || echo -pre)"}"

function check {
  build_check_image "${MAYA_IMAGE}:${MAYA_IMAGE_TAG}" "${MAYA_FORCE_BUILD:-0}"
}

function build {
  build_require_images "$MAYA_BASE_IMAGE"
  local -a args=(
    --tag "${MAYA_IMAGE}:${MAYA_IMAGE_TAG}"
    --build-arg ROCM_IMAGE="$MAYA_BASE_IMAGE"
    --build-arg MAYA_REPO="$MAYA_REPO"
    --build-arg MAYA_BRANCH="$MAYA_BRANCH"
    --build-arg MAYA_COMMIT="$MAYA_COMMIT"
    --build-arg MAYA_PATCH="$MAYA_PATCH"
    --build-arg MAYA_BUILD_JOBS="$MAYA_BUILD_JOBS"
    --build-arg CMAKE_HIP_FLAGS="$MAYA_CMAKE_HIP_FLAGS"
    --build-arg CCACHE_MAXSIZE="$MAYA_CCACHE_MAXSIZE"
    --label org.opencontainers.image.source="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/project-maya"
    --label org.opencontainers.image.version="$MAYA_BRANCH"
    --label org.opencontainers.image.revision="$MAYA_COMMIT"
    --progress plain --target final --file ./build-image.Dockerfile --pull
  )
  if [ "$MAYA_IS_RELEASE" = 1 ]; then
    args+=(--tag "${MAYA_IMAGE}:${MAYA_PRESET_NAME}")
  fi
  if [ "$MAYA_PUSH" = 1 ]; then args+=(--push); else args+=(--load); fi
  mkdir -p logs
  print INFO "Build Maya ${MAYA_BRANCH} (${MAYA_COMMIT}), gfx906, patch ${MAYA_PATCH}"
  docker buildx build "${args[@]}" ./build-context 2>&1 | tee "logs/build_$(date +%Y%m%d%H%M%S).log"
}

build_dispatch check build "$@"
