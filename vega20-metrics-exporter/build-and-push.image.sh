#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh
source ../.build/build-common.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${METRICS_VERSION:="0.1.0"}"
: "${METRICS_IMAGE:="docker.io/mixa3607/vega20-metrics-exporter"}"
: "${METRICS_PUSH:="1"}"
: "${METRICS_IS_RELEASE:="0"}"
: "${METRICS_PACKAGES_SOURCE:="context"}"
: "${METRICS_VERSION_SUFFIX:="${REPO_GIT_REF}"}"
: "${METRICS_PACKAGE_VERSION:="${METRICS_VERSION}+${METRICS_VERSION_SUFFIX}"}"
: "${METRICS_PACKAGES_DIR:="$PWD/output/vega20-metrics-exporter-${METRICS_PACKAGE_VERSION}"}"

if [ "$METRICS_IS_RELEASE" = "1" ]; then
  IMAGE_TAGS=(
    "${METRICS_IMAGE}:${METRICS_VERSION}-${REPO_GIT_REF}"
    "${METRICS_IMAGE}:${METRICS_VERSION}"
  )
else
  IMAGE_TAGS=(
    "${METRICS_IMAGE}:${METRICS_VERSION}-${REPO_GIT_REF}-pre"
  )
fi

function check {
  build_check_image "${IMAGE_TAGS[0]}" "${METRICS_FORCE_BUILD:-0}"
}

function build {
  build_require_images "docker.io/library/ubuntu:24.04"

  local -a DOCKER_EXTRA_ARGS=(
    --build-arg "PACKAGE_SOURCE=${METRICS_PACKAGES_SOURCE}"
    --progress plain
    --pull
    --target final
    --file ./build-image.Dockerfile
  )
  local tag
  for tag in "${IMAGE_TAGS[@]}"; do
    DOCKER_EXTRA_ARGS+=(--tag "$tag")
  done

  if [ "$METRICS_PACKAGES_SOURCE" = "context" ]; then
    if [ ! -d "$METRICS_PACKAGES_DIR" ]; then
      print ERR "$METRICS_PACKAGES_DIR does not exist. Build the deb first."
      return 1
    fi
    DOCKER_EXTRA_ARGS+=(--build-context "packages=${METRICS_PACKAGES_DIR}")
  elif [ "$METRICS_PACKAGES_SOURCE" = "apt" ]; then
    DOCKER_EXTRA_ARGS+=(--build-context "packages=$(mktemp -d)")
  else
    print ERR "Unsupported METRICS_PACKAGES_SOURCE=$METRICS_PACKAGES_SOURCE" >&2
    return 1
  fi

  if [ "$METRICS_PUSH" = "1" ]; then
    DOCKER_EXTRA_ARGS+=(--push)
  fi

  mkdir -p ./logs
  docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build-image_$(date +%Y%m%d%H%M%S).log"
}

build_dispatch check build "$@"
