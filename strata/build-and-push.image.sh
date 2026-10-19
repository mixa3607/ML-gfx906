#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh
source ../.build/build-common.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${ROCM_ARCH:="gfx906"}"
: "${ROCM_IMAGE:="docker.io/mixa3607/rocm-gfx906"}"
: "${STRATA_IMAGE:="docker.io/mixa3607/strata-gfx906"}"
: "${STRATA_ROCM_VERSION:="10.1"}"
: "${STRATA_REPO:="https://github.com/Niko1221/Strata.git"}"
: "${STRATA_BRANCH:="v0.2.0-beta"}"
: "${STRATA_COMMIT:=""}"
: "${STRATA_CCACHE_MAXSIZE:="2G"}"
: "${STRATA_PATCH:="gfx906-setup.patch"}"
: "${STRATA_IS_RELEASE:="0"}"
: "${STRATA_PUSH:="1"}"
: "${STRATA_PRESET_NAME:="${STRATA_BRANCH}-rocm-${STRATA_ROCM_VERSION}"}"
: "${STRATA_BASE_IMAGE:="${ROCM_IMAGE}:${STRATA_ROCM_VERSION}-complete"}"

if [ "$STRATA_IS_RELEASE" == "1" ]; then
  IMAGE_TAGS=(
    "${STRATA_IMAGE}:${STRATA_PRESET_NAME}-${REPO_GIT_REF}"
    "${STRATA_IMAGE}:${STRATA_PRESET_NAME}"
  )
else
  IMAGE_TAGS=(
    "${STRATA_IMAGE}:${STRATA_PRESET_NAME}-${REPO_GIT_REF}-pre"
  )
fi

function check {
  build_check_image "${IMAGE_TAGS[0]}" "${STRATA_FORCE_BUILD:-0}"
}

function build {
  build_require_images "$STRATA_BASE_IMAGE"

  local -A IMAGE_ANNOTATIONS
  IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
  IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
  IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/strata"
  IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
  IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="Strata gfx906"
  IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${STRATA_BASE_IMAGE}"

  print INFO "Start building Strata image..."
  print INFO "STRATA_REPO:    ${STRATA_REPO}"
  print INFO "STRATA_BRANCH:  ${STRATA_BRANCH}"
  print INFO "STRATA_COMMIT:  ${STRATA_COMMIT}"
  print INFO "STRATA_PATCH:   ${STRATA_PATCH}"
  print INFO "ROCM_ARCH:      ${ROCM_ARCH}"
  print INFO "ROCM_VERSION:   ${STRATA_ROCM_VERSION}"
  print INFO "CCACHE_MAXSIZE: ${STRATA_CCACHE_MAXSIZE}"
  print INFO "IS_RELEASE:     ${STRATA_IS_RELEASE}"

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
    --build-arg ROCM_IMAGE="${STRATA_BASE_IMAGE}"
    --build-arg STRATA_REPO="${STRATA_REPO}"
    --build-arg STRATA_BRANCH="${STRATA_BRANCH}"
    --build-arg STRATA_COMMIT="${STRATA_COMMIT}"
    --build-arg STRATA_PATCH="${STRATA_PATCH}"
    --build-arg CCACHE_MAXSIZE="${STRATA_CCACHE_MAXSIZE}"
    --progress plain
    --target final
    --file ./build-image.Dockerfile
    --pull
  )

  if [ "$STRATA_PUSH" == "1" ]; then
    DOCKER_EXTRA_ARGS+=(--push)
  fi

  mkdir -p ./logs
  print INFO "Build Strata"
  docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"
}

build_dispatch check build "$@"
