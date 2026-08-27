#!/usr/bin/env bash

pushd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null

if [ -z "${METRICS_VERSION:-}" ]; then METRICS_VERSION="0.1.0"; fi
if [ -z "${METRICS_IMAGE:-}" ]; then METRICS_IMAGE="docker.io/mixa3607/vega20-metrics-exporter"; fi
if [ -z "${METRICS_PUSH:-}" ]; then METRICS_PUSH="1"; fi
if [ -z "${METRICS_PACKAGES_SOURCE:-}" ]; then METRICS_PACKAGES_SOURCE="context"; fi

popd >/dev/null
