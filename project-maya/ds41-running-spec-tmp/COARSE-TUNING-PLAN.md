# DSpark coarse tuning plan: chunk2048, PP2048, TG256

## Status and scope

This is the agreed plan on paper, with the user's correction to retain
**TG256**, not TG512. This documentation request does not start another GPU
run or authorize Kubernetes writes. Obtain execution approval before running.

The primary objective is **decode tokens/s**, not complete-request wall time.
Retain prefill, TTFT and wall time as the cost of improving decode; do not hide
regressions or describe a decode-only gain as a full-request gain.

Future test configurations use **`--prefill-chunk 2048` instead of 4096**.
Do not change the serving `../ds41-running/decode.yaml`, existing benchmark
configs, frozen inputs or previous results as part of recording this plan.
The previous chunk4096 result is context, not the new comparison baseline:
[220Gi results](retry-220gi/RESULTS.md).

## Fixed workload and runtime

| Setting | Fixed value |
| --- | --- |
| Image | v1.1.28-rocm-10.1, digest `sha256:3cf3dba357c941a190630b0fcf33efd501fe693d9510fa7332522f4b072e30d3` |
| Model/tokenizer/drafter | Same revisions, pack construction and weight formats as the 220Gi screen |
| Devices | Four MI50 32 GB, visible IDs `0,1,2,3`, worker6 |
| Parallelism | TP4, `DS4_TP_GGUF_UNEVEN=1` |
| Context capacity | 196608, native KV precision unchanged |
| CPU | 56 engine threads, same cpuset, no CPU quota |
| Memory | **220Gi** for every start, including the no-drafter baseline |
| Prefill chunk | **2048** |
| VRAM reserve | 1280 MiB |
| Experts | `--mmap-experts off`; require full CPU-expert copies |
| Vision | On, loaded as before; no image requests in this suite |
| DSpark block placement | **`DS4_DRAFT_DEV=1,2,3`** whenever the drafter is loaded |
| Request size | **PP2048 / TG256** |
| Sampling | Greedy, fixed seed, non-thinking, unchanged penalties |
| Concurrency | One serial request at a time |
| Reuse/skips | Zero cross-request KV reuse, no response-cache substitution, no approximate expert skips |
| Calibration | No automatic speed calibration or other runtime autotuning |

Keep all other environment settings from the successful 220Gi screen fixed.
Do not retest the default GPU0 drafter placement: it already failed with OOM
at 220Gi and is outside this sweep. Remove `DS4_DRAFT_DEV` for `--dspark none`;
the engine rejects a block-placement setting when no drafter is loaded.

Use the existing frozen `cases.jsonl`: three warmup and three measurement
cases, following [CORPUS.md](../benchmarking/CORPUS.md). Retain its hash,
article revisions, attribution and token IDs. Do not refetch the corpus or
replace prompts after seeing timings. Every completed request must reach
TG256 naturally; preserve short EOS as an incomplete sample, never override it.

Initialize every engine start from a private copy of the same saved
`retry-220gi/seed-profile.bin`, SHA-256
`bcfd7697fc070b0ebcb0138c0ef029429ea0d4ff81ca60eeb7804e08efd0cd29`.
Never inherit another start's learned profile.

## Measurement procedure

1. Freeze the ordered parameter points, randomization seed and case hashes
   before each stage. Later stages may use earlier results as specified below;
   record their choices before timing those later points.
2. After each fresh engine load, run the three warmup requests, unscored.
   Keep that engine alive for its parameter block.
3. At each parameter point, run the same three measurement requests in their
   frozen order. Score only these requests, never model loading, warmups,
   collector ACKs or setup.
4. Confidence and cumulative thresholds can change per native `GEN` request
   without a restart. Randomize their candidate order within each stage.
   Repeat the default control point around these blocks to expose drift.
5. `DS4_DSPARK_MAX` is read at engine startup: each changed MAX needs a fresh
   engine and the same three startup warmups. Use the same profile seed.
6. Continuous local export with fsync/ACK checkpoints is mandatory, using the
   tested collector approach. Preserve start/READY manifests, native logs,
   complete result rows and lightweight memory/I/O counters outside the pod.

Per-request switching keeps the loaded drafter and its VRAM allocation fixed,
but does not reset adaptive caches or erase warmup history. Randomization and
controls only screen for this bias; they do not prove identical cache states.
If an identical control's pooled decode rate changes by more than 5%, flag
that block as drift-affected and do not declare its winner. Do not silently
increase warmups, rerun points or expand the sweep; agree on a revised run.

## Staged coarse sweep

