# CPU48 baseline: five-arm flag block

**Completed:** 2026-11-01 11:54:36–13:18:35 UTC, about 84 minutes from the
first suite start through the last suite shutdown, including inter-arm gaps.
All five runners exited with code 0. All 110 requests completed TG256 with
`finish=length`, nonzero speculative offers, `reused=0` and no slot operations.
The five test pods were deleted; every post-cleanup sample shows all four
GPUs at 0% utilization and 10 MB VRAM used each.

## Results

Each arm pools ten measurement requests; twelve warmups per arm are excluded.
Each measurement set contains 126976 prompt tokens and 2560 generated tokens.

| Arm | Prefill tok/s | vs control | Decode tok/s | vs control | Accepted / offered drafts |
| --- | ---: | ---: | ---: | ---: | ---: |
| control | 344.69 | — | 35.06 | — | 1284 / 1618 (79.36%) |
| skip | 396.81 | +15.12% | 34.78 | -0.79% | 1278 / 1638 (78.02%) |
| swizzle | 357.81 | +3.80% | 35.34 | +0.81% | 1279 / 1554 (82.30%) |
| hcfuse | 350.81 | +1.77% | 37.05 | +5.69% | 1314 / 1599 (82.18%) |
| routefuse | 353.32 | +2.50% | 35.32 | +0.75% | 1251 / 1605 (77.94%) |

The fresh control differs from the selected CPU48 measurement by -0.85% PP
and -1.72% TG. All flag deltas use this block's fresh control, not CPU74 or
the earlier CPU48 measurement. No performance threshold or automatic
pass/fail decision was applied during the runs. The active baseline remains
unchanged; the subsequent user selection is recorded below.

[comparison.md](comparison.md) contains per-length results;
[comparison.json](comparison.json) also retains per-request deltas and
diagnostic counts. Per-length observations retained alongside the selection:

- `skip`: per-length PP gains range from +77.21% at PP2048 to +3.51% at
  PP32768; all ten individual PP measurements improved. TG varies by length:
  PP16384 -5.87%, PP32768 -2.87%, with gains at the shorter three lengths.
- `swizzle`: each length's pooled PP improved; pooled TG ranges from -2.26%
  at PP32768 to +3.84% at PP4096.
- `hcfuse`: each length's pooled TG improved (+1.27% to +7.71%); PP32768
  is -1.18% while pooled PP over the suite is +1.77%.
- `routefuse`: pooled PP32768 is -0.59%; TG by length ranges from -1.31%
  to +4.61%.

These are sequential single-run measurements with two prompts per length,
not confidence intervals, significance tests or isolated kernel timings.
Draft counters and adaptive histories differ; no output-token parity or
quality conclusion follows from timing or native fusion checks.

## Accepted individual best-tested values

By task agreement, record the following in the inventory's best-tested column:

- `DS4_SKIP_UNPICKED=1`
- `DS4_HIP_ATTN_SWIZZLE=1`
- `MAYA_DS4_HC_FUSE=2`
- `MAYA_DS4_ROUTE_FUSE=2`

These are accepted results of separate single-flag tests, not an automatically
updated baseline or a tested combined configuration. The skip selection accepts
the observed PP/TG tradeoff, including pooled TG -0.79% and PP16384 TG -5.87%.
Small gains in other arms do not establish statistical significance. No new
run or combined-speedup claim accompanies this documentation decision.

## Approved scope

Run serially, each variant independently on the captured
[CPU48 baseline configuration](baseline-config.json):

| Order | Arm | Only change relative to baseline |
| ---: | --- | --- |
| 1 | `control` | None: fresh baseline control |
| 2 | `skip` | `DS4_SKIP_UNPICKED=1` |
| 3 | `swizzle` | `DS4_HIP_ATTN_SWIZZLE=1` |
| 4 | `hcfuse` | `MAYA_DS4_HC_FUSE=2` |
| 5 | `routefuse` | `MAYA_DS4_ROUTE_FUSE=2`; keep inherited `DS4_AHEAD=1` |

The run scope specified no performance success/failure thresholds or automatic
baseline changes. Report PP/TG results and deltas versus the fresh control;
selection is a separate user decision. Runtime/setup validation is separate
from judging performance. No cumulative combinations, extra CPU values or
additional flags.

## Method and provenance

- Frozen `ds41f-ru-long` cases, twelve PP2048 warmups followed by
  PP2048/4096/8192/16384/32768 twice, TG256. One resident engine per arm,
  serial requests, temperature 0, `spec=1`, no cross-request KV reuse.
- CPU48, TP4, context 524288, prefill chunk 4096, DSpark/vision on,
  `MAYA_DS4_SLOT_KEEP=0`, two NUMA RAM parts and the same UD-Q8_K_XL pack.
