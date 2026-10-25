# DSpark: faster decode, no full-request gain in the short screen

## Verdict

With `--dspark on` and `DS4_DRAFT_DEV=1,2,3`, the pooled native decode rate
increased **27.93 -> 36.22 tok/s (+29.7%)**. This passes the pre-agreed 10%
coarse-screen threshold and justifies a separate full A/B, not automatic
promotion to the serving default.

Prefill decreased **88.69 -> 80.91 tok/s (-8.8%)**. The three scored requests
took **96.67 -> 97.06 seconds (+0.4%)** overall: essentially no request-wall
gain on this PP2048/TG256 mixture. Longer outputs were not tested.

The default drafter placement on GPU0 did not reach READY: it was OOM-killed
at 220Gi. Do not infer a throughput or acceptance result for that mode.

## Scored results

Every completed start used the same three unscored warmups, followed by three
scored requests. Each request fully prefills 2048 tokens and generates 256,
greedy, non-thinking, natural EOS, one request at a time, zero cross-request
reuse and no approximate expert skips. A and C each completed all six requests.

| Mode | Prefill tok/s | Native decode tok/s | Scored wall, s | Draft acceptance |
| --- | ---: | ---: | ---: | ---: |
| A: `--dspark none` | 88.69 | 27.93 | 96.67 | n/a |
| B: `--dspark on`, default placement | n/a | n/a | n/a | OOM during load |
| C: `--dspark on`, `DS4_DRAFT_DEV=1,2,3` | 80.91 | 36.22 | 97.06 | 410/503 = 81.5% |

Pooled prefill is `sum(PP) / sum(native_prompt_seconds)`. Native decode is
`sum(TG - 1) / sum(native_decode_seconds)`, not the engine log's `TG/time`.
Delivery-based decode rates are 27.9298 and 36.2167 tok/s, respectively. These
are native-protocol measurements, not HTTP latency or frontend throughput.
DSpark delivery is bursty; no token-level ITL claim is made.

| Scored article | A decode tok/s | C decode tok/s | C/A gain |
| --- | ---: | ---: | ---: |
| Книгопечатание | 27.67 | 33.46 | +20.9% |
| Вулкан | 28.01 | 37.54 | +34.0% |
| Электрический двигатель | 28.11 | 38.03 | +35.3% |

C's accepted drafts supplied 410/768 = **53.4%** of the generated tokens.
Total native prefill was 69.2734 s for A versus 75.9344 s for C; decode was
27.3896 s versus 21.1212 s. The prefill loss offset the decode savings.

## Correctness and limitations

**Greedy outputs are not token-identical.** All six A/C sequences differ.
For the three scored requests the first differing token is at zero-based
indices 19, 48 and 73. This run does not establish why they differ: no
logit-level or reference-quality validation was approved or run. Do not claim
bit-exact decoding, equivalent answers or a measured quality improvement.

Completed A/C requests had no native `ERR`, cancellation, short EOS, input
truncation, cross-request reuse, OOM-kill delta or CPU-quota throttling. Native
STAT records reported zero skipped experts. However, both A/C startup logs
contain missing gfx906 rocBLASLt/Tensile/`hipModuleLoad` diagnostics during the
first warmup. Inference continued and every request completed. Those messages
are retained; this is not a clean-library-backend validation.

This is a fixed-order, three-warmup/three-measurement screen, not an A/B/A or
reverse-order repeat. Warmup decode rates still varied: A 19.95/25.17/25.69,
C 29.20/33.09/33.66 tok/s. Different articles also change routing. No stable
steady state, statistical confidence or general traffic representativeness
is established. No long-context, image, thinking, sampled-output, concurrency
or long-generation performance/correctness check was run.

## Runtime, memory and placement

- Four AMD MI50 32 GB on worker6, ROCm 10.1, gfx906. Hardware inventory is in
  the parent directory's `hardware-*.json`.
- Same image digest for all starts:
  `sha256:3cf3dba357c941a190630b0fcf33efd501fe693d9510fa7332522f4b072e30d3`;
  source commit `6afa525bbabc3a8f5fd165f89e9bc72155d9bd39`.
- Same UD-Q8_K_XL model, cached GGUF revision
  `60ad3651641b5c97679c807e064ab1d7a3ca1455`, same pack index hashes.
- TP4, context capacity196608, actual KV format `fp4`, CPU56, chunk4096,
  reserve1280, mmap-experts off, native vision loaded on GPU0. No Maya
  autocalibration. Full explicit options are in each run's `config.json`.
- Each container: 220Gi memory limit, no CPU quota, effective cpuset 0-75.
  C's native log confirms block 0 on GPU1, block 1 on GPU2, block 2 on GPU3;
  TP4 and vision are verified by READY metadata, not just requested flags.
- All CPU-lane experts were copied: A **10219/10219 (192.1 GB)**;
  C **10722/10722 (201.6 GB)**. Main-model VRAM expert slots per member
  decreased from 5141 to 4638 when C loaded its drafter.
- B copied **11935/11935 (224.4 GB)** before the cgroup OOM at
  **2026-10-25 21:43:05 UTC**. Kernel evidence and final Kubernetes
  `OOMKilled` status are `kernel-after-b.txt` and `pod-after-run.json`.
- Both A/C charged nearly the 220Gi cap, including reclaimable filesystem
  cache. That is not a measured 220Gi minimum. At the end of the last scored
  request, anon+shmem+kernel was approximately **192.42Gi for A**, **201.23Gi
  for C**. C's anon+shmem alone was 200.54Gi. Do not assume the current 200Gi
  production limit can support this exact C configuration; only 220Gi was
  successfully measured.

A completed in the first retry pod, then B's group OOM killed that container.
Only the still-unstarted C was run in a replacement pod with the identical
220Gi manifest. A/B were not repeated: three total engine starts. Filesystem
cache/ownership can change after an OOM and across pod replacement; this is
an additional ordering/accounting limitation. Model loading is not scored
(A 325.2 s, C 265.4 s).

## Reproducibility and evidence

- Combined metrics: `run/summary.json`; A/B artifacts: `run/`; C: `run-c/`.
  Each collector's `exit.json` records the exit code and saved-result count.
- Full inputs/token IDs and Wikipedia revision/license attribution are the
  parent directory's `cases.jsonl`, `cases.manifest.json`, `sources.jsonl`.
  Their exact hashes and the common original profile hash are in both manifests.
- `seed-profile.bin` preserves that original profile, SHA-256
  `bcfd7697fc070b0ebcb0138c0ef029429ea0d4ff81ca60eeb7804e08efd0cd29`.
  Each start used a private copy, never a previous run's updated profile.
- `screen-abc.py` and `screen-c.py` preserve the exact runner sources; their
  hashes match the corresponding manifests. The latter adds single-mode CLI
  selection only. Export code and collector tests are in the parent directory.
- Config, start/READY/final manifests, completed results, native stdout/stderr
  and 15-second cgroup snapshots were continuously exported to the local
  repository. The collector fsyncs and ACKs each checkpoint outside timed
  requests. B's OOM did not lose A's results or B's diagnostics.
- Nine CPU-only tests passed, including simulated exit-137 evidence retention.
  Source hashes, frozen cases, original profile and pack hashes were checked.

Both temporary pods were deleted. Final read-only inspection confirms no test
pod, all four AMD GPUs idle at about 10 MB each, and the production Deployment
still at zero. See `cleanup-b.txt`, `cleanup-c.txt`, `pods-after-cleanup.json`,
`gpu-after-cleanup.txt` and `deployment-replicas-after.txt`. `decode.yaml` and
production PVC/HF cache contents were not modified.
