#!/usr/bin/env bash
set -euo pipefail
cd /opt/maya

# All commands go through upstream's maya.py, so its config checks, pack
# validation and engine refresh keep working after a version bump.
case "${1:-}" in
  serve)
    shift
    : "${MAYA_CONFIG:?Set MAYA_CONFIG to an installed JSON config}"
    exec python maya.py --backend hip --config "$MAYA_CONFIG" \
      --host 0.0.0.0 --port "${PORT:-8080}" "$@"
    ;;
  setup)
    shift
    python maya.py --backend hip --setup --no-start --plain "$@"
    # Setup writes its configs next to the source; keep them on the volume.
    mkdir -p /data/config
    shopt -s nullglob
    for config in /opt/maya/maya-*-hip.json; do
      cp "$config" /data/config/
    done
    ;;
  *) exec python maya.py --backend hip "$@" ;;
esac
