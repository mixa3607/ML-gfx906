#/bin/bash

function docker_image_pushed {
  if docker buildx imagetools inspect "$1" > /dev/null 2> /dev/null; then
    return 0
  else
    return 1
  fi
}

function git_get_current_tag {
  if [ "$1" != "" ]; then pushd "$1" > /dev/null; fi
  git tag --points-at HEAD
  if [ "$1" != "" ]; then popd > /dev/null; fi
}

function git_get_current_sha {
  if [ "$1" != "" ]; then pushd "$1" > /dev/null; fi
  git rev-parse --short HEAD
  if [ "$1" != "" ]; then popd > /dev/null; fi
}

if [ "$REPO_GIT_REF" == "" ]; then
  REPO_GIT_REF="$(git_get_current_tag)"
fi
if [ "$REPO_GIT_REF" == "" ]; then
  REPO_GIT_REF="$(git_get_current_sha)"
fi

if [ "$BASE_UBUNTU_REGISTRY" == "" ]; then
  BASE_UBUNTU_REGISTRY=docker.io/library
fi

source $(dirname ${BASH_SOURCE[0]})/rocm/env.sh
source $(dirname ${BASH_SOURCE[0]})/llama.cpp/env.sh
source $(dirname ${BASH_SOURCE[0]})/comfyui/env.sh
