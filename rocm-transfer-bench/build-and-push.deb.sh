#/bin/bash
set -eo pipefail

cd $(dirname $0)
source ../env.sh "rocm-transfer-bench" "rocm"

TB_VERSION_SUFFIX="${ROCM_VERSION}+${ROCM_ARCH}+${REPO_GIT_REF}"
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
  --pull
  --target final 
  --file ./build-deb.Dockerfile
  --output "type=local,dest=$TB_PACKAGES_DIR"
)

mkdir -p ./logs || true
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log

# Push packages
if [ "$TB_PUSH" == "1" ]; then
  SCP_DST="k3s@kube-worker6.arkprojects.lan:/home/k3s/rocm-dev-packages/rocm-transfer-bench"
  find "$TB_PACKAGES_DIR" -maxdepth 1 -mindepth 1 -name "*.deb" | xargs -I {} scp {} "$SCP_DST" 
fi
