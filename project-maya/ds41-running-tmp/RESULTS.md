# Measurements, 2026-10-24–25

> **Current criterion:** full model computation and context, with ordinary
> floating-point/adaptive-cache differences allowed (approved 2026-10-25).
> No whole-engine bit-exact claim is made. Historical strict rejections below
> remain unchanged; they are not retroactive passes. The CPU56/NUMA2/chunk4096
> finalist passed 64K retrieval and actual vision smoke on both v1.1.26 and
> v1.1.27. Final held-out timing remains pending.

## Completed cache/source diagnosis (approach 1 follow-up)

Recovered after the server restart without rerunning GPU work:
`/tmp/opencode/ds41-cache-diagnosis-01`, copied from
`/data/runs/cache-diagnosis-01`.

- Frozen placement (`--no-expert-cache`): mmap CPU48 versus full-copy CPU48
  and CPU56 each passed **512/512 full-vocabulary logit rows** across PP2048
  and PP8192, with finite logits and matching generated tokens.
- Adaptive full-copy CPU48 with `DS4_CHECK_SWAPS=1`: **507** logged byte checks
  matched the model file, **zero** MISMATCH lines. The checks actually executed.
- This bounds the evidence: no source-byte or fixed-placement discrepancy was
  found in these cases. It does not prove global adaptive determinism, nor that
  arbitrary token divergences are harmless. Diagnostic timings include dumps
  and are not warm performance comparisons.

## Approach 2: full-compute runtime matrix

**Subsequent user instruction:** long-context validation is capped at **64K**
(65536 prompt tokens), while configured capacity remains 196608. The prepared
128K/194K cases will not be executed. This limits the scope of verified context
behavior; a 64K pass must not be reported as a tested 192K workload.

The user also provided and approved sequential testing of
`mixa3607/maya-gfx906:v1.1.27-rocm-10.1` in a separate pod after this matrix.
Registry index digest:
`sha256:d46312703b79af1cd70174ae9ef2faee23875db9c51f90353424aba6101ac2c1`;
linux/amd64 manifest:
`sha256:ef40b51b57820f5770ad3dd7d852fe14bfc9639913a19e9bd125c13618e638f2`.
The first v1.1.27 attempt failed at the reduced 185Gi cap. The approved 187Gi
retry completed; its exploratory comparison is reported below.

The user explicitly relaxed whole-engine bitwise repeatability, not the model's
compute/context requirements. RAM/NUMA/CPU/chunk choices are eligible for new
timing; approximate expert/prompt skips, reduced retention, context truncation
and extra quantization remain forbidden. YOCO1 and flow are separate checks.
The new runner does not consume or rewrite old strict verdicts/invalidation.

Completed matrix: full copies, Engram256, CPU48/NUMA1/chunk2048 control;
CPU56 with NUMA1/2 and chunk2048/4096; repeated fresh control. All reuse the
same frozen 12-warmup/six-dev history from `fair-copy48-time-01`, without dumps.

| CPU / NUMA parts / chunk | PP2048 | PP4096 | PP8192 | Pooled TG | Scored wall s |
| --- | ---: | ---: | ---: | ---: | ---: |
| 48 / 1 / 2048, control A | 91.17 | 116.35 | 134.69 | 21.466 | 308.266 |
| 56 / 1 / 2048 | 91.77 | 113.73 | 131.77 | 21.183 | 313.248 |
| 56 / 2 / 2048 | 98.63 | 129.55 | 149.03 | 22.184 | 283.689 |
| 56 / 1 / 4096 | 93.36 | 129.06 | 171.94 | 21.610 | 273.449 |
| **56 / 2 / 4096** | **103.36** | **132.72** | **173.59** | **22.228** | **264.585** |
| 48 / 1 / 2048, control repeat | 91.40 | 110.23 | 135.65 | 21.393 | 311.454 |

Rates pool measured tokens/time; startup and the 12 warmups are excluded. The
best measured point improves aggregate PP **21.1–22.6%**, TG **3.5–3.9%**, and
scored wall **14.2–15.0%** against the two RAM controls in this series. CPU56
alone did not help; two NUMA parts and chunk4096 matter here. These are results
for this order, not confidence intervals or a proof of a global optimum. The
earlier mmap-versus-RAM series remains a separate experiment; do not multiply
gains across series with different timings and generated outputs.

All six engines completed 18 requests with TG256, zero reused/drafted tokens,
and full CPU-expert copies. No OOM/kills or CPU throttling. The 4096-chunk
configuration held 9934 CPU experts (186.77 GB, fewer VRAM slots because of its
larger prompt buffers); chunk2048 held 9843 (185.05 GB). Charged anonymous
memory peaked around **176.1 GiB** with chunk4096 and **174.5 GiB** with
chunk2048, with file-cache reclaim inside the 192Gi cap. Startup was 209–358 s,
not scored. The original runner copy `/data/bench-update-full-compute` was used
unchanged for every candidate. Raw artifacts and pooled `summary.json` are
saved locally at `/tmp/opencode/ds41-full-compute-runtime-01` and remain in the
pod at `/data/runs/full-compute-runtime-01`.

