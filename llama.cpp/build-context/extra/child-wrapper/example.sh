#!/usr/bin/env bash
set -e

binary=$1
shift

unset M36_LLAMA_CHILD_WRAPPER

# export HIP_VISIBLE_DEVICES=0
echo "child-wrapper: starting $binary" >&2
exec "$binary" "$@"
