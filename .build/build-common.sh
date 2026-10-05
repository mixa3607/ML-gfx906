#!/usr/bin/env bash

# Return 0 for an existing image, 1 for a missing manifest, 2 for lookup errors.
function build_image_exists {
  local image="$1" error
  if error="$(docker buildx imagetools inspect "$image" 2>&1)"; then
    return 0
  fi

  case "$error" in
    *"manifest unknown"*|*"MANIFEST_UNKNOWN"*|*"no such manifest"*|*"$image: not found"*)
      return 1
      ;;
  esac

  printf 'Cannot inspect image %s:\n%s\n' "$image" "$error" >&2
  return 2
}

# stdout is only true/false; a failed lookup is not a missing artifact.
function build_check_image {
  local image="$1" force="${2:-0}" status
  if [ "$force" == "1" ]; then
    echo "Force build is set." >&2
    echo true
    return 0
  fi

  if build_image_exists "$image"; then
    echo "$image already in registry. Skip." >&2
    echo false
  else
    status=$?
    if [ "$status" != "1" ]; then
      return "$status"
    fi
    echo true
  fi
}

function build_require_images {
  local image status
  for image in "$@"; do
    if build_image_exists "$image"; then
      continue
    else
      status=$?
      if [ "$status" == "1" ]; then
        echo "Required base image $image is not published yet." >&2
      fi
      return "$status"
    fi
  done
}

# Usage: build_dispatch CHECK_FUNCTION BUILD_FUNCTION [check|build]
# Keep the build callback outside conditionals so its errexit remains active.
function build_dispatch {
  local check_function="$1" build_function="$2" needed status
  shift 2
  if [ "$#" -gt 1 ]; then
    echo "Usage: $0 [check|build]" >&2
    return 2
  fi

  case "${1:-}" in
    check) "$check_function" ;;
    build) "$build_function" ;;
    "")
      if needed="$("$check_function")"; then
        case "$needed" in
          true) ;;
          false) return 0 ;;
          *) echo "Invalid check result: $needed" >&2; return 2 ;;
        esac
      else
        status=$?
        return "$status"
      fi
      "$build_function"
      ;;
    *) echo "Unsupported command: $1. Use check or build." >&2; return 2 ;;
  esac
}