Functional validation tooling is prepared separately: an exact PP65536 probe
with name/code records near the beginning/middle/end, finite-logit checks,
natural EOS up to 128, and GENI shapes/blank content checks without requiring
identical outputs. **At this matrix stage those GPU checks had not run** (later
results are below). Local checks at that stage: 23 unit
tests pass; Python compilation and shell syntax checks pass. The best runtime
point is a timing finalist, not yet a final context/vision recommendation.

## Approach 3: v1.1.27 comparison and bounded functional validation

Created the approved `apps-ml/maya-ds41-bench-v127` pod on worker6. Its source
commit is `4615f346d9311dd1ce9f5738ab04446f023a6e42`, engine fingerprint
`8933c5ceb60f89e7`, HIP target gfx906. Preparation uses the same read-only HF
snapshot and converts vision locally; it does not download or copy GGUF blobs.
The resulting `ds4.txt` and `tensors.txt` hashes **match v1.1.26 exactly**:

- `ds4.txt`: `e1c6053dc995b76104af2d86ee332c85ba3a1684f28c4de2e39a26c5af9bbae9`
- `tensors.txt`: `39a113954916e310dd42f2a39db7214c34fbb3a3d73723c4e2dc29e0d43c608b`
- Seed profile remains `44fb8ea94ba449b1eb2218e867453ff432613ac7fa285ba7087bd683296c97e2`.

Prepared one PP65536 functional probe: complete name/code spans at token ranges
128–148, 32768–32787, and 65331–65351. The final question contains the names,
not the codes. Both images will use the same file and the CPU56/NUMA2/chunk4096
finalist, with skips off. Context and GENI shapes/blank checks share one loaded
engine to avoid another expensive startup; dumps are enabled only for this
functional validation, never for the separate performance comparison.

The original final holdout file is preserved. A new filtered
`/data/heldout64k-final-01.jsonl` retains its 12 warmups plus six holdout requests
through PP65536, with source/selected hashes in a sidecar manifest. It has not
run. No 128K/194K request will be executed.

### v1.1.26 finalist functional result

`functional64k-finalist-v126-01` completed: all three 64K name/code associations
were retrieved correctly (544758 / 497540 / 918326). The red rectangle and blue
circle were described correctly; the blank image was described as plain white
without objects. Context and both images used natural EOS and finite-logit
validation, not TG256 timing. Source artifacts are retained at
`/tmp/opencode/ds41-functional64k-finalist-v126-01`. This is bounded functional
evidence at 64K, not verification of 192K workloads or general vision quality.

Before the v1.1.27 run, the stopped old pod retained about **6.9 GiB** of file
cache/kernel accounting. To avoid borrowing memory outside the intended budget,
the new pod was resized in place to **185Gi** (no CPU quota). The runner's
optional `BENCH_PEER_CGROUP` snapshots record the old pod and reject a new-pod
limit plus peer charge above 192Gi. Full expert copies are still mandatory;
insufficient allocation stops the test instead of accepting partial copies.
The old kubectl client cannot name the resize subresource, so the same supported
API update was sent with `kubectl replace --raw .../resize`; the pod stayed up.

### v1.1.27 attempt at 185Gi: cgroup OOM, no scored result

`finalist-v127-time-01` loaded in 240.9 s and passed the full-expert-copy guard.
It completed two warmups, then **OOMKilled the whole container** during the
third warmup. Kubernetes reports exit137/OOMKilled; the kernel reports
`CONSTRAINT_MEMCG` at the test pod's 185Gi limit, not host-wide exhaustion.
At the OOM, accounting was about **175.884 GiB anonymous + 8.507 GiB shared
memory + 0.608 GiB kernel**: essentially the entire cap, with no meaningful
reclaimable file cache left. The shared-memory charge is not evictable page
cache; anonymous memory alone was not a sufficient sizing estimate.

**This reduced limit was an experiment-side choice to account for retained
peer-pod cache. It was too tight; this is not evidence that v1.1.27 regresses or
fails at the original 192Gi budget.** No development request was scored, so the
two warmup rates cannot be used to compare image performance. The successful
v1.1.26 timings and 64K/vision result remain unchanged.

Because `memory.oom.group` killed PID1 as well, the pod is Failed/restart0 and
cannot be entered. A read-only inspection through the toolkit's host PID view
found that kubelet already removed its emptyDir contents; detailed in-pod
results/logs are unavailable. Kubernetes status and kernel OOM evidence were
saved to `/tmp/opencode/ds41-v127-oom-01`. Stdout retains the two warmup metrics.
GPUs returned to idle; no blind retry was started and no pod was deleted.

A revised retry needs an explicitly agreed replacement of the failed pod.
The old pod now retains about 4Gi; a 187Gi replacement plus peer accounting
would stay below 192Gi while adding 2Gi above the failed cap. Stream result
records outside the container so another group OOM cannot erase the evidence.
Do not treat this proposed retry as executed or as a guaranteed fit.

### Approved 187Gi retry preparation

