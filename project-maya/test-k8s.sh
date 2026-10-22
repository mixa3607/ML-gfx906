#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${MAYA_TEST_NAMESPACE:=apps-ml}"
: "${MAYA_TEST_IMAGE:=registry.arkprojects.space/apps/maya-gfx906:v1.1.21-rocm-10.1-test}"
mkdir -p logs
job="$(sed -e "s|namespace: apps-ml|namespace: $MAYA_TEST_NAMESPACE|" \
           -e "s|image: registry.arkprojects.space/apps/maya-gfx906:.*|image: $MAYA_TEST_IMAGE|" \
           test-job.yaml | kubectl create -f - -o name)"
echo "Created $job in $MAYA_TEST_NAMESPACE (TTL: 1 hour after completion)"
selector="batch.kubernetes.io/job-name=${job#*/}"
kubectl -n "$MAYA_TEST_NAMESPACE" wait --for=create pod -l "$selector" --timeout=60s
# A container ID exists for running AND already terminated containers. Waiting
# for Ready instead can miss a short test run; logs alone races ContainerCreating.
kubectl -n "$MAYA_TEST_NAMESPACE" wait --for=jsonpath='{.status.containerStatuses[0].containerID}' \
  pod -l "$selector" --timeout=10m
kubectl -n "$MAYA_TEST_NAMESPACE" logs -f "$job" --pod-running-timeout=10m \
  2>&1 | tee "logs/${job#*/}.log"
# logs exits successfully even when the container failed. Inspect the Job too.
kubectl -n "$MAYA_TEST_NAMESPACE" wait --for=condition=complete "$job" --timeout=30s
