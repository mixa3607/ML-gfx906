#/bin/bash

if [ "$REPO_GIT_REF" == "" ]; then
  REPO_GIT_REF="$(git tag --points-at HEAD)"
fi
if [ "$REPO_GIT_REF" == "" ]; then
  REPO_GIT_REF="$(git rev-parse --short HEAD)"
fi

if [ "$BASE_UBUNTU_REGISTRY" == "" ]; then
  BASE_UBUNTU_REGISTRY=docker.io/library
fi

source $(dirname ${BASH_SOURCE[0]})/rocm/env.sh
source $(dirname ${BASH_SOURCE[0]})/llama.cpp/env.sh
source $(dirname ${BASH_SOURCE[0]})/comfyui/env.sh