The user approved replacing only the Failed v1.1.27 pod and retrying at
**187Gi**, retaining the same CPU56/NUMA2/chunk4096 config and frozen inputs.
The failed pod was deleted, and its replacement uses the same pinned image,
read-only HF cache and no CPU quota. The old v1.1.26 pod is untouched.

Added opt-in streamed records (`BENCH_STREAM_EVENTS=1`) and a local collector
that fsyncs manifests, READY/full-copy metadata, complete result rows and
functional records outside the pod. Missing request counts/nonzero exits stay
failures; no partial warmup is promoted to a performance result. This changes
artifact handling, not model math or the captured request timing interval.
The 187Gi timing attempt and its subsequent 64K/vision checks completed as
reported below.
Before GPU execution, 26 local unit tests passed, including collector success,
preservation after exit137, and rejection of an incomplete zero-exit stream.
Python compilation and diff whitespace checks also passed.

### v1.1.27 timing at 187Gi: completed, no demonstrated speedup

The local collector received all **18/18** complete records and exit0. Each
run used the same frozen 12 warmups plus six scored development requests,
TG256, full CPU copies **9934/9934**, vision loaded, context196608, TP2,
CPU56/NUMA2/chunk4096, Engram256, skips/speculation off, and no logits dumps.
Config and case hashes match the v1.1.26 finalist exactly. Startup was 245.7 s
and is excluded. The comparison is with that earlier finalist measurement,
not a new interleaved image A/B/A.

| Pooled metric | v1.1.26 finalist | v1.1.27 retry |
| --- | ---: | ---: |
| PP2048 tok/s | 103.36 | 92.45 |
| PP4096 tok/s | 132.72 | 130.05 |
| PP8192 tok/s | 173.59 | 175.07 |
| All scored PP tok/s | 146.48 | 142.73 |
| All scored TG tok/s | 22.228 | 21.844 |
| Six scored requests, wall s | 264.585 | 270.943 |

Observed v1.1.27 versus that v1.1.26 run: aggregate PP -2.6%, TG -1.7%, wall
+2.4%, with PP8192 +0.9%. **No speedup is demonstrated, and this is not proof
of a version regression.** The starts are sequential, cache/output histories
may differ, and memory is partitioned differently (old single pod 192Gi;
new pod 187Gi plus retained peer accounting). Do not assign these small total
differences to a particular upstream kernel or claim statistical significance.

No OOM/kills, throttling, KV reuse or speculative tokens. New-pod peak was
187.0 GiB, anonymous memory about 176.1 GiB, shared memory about 8.51 GiB.
The maximum recorded new-pod hard limit plus peer charge was **191.014 GiB**.
The peer guard accounts for the known old pod, not unrelated host cache users.
Scored decode reads were 0.107–0.160 MB/token.

Durable local records: `/tmp/opencode/ds41-v127-time-02` (manifest, READY,
request rows, after snapshot and exit.json), supplemented by the in-pod artifact
copy `/tmp/opencode/ds41-v127-time-02-pod`. The old successful/failed runs are
unchanged. The same 64K retrieval and real-image checks on v1.1.27 are reported
below, separately with finite-logit dumps; their timings are not benchmarks.

### v1.1.27 functional result at 187Gi: 64K and vision passed

The local collector reports exit0 and the complete expected context record,
plus both vision records and the final verdict. PP65536 retrieved all three
name/code associations correctly, with natural EOS after 29 output tokens.
The red rectangle/blue circle and white blank control were described correctly.
All captured context and image logits were finite, with zero KV reuse or
speculative tokens, no OOM/kills and no CPU throttling. Prompt skipping remained
off. The recorded new-pod cap plus peer charge was about 190.794 GiB at the
context checkpoint; server capacity remained 196608.

The diagnostic context prefill took 270.726 s and the full native request
272.540 s. These are **functional validation timings with dumps**, not a warm
TG256 benchmark or a paired long-context performance result. This verifies the
bounded 64K retrieval and simple real-image cases, not all tasks at 64K or
inference at 192K.

Durable local artifacts: `/tmp/opencode/ds41-v127-functional64k-02`, supplemented
by `/tmp/opencode/ds41-v127-functional64k-02-pod`. Together with the completed
timing above, the user-built v1.1.27 image works for these cases at the approved
187Gi-plus-peer budget; no additional speed benefit over manual RAM copies in
v1.1.26 was demonstrated.

## Approach 4: dependency-safe YOCO1

This is the previously approved YOCO1 check, not YOCO2 or reduced retention.
Use the same v1.1.27 CPU56/NUMA2/chunk4096/Engram256/full-copy finalist and the
same 187Gi-plus-peer budget; change only `STRATA_DS4_PROMPT_SKIP` from 0 to 1.
First replay the exact frozen PP65536 retrieval plus shapes/blank inputs with
finite-logit dumps. Require real activation on layers 20–39 with **2668 kept
rows**, not merely successful startup with an environment variable. If that
functional gate passes, time the original frozen warm development history with
dumps/verbose off, against the existing v1.1.27 no-skip result. No held-out
data is used for this tuning, and no YOCO1 gain is claimed yet.

### YOCO1 functional gate passed

