# Side story: CPU48/four flags with TP2 or prefill chunk 2048

## Results

Both approved runs completed on 2026-11-01 with exit code 0:
`tp2` at 17:38:24–17:57:14 UTC, then `chunk2048` at 17:57:50–18:12:57 UTC.
All 44 requests completed TG256 with `finish=length`, zero KV reuse and no
slot operations. All 20 measurements are retained, with no extra GPU runs.
See [pooled and best-of-two tables with case IDs](comparison.md),
[machine-readable comparison](comparison.json), and raw artifacts in
[tp2](tp2/) and [chunk2048](chunk2048/).

| Configuration | Pooled PP tok/s | PP vs saved final | Pooled TG tok/s | TG vs saved final |
| --- | ---: | ---: | ---: | ---: |
| Saved final CPU48/four flags, TP4/chunk4096 | 410.83 | — | 35.88 | — |
| TP2/chunk4096, all four GPUs | 248.78 | -39.45% | 25.79 | -28.13% |
| TP4/chunk2048 | 352.54 | -14.19% | 35.08 | -2.23% |

TP2 is slower in every per-length pooled and best-of-two PP/TG comparison.
Its pooled PP declines by 33.48–40.59% and TG by 24.19–32.96% across lengths.
Chunk2048 leaves PP2048 nearly unchanged (+0.40%), but pooled PP declines
at every longer length (-8.28% at 4096 through -16.85% at 32768). Pooled TG
is +2.23% at PP2048 and -2.78% to -4.37% in the other groups. Its best-of-two
view is similar, with an additional small TG +0.11% at PP8192; these optimistic
maxima do not replace the primary pooled results.

Neither side configuration improves pooled PP or TG over the saved final
baseline. The saved reference predates these runs by several hours and was
not rerun; no significance claim or isolated kernel attribution is made.
Changing layout/chunk and automatic residency can also change answers;
no output-token or quality comparison was performed. The selected
CPU48/four-flag TP4/chunk4096 baseline is unchanged, not automatically replaced.

### Runtime validation and diagnostics

- Actual TP2 was confirmed without fallback: 1152 FFN values per member,
  logical CUDA0/1 on trunk layers 0–19 and CUDA2/3 on 20–39. The head moved
  from CUDA0 to CUDA2. DSpark blocks 0/1/2 stayed on CUDA1/2/3 through the
  approved global `DRAFT_GPU` setting (target groups 0/1/1).
- Chunk2048 retained one TP4 group with 576 FFN values per member, head on
  CUDA0 and original `DRAFT_DEV=1,2,3`. Startup reports chunk 2048; TP2 reports
  chunk 4096. Both retain CPU48 and the four selected flags.
- Both arms passed all eight HC startup checks (single-/16-row) and twelve
  route checks (single-/3-/16-row) across all four GPUs. These native checks
  cover their own arithmetic, not equality of answers across layouts.
- Automatic CPU-lane residency changed from 10647 experts (200.2 GB,
  200.9 GB pinned) in saved final-four to 10381 (195.2 GB, 195.9 GB pinned)
  with TP2 and 10555 (198.4 GB, 199.2 GB pinned) with chunk2048. Every CPU-lane
  expert was copied into RAM across two NUMA parts in both new runs. Lower
  RAM requirements did not yield higher measured throughput here.
- Pod cgroup peaks were 215.07/218.47 GiB for TP2/chunk2048 against 220 GiB;
  all `memory.events` counters stayed zero. Peaks include preparation and file
  cache; this is not an isolated model-allocation comparison with saved final.
- All input/script/artifact hashes verify. Image, executable/source, model,
  drafter/vision, seed and nonexperimental settings match saved final-four:
  Maya v1.1.45 source `6ecbd3cbc5330b57f70cd5cf8a5c42eb8ef950cc`, ROCm 10.1,
  4 × MI50 32GB. Only the approved args/drafter-variable changes were applied.
- Each log retains the same two `rocblaslt error` entries for
  `TensileLibrary_lazy_gfx906.dat` and 12 `hipModuleLoad failed` entries as
  saved final-four. All requests completed; the preferred hipBLASLt path
  remains unverified.
- Both test pods were deleted. Recorded cleanup samples and a subsequent
  read-only inspection show 0% GPU utilization and 10 MB VRAM used per card.
  No shared workload or model-cache blob was modified.

## Approved scope

Exactly two serial full-suite runs, each independently based on the selected
[CPU48/four-flag baseline](../../base-params/README.md), without changing it:

