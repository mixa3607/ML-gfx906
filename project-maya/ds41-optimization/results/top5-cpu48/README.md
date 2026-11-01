# CPU48: five remaining high-priority candidates

**Completed:** 2026-11-01 14:49:26–16:14:29 UTC, about 85 minutes from the
first suite start through the last suite shutdown, including inter-arm gaps.
All five runners exited with code 0. All 110 requests completed TG256 with
`finish=length`, nonzero speculative offers, `reused=0` and no slot operations.
All five test pods were deleted; each cleanup sample shows all four GPUs
at 0% utilization and 10 MB VRAM used each.

## Results

Ten measurement requests per arm, excluding twelve warmups: 126976 prompt
tokens and 2560 generated tokens per measurement set. Deltas use the saved
control, not a fresh control or an optimized combined configuration.

| Arm | Prefill tok/s | vs saved control | Decode tok/s | vs saved control | Accepted / offered drafts | Pod memory peak GiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Saved control | 344.69 | — | 35.06 | — | 1284 / 1618 (79.36%) | Not recorded |
| draft-cost | 354.88 | +2.95% | 36.27 | +3.46% | 1345 / 1774 (75.82%) | 219.61 |
| decode-trim | 332.50 | -3.54% | 35.91 | +2.43% | 1287 / 1621 (79.40%) | 219.62 |
| hc-mix | 348.79 | +1.19% | 35.68 | +1.79% | 1301 / 1609 (80.86%) | 219.36 |
| engram-cache | 345.55 | +0.25% | 34.86 | -0.57% | 1257 / 1599 (78.61%) | 219.35 |
| markov-q8 | 339.72 | -1.44% | 34.87 | -0.54% | 1271 / 1611 (78.90%) | 218.89 |

[comparison.md](comparison.md) contains per-length results;
[comparison.json](comparison.json) also records per-request deltas, memory,
expert placement, timestamps and diagnostics. Observations without a
performance acceptance decision:

- `draft-cost`: all ten PP measurements improved versus saved control.
  Per-length pooled TG ranges from -0.53% at PP32768 to +9.93% at PP4096.
  The lower acceptance percentage does not by itself imply slower decoding;
  the measured pooled TG increased. All 22 requests logged cost-policy reports.
- `decode-trim`: nine of ten PP measurements improved, but PP32768 has one
  98475.6 ms prompt read and another at 77977.3 ms. The saved control's two
  reads were 77343.2 and 78233.8 ms. Keep the slow request in all aggregates:
  PP32768 is -11.83%, driving pooled PP to -3.54%. Its cause is not established
  by these artifacts; no request was discarded or rerun. TG PP16384 is -3.21%.
- `hc-mix`: small pooled PP/TG gains, with per-length TG PP16384 -2.39%.
- `engram-cache`: the 4096 setting passed the preflight estimate and retained
  identical expert placement/pinning. Pooled PP +0.25% and TG -0.57% do not
  establish a useful improvement or a cache-size optimum.
- `markov-q8`: both pooled speeds are below saved control. Automatic residency
  differs: 10645 CPU-lane experts rather than 10647, all copied into RAM
  (200.1 GB rather than 200.2 GB; pinned copies round to 200.9 GB in both).
  The sole config change is Markov Q8; no profile or placement override was
  introduced. This is an end-to-end flag measurement, not an isolated head test.

No new control was run: the reference timestamps are 11:54:36–12:11:42 UTC,
several hours before these candidates. These are sequential single-run
measurements with two prompts per length; inter-run drift and adaptive/draft
histories can affect small differences. No statistical-significance or
whole-answer parity claim, automatic flag acceptance or baseline/best-tested
change is made.

## Subsequent user selection

