#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh
source ../.build/build-common.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${ROCM_ARCH:="gfx906"}"
: "${ROCM_IMAGE:="docker.io/mixa3607/rocm-gfx906"}"
: "${MAYA_IMAGE:="docker.io/mixa3607/maya-gfx906"}"
: "${MAYA_ROCM_VERSION:="10.1"}"
: "${MAYA_REPO:="https://github.com/mw00/project-maya.git"}"
: "${MAYA_BRANCH:="v1.1.21"}"
: "${MAYA_COMMIT:=""}"
: "${MAYA_BUILD_JOBS:=""}"
: "${MAYA_CMAKE_HIP_FLAGS:=""}"
: "${MAYA_CCACHE_MAXSIZE:="2G"}"
: "${MAYA_IS_RELEASE:="0"}"
: "${MAYA_PATCH:="gfx906.patch"}"
: "${MAYA_PUSH:="1"}"
: "${MAYA_PRESET_NAME:="${MAYA_BRANCH}-rocm-${MAYA_ROCM_VERSION}"}"
: "${MAYA_BASE_IMAGE:="${ROCM_IMAGE}:${MAYA_ROCM_VERSION}-complete"}"

if [ "$MAYA_IS_RELEASE" == "1" ]; then
  IMAGE_TAGS=(
    "${MAYA_IMAGE}:${MAYA_PRESET_NAME}-${REPO_GIT_REF}"
    "${MAYA_IMAGE}:${MAYA_PRESET_NAME}"
  )
else
  IMAGE_TAGS=(
    "${MAYA_IMAGE}:${MAYA_PRESET_NAME}-${REPO_GIT_REF}-pre"
  )
fi

function check {
  build_check_image "${IMAGE_TAGS[0]}" "${MAYA_FORCE_BUILD:-0}"
}

function build {
  build_require_images "$MAYA_BASE_IMAGE"

  local -A IMAGE_ANNOTATIONS
  IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
  IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
  IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/project-maya"
  IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
  IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="Project Maya gfx906"
  IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${MAYA_BASE_IMAGE}"

  print INFO "Start building project-maya image..."
  print INFO "MAYA_REPO:        ${MAYA_REPO}"
  print INFO "MAYA_BRANCH:      ${MAYA_BRANCH}"
  print INFO "MAYA_COMMIT:      ${MAYA_COMMIT}"
  print INFO "MAYA_BUILD_JOBS:  ${MAYA_BUILD_JOBS}"
  print INFO "MAYA_PATCH:       ${MAYA_PATCH}"
  print INFO "ROCM_ARCH:        ${ROCM_ARCH}"
  print INFO "ROCM_VERSION:     ${MAYA_ROCM_VERSION}"
  print INFO "CMAKE_HIP_FLAGS:  ${MAYA_CMAKE_HIP_FLAGS}"
  print INFO "CCACHE_MAXSIZE:   ${MAYA_CCACHE_MAXSIZE}"
  print INFO "IS_RELEASE:       ${MAYA_IS_RELEASE}"

  local -a DOCKER_EXTRA_ARGS=()
  local i key
  for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
    print INFO "TAG:          ${IMAGE_TAGS[$i]}"
    DOCKER_EXTRA_ARGS+=("--tag" "${IMAGE_TAGS[$i]}")
  done
  for key in "${!IMAGE_ANNOTATIONS[@]}"; do
    print INFO "ANNOTATION:   ${key}: ${IMAGE_ANNOTATIONS[$key]}"
    DOCKER_EXTRA_ARGS+=("--annotation" "${key}=${IMAGE_ANNOTATIONS[$key]}")
  done

  DOCKER_EXTRA_ARGS+=(
    --build-arg ROCM_IMAGE="${MAYA_BASE_IMAGE}"
    --build-arg ROCM_ARCH="${ROCM_ARCH}"
    --build-arg MAYA_REPO="${MAYA_REPO}"
    --build-arg MAYA_BRANCH="${MAYA_BRANCH}"
    --build-arg MAYA_COMMIT="${MAYA_COMMIT}"
    --build-arg MAYA_BUILD_JOBS="${MAYA_BUILD_JOBS}"
    --build-arg MAYA_PATCH="${MAYA_PATCH}"
    --build-arg CMAKE_HIP_FLAGS="${MAYA_CMAKE_HIP_FLAGS}"
    --build-arg CCACHE_MAXSIZE="${MAYA_CCACHE_MAXSIZE}"
    --progress plain
    --target final
    --file ./build-image.Dockerfile
    --pull
  )

  if [ "$MAYA_PUSH" == "1" ]; then
    DOCKER_EXTRA_ARGS+=(--push)
  fi

  mkdir -p ./logs
  print INFO "Build project-maya"
  docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"
}

build_dispatch check build "$@"
