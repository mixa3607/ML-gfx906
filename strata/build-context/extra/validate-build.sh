#!/usr/bin/env bash
set -euo pipefail
cd /opt/strata/terminal

PY=./python/bin/python3
shopt -s nullglob
components=(/opt/strata/components/engine/*)
(( ${#components[@]} )) || { echo "no engine component in /opt/strata/components/engine" >&2; exit 1; }

for component in "${components[@]}"; do
    # Full manifest hash check. package_engine.py --verify would also demand that
    # every imported library is bundled; the ROCm libraries come from the base
    # image by design, so only ldd below checks the runtime dependencies.
    "$PY" -c 'import sys; from pathlib import Path; from strata_control import engine_component as ec; ec.verify(ec.read_manifest(Path(sys.argv[1])), full=True)' "$component"

    # ROCm libraries come from the base image; every other dependency of the
    # engine and its two vision readers must resolve inside this image.
    for binary in "$component"/strata "$component"/strata-vision "$component"/strata-vision-hip; do
        [ -x "$binary" ] || { echo "missing $binary" >&2; exit 1; }
        dependencies="$(ldd "$binary" || true)"
        if [[ "$dependencies" == *"not found"* ]]; then
            printf '%s:\n%s\n' "$binary" "$dependencies" >&2
            exit 1
        fi
    done
done