- Each arm gets its own pod, working directory, newly generated pack index
  and original image-provided expert-profile seed. Adaptive state remains
  within an arm, never shared with another arm.
- Same pinned image and hardware as the [selected CPU48 run](../cpu-threads/README.md):
  Maya v1.1.45, source `6ecbd3cbc5330b57f70cd5cf8a5c42eb8ef950cc`, ROCm 10.1,
  four MI50 32 GB gfx906 GPUs, 76 physical CPU cores, SMT off, two NUMA nodes,
  220 GiB pod RAM and no CPU quota on `kube-worker6.arkprojects.lan`.
- Image: `docker.io/mixa3607/maya-gfx906@sha256:50210b2fdec9c2e36b57fe0c8de2d3a9dd2d1fb33bb99757b37f229e824d51d2`.
- Source PVCs are read-only. Use cached model/drafter blobs and prepared vision
  by reference; no model-weight downloads or copies. The recorded preparation
  and remote runner from the preceding runs are reused without modification.
- Validate exact nonexperimental arguments/environment, image and engine
  identities, seed and pack metadata, CPU/GPU topology, full-RAM expert copies
  and pinning. Preserve native fusion startup parity checks and their logs.
  Effective environment confirms requested settings; no kernel profiler or
  output-token parity check is added. Swizzle's bit-exact classification is
  based on the user's prior tests, not a new parity claim.
- Pool token counts over native engine times; exclude warmups. Report
  per-length, pooled and per-request PP/TG deltas, plus draft acceptance
  (combined DSpark and prompt lookup). Timings include native state preparation
  and checkpoints, not pure GPU kernels or client TTFT.
- Export raw results, logs, exact config/pod, metadata, seed/final profile and
  input/script/artifact hashes. Delete each test pod and verify idle GPUs.
  A runtime/setup error stops the queue for investigation; slow performance
  alone does not stop it. The expected block duration is approximate.

## Diagnostics, artifacts and validation

Each arm matched the selected CPU48 engine/image identities, nonexperimental
arguments/environment, model/drafter/vision and generated pack metadata,
original expert-profile seed, local gfx906 patch evidence and GPU static
metadata. Startup confirms actual TP4, 48 CPU threads, all 10647 CPU-lane
experts copied into RAM (200.2 GB, two NUMA parts), and 200.9 GB of pinned
expert copies.

The HC arm passed eight native startup parity checks: single-row and 16-row
checks on each of the four GPUs. The route arm passed twelve checks:
single-row, 3-row and 16-row checks on each GPU. Logs report bit-for-bit
agreement for the computations those checks cover; these are not whole-answer
parity tests.

All five logs retain two `rocblaslt error` diagnostics for
`TensileLibrary_lazy_gfx906.dat` and twelve `hipModuleLoad failed` messages for
gfx906/xnack `Kernels.so-000` modules. All requests completed; availability of
the preferred hipBLASLt path is not established.

Each arm directory retains raw `results.jsonl`, `summary.json`, `engine.log`,
`run-metadata.json`, exact `maya-config.json`, pod manifest/snapshot,
pack/patch metadata, seed/final expert profiles, hardware/idle snapshots,
`source-state.json` and `artifact-sha256.json`. Input, script and artifact
hashes verify, and summaries/comparison reproduce byte-for-byte. Frozen cases
SHA-256: `3195a02e90078b366c00dce429652b386fe3616d879cdd25c1a6f288435b46c3`.
Active baseline, preceding results, model blobs and other workloads were not
modified.

## Execution and CPU-only analysis

The launch command creates a pod and runs real GPUs; it requires explicit
approval for the workload and pod creation/deletion, and refuses to overwrite
an arm directory. From the repository root, run the approved order:

```bash
python3 project-maya/ds41-optimization/results/flags-cpu48/scripts/run.py control
python3 project-maya/ds41-optimization/results/flags-cpu48/scripts/run.py skip
python3 project-maya/ds41-optimization/results/flags-cpu48/scripts/run.py swizzle
python3 project-maya/ds41-optimization/results/flags-cpu48/scripts/run.py hcfuse
python3 project-maya/ds41-optimization/results/flags-cpu48/scripts/run.py routefuse
```

After the block, `python3 project-maya/ds41-optimization/results/flags-cpu48/compare.py`
revalidates and aggregates on CPU only. The comparison and tests do not access
Kubernetes or start an engine.

CPU validation: 11 benchmarking tests and 12 block-specific tests passed.
The latter cover isolated overrides and aliases, CPU/config/environment
consistency, native fusion-check coverage, slots/KV reuse, seed drift,
aggregation/deltas and complete report generation on synthetic artifacts.

```bash
cd project-maya/ds41-optimization/results/flags-cpu48
python3 -m unittest -v
```
