#/bin/bash

set -o allexport
ROOT_DIR="../.."
source $ROOT_DIR/env.sh
cat readme.md | envsubst > $ROOT_DIR/readme.md
