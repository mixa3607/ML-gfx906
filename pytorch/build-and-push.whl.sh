#/bin/bash
set -eo pipefail

cd $(dirname $0)
source ../env.sh "pytorch" "rocm"

TORCH_VERSION_SUFFIX="${ROCM_ARCH}.${REPO_GIT_REF}"
TORCH_BASE_IMAGE="${ROCM_IMAGE}:${TORCH_ROCM_VERSION}-complete"
ROCM_PACKAGES_DIR="$PWD/output/rocm${TORCH_ROCM_VERSION}"
TORCH_PACKAGES_DIR="$ROCM_PACKAGES_DIR/torch-${TORCH_VERSION}+${TORCH_VERSION_SUFFIX}"

echo "Start building PyTorch packages..."
echo "TORCH_VERSION:        ${TORCH_VERSION}"
echo "TORCH VERSION SUFFIX: ${TORCH_VERSION_SUFFIX}"
echo "TORCH PACKAGES DIR:   ${TORCH_PACKAGES_DIR}"
echo "ROCM IMAGE:           ${TORCH_BASE_IMAGE}"
echo "ROCM ARCH:            ${ROCM_ARCH}"
echo "ROCM VERSION:         ${TORCH_ROCM_VERSION}"

DOCKER_EXTRA_ARGS=()
if [ -d  "$TORCH_PACKAGES_DIR" ]; then
  echo "Directory $TORCH_PACKAGES_DIR exist. "
  if [ "$TORCH_FORCE_BUILD" == "1" ]; then
    echo "Force build..."
  else
    echo "Skip."
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
echo "Build PyTorch wheel packages"
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log

if [ "$TORCH_PUSH" == "1" ]; then
  if ! [ -e ".venv/bin/activate" ]; then
    echo "Creating venv in .venv"
    python3 -m venv .venv
    source ./.venv/bin/activate
    python3 -m venv install s3cmd
  fi
  source ./.venv/bin/activate
  
  ls "$TORCH_PACKAGES_DIR" | grep -E '\.whl$' > "$TORCH_PACKAGES_DIR/index.txt"
  echo "Torch whl packages in index:"
  cat "$TORCH_PACKAGES_DIR/index.txt"
  s3cmd put -r "$ROCM_PACKAGES_DIR" "s3://py-gfx906/" --acl-public
fi
