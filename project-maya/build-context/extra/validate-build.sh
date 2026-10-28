#!/usr/bin/env bash
set -euo pipefail
cd /opt/maya

for binary in build-hip/maya build-hip/maya-ds4 build-hip/maya-mm3 build-vision-cpu/bin/maya-vision; do
    dependencies="$(ldd "$binary")"
    if [[ "$dependencies" == *"not found"* ]]; then
        printf '%s:\n%s\n' "$binary" "$dependencies" >&2
        exit 1
    fi
done
