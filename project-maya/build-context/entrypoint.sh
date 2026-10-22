#!/usr/bin/env bash
set -euo pipefail
cd /opt/maya
case "${1:-}" in
  serve)
    shift
    : "${MAYA_CONFIG:?Set MAYA_CONFIG to an installed JSON config}"
    exec python serve/server.py --engine strata --config "$MAYA_CONFIG" --host 0.0.0.0 --port "${PORT:-8080}" "$@"
    ;;
  setup)
    shift
    python maya.py --backend hip --setup --no-start "$@"
    mkdir -p /data/config
    for config in /opt/maya/maya-*-hip.json; do
      [ ! -f "$config" ] || cp "$config" /data/config/
    done
    ;;
  *) exec python maya.py --backend hip "$@" ;;
esac
