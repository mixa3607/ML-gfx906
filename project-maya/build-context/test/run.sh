#!/usr/bin/env bash
set -euo pipefail
cd /opt/maya
export HIP_VISIBLE_DEVICES="${HIP_VISIBLE_DEVICES:-0}"
python tools/check_hip_compat.py
python -m unittest -b tools.test_maya_hip tools.test_hip_archs
/usr/local/bin/maya --check --gpu 0
./build-hip/gfx906-wave64
ctest --test-dir build-hip --output-on-failure --no-tests=error --timeout 120 \
  -R "${MAYA_TEST_REGEX:-^(hip_.*|glm_(hc|kda|ffn|dsa|layer)_parity|glm_model_test|glm_lat8_test|iq1_s_parity|exl3_test|glm_mv_nt_test|glm_mv_nt_generic|platform_memory_test)$}" "$@"
./build-hip/hip_expert_kernel_bench --parity-only --sweep
