#!/usr/bin/env bash
set -e

binary=$1
shift

# Leave other preload libraries intact, but disable wrapping in descendants.
unset M36_LLAMA_CHILD_WRAPPER

# Customize the child's environment or arguments here.
# export HIP_VISIBLE_DEVICES=0
echo "child-wrapper: starting $binary" >&2
exec "$binary" "$@"
