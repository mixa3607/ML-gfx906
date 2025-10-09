#/bin/bash

source ./env.sh

if ! [ -z "$(git status --porcelain)" ]; then 
  echo "Workdir is dirty. Exit"
  exit 10
fi

TAG_NAME=$(git_get_current_tag)
if [ "$TAG_NAME" == "" ]; then
  TAG_NAME="$(date +%Y%m%d%H%M%S)"
  git tag -a "$TAG_NAME"
  echo -e "New tag $TAG_NAME" -m "none"
else
  echo "Commit already tagged with $TAG_NAME"
fi