Accept `MAYA_DS4_DRAFT_COST=1` and `MAYA_DS4_DECODE_TRIM=15` as individually
selected values. Retain `DS4_ENGRAM_CACHE_MB=256` and unset/default-off
`MAYA_DS4_MARKOV_Q8` (`0`). Leave `MAYA_DS4_HC_MIX_SPLIT` undecided for the
[two combined-candidate tests](../final-candidates-cpu48/README.md).
This is a separate user decision, not a threshold applied by the benchmark.
The raw data and primary pooled summaries, including the slow PP32768 request,
remain unchanged. The active baseline is not automatically updated.

## Approved scope

Five serial full-suite runs, each independently over the unchanged
[CPU48 baseline](../flags-cpu48/baseline-config.json), without the four
previously selected single-flag optimizations:

| Order | Arm | Only baseline override |
| ---: | --- | --- |
| 1 | `draft-cost` | `MAYA_DS4_DRAFT_COST=1` |
| 2 | `decode-trim` | `MAYA_DS4_DECODE_TRIM=15` |
| 3 | `hc-mix` | `MAYA_DS4_HC_MIX_SPLIT=1` |
| 4 | `engram-cache` | `DS4_ENGRAM_CACHE_MB=4096` instead of 256 |
| 5 | `markov-q8` | `MAYA_DS4_MARKOV_Q8=1` |

**No fresh control is run.** Use the saved
[single-flag-block control](../flags-cpu48/README.md), retaining its earlier
timestamps and the possibility of drift. No performance thresholds,
automatic baseline/best-tested changes, additional variants or fallback flags.
The priority order is an estimate of potential, not a measured speed ranking.

## Method and resource safeguards

Use the frozen `ds41f-ru-long` cases: 12 PP2048 warmups and ten measurements,
PP2048/4096/8192/16384/32768 twice, TG256. Each arm has one resident engine,
fresh original expert-profile seed and pack index in a separate pod on
`kube-worker6.arkprojects.lan`. Keep CPU48, TP4, `spec=1`, temperature 0,
context 524288, prefill chunk 4096, DSpark/vision on, `SLOT_KEEP=0`, no KV reuse
and two NUMA RAM parts. Adaptive state remains within an arm.

Preserve the image/source/model/drafter/vision and gfx906 patches of the
[preceding tests](../combos-cpu48/README.md). Source PVCs are read-only; no
model weights are copied/downloaded. The original preparation and CPU48 runner
are reused without modification; a wrapper records cgroup memory before and
after the engine run. The pod limit remains 220 GiB, with no CPU quota.

For cache=4096, preflight estimates 200.9 GB for pinned expert copies,
8 GiB for the 4 GiB cache payload plus index/allocation overhead, and 16 GiB
for other work. Require this estimate to fit both host available RAM and
remaining cgroup headroom before starting the engine. This is a conservative
estimate, not proof of peak working-set size. If it does not fit, record the
blocker and stop rather than lowering the cache, raising the limit or changing
expert placement. Require the cache arm to preserve the reference's full
CPU-expert placement and pinning. All arms must copy every CPU-lane expert
into RAM and pin those copies; flag-induced allocation/residency differences
are recorded, not hidden by changing configuration or profile.

Capture `memory.peak`, `memory.events`, current/stat accounting and host
available memory in `memory.json`. Peak includes preparation and charged file
cache, not just anonymous resident weights; no equivalent peak was captured
for the saved control. Require no OOM events. Native decode-trim checks are
preserved and must cover all four devices plus mapped hand-offs. Markov Q8's
verified-answer-preserving classification follows the accepted task contract;
this block does not add whole-answer parity or quality testing.

Record raw results, effective arguments/environment, configuration/pod,
model/pack/patch/profile/hardware identities, logs, memory and input/script/
artifact hashes. Export each arm and delete its pod, then verify idle GPUs.
Runtime/setup errors stop the queue; performance alone does not.

Report pooled token/time PP/TG without warmups, per-length/per-request deltas
versus the saved control, draft acceptance (DSpark plus prompt lookup), memory
and expert placement. Native timings are not client TTFT or pure kernel time.

## Diagnostics and artifacts

