#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh
source ../.build/build-common.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${ROCM_ARCH:="gfx906"}"
: "${ROCM_IMAGE:="docker.io/mixa3607/rocm-gfx906"}"
: "${TORCH_ROCM_VERSION:="7.14"}"
: "${TORCH_VERSION:="v2.14.0"}"
: "${TORCH_PUSH:="0"}"
: "${TORCH_VERSION_SUFFIX:="${ROCM_ARCH}.${REPO_GIT_REF}"}"
: "${TORCH_BASE_IMAGE:="${ROCM_IMAGE}:${TORCH_ROCM_VERSION}-complete"}"
: "${TORCH_PACKAGES_DIR:="$PWD/output/rocm${TORCH_ROCM_VERSION}/torch-${TORCH_VERSION}+${TORCH_VERSION_SUFFIX}"}"
: "${TORCH_PACKAGES_S3:="s3://py-gfx906/rocm${TORCH_ROCM_VERSION}/torch-${TORCH_VERSION}+${TORCH_VERSION_SUFFIX}/"}"

function check {
  if [ "${TORCH_FORCE_BUILD:-0}" == "1" ]; then
    echo "Force build is set." >&2
    echo true
    return 0
  fi
  if [ -d "$TORCH_PACKAGES_DIR" ]; then
    echo "Directory $TORCH_PACKAGES_DIR exist." >&2 
    echo false
  else
    echo true
  fi
}

function build {
  build_require_images "$TORCH_BASE_IMAGE"

  print INFO "Start building PyTorch packages..."
  print INFO "TORCH_VERSION:        ${TORCH_VERSION}"
  print INFO "TORCH VERSION SUFFIX: ${TORCH_VERSION_SUFFIX}"
  print INFO "TORCH PACKAGES DIR:   ${TORCH_PACKAGES_DIR}"
  print INFO "TORCH PACKAGES S3:    ${TORCH_PACKAGES_S3}"
  print INFO "ROCM IMAGE:           ${TORCH_BASE_IMAGE}"
  print INFO "ROCM ARCH:            ${ROCM_ARCH}"
  print INFO "ROCM VERSION:         ${TORCH_ROCM_VERSION}"

  local -a DOCKER_EXTRA_ARGS=(
    --build-arg "BASE_ROCM_IMAGE=${TORCH_BASE_IMAGE}"
    --build-arg "ROCM_ARCH=${ROCM_ARCH}"
    --build-arg "VERSION_SUFFIX=${TORCH_VERSION_SUFFIX}"
    --build-arg "PYTORCH_BRANCH=${TORCH_VERSION}"
    --build-arg "PYTORCH_VISION_BRANCH=${TORCH_VISION_VERSION}"
    --build-arg "MAX_JOBS=${TORCH_MAX_JOBS}"
    --output "type=local,dest=$TORCH_PACKAGES_DIR"
    --progress plain
    --target final
    --file ./build-whl.Dockerfile
    --pull
  )

  mkdir -p ./logs
  print INFO "Build PyTorch wheel packages"
  docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"

  ls "$TORCH_PACKAGES_DIR" | grep -E '\.whl$' > "$TORCH_PACKAGES_DIR/index.txt"
  print INFO "Torch whl packages in index:"
  cat "$TORCH_PACKAGES_DIR/index.txt"

  if [ "$TORCH_PUSH" == "1" ]; then
    if ! [ -e .venv/bin/activate ]; then
      print INFO "Creating venv in .venv"
      python3 -m venv .venv
      source ./.venv/bin/activate
      python3 -m pip install s3cmd
    fi
    source ./.venv/bin/activate
    pushd "$TORCH_PACKAGES_DIR"
    s3cmd put -r . "$TORCH_PACKAGES_S3" --acl-public
    popd
  fi
}

build_dispatch check build "$@"