The collector received the context record, both image records and exit0. The
runtime logged exactly:

```text
ds4: prompt skip: layers 20-39 from CUDA2, 62868 early rows KV-only, 2668 kept
```

All three codes at PP65536 were retrieved correctly, natural EOS after 29
tokens; red rectangle/blue circle and the white blank image were described
correctly. All tested logits were finite, with no OOM/kills or CPU throttling.
The recorded new-pod cap plus peer charge was about 190.209 GiB at the context
checkpoint. No retention override, expert skip, speculation or KV reuse.

The diagnostic prompt time was 260.935 s versus the earlier no-skip diagnostic's
270.726 s. These are separate dump-enabled functional runs, **not a verified
warm performance gain**. Pipeline overlap, chunk shapes and cache state can
change the benefit; dependency-safe pruning need not accelerate this topology.
The dump-free frozen development comparison is the next measurement.

Durable local artifacts: `/tmp/opencode/ds41-yoco1-functional64k-01`, supplemented
by `/tmp/opencode/ds41-yoco1-functional64k-01-pod`; exact candidate configs are
saved at `/tmp/opencode/ds41-yoco1-configs-01`. This is bounded functional
validation, not a proof of arbitrary-context equivalence or 192K inference.

### YOCO1 warm timing: no demonstrated gain

The dump-free candidate completed all 12 warmups plus six scored development
requests (18/18 streamed records, exit0), with the original non-verbose timing
arguments and only prompt skip changed to 1. Both starts used the same image,
seed profile, full copies 9934/9934, frozen inputs and 187Gi-plus-peer budget.

| Pooled metric | v1.1.27 skip0 | v1.1.27 YOCO1 |
| --- | ---: | ---: |
| PP2048 tok/s | 92.45 | 94.68 |
| PP4096 tok/s | 130.05 | 129.76 |
| PP8192 tok/s | 175.07 | 173.40 |
| All scored PP tok/s | 142.731 | 142.733 |
| All scored TG tok/s | 21.844 | 21.895 |
| Six scored requests, wall s | 270.943 | 270.771 |

Aggregate PP differs by about +0.001%, TG +0.24%, wall -0.06%: **no useful
speedup demonstrated**. PP2048 is below the YOCO activation threshold, so its
small change is not a skip benefit. PP4096/8192 did not improve in this single
comparison. This is not a new A/B/A or statistical equivalence proof.

No OOM/kills, CPU throttling, KV reuse or speculative tokens. Peak was 187Gi;
the maximum recorded hard-limit-plus-peer charge was 190.209Gi. Source/byte
integrity and 64K/vision checks remain passed, but correctness is not evidence
of a performance gain. **Keep YOCO off for the selected warm 2K–8K baseline.**
The separate 64K diagnostic comparison is not promoted into a timing claim.

Artifacts: `/tmp/opencode/ds41-yoco1-time-01` (durable records) and
`/tmp/opencode/ds41-yoco1-time-01-pod` (complete in-pod artifacts). Next, inspect
and screen flow/pump separately with YOCO off, starting with bounded inputs
and the native TP/flow copy checker rather than another full long-context run.

## Approach 5: bounded flow/pump screen

Inspected the shipped v1.1.27 source: the native TP checker is gated on
whole-block TP, and checks the flow's partial/whole staging against the exact
member blob with guard bytes, in addition to a finite numerical parts-versus-
whole check. The flow/pump candidates use TP2, the same CPU56/NUMA2/chunk4096
finalist, YOCO off, full copies and the same 187Gi-plus-peer budget. Whole-block
TP preserves this model's 1152/1152 FFN split (all experts MXFP4, block32), while
selecting the scratch/gather flow transfer path. It may still change packing
and resource use, so do not attribute a result solely to pump or solely to flow.

Prepared pump0 and pump1 configs with `DS4_TP_CHECK=1` and actual activation
logging. First run only PP2048 and PP4096 from the frozen development history,
TG256, finite logits, with a 600s load/request deadline. No steady-state speed
claim from this diagnostic. A checker/runtime failure stops work, not a retry
with checks disabled. Long-context/vision and warm timing require a promising
clean screen; no warm flow benefit or general long-context compatibility proof
is claimed. The bounded 64K result is reported below.

### Flow, pump0: bounded diagnostic passed

The first candidate completed PP2048/TG256 and PP4096/TG256, with finite
**512/512** full-vocabulary logit rows, exit0 and both streamed result records.
All four devices were actually activated on the flow and logged streamed
prompt work. The native numerical TP checker passed; all **four** flow-copy
checks passed byte-for-byte with their guard bytes intact. This is a real
checker execution, not a flag-only/no-op pass, and it is not a whole-engine
bit-exact claim.

The full-copy guard reports **9935/9935** CPU experts: the flow/TP path changes
packing slightly versus the previous 9934-expert baseline. No OOM/kills or CPU
throttling; recorded hard-limit-plus-peer charge about 188.078Gi. Startup was
217.5 s. Dump-enabled diagnostic PP was 88.24/120.66 tok/s and TG 16.84/20.15;
with only one short warmup these are **not steady-state speed evidence** or a
comparison against the earlier fully warmed baseline.

