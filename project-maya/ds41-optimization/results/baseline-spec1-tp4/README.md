# TP4 baseline with speculative decoding

**Completed:** all 22 requests of `ds41f-ru-long`, exit code 0, with
`temperature=0 spec=1`. Twelve warmups are excluded from the measurements below.
All requests generated 256 tokens, finished with `length`, and reported zero
prefix/KV reuse. These are warm, serial-request throughput results, not quality,
concurrency, client TTFT, cold-start or full-512K-context measurements.

## Results

Each row pools the two measurement requests at that input length. Speeds are
total tokens divided by total native engine milliseconds, not means of speeds.

| PP tokens | Requests | Generated tokens | Prefill tok/s | Decode tok/s | Accepted / offered drafts |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 2 | 512 | 168.83 | 30.12 | 216 / 271 |
| 4096 | 2 | 512 | 249.39 | 32.16 | 257 / 324 |
| 8192 | 2 | 512 | 335.18 | 33.99 | 285 / 375 |
| 16384 | 2 | 512 | 397.64 | 31.14 | 265 / 347 |
| 32768 | 2 | 512 | 421.15 | 29.22 | 248 / 324 |
| **All measurements** | **10** | **2560** | **369.11** | **31.24** | **1271 / 1641 (77.45%)** |

The measured prompts total 126976 tokens, taking 344005.9 ms of native prompt
time; generation took 81947.3 ms. `DONE` draft counters include prompt-lookup
drafts as well as DSpark drafts, so the acceptance above is not a DSpark-only
statistic. Prompt lookup stayed at its inherited default; it was not tuned.
Two observations per length do not establish confidence intervals or a speedup
over any other configuration.

## Configuration and provenance

- Run: 2026-10-31 23:17:06 to 23:33:51 UTC, including model startup, warmups,
  measured requests and shutdown.
- Image: `docker.io/mixa3607/maya-gfx906:v1.1.45-rocm-10.1`, pinned to
  `sha256:50210b2fdec9c2e36b57fe0c8de2d3a9dd2d1fb33bb99757b37f229e824d51d2`.
- Upstream source: `6ecbd3cbc5330b57f70cd5cf8a5c42eb8ef950cc` (v1.1.45).
  [patch-verification.json](patch-verification.json) verifies the image source
  contains both local gfx906 patches; fusion switches were not enabled.
- Suite: `project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl`, unchanged.
  SHA-256: `3195a02e90078b366c00dce429652b386fe3616d879cdd25c1a6f288435b46c3`.
- Config: [maya-config.json](maya-config.json), matching the updated
  [baseline](../../base-params/maya-config.json). TP4, context 524288,
  prefill chunk 4096, DSpark on, vision on, expert copying off mmap,
  two NUMA parts, Engram cache 256 MB, drafter members `1,2,3`,
  `PROMPT_SKIP=2`, `SLOT_KEEP=1`, `SLOT_CAP=4`.
- `MAYA_DS4_TP_GGUF_UNEVEN=1` is the only config change from the
  [failed first attempt](../baseline-spec1/README.md). Actual TP4 and equal
  576-value member FFN partitions are confirmed by the startup log; no TP2
  fallback occurred.
- Hardware: four 32 GB gfx906 GPUs on `kube-worker6.arkprojects.lan`, two
  38-core CPU sockets / NUMA nodes, 76 physical cores, SMT off, approximately
  251.5 GiB host RAM, no swap. All GPU PCI devices report CPU NUMA node 0.
- CPU threads: automatic, **74 selected**. This is an observation of this
  baseline, not an optimum; 48/56-core alternatives have not been measured.
- Pod limit: 220 GiB RAM, no CPU quota, affinity CPUs 0-75, unlimited memlock.
  The log confirms all 10647 CPU-lane experts copied into RAM (200.2 GB, two
  NUMA parts) and 200.9 GB of expert copies pinned. No strict-all-RAM flag was
  added to obtain this result.
- Model: cached UD-Q8_K_XL at revision
  `60ad3651641b5c97679c807e064ab1d7a3ca1455`. Pack inventory includes native
  MXFP4 experts, MXFP8 Engram and BF16/F32/Q8_0 components; the quant's name
  does not mean all weights are Q8. Drafter revision:
  `d1fc01009f21e26157acb6858c315d0365483b72`.
- A fresh isolated pack index and image-provided expert-profile seed were used.
  Warmups and measurements shared one loaded engine and adaptive caches/profile.
  Model/drafter blobs and existing vision artifacts were referenced read-only;
  no model weights or blobs were copied or downloaded.
- `SLOT_KEEP=1` also saved/spilled conversation states during this run, but
  `reused=0` for every request. Throughput does not measure the potential
  acceleration from resuming those slots.

## Observed library diagnostics

The first warmup's stderr includes:

```text
rocblaslt error: Cannot read "TensileLibrary_lazy_gfx906.dat" (or .zlib variant): No such file or directory
rocblaslt error: Could not load "TensileLibrary_lazy_gfx906.dat"
hipModuleLoad failed: Kernels.so-000-gfx906.hsaco
```

Similar load messages name the xnack variants. The engine continued and all
requests completed. No ROCm libraries, model precision or engine paths were
replaced to suppress these messages. Their presence is part of this baseline;
the result does not establish that hipBLASLt's preferred path was available.

## Recomputing the summary

From the repository root:

```bash
python3 project-maya/ds41-optimization/results/baseline-spec1-tp4/summarize.py \
  project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl \
  project-maya/ds41-optimization/results/baseline-spec1-tp4
```

The script rejects incomplete runs, mismatched schedules, KV reuse or absent
measured speculative offers. Its aggregation and reuse rejection were also
checked against synthetic CPU-only data. The benchmarking unit tests passed
11/11; frozen cases were not regenerated.

## Artifacts and cleanup

- `results.jsonl`: all 22 raw per-request `DONE` records, including warmups.
- `summary.json`: validated per-length and pooled measurement results.
- `engine.log`: complete native startup, request and shutdown diagnostics.
- `run-metadata.json`: command, effective environment, source/engine/input
  hashes, host topology, cgroup/limits, timing and exit code.
- `pack-metadata.json`: revisions, blob identities, index hashes and vision
  manifest; `expert-profile.seed.bin` / `expert-profile.final.bin` preserve the
  initial seed and the run's resulting counts.
- `pod.json`, `gpu-static.json`, `patch-verification.json`: deployment,
  hardware and local-patch provenance.
- `gpu-after-cleanup.txt`: after pod deletion, all four GPUs at 0% utilization
  and approximately 10 MB VRAM used each. Other workloads/PVCs were not changed.

No individually optimized flag values or quality/performance improvements are
claimed from this baseline-only run.
