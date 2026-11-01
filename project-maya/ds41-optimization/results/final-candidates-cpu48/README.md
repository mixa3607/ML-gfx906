# CPU48 final candidates: six flags with and without HC mix/split

## Results

Both approved runs completed on 2026-11-01 with exit code 0: `six` at
16:44:15–16:59:46 UTC, then `six-hc-mix` at 17:00:23–17:14:41 UTC.
See [all pooled and best-of-two tables](comparison.md), the
[machine-readable comparison and selected case IDs](comparison.json), and
the unchanged raw artifacts in [six](six/) and [six-hc-mix](six-hc-mix/).

| Configuration | Pooled PP tok/s | Pooled TG tok/s | PP vs saved four | TG vs saved four |
| --- | ---: | ---: | ---: | ---: |
| Saved CPU48 control | 344.69 | 35.06 | — | — |
| Saved four flags | 410.83 | 35.88 | — | — |
| Six flags | 381.26 | 35.29 | -7.20% | -1.64% |
| Six flags + HC mix/split | 404.12 | 34.77 | -1.63% | -3.08% |

Adding HC mix/split to six flags measured **PP +5.99%, TG -1.47%** overall.
The PP gain is concentrated at 16384/32768 (+7.73%/+12.81%); shorter PP
groups decline by 4.81–7.16%. TG improves at PP16384 (+9.86%) but declines
in the other four groups. The separate best-of-two view has the same direction
in every per-length PP/TG comparison; it does not change this tradeoff.

The six-flag combination did not reproduce the sum of the individually
selected gains. Neither new combination exceeds the saved four-flag result
in pooled PP or TG. This does not isolate draft cost versus trim or establish
that either flag is guaranteed harmful: both were added together, and the
four-flag reference ran at 14:14:40–14:28:10 UTC, before these candidates.
The control ran at 11:54:36–12:11:42 UTC. No new control, rerun, exclusion or
additional variant was performed. HC mix remains undecided, and the active
baseline and individually selected values remain unchanged.

### Validation and limitations

- Hash manifests and recorded script/input hashes verify for both new arms
  and both saved references. Effective settings differ only as intended;
  pinned image, executable/source, model metadata, frozen cases and original
  expert-profile seed match the reference. Maya v1.1.45 source
  `6ecbd3cbc5330b57f70cd5cf8a5c42eb8ef950cc`, ROCm 10.1, 4 × MI50 32GB.
- All 44 requests completed TG256, with zero KV reuse and no slot activity.
  All 20 measurements are retained, including `six` PP32768 times of
  86545.8 and 77873.7 ms; the corresponding HC-mix times are 72022.0 and
  73725.0 ms. No cause for the time differences was established.
- Both arms passed HC checks on four GPUs at one/16 rows, route checks at
  one/three/16 rows, and trim checks on four GPUs including `copy_regions`
  and all 12 ordered hand-off pairs. Draft-cost reports appear on all 22
  requests per arm; HC mix activation appears only in the second arm.
  These native checks are not a full-answer parity or quality test.
- Both arms copied all 10647 CPU-lane experts into RAM (200.2 GB across two
  NUMA parts), with 200.9 GB pinned. Pod cgroup peaks were 218.87/218.66 GiB
  against 220 GiB; all `memory.events` counters stayed zero. Peaks include
  preparation and file cache, not just live model allocations.
- Accepted/offered drafts were 1288/1739 (74.07%) and 1266/1720 (73.60%),
  versus 1299/1636 (79.40%) for saved four. With the cost policy enabled,
  offered lengths and histories can differ; acceptance alone is not a speed
  or quality verdict and combines DSpark with prompt lookup.
- Each log still contains two `rocblaslt error` entries for
  `TensileLibrary_lazy_gfx906.dat` and 12 `hipModuleLoad failed` entries, as
  do the saved references. Requests completed, but the preferred hipBLASLt
  path is not verified by these runs.
- Both test pods were deleted. Recorded cleanup samples and a subsequent
  read-only check show all four GPUs at 0% utilization and 10 MB VRAM used.

## Approved scope and decisions

Exactly two serial full-suite runs over the unchanged CPU48 baseline:

| Arm | Overrides |
| --- | --- |
| `six` | `DS4_SKIP_UNPICKED=1`, `DS4_HIP_ATTN_SWIZZLE=1`, `MAYA_DS4_HC_FUSE=2`, `MAYA_DS4_ROUTE_FUSE=2`, `MAYA_DS4_DRAFT_COST=1`, `MAYA_DS4_DECODE_TRIM=15` |
| `six-hc-mix` | Same six settings plus `MAYA_DS4_HC_MIX_SPLIT=1` |

Draft cost `1` and decode trim `15` are accepted individually by task agreement.
Retain `DS4_ENGRAM_CACHE_MB=256` and unset/default-off Markov Q8. HC mix/split
remains undecided; the second run differs from the first only in this setting.
These are test candidates, not an adopted production configuration or an
automatic change to the active baseline. No extra control, variants, threshold
screening, GitHub push or production deployment is part of this task.

## Method

Keep the captured [CPU48 baseline](../flags-cpu48/baseline-config.json), image,
source, model/drafter/vision, profiles and [test method](../top5-cpu48/README.md).
TP4, CPU48, context 524288, prefill chunk 4096, DSpark/vision on, temperature 0,
`spec=1`, `SLOT_KEEP=0`, zero KV reuse and two NUMA RAM parts remain fixed.
Each candidate gets a separate pod and fresh original expert-profile seed and
pack index; one resident engine serves 12 PP2048 warmups then ten measurements
(PP2048 through PP32768 twice, TG256). Adaptive state stays within a run.

Run only on `kube-worker6.arkprojects.lan`. Keep read-only source PVCs,
cached blobs and prepared vision references, the existing 220 GiB limit and
no CPU quota. No downloads or copies of model-weight files, profile substitution,
ROCm/library replacement or bypass of native parity guards. Export evidence,
delete each test pod and verify idle GPUs. Setup/runtime errors stop the queue;
slow measurements alone do not.

Require full CPU-expert RAM copies and pinning, unchanged nonexperimental
settings and identities, both HC/route multirow check suites, all trim-bit
checks including mapped hand-offs, and draft-cost diagnostics. The seventh
setting also needs its activation log. Reuse the recorded memory wrapper and
runner, capturing `memory.peak`/events and verifying no OOM. Native checks do
not establish whole-answer parity or quality.

## Comparisons

Primary: `six-hc-mix` versus `six`, both newly measured. Also compare both
against the saved [CPU48 control](../flags-cpu48/README.md) and
[four-flag combination](../combos-cpu48/README.md). No fresh control is run;
old references may include inter-block drift. Do not add/multiply individual
gains or claim statistical significance from these single serial runs.

Keep raw results and primary pooled rates (total tokens / total native time),
excluding warmups. Separately provide per-length best-of-two PP and TG maxima
with selected case IDs and comparisons using the same best-of-two convention.
The two cases at each length are different prompts, not identical repeated
inputs. PP/TG maxima can select different cases and differ across candidates;
this optimistic view is not a pooled result or one jointly observed request.
No slower request is removed from the primary summary. Draft acceptance
combines DSpark and prompt lookup; native timings are not client TTFT.

## Execution and CPU-only analysis

Real GPU use and pod creation/deletion need explicit approval. From repo root:

```bash
python3 project-maya/ds41-optimization/results/final-candidates-cpu48/scripts/run.py six
python3 project-maya/ds41-optimization/results/final-candidates-cpu48/scripts/run.py six-hc-mix
```

Existing result directories cannot be overwritten. CPU-only recomputation:

```bash
python3 project-maya/ds41-optimization/results/final-candidates-cpu48/compare.py
```

CPU-only tests, without engines or Kubernetes:

```bash
cd project-maya/ds41-optimization/results/final-candidates-cpu48
python3 -m unittest -v
```

CPU validation: 11 benchmarking tests and 9 candidate-specific tests passed.
The latter cover exact six/seven-flag isolation, default cache/Markov values,
both combined configurations and native-check coverage, missing checks,
unexpected flags, OOM/KV reuse, independent best-of-two maxima with warmups
excluded, the required two cases per length, and complete synthetic report
generation with direct HC-mix comparison and selection provenance.