- `draft-cost`: 14:49:26.722091–15:06:03.307718 UTC.
- `decode-trim`: 15:06:39.959869–15:22:42.536503 UTC.
- `hc-mix`: 15:23:18.892011–15:40:02.075430 UTC.
- `engram-cache`: 15:40:38.111700–15:57:20.283586 UTC.
- `markov-q8`: 15:57:56.429916–16:14:29.651241 UTC.
- Nonexperimental effective settings, engine/image identities, model/drafter/
  vision and pack metadata, original expert-profile seed, local gfx906 patch
  evidence and static GPU metadata matched the saved control. Startup confirms
  actual TP4, CPU48, full CPU-expert RAM copies, two NUMA parts and pinning.
- Decode trim passed 16 rounding/GEMV parity cases on each GPU, copy-regions
  checks on each GPU, and mapped hand-off checks across all 12 ordered device
  pairs. These nine log reports cover the four mask bits, not whole answers.
  HC mix and Markov startup activation diagnostics are retained; no new
  dedicated parity test was added for either.
- Every arm's `memory.events` counters remained zero, including `max`, `oom`
  and `oom_kill`. Peak pod charges were 218.89–219.62 GiB under the unchanged
  220 GiB limit. Peaks include preparation and file cache; the before/after
  accounting does not locate the peak in time or prove a large spare working-set
  budget. The saved control has no comparable memory-peak record. Successful
  cache=4096 here does not establish that 8192 or full-table RAM mode fits.
- Cache preflight estimated 226669803776 bytes against 236194869248 available
  under the pod/host checks. No RAM limit, expert-copy policy or source PVC
  was changed to make the run fit.
- Each log retains two `rocblaslt error` diagnostics for
  `TensileLibrary_lazy_gfx906.dat` and twelve `hipModuleLoad failed` messages
  for gfx906/xnack `Kernels.so-000` modules. All requests completed; preferred
  hipBLASLt-path availability remains unestablished.
- Extraction for `decode-trim` emitted a `tar` future-mtime warning for
  `config.json` (about 22.4 seconds). The captured config hash matched; no
  cross-host clock synchronization is asserted. Throughput uses native engine
  durations, not host/pod timestamp differences.
- Each arm retains raw results, summary, engine log, run metadata, exact config
  and pod manifest/snapshot, pack/patch metadata, seed/final profiles,
  `memory.json`, hardware/idle samples, source-state and artifact hash manifests.
  Input/script/artifact hashes verify, and summaries/comparison reproduce
  byte-for-byte. Active baseline, existing best-tested values, prior raw
  artifacts, model blobs and other workloads were not modified.

## Execution and CPU-only analysis

Real GPU runs and pod creation/deletion require explicit approval. Run from
the repository root in the approved order, without an extra control:

```bash
python3 project-maya/ds41-optimization/results/top5-cpu48/scripts/run.py draft-cost
python3 project-maya/ds41-optimization/results/top5-cpu48/scripts/run.py decode-trim
python3 project-maya/ds41-optimization/results/top5-cpu48/scripts/run.py hc-mix
python3 project-maya/ds41-optimization/results/top5-cpu48/scripts/run.py engram-cache
python3 project-maya/ds41-optimization/results/top5-cpu48/scripts/run.py markov-q8
```

The launcher refuses to overwrite an arm directory. CPU-only recomputation:

```bash
python3 project-maya/ds41-optimization/results/top5-cpu48/compare.py
```

CPU-only tests, with no engines or Kubernetes access:

```bash
cd project-maya/ds41-optimization/results/top5-cpu48
python3 -m unittest -v
```

CPU validation: 11 benchmarking tests and 9 block-specific tests passed.
Checks cover the exact five isolated overrides, baseline identity, RAM budget,
all arm validators, missing trim checks, complete expert copies, OOM events,
unrelated environment changes, KV reuse, warmup exclusion and synthetic report
generation with the saved control and explicit missing control-memory data.
