#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh 'rocm-tensile' 'rocm'

DOCKER_EXTRA_ARGS=()
mkdir ./logs || true
docker buildx build ${DOCKER_EXTRA_ARGS[@]} \
  --build-arg ROCM_IMAGE="${PATCHED_ROCM_IMAGE}:${TENSILE_ROCM_VERSION}-complete" \
  --build-arg ROCM_ARCH="${ROCM_ARCH}" \
  --output type=tar,dest=./output/tensile-files-${TENSILE_ROCM_VERSION}.tgz \
  --target final -f ./rocm-tensile.Dockerfile --progress=plain ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
