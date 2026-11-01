# CPU48 combinations: two pairs and all four flags

**Completed:** 2026-11-01 13:42:00–14:28:10 UTC, about 46 minutes from the
first suite start through the last suite shutdown, including inter-arm gaps.
All three runners exited with code 0. All 66 requests completed TG256 with
`finish=length`, nonzero speculative offers, `reused=0` and no slot operations.
All three pods were deleted; each cleanup sample shows all four GPUs at 0%
utilization and 10 MB VRAM used per GPU.

## Results

Each arm pools ten measurement requests (126976 prompt tokens and 2560
generated tokens), excluding twelve warmups. The control below is from the
preceding block, not a new control measurement.

| Arm | Prefill tok/s | vs saved control | Decode tok/s | vs saved control | Accepted / offered drafts |
| --- | ---: | ---: | ---: | ---: | ---: |
| Saved control | 344.69 | — | 35.06 | — | 1284 / 1618 (79.36%) |
| skip-swizzle | 401.29 | +16.42% | 35.57 | +1.46% | 1340 / 1682 (79.67%) |
| hc-route | 357.52 | +3.72% | 36.49 | +4.09% | 1284 / 1600 (80.25%) |
| all | 410.83 | +19.19% | 35.88 | +2.34% | 1299 / 1636 (79.40%) |

[comparison.md](comparison.md) includes individual-flag and pair comparisons
and per-length PP/TG; [comparison.json](comparison.json) also retains
per-request deltas, all eight runs' timestamps and diagnostic counts.
Observations, without a performance acceptance decision:

- `skip-swizzle` versus skip alone: PP +1.13%, TG +2.27%. Versus swizzle
  alone: PP +12.15%, TG +0.64%.
- `hc-route` versus HC alone: PP +1.91%, TG -1.52%. Versus route alone:
  PP +1.19%, TG +3.31%.
- All four versus `skip-swizzle`: PP +2.38%, TG +0.87%. Versus `hc-route`:
  PP +14.91%, TG -1.68%.
- All four have the highest pooled PP among the eight recorded configurations,
  but not the highest TG: 35.88 tok/s versus 37.05 with HC alone (-3.17%).
- All-four per-length PP gains versus saved control range from +5.81% at
  PP32768 to +81.14% at PP2048. TG at PP16384 is -2.91%, despite positive
  pooled TG over the complete measurement set.

These are single serial runs with two prompts per length. The saved control
ran at 11:54:36–12:11:42 UTC, and the individual-flag runs at
12:12:18–13:18:35 UTC. There is no contemporaneous control for these
combinations; small differences may include inter-block drift and different
adaptive/draft histories. No confidence interval, statistical-significance
claim, additive/multiplicative speedup assumption or baseline/best-tested
change is made.

## Approved scope

Three serial full-suite runs, independently over the unchanged CPU48 baseline:

| Order | Arm | Overrides |
| ---: | --- | --- |
| 1 | `skip-swizzle` | `DS4_SKIP_UNPICKED=1`, `DS4_HIP_ATTN_SWIZZLE=1` |
| 2 | `hc-route` | `MAYA_DS4_HC_FUSE=2`, `MAYA_DS4_ROUTE_FUSE=2` |
| 3 | `all` | All four overrides above |

No fresh control is run in this block. Comparisons use the saved
[control and single-flag results](../flags-cpu48/README.md) and explicitly
identify their earlier timestamps. Conditions may drift between blocks;
do not infer significance or pure interaction effects from small differences.
No automatic baseline or individual best-tested changes, performance thresholds,
additional configurations or GPU runs are part of this task.

## Method and provenance

Keep the [captured CPU48 baseline](../flags-cpu48/baseline-config.json), fixed
cases and [preceding methodology](../flags-cpu48/README.md): TP4, CPU48,
`spec=1`, temperature 0, context 524288, prefill chunk 4096, DSpark/vision on,
`SLOT_KEEP=0`, no cross-request KV reuse and two NUMA RAM parts. Each arm
gets a separate pod, fresh pack index, original expert-profile seed and one
resident engine for 12 PP2048 warmups plus 10 measurements (PP2048 through
PP32768 twice, TG256). Adaptive state is not shared between arms.

