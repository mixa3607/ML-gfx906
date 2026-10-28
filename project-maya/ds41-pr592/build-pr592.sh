#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source ../.build/.env-local.sh
export RVS_PUSH=0 TB_PUSH=0
source ./preset.v1.1.32-rocm-10.1.sh
export MAYA_BRANCH=v1.1.34
export MAYA_COMMIT=9a0876f5861de25f4cb56b7e19e1c8b63704dcda
export MAYA_PRESET_NAME=v1.1.34-pr592-9a0876f-rocm-10.1
export MAYA_BASE_IMAGE=docker.io/mixa3607/rocm-gfx906@sha256:2c124ecab56dd5f509a4310507435bc75588b3fed2e1d4fa28671a2977406395
export MAYA_IS_RELEASE=0 MAYA_PUSH=1 MAYA_BUILD_JOBS=8
export REPO_GIT_REF=e61d86c
if [[ "$MAYA_IMAGE" != registry.arkprojects.space/apps/* ]]; then
  echo 'Refusing a non-test destination' >&2
  exit 1
fi
printf '%s\n' \
  "MAYA_IMAGE=$MAYA_IMAGE" "MAYA_BRANCH=$MAYA_BRANCH" "MAYA_COMMIT=$MAYA_COMMIT" \
  "MAYA_PRESET_NAME=$MAYA_PRESET_NAME" "MAYA_BASE_IMAGE=$MAYA_BASE_IMAGE" \
  "MAYA_PATCH=$MAYA_PATCH" "MAYA_CMAKE_HIP_FLAGS=$MAYA_CMAKE_HIP_FLAGS" \
  "MAYA_BUILD_JOBS=$MAYA_BUILD_JOBS" "MAYA_IS_RELEASE=$MAYA_IS_RELEASE" \
  "MAYA_PUSH=$MAYA_PUSH" "RVS_PUSH=$RVS_PUSH" "TB_PUSH=$TB_PUSH" "REPO_GIT_REF=$REPO_GIT_REF"
bash ./build-and-push.image.sh "$@"
