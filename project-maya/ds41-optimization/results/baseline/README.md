# DeepSeek-V4.1-Flash CPU74 reference

The active baseline is [CPU48](../cpu-threads/README.md). This directory
retains the CPU74 reference run and its original configuration and artifacts.

**Completed:** 2026-11-01 10:26:21–10:43:24 UTC, including startup, warmups,
measurement requests and shutdown. Runner exit code: 0. All 22 requests
generated 256 tokens, finished with `length`, offered speculative drafts and
reported `reused=0`. The log contains no conversation-slot operations.

## Results

Each length pools two measurement requests. Twelve warmups are excluded.

| PP tokens | Requests | Generated tokens | Prefill tok/s | Decode tok/s | Accepted / offered drafts |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 2 | 512 | 135.75 | 29.28 | 223 / 280 |
| 4096 | 2 | 512 | 209.20 | 30.70 | 254 / 331 |
| 8192 | 2 | 512 | 300.69 | 31.30 | 268 / 331 |
| 16384 | 2 | 512 | 371.60 | 29.20 | 231 / 266 |
| 32768 | 2 | 512 | 391.19 | 29.99 | 277 / 334 |
| **Pooled measurements** | **10** | **2560** | **334.56** | **30.07** | **1253 / 1542 (81.26%)** |

Measured prompts total 126976 tokens and 379527.6 ms of native prompt time;
generation totals 85129.0 ms. Two different prompts per length and one run
do not establish confidence intervals or a performance optimum.

## Configuration and method

- Suite: `project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl`.
  Twelve PP2048 warmups, then PP2048/4096/8192/16384/32768 twice; TG256.
  Only the ten measurement requests are scored.
- Greedy decoding, thinking off, speculative decoding requested with `spec=1`.
  One resident engine, serial independent requests, no cross-request KV reuse.
- Explicit `--cpu-threads 74`, TP4, context 524288, prefill chunk 4096,
  DSpark and vision on, `--mmap-experts off`, two NUMA RAM parts.
- `MAYA_DS4_SLOT_KEEP=0`: conversation-slot saving, restoring and spilling are
  disabled. `MAYA_DS4_SLOT_CAP=4` is inactive. Native prompt timings still
  include engine preparation and checkpoints, not just GPU-kernel computation.
- Config: [captured CPU74 configuration](maya-config.json). The
  [active baseline configuration](../../base-params/maya-config.json) uses CPU48.
- Image: `docker.io/mixa3607/maya-gfx906@sha256:50210b2fdec9c2e36b57fe0c8de2d3a9dd2d1fb33bb99757b37f229e824d51d2`.
  Maya v1.1.45, upstream source `6ecbd3cbc5330b57f70cd5cf8a5c42eb8ef950cc`,
  ROCm 10.1 with local gfx906 patches.
- Four MI50 32 GB gfx906 GPUs on `kube-worker6.arkprojects.lan`, 76 physical
  CPU cores, two NUMA nodes, SMT off. Pod RAM limit: 220 GiB, no CPU quota.
- Startup confirms actual TP4 with equal 576-value FFN member partitions and
  74 CPU threads. All 10647 CPU-lane experts were copied into RAM (200.2 GB,
  two NUMA parts); 200.9 GB of expert copies were pinned.
- Fresh image-provided expert-profile seed and isolated pack index. Model and
  drafter blobs and prepared vision files are referenced from read-only PVCs;
  no model-weight files are copied or downloaded. Adaptive profile/cache
  updates within the engine are retained across warmups and measurements.

Speeds use total tokens divided by total native engine milliseconds, with
warmups excluded. They are not client TTFT or full-512K-context measurements,
and do not establish model quality or individually optimized flag values.
Draft counters combine DSpark and prompt lookup, not DSpark alone.

## Diagnostics and artifacts

The log records two rocBLASLt errors loading `TensileLibrary_lazy_gfx906.dat`
and 12 `hipModuleLoad failed` messages for gfx906/xnack `Kernels.so-000` modules.
The engine continued and completed every request. No ROCm libraries or engine
paths were replaced; preferred hipBLASLt-path availability is not established.

- `results.jsonl`, `summary.json`, `aggregation.txt`: raw `DONE` records and
  per-length/pooled results. The summary reproduces byte-for-byte.
- `engine.log`, `run-metadata.json`: native diagnostics, effective command and
  environment, engine/source/input hashes, timings, CPU topology and limits.
- `maya-config.json`, `pack-metadata.json`, `patch-verification.json`: exact
  configuration, model/drafter revisions and blob identities, generated pack
  hashes, and both local gfx906 patches verified in image source.
- `expert-profile.seed.bin`, `expert-profile.final.bin`: seed and resulting
  adaptive profile. Frozen cases SHA-256:
  `3195a02e90078b366c00dce429652b386fe3616d879cdd25c1a6f288435b46c3`.
- `pod.json`, `gpu-static.json`, `gpu-before.txt`, `gpu-after-cleanup.txt`:
  deployment and hardware evidence. The pod was deleted; all four GPUs were
  then at 0% utilization with 10 MB VRAM used each.
- `source-state.json`, `artifact-sha256.json`, `scripts/`: execution helpers
  and verified hashes. Source PVCs and other workloads were not modified.

## Recomputing the summary

From the repository root, CPU only:

```bash
python3 project-maya/ds41-optimization/results/baseline/summarize.py \
  project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl \
  project-maya/ds41-optimization/results/baseline
```

The summarizer validates the schedule, exit code, explicit CPU74, disabled
slots, absent slot diagnostics, no KV reuse and measured speculative offers.
`scripts/run.py` instead creates/deletes a pod and runs real GPU workloads;
it requires explicit hardware/cluster approval and refuses to overwrite a run.

## CPU validation

The 11 benchmarking unit tests passed. Synthetic CPU-only checks verified
warmup exclusion and pooled token/time aggregation, and confirmed rejection
of slot diagnostics, KV reuse and a CPU-thread setting other than 74.