Use the same pinned Maya v1.1.45 image, ROCm 10.1, gfx906 patches, model,
drafter, prepared vision and four MI50 GPUs on `kube-worker6.arkprojects.lan`.
Source PVCs remain read-only; no model downloads or weight copies. The existing
preparation and remote runner are reused unchanged. Validate all nonexperimental
arguments/environment, seed/pack/image/engine identities, CPU/GPU topology,
full expert copies and pinning. Both native fusion check suites are required
on all four devices when enabled together, including their multirow checks.
These checks are not output-token parity or model-quality tests.

Record raw results, exact configuration and pod, native logs, effective args/env,
timings, seed/final profiles, hardware/idle samples and input/script/artifact
hashes. Export results before deleting each pod and checking GPUs are idle.
Runtime/setup errors stop the queue; performance alone does not.

Report separate PP/TG pooled token/time rates without warmups, per-length and
per-request deltas versus the saved control and constituent single-flag arms,
and all-four versus each pair. Draft acceptance combines DSpark and prompt
lookup. Do not add or multiply individual speedups as a measured combined
prediction; measure each combination. Native timings are not client TTFT or
GPU-kernel-only timings.

## Diagnostics, artifacts and validation

- `skip-swizzle`: 13:42:00.997554–13:56:24.993231 UTC.
- `hc-route`: 13:57:01.981816–14:14:03.483062 UTC.
- `all`: 14:14:40.137462–14:28:10.186773 UTC.
- All arms matched the saved control's engine/image, nonexperimental arguments
  and environment, model/drafter/vision and generated pack metadata, original
  profile seed, local gfx906 patch evidence and static GPU metadata. Startup
  confirms actual TP4, CPU48, all 10647 CPU-lane experts copied into RAM
  (200.2 GB, two NUMA parts), and 200.9 GB of pinned expert copies.
- Both `hc-route` and `all` passed eight HC startup checks (single-/16-row)
  and twelve route startup checks (single-/3-/16-row), covering all four GPUs
  while both flags were enabled. Logs report bit-for-bit agreement within
  their coverage; these are not whole-answer parity tests.
- Each log retains two `rocblaslt error` diagnostics for
  `TensileLibrary_lazy_gfx906.dat` and twelve `hipModuleLoad failed` messages
  for gfx906/xnack `Kernels.so-000` modules. All requests completed; preferred
  hipBLASLt-path availability remains unestablished.
- Host-side extraction for `all` reported a `tar` future-mtime warning for
  `config.json` (about 22.4 seconds). The captured config hash matched. No
  cross-host clock synchronization is asserted: reported suite UTC timestamps
  come from pod metadata, and throughput uses native engine durations rather
  than host/pod timestamp differences.
- Each arm retains raw `results.jsonl`, `summary.json`, `engine.log`,
  `run-metadata.json`, exact config and pod manifest/snapshot, pack/patch
  metadata, seed/final profiles, hardware/idle samples, `source-state.json`
  and `artifact-sha256.json`. Input, script and artifact hashes verify;
  summaries and the comparison reproduce byte-for-byte. The active baseline,
  individual best-tested values, prior raw artifacts, model blobs and other
  workloads were not modified.

## Execution and CPU analysis

These commands create/delete test pods and use real GPUs; explicit approval
is required. From the repository root:

```bash
python3 project-maya/ds41-optimization/results/combos-cpu48/scripts/run.py skip-swizzle
python3 project-maya/ds41-optimization/results/combos-cpu48/scripts/run.py hc-route
python3 project-maya/ds41-optimization/results/combos-cpu48/scripts/run.py all
```

The launchers refuse to overwrite a result directory. CPU-only recomputation:

```bash
python3 project-maya/ds41-optimization/results/combos-cpu48/compare.py
```

CPU-only tests:

```bash
cd project-maya/ds41-optimization/results/combos-cpu48
python3 -m unittest -v
```

CPU validation: 11 benchmarking tests and 9 combination-specific tests passed.
The latter cover disjoint pairs and their four-flag union, exact overrides and
fusion aliases, all three configurations, both native fusion suites, missing
checks/flags, unrelated environment changes, KV reuse, warmup exclusion and
report generation on synthetic artifacts using the recorded earlier control.
