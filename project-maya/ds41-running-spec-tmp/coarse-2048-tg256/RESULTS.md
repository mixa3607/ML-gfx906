# Chunk2048 / PP2048 / TG256: coarse sweep stopped on restart drift

## Outcome

**Stages 1-4 were measured; no final winner or two confirmed finalists.**
The opening control of stage 5 repeated `conf=0.5, cum=0.5, MAX=0` on a fresh
engine and fell **38.17 -> 35.01 decode tok/s (-8.30%)**, beyond the agreed 5%
drift limit. The runner stopped as required. No interaction candidates, final
confirmations, closing no-drafter baseline or fine tuning were run.

All **60 requests** (18 warmups, 42 measurements) were valid PP2048/TG256
samples and durably exported. Exit code **2** means a planned drift stop,
not OOM or lost evidence. The whole experiment is incomplete. The last session
manifest is marked incomplete because its control failed, even though its six
requests completed normally.

The strongest observed threshold point was `0.5 / 0.3 / MAX0` at **39.30 tok/s**,
but its **+2.95%** over the initial default is below the 5% resolution rule.
Do not call it an optimum or promote it to serving.

## Measurements

Each table row pools three measurement requests; warmups are excluded.
The primary metric is `sum(TG - 1) / sum(native_decode_seconds)`, not an
arithmetic mean of per-request rates. Confidence/cumulative rows share one
loaded engine; MAX rows require new starts and therefore have different warmup
histories. These are diagnostic measurements, **not a confirmed final ranking**.

| Point | Conf | Cum | MAX | Decode tok/s | Prefill tok/s | Scored wall, s | Acceptance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No drafter (`none`) | — | — | — | 28.40 | 92.43 | 93.42 | — |
| Loaded drafter, `spec=0` | — | — | 0 | 27.21 | 85.90 | 99.64 | — |
| Initial default, `spec=1` | 0.5 | 0.5 | 0 | 38.17 | 92.20 | 86.68 | 82.1% |
| Confidence 0.7 | 0.7 | 0.5 | 0 | 35.98 | 93.34 | 87.09 | 85.8% |
| Confidence 0.3 | 0.3 | 0.5 | 0 | 38.04 | 92.65 | 86.43 | 80.9% |
| Confidence closing control | 0.5 | 0.5 | 0 | 38.62 | 92.98 | 85.89 | 83.9% |
| Cumulative disabled | 0.5 | 0 | 0 | 38.39 | 93.31 | 85.77 | 75.5% |
| Cumulative 0.3 | 0.5 | 0.3 | 0 | 39.30 | 93.55 | 85.15 | 80.2% |
| Cumulative 0.7 | 0.5 | 0.7 | 0 | 34.63 | 94.39 | 87.19 | 87.3% |
| Cumulative closing control | 0.5 | 0.5 | 0 | 38.65 | 89.92 | 88.12 | 83.2% |
| MAX2, fresh engine | 0.5 | 0.5 | 2 | 35.49 | 83.10 | 95.50 | 87.9% |
| MAX1, fresh engine | 0.5 | 0.5 | 1 | 31.34 | 85.72 | 96.09 | 87.5% |
| MAX3, fresh engine | 0.5 | 0.5 | 3 | 35.24 | 81.74 | 96.88 | 84.0% |
| MAX0 restart control | 0.5 | 0.5 | 0 | 35.01 | 81.63 | 97.13 | 81.2% |

The initial default was **+34.43% decode versus no drafter**, or **+40.27%
versus the loaded-drafter `spec=0` point**. Its scored wall time was 86.68 s
versus 93.42 s without a drafter. The fresh default control still measured
+23.28% decode relative to the opening `none`, but wall time was 97.13 s.
There is no closing `none` repeat to validate either cross-start comparison.
Do not turn these observations into a stable end-to-end acceleration claim.

## Selection, controls and stopping

- Shuffle seed **20261026**, stage seed `seed + stage`. Actual schedules were
  saved and acknowledged before timing each stage (`run/stage-*.json`).
- Confidence order was **0.7, 0.3**, reusing the initial 0.5 measurement.
  The closing 0.5 control changed **+1.18%**, passing the drift rule.
- Confidence **0.5** was retained: 0.3 was effectively tied, and 0.7 was slower.
- Cumulative order was **0, 0.3, 0.7**, reusing the selected confidence's 0.5
  result. The default control changed **+0.08%** over the preceding control.