| Order | Arm | Changes from final baseline |
| ---: | --- | --- |
| 1 | `tp2` | `--tp 4` → `2`; remove `MAYA_DS4_DRAFT_DEV=1,2,3`, use `MAYA_DS4_DRAFT_GPU=1,2,3` |
| 2 | `chunk2048` | `--prefill-chunk 4096` → `2048`, retaining TP4 and original `DRAFT_DEV` |

TP2 uses **all four GPUs as two pairs**, not two GPUs total. The user separately
approved the necessary drafter-variable replacement: `DRAFT_DEV` indexes a
member of one TP group, so `1,2,3` is invalid in a two-member group.
`DRAFT_GPU` selects global logical CUDA IDs and preserves blocks 0/1/2 on
logical CUDA1/2/3. With unchanged `HIP_VISIBLE_DEVICES=1,0,3,2`, their physical
placement is unchanged, though the target groups and memory accounting differ.
This behavior was inspected in the matching local Maya source
`6ecbd3cbc5330b57f70cd5cf8a5c42eb8ef950cc`, `draft_devs()`/`draft_gpus()` in
`src/ds4/ds4_model.cu`. No extra TP2 transport flags or manual layer split.

Batch means the **prefill chunk**, not concurrent requests, generated tokens
or prompt length. The second arm keeps the original TP4 layout. There is no
combined TP2/chunk2048 arm, extra control, rerun, threshold screening or
automatic adoption. These explicit side experiments relax the main campaign's
fixed TP/chunk constraint: different arithmetic/layout/chunk boundaries may
change answers. Startup fusion checks do not prove cross-layout answer parity.

## Method and evidence

Keep CPU48 and the four selected flags, UD-Q8_K_XL, context 524288, `spec=1`,
temperature 0, DSpark/vision, Engram cache 256, prompt skip 2, slots off,
`DS4_COPY_NUMA=2`, and the original expert-profile seed. No draft cost, decode
trim, HC mix, Markov Q8 or additional approximations. Use the existing pinned
Maya v1.1.45/ROCm 10.1 image on four MI50 32GB GPUs on worker6.

Each arm uses its own pod, fresh pack metadata/profile seed and one resident
engine: 12 PP2048 warmups plus ten measurements, two different frozen prompts
at each length 2048/4096/8192/16384/32768, requesting TG256. Reuse the recorded
remote runner and memory wrapper unchanged; do not regenerate cases. Input
cases SHA256: `3195a02e90078b366c00dce429652b386fe3616d879cdd25c1a6f288435b46c3`.
All timing samples are retained; warmups are excluded from summaries.

Keep read-only source PVCs and the 220 GiB pod limit, no CPU quota. No model
downloads/copies, shared-pod modifications or image rebuilds. Native logs must
show the requested actual TP width/group count and chunk, all four devices,
CPU48, complete expert RAM copies/pinning, and all HC/route startup checks.
Automatic expert residency/layer placement can change; record it rather than
forcing the old counts. Capture memory peak/events, reject OOM, export raw
artifacts, delete each pod and verify idle GPUs. Errors stop the queue without
fallback or extra GPU attempts.

Primary comparisons use pooled token/native-time rates against the saved
[`combos-cpu48/all`](../combos-cpu48/README.md) run (2026-11-01,
14:14:40–14:28:10 UTC), PP/TG 410.83/35.88 tok/s. It is not a new control:
drift, automatic placement, adaptive histories and possibly changed answers
limit causal attribution. Preserve per-request/per-length comparisons.
Report separate best-of-two independent PP/TG maxima with case IDs; these are
different prompts, not repetitions or one jointly observed request. No quality,
whole-answer parity or statistical-significance claim. Draft acceptance includes
DSpark and prompt lookup; native prompt time is not client TTFT/kernel-only time.

## Execution

User approval covers these two GPU runs and creation/deletion of their pods,
CPU tests, documentation and local commit, without push or deployment.
From repository root (existing result directories cannot be overwritten):

```bash
python3 project-maya/ds41-optimization/results/side-layout-cpu48/scripts/run.py tp2
python3 project-maya/ds41-optimization/results/side-layout-cpu48/scripts/run.py chunk2048
```

CPU-only analysis and tests:

```bash
python3 project-maya/ds41-optimization/results/side-layout-cpu48/compare.py
cd project-maya/ds41-optimization/results/side-layout-cpu48
python3 -m unittest -v
```

Before GPU execution, 11 side-story CPU tests and 11 benchmarking tests passed.
Synthetic checks cover exact independent changes, both drafter aliases,
actual TP/group/chunk evidence, placement, missing device/fusion checks,
unrelated environment changes, incomplete RAM copies, OOM and KV reuse,
plus full pooled/best-of-two report generation with selected case IDs.
