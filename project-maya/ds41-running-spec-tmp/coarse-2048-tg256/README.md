# Executing the chunk2048 / PP2048 / TG256 plan

**Stopped as planned on restart-control drift (-8.30%) after stages 1-4.
All 60 requests were preserved; no confirmed finalists. The pod is deleted.
See [RESULTS.md](RESULTS.md). Do not rerun GPU commands without new approval.**

Execution of [the bounded plan](../COARSE-TUNING-PLAN.md) was approved by the
user on 2026-10-26, including the isolated worker6 GPU run, temporary test pod
and cleanup. The production Deployment and its data are not changed.

`tune.py` executes the stages adaptively, freezing each later-stage schedule
before timing it. Fixed shuffle seed: **20261026**, stage seed `seed + stage`.
Confidence/cumulative candidates reuse their already-measured shared points.
The default control closes each threshold block and opens the next one.
MAX1/2/3 start order is shuffled, with a fresh engine/seed and three warmups
each; MAX0 reuses its threshold result. A separate interaction start repeats
the selected MAX point before and after up to two neighboring tuples. Two
finalists and the no-drafter baseline are then repeated on fresh engines.

Within 5% of the fastest point, sequential stage selection prefers thresholds
nearest the defaults, then uncapped MAX0. These are unresolved ties, not
verified winners. Finalist nomination takes the two fastest distinct measured
tuples; confirmation and ties must be reported, not hidden.

**Control drift above 5%, any invalid request, incomplete expert copy or OOM
stops execution without retries, extra warmups or an expanded grid.** Preserve
the partial results and obtain agreement before any revised run. Inconclusive
finalist confirmations do not authorize additional tests.

All starts use the saved original `../retry-220gi/seed-profile.bin`, uploaded
before preparation, rather than the current profile on the serving PVC.
Model weights and the vision pack are read-only; pack indices live on emptyDir
and refer to cached weight files. No downloads or weight copies are needed.

`../screen.py` provides the native engine reader, request timings and validation;
its only new interface is optional per-request tuning keys. `../stream.py`
provides the existing artifact/ACK framing. `collect_tune.py` applies a separate
strict allowlist for the bounded session names and fsyncs local artifacts before
each ACK. Stage schedules, complete output token IDs, timing and memory/I/O
records survive outside the test pod. `run/exit.json` and `run/summary.json`
distinguish completed, drift-stopped and failed experiments.

CPU-only checks, before GPU execution:

```bash
python3 -m unittest discover -s project-maya/ds41-running-spec-tmp -p 'test_*.py' -v
python3 -m unittest discover -s project-maya/ds41-running-spec-tmp/coarse-2048-tg256 -p 'test_*.py' -v
```

Collector command, from the repository root after preparation/preflight:

```bash
python3 project-maya/ds41-running-spec-tmp/coarse-2048-tg256/collect_tune.py \
  --out project-maya/ds41-running-spec-tmp/coarse-2048-tg256/run -- \
  kubectl -n apps-ml exec -i maya-ds41-dspark-coarse-2048 -- \
  env BENCH_STREAM=1 python /data/screen/coarse-2048-tg256/tune.py
```

Use an unlimited external timeout. Never restart the collector against this
directory or re-execute the GPU command after a disconnect. Inspect and retain
the evidence, terminate the test workload and clean up its pod.
