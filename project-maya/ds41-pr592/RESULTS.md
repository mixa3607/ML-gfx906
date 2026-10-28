# TP2 baseline collected; PR #592 fails the runtime gate

Date: 2026-10-28. **There is no valid baseline-versus-PR speed comparison.**
The unchanged v1.1.34 engine generates successfully at the approved TP2
settings. The PR image builds and loads, enables peer transport on both GPU
pairs, then rejects its first prompt after peer-reduction timeouts. No PR
benchmark or fresh baseline A2 was run after this failed gate.

## Configuration

- Four AMD Instinct MI50 32 GB / gfx906; PCIe pairs GPU0/1 and GPU2/3, TP2.
- ROCm 10.1; model DeepSeek-V4.1-Flash-1017 UD-Q8_K_XL, existing DSpark drafter.
- Base settings from [`values.dspark.yaml`](values.dspark.yaml), changing only
  `--tp 4` to `2` and `DS4_DRAFT_DEV=1,2,3` to the approved `0,1,1`.
- Prefill chunk 2048, maximum context 196608, TG target 256, 56 CPU threads,
  reserve 512 MiB, DSpark/vision on, mmap off, 220 GiB limit, no CPU quota.
- All 10218 CPU-lane experts copied into RAM; same expert slots in both images.
  The PR allocated an additional 80 MiB per GPU after placement.
- Greedy native requests, seed 1, one request at a time, original DSpark and
  suffix lookup retained. Zero cross-request reused tokens required.
- Original profile seed SHA256:
  `a9e8219fd4c34ddfa6be80528eb8834322d791d783a1a08364d6f987be00b999`.
- Final ordered input SHA256:
  `36205b13258fe95826ca0a8dcf7437553b45704fcd5e73fbd9b590c22d06ae57`.

Exact image/source identities, model snapshot paths, frozen token IDs and
attributed prose sources are retained in this directory; see [README.md](README.md).
Models and the existing data PVC were mounted read-only. No weights were
downloaded or copied.

## Baseline v1.1.34

The unscored gate loaded in 250.80 s and completed PP2048/TG32 with coherent
Russian output. The scored process was a separate start (301.13 s load), with
12 PP2048/TG256 warmups followed by eight measurement requests. Warmups and load
time are excluded below. Each nonzero context has two complete TG256 requests.

| Requested input/context | Actual PP | PP, tok/s | Native decode, tok/s | Actual TG |
| ---: | ---: | ---: | ---: | --- |
| 0 | 1 (BOS) | — | — | 135, 165; natural EOS |
| 4096 | 4096 | 150.51 | 25.88 | 256, 256 |
| 8192 | 8192 | 185.88 | 28.10 | 256, 256 |
| 16384 | 16384 | 204.73 | 24.56 | 256, 256 |

Rates pool tokens over native time, separately for PP and decode. Decode uses
`sum(TG-1) / sum(decode_seconds)`, not the engine log's `TG / decode_seconds`.
These are native-protocol boundaries, not HTTP throughput or individual-token
latencies. No throughput is reported for incomplete BOS-only requests.

All 20 requests executed without KV reuse, computation skips, OOM kills or CPU
quota throttling. The full-suite `complete` flag is nevertheless **false**:
the two zero-context requests did not reach TG256. Per-context eligibility and
raw counters are in [`summary.json`](summary.json) and
[`A-baseline/results.jsonl`](A-baseline/results.jsonl).

This is one short warm-cache series, not a statistically established steady
state. Identical warmup inputs in the rejected first attempt and final A did
not produce identical token sequences despite greedy sampling and seed 1;
content-dependent DSpark decode therefore has an observed reproducibility
limitation even without the PR. No improvement or bitwise-output claim follows.

## PR #592 failure

Source: `9a0876f5861de25f4cb56b7e19e1c8b63704dcda`.
Image: `registry.arkprojects.space/apps/maya-gfx906@sha256:3063e35de96907d8624df4f2a6ebf0905fd56de168cf6583762b25134ae903a5`.

With `DS4_HIP_PEER_AR=1`, load completed in 236.53 s and logged:

```text
ds4: exact peer prefill all-reduce enabled on HIP0/HIP1 (80 MiB/rank)
ds4: exact peer prefill all-reduce enabled on HIP2/HIP3 (80 MiB/rank)
```

The first PP2048/TG32 gate request produced **zero generated tokens** and failed:

```text
ERR peer all-reduce failed; model state invalid, reload required
```

| GPU | Rank | Failed sequence | Observed sequence | First failing block | Elapsed ticks | Timeout ticks |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 7 | 5 | 6 | 50000004 | 50000000 |
| 1 | 1 | 7 | 5 | 27 | 50000004 | 50000000 |
| 2 | 0 | 1 | 0 | 32 | 50000000 | 50000000 |
| 3 | 1 | 1 | 0 | 15 | 50000004 | 50000000 |

Every diagnostic reports `error=1`, `stream_status=0`, `copy_status=0` and last
submitted sequence 40. The payload is `n4=2621440` (2048 × 5120 floats);
the configured deadline is two seconds. This demonstrates a transport timeout
on this setup; it does **not** establish whether peer visibility, scheduling or
another implementation/hardware detail caused it. No timeout increase, driver
tuning, GPU remapping or source fix was attempted.

There were no OOM kills. The engine rejected the request and exited on QUIT;
all GPUs returned to idle. Missing gfx906 rocBLASLt library warnings occurred
in both images, including the successful baseline, and are not established as
the cause of the new transport failure.

Evidence: [`startup-pr592/result.json`](startup-pr592/result.json),
[`startup-pr592/engine.log`](startup-pr592/engine.log),
[`startup-pr592/protocol.log`](startup-pr592/protocol.log).

## Rejected attempt, checks and cleanup

- `attempt1/` preserves the original ordered cases and partial baseline. A
  BOS-only request before PP4096 caused upstream to reuse a one-token
  checkpoint. The series was rejected. Moving BOS-only requests to the end
  preserved every input's IDs and yielded verified zero reuse in final A.
- The first harness launch failed to resolve the container's nested cgroup
  path before starting the engine; its traceback is retained in
  `startup-harness-error.txt` and the path handling was corrected.
- Candidate remote build and runtime-library validation passed. Local harness
  unit tests, shell syntax checks, frozen-input hash checks and `git diff --check`
  passed. Raw console output retains progress CRs/padding and is excluded from
  whitespace checks by the local `.gitattributes`. No standalone peer primitive
  test or model-level fault injection ran.
- Both task pods were deleted; unrelated workloads and production values were
  not modified. [`gpu-after-cleanup.txt`](gpu-after-cleanup.txt) records **0% GPU
  usage and 10 MiB VRAM used per GPU**.

Further peer-transport diagnosis or a test-only fixed-token/EOS-override
benchmark requires a separately agreed scope.
