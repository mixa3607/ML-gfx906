#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh "pytorch" "rocm"

TORCH_VERSION_SUFFIX="${ROCM_ARCH}.${REPO_GIT_REF}"
TORCH_BASE_IMAGE="${ROCM_IMAGE}:${TORCH_ROCM_VERSION}-complete"
TORCH_PACKAGES_DIR="$PWD/output/rocm${TORCH_ROCM_VERSION}/torch-${TORCH_VERSION}+${TORCH_VERSION_SUFFIX}"
TORCH_PACKAGES_URL="https://s3.arkprojects.space/py-gfx906/rocm${TORCH_ROCM_VERSION}/torch-${TORCH_VERSION}+${TORCH_VERSION_SUFFIX}"
IMAGE_TAGS=(
  "$TORCH_IMAGE:${TORCH_VERSION}-rocm-${TORCH_ROCM_VERSION}-${REPO_GIT_REF}"
  "$TORCH_IMAGE:${TORCH_VERSION}-rocm-${TORCH_ROCM_VERSION}"
)

declare -A IMAGE_ANNOTATIONS
IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/pytorch"
IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="PyTorch gfx906"
IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${TORCH_BASE_IMAGE}"

echo "Start building PyTorch image..."
echo "TORCH_VERSION:        ${TORCH_VERSION}"
echo "TORCH VERSION SUFFIX: ${TORCH_VERSION_SUFFIX}"
echo "TORCH PACKAGES SRC:   ${TORCH_PACKAGES_SOURCE}"
echo "TORCH PACKAGES DIR:   ${TORCH_PACKAGES_DIR}"
echo "TORCH PACKAGES URL:   ${TORCH_PACKAGES_URL}"
echo "ROCM IMAGE:           ${TORCH_BASE_IMAGE}"
echo "ROCM ARCH:            ${ROCM_ARCH}"
echo "ROCM VERSION:         ${TORCH_ROCM_VERSION}"
echo "PUSH:                 ${TORCH_PUSH}"

DOCKER_EXTRA_ARGS=()
for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
  echo "TAG:          ${IMAGE_TAGS[$i]}"
  DOCKER_EXTRA_ARGS+=("--tag" "${IMAGE_TAGS[$i]}")
done
for key in "${!IMAGE_ANNOTATIONS[@]}"; do
  echo "ANNOTATION:   ${key}: ${IMAGE_ANNOTATIONS[$key]}"
  DOCKER_EXTRA_ARGS+=("--annotation" "${key}=${IMAGE_ANNOTATIONS[$key]}")
done

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo -n "${IMAGE_TAGS[0]} already in registry. "
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
  --build-arg "PYTORCH_MAX_JOBS=${TORCH_MAX_JOBS}"
  --build-arg "PYTORCH_VISION_BRANCH=${TORCH_VISION_VERSION}"
  --progress plain
  --target final 
  --file ./build-image.Dockerfile
  --pull
)

if [ "$TORCH_PUSH" == "1" ]; then
  DOCKER_EXTRA_ARGS+=(
    --push
  )
fi

if [ "$TORCH_PACKAGES_SOURCE" == "fetch" ]; then
  DOCKER_EXTRA_ARGS+=(
    --build-arg "PACKAGE_SOURCE=fetch"
    --build-arg "PACKAGES_BASE_URL=$TORCH_PACKAGES_URL"
    --build-context "packages=$(mktemp -d)"
  )
elif [ "$TORCH_PACKAGES_SOURCE" == "context" ]; then
  if ! [ -d  "$TORCH_PACKAGES_DIR" ]; then
    echo "$TORCH_PACKAGES_DIR not exist. Try \"fetch\" source type"
    exit 1
  fi
  DOCKER_EXTRA_ARGS+=(
    --build-arg "PACKAGE_SOURCE=context"
    --build-context "packages=$TORCH_PACKAGES_DIR"
  )
else
  echo "TORCH_PACKAGES_SOURCE=$TORCH_PACKAGES_SOURCE not supported"
  exit 1
fi

mkdir -p ./logs || true
echo "Install torch whl packages to image"
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