Artifacts: `/tmp/opencode/ds41-flow-pump0-screen-01` (durable records) and
`/tmp/opencode/ds41-flow-pump0-screen-01-pod` (complete in-pod artifacts).
Pump1 was checked separately on the exact same two inputs, as reported below.
Its subsequent 64K/vision check passed; warm timing is still in progress.

### Flow, pump1: bounded diagnostic also passed

The second candidate completed both requests with exit0, 512/512 finite logit
rows, all four GPUs active and streaming, the native numerical TP pass, and
all four guarded byte-copy checks passed. Full copies **9935/9935**, no OOM or
CPU throttling, recorded hard-limit-plus-peer charge about 187.754Gi. Startup
164.9 s. Diagnostic PP was 105.78/132.61 tok/s and TG 18.63/20.97.

Pump1 looks worth advancing, but **the two short dump-enabled starts do not
prove that pump is faster**: order, placement and cache state are uncontrolled
at this small sample size. Select pump1 as the next candidate, keeping YOCO
off and all other flow settings unchanged. First replay the frozen PP65536
retrieval and shapes/blank, require finite logits and actual 64K streamed work
on all four GPUs, then (only if passed) measure the frozen warm development
suite without dumps. The completed 64K result is below; no warm flow gain is
claimed yet.

Artifacts: `/tmp/opencode/ds41-flow-pump1-screen-01` and its complete in-pod
copy `/tmp/opencode/ds41-flow-pump1-screen-01-pod`.

### Flow/pump1 functional gate: 64K and vision passed

The collector received the context result, both image records and exit0. All
three name/code associations at PP65536 were retrieved correctly, with natural
EOS after 29 tokens; the shapes and blank image were described correctly. All
tested logits were finite, with no OOM/kills or CPU throttling. The log confirms
actual streamed PP65536 work on **all four devices**, a native numerical TP
pass, and four successful byte-for-byte flow-copy checks with guards intact.
YOCO was off. Recorded hard-limit-plus-peer charge about 187.754Gi.

The diagnostic long prompt took **393.034 s** (request wall394.730 s), versus
the earlier stock no-flow diagnostic's 270.726 s. These are separate functional
runs with dumps, not a formal warm speed comparison; the longer observed time
is nevertheless a warning against assuming flow improves long prefill.
The flow log reports zero expert-file reads, all streamed experts from RAM,
and about 107–108 s waiting for reads per GPU. Those per-device waits overlap
and must not be summed; "reads" here includes RAM staging, not proof of SSD I/O.
This identifies an observed stall counter, not a demonstrated sole cause.

Artifacts: `/tmp/opencode/ds41-flow-pump1-functional64k-01` and its in-pod copy
`/tmp/opencode/ds41-flow-pump1-functional64k-01-pod`. A dedicated warm 2K/4K/8K
run is now in progress, with the exact original 12-warmup/six-dev history,
non-verbose arguments, no logits dumps, and the load-time TP diagnostic flag
removed. Flow/whole-block TP/pump settings remain unchanged. The timing config
is saved as `/tmp/opencode/ds41-flow-pump1-timing.json`, SHA-256
`1b53066be703e87dcd92cf3cad36bcb1877ce7c242b421e3b0f1d0d20890d9cc`.

### Unrun topology option: genuine TP4 needs whole-block mode

Source inspection of v1.1.27 found an important limitation for a future TP
comparison: this model has FFN2304, 64 attention heads and 8 output groups.
Without whole-block mode, TP4 gives FFN576 per member, rejected by the native
128-value alignment rule; TP3 then fails the heads/groups divisibility checks,
so nominal `--tp 4` falls back to TP2. A calibration that only varies `--tp`
while leaving whole-block mode off therefore need not test a genuine TP4.

With whole-block mode, all-MXFP4 weights split in 32-value blocks: 72 blocks
split 18/18/18/18, so FFN576 is allowed. A real TP4 test must verify runtime
`tp_n=4`, pass the native checker, and discuss the potential TG-versus-PP
tradeoff (one pipeline group rather than two). **No TP4 GPU test has been run
or added to the currently approved TP2 flow comparison.**

## Approach 1: historical strict protocol and measurements

## Initial screening baseline (not a steady-state result)

- Image: `docker.io/mixa3607/maya-gfx906:v1.1.26-rocm-10.1`, digest
  `sha256:f0bfc1ed9525d0f99a11d6ef1f4954da4a63b393053b65e93a31ae3dfbe581b5`.
- Upstream Git commit: `f26d8bab43f9b10f0475986b541dc46ada45285e`
  (`SOURCE_COMMIT`). Patched engine-source fingerprint:
  `d755c2b1d3c8f655` (`MAYA-BUILD.json:src`), ROCm 10.1, gfx906.
- Model: cached `unsloth/DeepSeek-V4.1-Flash-1017-GGUF`, revision
  `60ad3651641b5c97679c807e064ab1d7a3ca1455`, UD-Q8_K_XL.
- Four MI50 32 GB, all attached to NUMA node 0, PCIe 4.0 x16. Host has
  76 physical/logical CPUs over two NUMA nodes, SMT disabled.
