# Skip/fusion comparison with 74 CPU threads

**Completed:** all four arms, 88 requests total (48 warmups and 40 scored
requests), exit code 0 in every arm. Every request reached TG256 with
`finish=length`, nonzero draft offers and `reused=0`. Keep both additional
optimizations off for the full-suite baseline; retain explicit CPU74.

## Results and decision

Speeds pool tokens/time across the 10 measured requests, excluding warmups.
Deltas below compare against this experiment's explicit-CPU74 control, not the
earlier auto-thread baseline. All fusion arms used skip=0 after the skip arm
failed the predeclared screening rule.

| Arm | Skip | HC fuse | PP tok/s | PP delta | TG tok/s | TG delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Control | 0 | 0 | 365.11 | — | 30.68 | — |
| Skip | 1 | 0 | 384.71 | +5.37% | 30.00 | -2.22% |
| HC fuse 1 | 0 | 1 | 365.48 | +0.10% | 30.48 | -0.62% |
| HC fuse 2 | 0 | 2 | 353.70 | -3.12% | 30.49 | -0.61% |

### Skip: promising for shorter prefill, not accepted for the full suite

| PP | Control → skip PP tok/s | PP delta | Control → skip TG tok/s | TG delta |
| ---: | ---: | ---: | ---: | ---: |
| 2048 | 170.05 → 213.51 | +25.56% | 30.40 → 28.31 | -6.86% |
| 4096 | 241.56 → 292.63 | +21.14% | 32.72 → 31.17 | -4.75% |
| 8192 | 332.62 → 350.68 | +5.43% | 32.47 → 31.78 | -2.12% |
| 16384 | 378.01 → 376.04 | -0.52% | 29.89 → 30.32 | +1.43% |
| 32768 | 426.01 → 439.79 | +3.23% | 28.34 → 28.70 | +1.28% |

Pooled prefill improved by 11.31% in the first measurement pass and changed by
-0.03% in the second. Together with the PP2048 decode regression greater than
5%, this rejects skip=1 under the rule fixed before data collection. It does
not prove a reproducible decode slowdown caused by this prefill-only switch.
The short-prefill gain merits a focused repeat if that workload becomes the
priority, but no repeat or extra GPU test was performed here.

### Fusion: startup parity passed, no useful throughput gain observed

HC fuse 1 passed the native startup checks on all four GPUs (24 cases per GPU).
HC fuse 2 passed them for both one-row and 16-row inputs (24 cases for each
shape per GPU). Logs explicitly report bit-for-bit equality to the unfused
kernels, finite values and intact guards. This verifies the covered startup
cases, not equality of all generated tokens or whole-model logits.

Neither mode showed a decode gain in this suite. Retain HC fuse=0; small deltas
are observations from one run per configuration, not demonstrated regressions
or confidence intervals. HC fuse 2's second-pass PP4096 time was 22817.3 ms
versus control 17509.9 ms; it is retained as measured, not removed as an outlier.
Skip's second-pass PP16384 also increased (48327.8 versus 42805.8 ms).
Sequential, non-randomized arms and only two different prompts per length
limit causal conclusions. No universal optimum or gain from explicit CPU74
versus automatic selection is claimed.

## Method fixed before collection

Approved scope: four serial full `ds41f-ru-long` runs, each in a new pod and
engine with the same image-provided expert-profile seed and isolated pack.
Both model-cache and prepared-vision PVCs stay read-only. No image builds,
weight downloads, model copies or changes to other workloads are needed.

All arms explicitly use `--cpu-threads 74`, TP4, speculation on, context
524288, prefill chunk 4096 and the remaining baseline settings. Each arm runs
the frozen 12 warmups and 10 measurement requests; only measurements are scored.

| Arm | `DS4_SKIP_UNPICKED` | `MAYA_DS4_HC_FUSE` |
| --- | ---: | ---: |
| `control` | 0 | 0 |
| `skip1` | 1 | 0 |
| `hcfuse1` | provisionally selected skip value | 1 |
| `hcfuse2` | same selected skip value | 2 |

The selection rule is fixed before collecting data: carry skip=1 into fusion
only if pooled prefill improves by at least 5%, pooled decode and every
per-length prefill/decode speed remain at least 95% of control, and pooled
prefill improves in each of the two measurement passes. Otherwise retain 0.
This is a conservative screening rule, not a significance test or proof of an
optimum. The two passes contain different prompts, not identical repetitions.
Borderline results need a separately reported repeat before accepting a gain.

Fusion arms are compared against the chosen skip arm with fusion off. Native
startup parity checks remain enabled; a failed check is a failed arm, never
worked around. Fusion 2 is still attempted if fusion 1 fails. A failed control
or skip run stops selection. Actual TP4, 74 threads, draft offers, zero KV reuse,
matching inputs/seed/binary and the pinned image are checked before scoring.

