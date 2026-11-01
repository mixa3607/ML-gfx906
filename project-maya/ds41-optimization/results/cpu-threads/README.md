# CPU-thread comparison: 74 / 56 / 48

**Completed:** 2026-11-01. Both candidates exited with code 0 and passed
baseline-equivalence and artifact/hash validation. Each completed all 22
requests at TG256, `finish=length`, `reused=0` and nonzero speculative offers;
neither log contains conversation-slot operations.

## Results

Ten measured requests per setting, excluding twelve warmups:

| CPU threads | Prefill tok/s | vs CPU74 | Decode tok/s | vs CPU74 | Accepted / offered drafts |
| ---: | ---: | ---: | ---: | ---: | ---: |
| [74](../baseline/README.md) | 334.56 | — | 30.07 | — | 1253 / 1542 (81.26%) |
| [56](cpu56/summary.json) | 347.03 | +3.73% | 35.72 | +18.80% | 1283 / 1613 (79.54%) |
| [48](cpu48/summary.json) | 347.64 | +3.91% | 35.67 | +18.61% | 1304 / 1639 (79.56%) |

Each setting measured 126976 prompt tokens and 2560 generated tokens. Native
prompt/decode totals were 365893.5 / 71659.2 ms for CPU56 and
365252.6 / 71772.0 ms for CPU48. Full per-length results are in
[comparison.md](comparison.md); [comparison.json](comparison.json) also records
per-request deltas and library diagnostic counts.

Both settings improved decode on all ten measured requests versus CPU74.
Per-length pooled TG gains range from +15.49% to +21.15% at CPU56 and
+15.78% to +23.86% at CPU48. Prefill is less consistent: individual-request
PP gains occurred on 6/10 requests at CPU56 and 9/10 at CPU48, though each
length's pooled PP improved. PP32768 contributes the largest pooled PP gain.

CPU48 versus CPU56 is +0.18% PP and -0.16% TG: these runs do not establish
a meaningful winner between them. The decode difference from CPU74 is large
and consistent within these measurements, but runs were sequential, not
randomized/repeated trials. Draft counters and adaptive histories differ;
this is an end-to-end engine result, not an isolated CPU-kernel benchmark or
an output-token parity check. Baseline remains CPU74; no additional CPU
values were run or automatically selected.

## Method

Compare the recorded [CPU74 baseline](../baseline/README.md) with two serial
full-suite runs, CPU56 followed by CPU48. Change only `--cpu-threads`; leave
the baseline configuration and artifacts unchanged.

Each candidate uses its own pod on `kube-worker6.arkprojects.lan`, fresh
image-provided expert-profile seed, generated pack index and resident engine.
The seed, model/drafter/vision identities, image digest, engine hash, effective
environment, non-CPU arguments and hardware/limits must match the baseline.
No model weights are downloaded or copied. Source PVCs are read-only.

The frozen `ds41f-ru-long` schedule is unchanged: 12 PP2048 warmups, then
PP2048/4096/8192/16384/32768 twice, TG256. Keep TP4, `spec=1`, `SLOT_KEEP=0`,
context 524288, chunk 4096, DSpark/vision on and two NUMA RAM parts. Require
zero KV reuse and no conversation-slot operations. Adaptive state is retained
within each run, not shared across runs.

Pool token counts over native engine milliseconds, excluding warmups; report
PP and TG separately. These are not client TTFT or GPU-kernel-only timings.
One run per setting and two prompts per length do not establish significance
or a universal optimum. Draft acceptance combines DSpark and prompt lookup.
Do not change baseline CPU74 or launch additional CPU values automatically.

## Provenance and cleanup

- CPU56: 10:51:27.709732–11:06:33.854426 UTC.
- CPU48: 11:07:09.917311–11:22:54.787306 UTC.
- Hardware and software match the [baseline](../baseline/README.md): four
  MI50 32 GB gfx906 GPUs, 76 physical CPU cores, SMT off, two NUMA nodes,
  no CPU quota and a 220 GiB pod RAM limit; Maya v1.1.45 / source
  `6ecbd3cbc5330b57f70cd5cf8a5c42eb8ef950cc`, ROCm 10.1, the same pinned image
  digest and both verified local gfx906 patches. GPU static metadata matches
  byte-for-byte. Each log confirms actual TP4, the requested CPU thread count,
  all 10647 CPU-lane experts copied into RAM (200.2 GB, two NUMA parts), and
  pinned expert copies (200.9 GB).
- Both logs retain two `rocblaslt error` and twelve `hipModuleLoad failed`
  diagnostics, matching the baseline counts. Every request completed;
  preferred hipBLASLt-path availability remains unestablished.
- Each `cpu56/` / `cpu48/` directory contains `results.jsonl`, `summary.json`,
  `aggregation.txt`, `engine.log`, `run-metadata.json`, the exact config and pod
  manifest, pack/patch metadata, seed/final profiles, hardware snapshots,
  `source-state.json` and `artifact-sha256.json`. Summaries reproduce
  byte-for-byte and all recorded input, script and artifact hashes verify.
- Both test pods were deleted. After each run, all four GPUs were at 0%
  utilization with 10 MB VRAM used. No other workload or source PVC was modified.
- CPU validation: 11 benchmarking tests and 14 experiment tests passed,
  covering config isolation, aggregation/warmup exclusion, invalid CPU/TP/spec,
  slots, KV reuse, schedule/offer validation, seed/environment drift and comparison.

## Execution

From the repository root, **only after explicit GPU and pod-write approval**:

```bash
python3 project-maya/ds41-optimization/results/cpu-threads/scripts/run.py 56
python3 project-maya/ds41-optimization/results/cpu-threads/scripts/run.py 48
```

The launcher refuses to overwrite a result directory, exports full results,
deletes each test pod and verifies idle GPUs after cleanup. Preparation uses
the frozen baseline `scripts/remote.py`; both scripts and the pod template
are recorded in the per-run script hash manifest.

CPU-only recomputation, with no Kubernetes access:

```bash
python3 project-maya/ds41-optimization/results/cpu-threads/summarize.py \
  project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl \
  project-maya/ds41-optimization/results/cpu-threads/cpu56 56
python3 project-maya/ds41-optimization/results/cpu-threads/summarize.py \
  project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl \
  project-maya/ds41-optimization/results/cpu-threads/cpu48 48
python3 project-maya/ds41-optimization/results/cpu-threads/compare.py
```

`compare.py` checks artifact/script hashes and baseline equivalence, then
writes `comparison.json` and `comparison.md`, including pooled and per-length
PP/TG deltas and per-request deltas. CPU checks for the experiment:

```bash
cd project-maya/ds41-optimization/results/cpu-threads
python3 -m unittest -v
```