| Stage | Parameter points | Fixed settings / purpose |
| --- | --- | --- |
| 1. New chunk2048 baselines | `--dspark none`; loaded drafter with native `spec=0`; loaded drafter with `spec=1` | Confidence `0.5`, cumulative `0.5`, MAX `0`. Separate practical no-drafter performance from speculation's effect at fixed drafter allocation. |
| 2. Confidence | **0.3 / 0.5 / 0.7** | Cumulative `0.5`, MAX `0`; select a promising confidence region. |
| 3. Cumulative | **0 / 0.3 / 0.5 / 0.7** | Selected confidence, MAX `0`; select a promising cumulative region. |
| 4. Verify-window cap | **MAX 1 / 2 / 3 / 0** | Selected confidence/cumulative pair; fresh engine for each changed MAX. |
| 5. Interaction check | **At most two neighboring combinations** | Cross neighboring confidence/cumulative levels already listed above, at the selected MAX. Freeze these choices before running; no full Cartesian sweep. |
| 6. Fresh-start confirmation | **Two finalists, then a repeat of the `none` baseline** | Each on a fresh engine with the same seed and three warmups plus three scored requests. Compare with the opening chunk2048 baseline and report control drift. |

Stages 2-4 comprise approximately **nine unique enabled parameter tuples**
after counting their shared points once: three confidence points, three new
cumulative points and three new MAX points. The no-drafter/loaded-off
baselines, deliberate control repeats, up to two interaction points and final
confirmation are additional runs, not part of that nine-point count.

Sequential one-axis selection can miss interactions. Stage 5 limits that risk
without claiming a global optimum. Final confirmation is a coarse consistency
check, not an untouched holdout, a reverse-order repeat or statistical proof.

## Parameter semantics and interfaces

- Engine default: `--dspark-conf 0.5`; native per-request override:
  `dspark_conf=F` (alias `spec_min_p`).
- Native per-request cumulative override: `dspark_cum=F` (alias `spec_cum`).
  Engine default is `STRATA_DS4_DSPARK_CUM=0.5`.
- Cumulative `0` disables the product-of-confidence cutoff only; the individual
  confidence floor still applies.
- `DS4_DSPARK_MAX=0` means the pack-defined limit, **not speculation off**.
  Positive values cap the drafts offered to verification. The cap is applied
  after computing the drafter block, so it does not shorten that computation.
- Native `spec=0/1` is an on/off request switch. Load the drafter for both
  sides of that fixed-allocation comparison; `none` is a separate baseline.
- Do not use the inactive `DS4_DSPARK_CONF` field, GLM's `spec_n_min` or a
  GLM-style `spec` window length. No sampled-drafter knobs or tensor/logit
  dumps during performance timing.

## Ranking and stopping rules

Primary score, pooled over the three measurement requests:

```text
decode_tok_s = sum(TG - 1) / sum(native_decode_seconds)
```

Do not average per-request tok/s. Keep native timing boundaries consistent;
the engine log's `TG/time` uses a different numerator. Native protocol timing
excludes HTTP. DSpark token delivery is bursty, so do not label event gaps as
per-token ITL.

Also retain:

- Per-case decode rates, prefill rate, TTFT and complete-request wall time.
- Drafts offered/accepted, acceptance ratio, accepted drafts per verify round
  where exposed, and accepted drafts as a fraction of generated tokens.
- Actual PP/TG, finish reason, reused tokens, skip counters and raw output IDs.
- Memory including charged file cache/shmem, CPU and available PCIe/I/O
  counters; no heavyweight profiler or new instrumentation during timing.
- Full CPU-expert copy counts, effective TP4/placement/context/vision metadata,
  OOM events, CPU throttling and library/native error diagnostics.

Differences **up to 5%** are inconclusive in this coarse suite. Keep the two
most consistent leaders, preferably with **at least 10% decode improvement
over the new chunk2048 `none` baseline**. Reject points with incomplete
requests, reuse, approximate skips, OOM or throttling. Preserve their evidence;
do not rank partial runs. Report unresolved ties rather than selecting the
fastest individual sample or expanding the budget automatically.

The previous A/C greedy outputs differed. This sweep must retain and compare
outputs, but speed alone cannot establish correctness, token equivalence or
answer quality. Record new pathologies; separate correctness/reference checks
are required before promoting a setting to production.

## Handoff to fine tuning

The output is a ranked table, two confirmed candidate tuples and bounded
promising regions for confidence, cumulative and MAX, with drift, memory,
prefill/wall costs and correctness limitations attached. If confirmation is
inconsistent, stop with an inconclusive result rather than naming a winner.

Only after a separate approval, fine tuning may narrow threshold steps to
`0.05-0.1`, test a disjoint article pool and separately examine longer output
lengths. **No longer-output runs are included in this plan: all current
warmups and measurements remain TG256.**

Future artifacts belong under `coarse-2048-tg256/` in this directory. Do not
overwrite the 200Gi attempt or `retry-220gi/`. Mount HF cache and serving data
read-only, avoid model downloads/weight copies, leave the production Deployment
unchanged, and delete test pods/check idle GPUs after any approved execution.
