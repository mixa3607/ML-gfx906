# Measurements, 2026-10-24–25

> **Current criterion:** full model computation and context, with ordinary
> floating-point/adaptive-cache differences allowed (approved 2026-10-25).
> No whole-engine bit-exact claim is made. Historical strict rejections below
> remain unchanged; they are not retroactive passes. Long-context retrieval,
> held-out timing and actual vision inference are still pending.

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

The user explicitly relaxed whole-engine bitwise repeatability, not the model's
compute/context requirements. RAM/NUMA/CPU/chunk choices are eligible for new
timing; approximate expert/prompt skips, reduced retention, context truncation
and extra quantization remain forbidden. YOCO1 and flow are separate checks.
The new runner does not consume or rewrite old strict verdicts/invalidation.

Prepared matrix: full copies, Engram256, CPU48/NUMA1/chunk2048 control;
CPU56 with NUMA1/2 and chunk2048/4096; repeated fresh control. All reuse the
same frozen 12-warmup/six-dev history from `fair-copy48-time-01`, without dumps.
No new performance result or final compatibility claim is available yet.

Functional validation tooling is prepared separately: exact PP32768/194560
probes with name/code records near the beginning/middle/end, finite-logit
checks, natural EOS up to 128, and GENI shapes/blank content checks without
requiring identical outputs. **These GPU checks have not run.** Local checks:
22 unit tests pass, Python compilation and shell syntax checks pass. The
ongoing runtime matrix uses the immutable `/data/bench-update-full-compute`
copy; later validation-tool edits do not change its runner between candidates.

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
