#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${TORCH_ROCM_VERSION:="7.14"}"
: "${TORCH_VERSION:="v2.13.0"}"
: "${TORCH_PUSH:="1"}"
: "${ROCM_ARCH:="gfx906"}"
: "${ROCM_IMAGE:="docker.io/mixa3607/rocm-gfx906"}"

TORCH_VERSION_SUFFIX="${ROCM_ARCH}.${REPO_GIT_REF}"
TORCH_BASE_IMAGE="${ROCM_IMAGE}:${TORCH_ROCM_VERSION}-complete"
ROCM_PACKAGES_DIR="$PWD/output/rocm${TORCH_ROCM_VERSION}"
TORCH_PACKAGES_DIR="$ROCM_PACKAGES_DIR/torch-${TORCH_VERSION}+${TORCH_VERSION_SUFFIX}"

print INFO "Start building PyTorch packages..."
print INFO "TORCH_VERSION:        ${TORCH_VERSION}"
print INFO "TORCH VERSION SUFFIX: ${TORCH_VERSION_SUFFIX}"
print INFO "TORCH PACKAGES DIR:   ${TORCH_PACKAGES_DIR}"
print INFO "ROCM IMAGE:           ${TORCH_BASE_IMAGE}"
print INFO "ROCM ARCH:            ${ROCM_ARCH}"
print INFO "ROCM VERSION:         ${TORCH_ROCM_VERSION}"

DOCKER_EXTRA_ARGS=()
if [ -d  "$TORCH_PACKAGES_DIR" ]; then
  print INFO "Directory $TORCH_PACKAGES_DIR exist. "
  if [ "$TORCH_FORCE_BUILD" == "1" ]; then
    print WARN "Force build..."
  else
    print WARN "Skip."
    exit 0
  fi
fi

DOCKER_EXTRA_ARGS+=(
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

mkdir -p ./logs || true
print INFO "Build PyTorch wheel packages"
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log

if [ "$TORCH_PUSH" == "1" ]; then
  if ! [ -e ".venv/bin/activate" ]; then
    print INFO "Creating venv in .venv"
    python3 -m venv .venv
    source ./.venv/bin/activate
    python3 -m venv install s3cmd
  fi
  source ./.venv/bin/activate
  
  ls "$TORCH_PACKAGES_DIR" | grep -E '\.whl$' > "$TORCH_PACKAGES_DIR/index.txt"
  print INFO "Torch whl packages in index:"
  cat "$TORCH_PACKAGES_DIR/index.txt"
  s3cmd put -r "$ROCM_PACKAGES_DIR" "s3://py-gfx906/" --acl-public
fi