- Configuration: [baseline.json](baseline.json), TP2, 48 CPU threads,
  prefill chunk 2048, context **196608**, vision on, DSpark unloaded, no skips.
- Pod: memory 192Gi, `cpu.max = max 100000`, cpuset `0-75`.
- Every request: complete PP2048, TG256, greedy, zero reused/drafted tokens.
- This was the first model start after the user's reboot. Startup took
  121.5 s and read 324.9 GB according to the process I/O counter. It already
  warmed the file cache: the first request is not a pure cold-storage test.
- Initial case file SHA-256:
  `f3f2a3aab3a24159f8f67fd67f67df1c554a9d911a1d65c96ce612e6b382bea3`.
- Seed expert profile SHA-256:
  `44fb8ea94ba449b1eb2218e867453ff432613ac7fa285ba7087bd683296c97e2`.

| Phase / lead article | PP tok/s | TG tok/s¹ | Native TTFT, s | ITL p95, s | Decode disk MB/token² |
| --- | ---: | ---: | ---: | ---: | ---: |
| Warmup / Шахматы | 84.88 | 12.73 | 24.13 | 0.105 | 37.17 |
| Warmup / Северный Ледовитый океан | 62.53 | 9.51 | 32.75 | 0.187 | 49.32 |
| Development / Импрессионизм | 23.29 | 7.21 | 87.93 | 0.248 | 47.23 |
| Development / Авторское право | 16.43 | 8.50 | 124.69 | 0.262 | 34.19 |

¹ Client-observed `(256-1)/(last-first)`, not the engine's `256/decode_time`.
² Engine's process-read counter normalized by decoded steps, decimal MB.

Memory stayed near the hard cap (191.95–192.00 GiB); about 189.5–189.9 GiB
was charged file cache. No CPU throttling and no OOM/OOM-kill events occurred.
The cgroup did record `memory.events:max`, indicating reclaim at the limit.
Across complete requests (PP plus TG), process disk reads were 36.4, 75.2,
121.3 and 93.0 GB respectively. Decode VRAM hit rate grew from 67.2% to
90.8%, but the overall request did not monotonically speed up.

These four requests demonstrate why repeating one hot prompt is misleading:
expert hit rate alone does not characterize topic-changing prefill or the
competition between expert pages and Engram tables. They do **not** establish
that the cache is steady after two warmup requests or that topic alone caused
the slowdown. More independent prompts, orders, and repeats are needed.

The stock image logged missing gfx906 hipBLASLt/Tensile kernels and continued
through its fallback. This run completed; changing the GEMM backend has not
been tested and must not be assumed bit-exact.

Raw initial run: `/tmp/opencode/ds41-baseline-smoke` locally and
`/data/runs/baseline-smoke` in `apps-ml/maya-ds41-bench`. All completed runs
stop their engine. The sleeping pod and its ephemeral data require explicit
cleanup approval.

## Corpus preparation

Frozen source snapshot: 84 distinct Russian Wikipedia pages, 12 warmup,
24 development and 48 held-out; 4,956,450 bytes of JSONL including attribution.
Source SHA-256: `a305ecae043b5c6eddabe254528c62ab952d94de5cd5965cc840b836d1c6d178`.
Local source: `/tmp/opencode/ds41-wiki.jsonl`; pod copy: `/data/wiki-final.jsonl`.

A held-out case file was successfully prepared for PP2048, 4096, 8192, 16384,
32768, 65536, 131072 and 194560, without repeating source passages. Preparing
these cases is **not** evidence that inference at those lengths was tested.

## Baseline numerical replay

Two fresh engine starts with the same seed expert profile and ordered four-case
history produced identical output tokens and identical SHA-256 hashes for
**all 1024 full-vocabulary f32 logits rows** (four requests x TG256). The
baseline is reproducible on this tested history; this does not prove arbitrary
long-context determinism.

These were validation runs with logits dumps enabled, **not timing runs**.
Their measured times varied substantially despite identical numerics: paired
development PP ratio B/A was 1.314, TG ratio 0.877. Two cases cannot establish
a confidence interval. Do not use a single validation run to rank candidates.

Raw runs: `/tmp/opencode/ds41-validate-base-{a,b}` locally and
`/data/runs/validate-base-{a,b}` in the pod. Numerical runtime-candidate
screening follows this gate; no candidate speedup has been established yet.

## Historical 20 TG / 170 PP reference

The user's reference is confirmed in branch `add-project-maya`,
`project-maya/VALIDATION.md`, section "Ring 200 / 300 / 400 MiB", and the
retained local artifact `project-maya/logs/maya-ds41-ring-hscp4-comparison.json`.
For the 400 MiB control, pooled passes 2–3 report **22.276 TG**, **170.420 PP
at 8192 tokens**, and **93.316 PP at 2048 tokens**. The TG number is aggregated
over four requests, not exclusively the 8K request.

