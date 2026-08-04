#/bin/bash
set -eo pipefail

cd $(dirname $0)
source ../env.sh "rocm-transfer-bench" "rocm"

TB_VERSION_SUFFIX="${ROCM_ARCH}+${REPO_GIT_REF}"
TB_BASE_IMAGE="${ROCM_IMAGE}:${ROCM_VERSION}-complete"
TB_PACKAGES_DIR="$PWD/output/rocm${ROCM_VERSION}/tb-${TB_VERSION}-${TB_VERSION_SUFFIX}"

echo "Start building TransferBench deb package..."
echo "TB VERSION:        ${TB_VERSION}"
echo "TB VERSION SUFFIX: ${TB_VERSION_SUFFIX}"
echo "TB PACKAGES DIR:   ${TB_PACKAGES_DIR}"
echo "ROCM IMAGE:        ${TB_BASE_IMAGE}"
echo "ROCM ARCH:         ${ROCM_ARCH}"
echo "ROCM VERSION:      ${ROCM_VERSION}"
echo "PUSH:              ${TB_PUSH}"

if [ -d "$TB_PACKAGES_DIR" ]; then
  echo "Directory $TB_PACKAGES_DIR exist. "
  if [ "$TB_FORCE_BUILD" == "1" ]; then
    echo "Force build..."
  else
    echo "Skip."
    exit 0
  fi
fi

DOCKER_EXTRA_ARGS=(
  --build-arg "BASE_ROCM_IMAGE=${TB_BASE_IMAGE}"
  --build-arg "ROCM_ARCH=${ROCM_ARCH}"
  --build-arg "ROCM_VERSION=${ROCM_VERSION}"
  --build-arg "VERSION_SUFFIX=${TB_VERSION_SUFFIX}"
  --build-arg "TB_BRANCH=${TB_VERSION}"
  --progress plain
)

mkdir -p ./logs || true
docker buildx build --target final --file ./build-deb.Dockerfile \
  --output "type=local,dest=$TB_PACKAGES_DIR" \
  "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log

# Push packages
if [ "$TB_PUSH" == "1" ]; then
  echo "not implemented"
  exit 1
fi
