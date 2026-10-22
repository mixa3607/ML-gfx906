# Strata v0.2.2 validation

Checked on 2026-10-22 against upstream commit
`011c9e600a93bbc9fd451c563501b5831c32bbca` (engine `0.1.47`).

## Required changes

- Drop the old CMake patch: upstream already sets the MMQ/trellis sources to HIP,
  adds `moe_f16_kq.cu` and defines `GGML_USE_HIP` for `strata_mmq_w4a4`.
- Drop the cuBLAS aliases: upstream excludes Qwen3.6's wave32 engine on gfx906.
- Keep gfx906 in setup's supported architectures and use system Python in the
  Docker healthcheck.
- Run `packaging/stage_tuning.py` before packaging. The new packager rejects
  HIP packages without `hipblaslt_version`, even when they have no tuning table.

## Passed

- Full Docker build: engine, CPU vision, HIP vision, component integrity and
  `ldd` checks; ROCm `10.1`, HIP flags
  `-mllvm -amdgpu-sched-strategy=max-ilp`.
- Image: `registry.arkprojects.space/apps/strata-gfx906:v0.2.2-rocm-10.1-smoke-20261022`.
  Index digest: `sha256:7a2762d442929f256c9c7abd871151d128a77a3e9e5660ffb3355772909a9fa5`.
- On `kube-worker6.arkprojects.lan`, MI50 32 GiB, GPU 0:
  `strata-device --selftest`, `iq_multi_parity`, `native_grouped_parity`,
  `gfx906_gdn_rec_head`, `hip_router_fast`, `elementwise_parity --selftest`,
  `rope_parity --selftest`, `quantize_act_parity --selftest`.
- Component resolution, full manifest verification, gfx906 detection, both
  vision executables' version checks and healthcheck loaded/empty responses.
- Offline Qwen3.8-Flash-Next Q4_K_M API inference using existing read-only NVMe
  weights and pack, `--spec 3`, context 4096: arithmetic returned `42`, code
  retrieval returned `AMBER-906`; real-server healthcheck passed.
- 29 upstream hipBLASLt tuning unit tests; 49 AMD setup tests excluding the two
  TheRock-index checks below; a separate mocked gfx906 KFD detection check.

The GPU-test image adds only a test-binary layer to the exact final-image
layers; no engine or runtime files are replaced.

## Limits

- The full AMD setup suite has two failing inherited `test_rocm_index_per_family`
  checks: they require a TheRock wheel index for every supported architecture.
  gfx906 uses this image's system ROCm, not TheRock wheels; no fictitious index
  was added to satisfy them.
- The first inference invocation used `--spec 0`; the cached native pack
  requires `--spec >= 2`. The corrected invocation passed.
- GPU vision inference, multi-GPU inference, other quantizations and long
  contexts were not tested. One fused RoPE subcheck skips on this build.
- CI checks out the workflow's pinned repository release. Publishing these
  fixes requires a new repository release or selecting the fixed ref through
  the existing `BUILD_REF` repository variable.