That runtime was v1.1.22 max-ILP, TP2, 56 threads, chunk4096, swizzle on,
reserve896, **all CPU experts copied to RAM**, context8704, vision off,
192 GB decimal RAM cap. The current experiment instead keeps context196608,
vision on, 192Gi, reserve1280 and starts with mmap/chunk2048. The old corpus
rotated six authored facts per topic into synthetic records, then repeated
the same four measured requests over three passes. KV reuse was zero, but
expert/Engram/file caches could benefit from repeated source text and topics.

Thus the historic numbers are useful and explain a stronger configuration,
but do not by themselves demonstrate a v1.1.26 regression or predict honest
topic-changing performance. That report also explicitly disclaims general
full-model bitwise parity; changed chunk/NUMA reductions need new numerical
checks under today's constraints.

Follow-up candidates use `--mmap-experts off` with one, then two NUMA parts,
retaining today's context, vision, reserve and chunk. The runner verifies the
load log actually reports **all** CPU experts copied; capped/partial fallback
is not accepted as a full-copy result. It does not force allocation past the
engine's RAM safety budget. These candidates are separate from the already
running four-point screening batch; no historical image is being deployed.

## First runtime numerical screening

Each candidate replayed the same four PP2048/TG256 requests, starting from the
same seed profile, and was compared with `validate-base-a`. Results:

| Single change from baseline | Full-logit comparison | Disposition |
| --- | --- | --- |
| Engram cache 256 -> 4096 MiB | 1024/1024 rows identical | Eligible for timing |
| CPU threads 48 -> 56 | 1024/1024 rows identical | Eligible for timing |
| 38 threads, affinity CPUs 0–37 | 1024/1024 rows identical | Eligible for timing |
| 64 GB protected expert copies, one NUMA part | First mismatch at row 12 of request 1; later tokens diverge | Rejected |

The failed copy variant had identical initial prompt logits, not an immediate
prefill discrepancy. Its later expert-promotion and CPU-lane statistics also
differed from baseline. This does not yet identify the cause: copied-source
arithmetic, asynchronous cache swaps, and cache-state changes must be separated
before attributing the mismatch to a particular mechanism. No copy candidate
is accepted merely because source tensor bytes are unchanged.

These runs used logits dumps. The apparently faster CPU56 samples (development
TG 10.98/17.56, PP 42.79/32.79 tok/s) are **not a demonstrated speedup**: the
earlier baseline replays already showed large variation. No candidate ranking
is established until dedicated repeated timing runs with the full warmup.

Raw batch: `/tmp/opencode/ds41-runtime-screen-01` locally and
`/data/runs/runtime-screen-01` in the pod. The two full-copy follow-ups are
reported below and retain the same strict numerical gate.

## Full CPU-expert copies

Both variants copied **9843/9843 CPU experts (185.1 GB)**, without reducing
context, disabling vision, or changing chunk, CPU count, reserve or precision.

| RAM layout | Full-logit comparison | Development PP tok/s | Development TG tok/s | Decode disk MB/token |
| --- | --- | --- | --- | --- |
| One NUMA part | **1024/1024 rows identical** | 92.54 / 98.24 | 20.11 / 20.54 | 0.160 / 0.115 |
| Two NUMA parts | Rejected: first mismatch at row 22 of request 1 | 107.50 / 106.12 | 21.93 / 22.22 | 0.167 / 0.115 |

Rates above are from dump-enabled **validation**, not dedicated performance
runs or a steady-state claim. Only the single-part variant is eligible for
further tuning. Its prompt-last row plus 255 decode-step rows on each of four
requests match the mmap baseline exactly; generated tokens match.

Single-part startup was 258.5 s (187.3 s copying), two-part startup 302.4 s
(205.9 s copying). Charged anonymous memory was about **174.3 GiB**, file cache
about **16.7 GiB**, total about **192 GiB**. No OOM/kills or CPU throttling.
The lower I/O is achieved by protecting expert bytes from file-cache eviction,
not by skipping experts or using fewer model weights. Startup is more expensive
and almost all RAM is committed while the engine runs.

Raw batch: `/tmp/opencode/ds41-full-copy-screen-01` locally and
`/data/runs/full-copy-screen-01` in the pod. Acceptance at PP2048 alone is not
enough for a chunk change; the extended checks below cover longer prompts.

## Combined / extended numerical checks

A new mmap reference and three combinations replayed the original four
requests, then new PP4096 and PP8192 development requests. All logit rows in
this batch were checked finite. The new reference's first four requests match
the original baseline **1024/1024 rows**, despite its different timing.

| Full one-part copies plus | First mismatch | Disposition |
| --- | --- | --- |
| CPU56, chunk2048, Engram256 | Decode row 15 of request 1 | Rejected |
| CPU56, chunk2048, Engram4096 | Decode row 15 of request 1 | Rejected |
| CPU56, chunk4096, Engram4096 | Prompt-last row of request 1 | Rejected |

The chunk4096 combination reached 170.68 PP8192 and 20.82 TG in validation,
reproducing the historical order of magnitude under today's capacity/vision
settings. It is nevertheless **not an accepted bit-exact optimization**.
Independent passing knobs are not assumed safe when combined. Asynchronous
cache swaps are a possible explanation for late decode-only differences, not
a proven cause and not grounds to waive the numerical criterion.