- Cumulative **0.5** was retained by the predeclared conservative tie rule:
  0.3 was only 2.95% above the original default; 0 and 0.5 were also close.
- MAX start order was **2, 1, 3**. MAX0 was retained by the same rule using
  its existing threshold measurement. All changed MAX starts had identical
  original profile seeds and exactly three startup warmups.
- Stage 5 froze up to two neighboring interactions, but its opening MAX0
  restart control failed **before either candidate was executed**.
- That control was **-8.30% versus the original default**, or **-9.44% versus
  the latest default control**. No retries, extra warmups or expanded grid
  were used to work around the stop.

The initial threshold engine had processed many more measurement requests
than the fresh engines. Adaptive expert/cache/profile state and ordering are
possible confounders; the cause of the drift was **not isolated**. In
particular, MAX1/2/3 cannot be cleanly ranked against the much more exercised
original MAX0. A possible cap penalty is not established by those numbers.

## Correctness and runtime limits

- Every saved request completed PP2048/TG256 with zero cross-request reuse.
  No native `ERR`, OOM-kill delta or CPU throttling was observed. Approximate
  skips were disabled; none were reported in the retained STAT records.
- Full CPU-expert copies were confirmed for every start: **10127/10127**
  without the drafter and **10631/10631** with it. Effective TP4, context196608,
  native vision and distributed drafter placement were checked at READY.
- **Greedy token equivalence is not established.** All three measured outputs
  differ from `none` for every other point, including loaded `spec=0`. Repeats
  of the same default tuple also differ. Thus divergence is not isolated to
  speculation, and a quality or exactness conclusion cannot be drawn.
- Every start emitted the known missing gfx906 rocBLASLt/Tensile/hipModuleLoad
  diagnostics in its native log. Requests completed, but this is not a clean
  backend validation.
- The same pinned image/source, model, tokenizer, pack hashes and frozen
  corpus/profile were used as in the 220Gi retry. Only the agreed chunk2048
  and spec-related test parameters changed. The chunk4096 historical results
  are not a controlled baseline for the chunk change.
- Four MI50 32 GB on worker6, TP4, CPU56, effective cpuset 0-75, no CPU quota,
  context196608, reserve1280, mmap-experts off, vision on, greedy seed1,
  non-thinking, serial native protocol, **220Gi** throughout.
- The memory cgroup reached its 220Gi charged limit including file cache.
  Per-request anon+shmem+kernel was approximately **189.72-189.86Gi** for
  `none` and **198.51-198.97Gi** for the loaded starts. This does not validate
  operation at 200Gi. `memory.peak` is cumulative across starts in one pod.

## Handoff

The threshold-only observations suggest keeping **confidence 0.3-0.5** and
**cumulative 0-0.5** as regions to revisit; higher acceptance at 0.7 did not
translate to higher decode throughput here. MAX0 remains a candidate, not a
confirmed winner. There are **no two confirmed finalists for fine tuning**.

A revised, separately approved run should first establish comparable warmup
and adaptive-state conditions across fresh starts, with matching controls.
Only then should it confirm candidate tuples or use smaller threshold steps.
No such revised run has been started.

## Evidence and cleanup

- `run/summary.json`: all pooled metrics, point metadata, per-case rates, TTFT,
  token comparisons, control deltas and the explicit drift status.
- `run/*/`: explicit runtime configs, start/READY/final manifests, native logs
  and full result rows including outputs, cgroup/process memory, CPU and I/O.
- `run/events.jsonl`: chronological artifact stream, all point definitions,
  frozen schedules and ACK checkpoints; `run/heartbeat.jsonl`: 15-second
  lightweight cgroup snapshots. Evidence is local, not dependent on emptyDir.
- `run/experiment.json`: exact runner/helper hashes. `preflight.json` verifies
  uploaded sources, cgroup limits and pack hashes against the prior retry.
- **16 CPU-only tests passed**; `verify_results.py` independently recomputes
  every point from raw rows and checks hashes, runtime, counters and cleanup.
  Run it with `python3 project-maya/ds41-running-spec-tmp/coarse-2048-tg256/verify_results.py`.
- The test process exited, the pod was deleted and all four GPUs returned to
  0% activity/about 10 MB used. Production stayed at zero replicas, with
  `decode.yaml`, serving PVC and HF cache unchanged. See `cleanup.txt`,
  `processes-after-run.txt`, `pods-after-cleanup.json`, `gpu-after-cleanup.txt`
  and `deployment-replicas-after.txt`.