`scripts/experiment.py` runs this approved four-arm experiment from the
repository root. It creates/deletes pods in `apps-ml` and runs real GPU workloads;
do not rerun it without hardware/cluster approval. The per-arm config snapshots,
raw results, native logs, metadata and summaries are saved alongside this file.
`decision.json` records the provisional skip selection. The old auto-thread
baseline remains historical evidence, not the control for this experiment.

## Provenance, diagnostics and cleanup

- Collection: 2026-10-31 23:44:47 to 2026-11-01 00:49:33 UTC, including
  per-arm startup, warmup, measurements and engine shutdown.
- Image: `docker.io/mixa3607/maya-gfx906@sha256:50210b2fdec9c2e36b57fe0c8de2d3a9dd2d1fb33bb99757b37f229e824d51d2`;
  Maya v1.1.45, source `6ecbd3cbc5330b57f70cd5cf8a5c42eb8ef950cc`, ROCm 10.1.
  The engine hash, both local gfx906 source patches, pack metadata and seed
  profile bytes match across all arms and the earlier successful baseline.
- Hardware: four MI50 32 GB gfx906 GPUs on `kube-worker6.arkprojects.lan`,
  76 physical CPU cores / two NUMA nodes, SMT off, no CPU quota, 220 GiB pod
  RAM limit. Every arm confirms actual TP4 with equal 576-value FFN parts,
  74 CPU threads, all 10647 CPU-lane experts copied into RAM in two NUMA parts
  and pinned expert copies. Hardware details are in `gpu-static.json` and
  per-arm metadata.
- Frozen cases SHA-256:
  `3195a02e90078b366c00dce429652b386fe3616d879cdd25c1a6f288435b46c3`.
  Every scored arm has 126976 prompt tokens and 2560 generated tokens.
- All arms retained the same rocBLASLt/Tensile diagnostics: inability to load
  `TensileLibrary_lazy_gfx906.dat` and gfx906/xnack `Kernels.so-000` modules.
  Each log has two `rocblaslt error` and 12 `hipModuleLoad failed` messages.
  All requests nevertheless completed. No libraries or paths were replaced;
  preferred hipBLASLt-path availability is not established by these results.
- Draft acceptance uses native combined DSpark and prompt-lookup counters,
  not DSpark-only acceptance. Adaptive profile/cache behavior is retained
  within each arm; it is not frozen between requests. Output IDs/logits were
  not captured, so these runs do not establish whole-model bit parity.
- Each pod was deleted after exporting its results, including before the next
  arm. All four cleanup samples confirm 0% utilization and 10 MB VRAM used on
  every GPU. The final pod is absent; other workloads and source PVCs were not
  changed. No model-weight files were copied or downloaded.

## Artifacts and CPU-only recomputation

Each arm folder contains `requested-config.json`, the effective
`maya-config.json` snapshot, `results.jsonl`, `summary.json`, `engine.log`,
`run-metadata.json`, pack/patch/pod metadata, seed/final expert profiles,
before/after GPU samples and `artifact-sha256.json`. All recorded hashes were
verified after collection. `source-state.json` records the scripts present
before collection; `scripts/compare.py` was added afterwards for reporting.

From the repository root, recompute one arm's summary with the existing
CPU-only summarizer (replace `control` with the desired arm):

```bash
python3 project-maya/ds41-optimization/results/baseline-spec1-tp4/summarize.py \
  project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl \
  project-maya/ds41-optimization/results/skip-hcfuse-cpu74/control
python3 project-maya/ds41-optimization/results/skip-hcfuse-cpu74/scripts/compare.py
```

The second command recreates `comparison.json` with per-length and pooled
rates/deltas and both measurement-pass rates. `decision.json` reproduces the
predeclared skip screening; `outcomes.json` records both fusion runs passing.
These CPU-only commands do not recreate pods or run the GPU experiment.

## CPU validation before GPU runs

- Benchmark runner/freezer unit tests: 11/11 passed.
- Predeclared skip-screening tests: 6/6 passed, including small gains, decode
  regressions, per-length regressions and inconsistent measurement passes.
- Upstream `ds4_ram_slice_test.cpp` at
  `6ecbd3cbc5330b57f70cd5cf8a5c42eb8ef950cc`: built with
  `g++ -std=c++20 -O2 -DNDEBUG -Wall -Wextra -fsanitize=address,undefined` and
  passed TP1/2/4, NUMA1/2, byte-copy, bounds and guard checks. This does not
  replace GPU/model parity tests.
- Script syntax and the baseline diff were checked: the baseline's only change
  from the previous successful run is explicit `--cpu-threads 74`.