Raw batch: `/tmp/opencode/ds41-combined-screen-01` locally and
`/data/runs/combined-screen-01` in the pod. No custom image has been built.

## Full-warm A/B/A timing

The remaining short-gate finalist is **CPU48 / full one-part copies /
chunk2048 / Engram256**, not any rejected CPU56 combination. A dump-free
A/B/A batch compares it with the original mmap baseline. Each fresh engine
gets 12 independent PP2048/TG256 Russian warmups, then six new development
requests (two each at PP2048/4096/8192), with identical order and separate
seed-profile copies. No source passage repeats within a case file.

Raw batch: `/tmp/opencode/ds41-fair-copy48-time-01` locally and
`/data/runs/fair-copy48-time-01` in the pod. The batch records numerical-gate
coverage in `eligibility.json`: the finalist's full-logit evidence so far covers
PP2048 only. Full-history output-token consistency is an additional rejection
check, **not** a replacement for full-logit proof at longer PP lengths.

All three runs completed without dumps or profiling. Each of the 18 requests
produced TG256 with zero reused/drafted tokens. All **4608 output token IDs**
(warmup included) match across mmap A, RAM-copy B and mmap A-repeat. Their
per-request CPU-expert and promotion counters also agree. No OOM/kills or CPU
throttling; all runs reached the 192Gi cap with file-cache reclaim.

Rates below pool token counts / measured times, not arithmetic means of rates.
TG uses 255 transitions per request, excluding the prefill-sampled first token.
Warmup and startup are excluded; there are only two scored cases per PP length.

| Metric | mmap A | Full copies, one part | mmap A-repeat |
| --- | ---: | ---: | ---: |
| PP2048 tok/s | 75.36 | **111.24** | 66.12 |
| PP4096 tok/s | 100.80 | **143.28** | 96.25 |
| PP8192 tok/s | 118.87 | **160.83** | 120.73 |
| All scored PP tok/s | 104.85 | **146.39** | 101.40 |
| All scored TG tok/s | 19.50 | **21.66** | 19.30 |
| Six scored requests, wall s | 351.91 | **266.53** | 362.05 |
| Startup s, excluded | 151.95 | 168.58 | 128.44 |

Against the two controls: aggregate PP **+39.6–44.4%**, TG **+11.0–12.2%**,
and scored request wall time **24.3–26.4% lower**. These are measured effects
for this frozen order and workload, not confidence intervals or a global
optimum. In particular, the earlier cold-ish 7–8 TG samples are **not** the
denominator for the warm decode gain.

| Complete PP | Mean native TTFT, mmap controls | Mean native TTFT, copies |
| --- | ---: | ---: |
| 2048 | 27.18 / 30.98 s | **18.41 s** |
| 4096 | 40.64 / 42.56 s | **28.59 s** |
| 8192 | 68.92 / 67.86 s | **50.94 s** |

Per-request ITL p95 ranges: **48.3–49.6 ms** with copies versus
**57.3–65.0 ms** in the controls. Decode storage reads: **0.113–0.161 MB/token**
with copies versus **1.851–5.246 MB/token** in the warm controls.

The warmup's early expert misses settle substantially before scoring (CPU-lane
experts fall from 78.6/token on request 1 to about 19–24 near its end; scored
requests use about 16–23). The varied corpus is not a formal stationarity
proof. A separate full-logit replay of this complete warmup/scoring history
failed, as detailed below. The held-out long-context suite and actual image
request have not run.

## Complete warm replay: short-gate acceptance invalidated

The original mmap configuration and CPU48/full-one-part-copy configuration
replayed all 18 requests with finite full-vocabulary logits captured. Despite
the earlier short pass and matching output tokens in the dump-free A/B/A,
the RAM replay diverged at **row 4 of the first request**; its first different
generated token was at zero-based position **132**. Subsequent prompt logits
and generated token sequences also differed.

This is the **same first prompt, initial profile, binary and configuration**
as the earlier successful RAM replay. The new mmap reference still matches
all 256 first-request logits of the original reference. After eight generated
tokens, the original/reference/earlier-RAM promotion counter is 5.714/token,
whereas the new RAM replay reports 5.571; CPU experts are 151.714 versus
152.000/token. This directly demonstrates variable cache activity, but is not
yet proof that tensor copies are corrupt or that arithmetic changed.

Thus a successful short comparison cannot be treated as a persistent approval
of adaptive RAM-copy mode. Its raw successful result is preserved, with a
separate `invalidation.json` appended to its gate directory; `timing.sh` refuses
such invalidated candidates. The measured warm speed benefit remains real for
that workload, but it is **not an accepted bit-exact speedup**.

Raw failed replay: `/tmp/opencode/ds41-fair-copy48-parity-01` locally and
`/data/runs/fair-copy48-parity-01` in the pod. A bounded diagnostic now freezes
expert placement for mmap/copy48/copy56 on PP2048 and PP8192, and separately
exercises the stock byte-for-byte GPU/RAM expert-swap checker. Frozen-policy
parity, if it passes, will not silently replace the original adaptive reference.
