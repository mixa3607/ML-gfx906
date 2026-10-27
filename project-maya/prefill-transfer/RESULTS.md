# TP4 prefill transfers on four MI50s, 2026-10-27

## Outcome

**Use the PR 520 transfer path; keep `DS4_SKIP_UNPICKED=0`.** The warmed
2K–8K suite improved from **91.06–92.64 to 200.41 tokens/s** in an A/B/fresh-A
comparison. Full scored-request wall time fell **47.0–47.7%**. Native decode
was **35.45** versus **36.27–37.21 tokens/s** (2.3–4.7% lower), not a demonstrated
decode gain. Adaptive placement, timing and generated sequences vary between
starts; do not describe this as identical decode performance.

On the build that also contains the opt-in PR 297 port, with pruning disabled,
chunk4096 reached **225.21 pooled prefill**, **241.25 at PP8192**, and **35.97
decode tokens/s**. Versus that same build's preceding chunk2048 control it
improved pooled PP **10.1%** and wall **6.5%**, with decode **2.7% lower**.
This chunk comparison is sequential, not a separate repeated A/B/A.

PR 297 really skipped transfers but slowed prefill **4.7–4.9%** relative to its
two disabled controls. Do not enable it for this workload. This result does
not establish its effect on other quants, prompts or cache residency.

## Matched runtime

- Node `kube-worker6.arkprojects.lan`, four MI50 32 GB, gfx906, ROCm 10.1.
- Host exposes 76 CPUs, two sockets/NUMA nodes (38 CPUs each), kernel
  `6.8.0-147-generic`; CPU model string `Genuine Intel(R) CPU 0000%@`.
- Upstream v1.1.30, `8621e33159f426da2d376be4ec012b0ce8fe2948`, max-ILP HIP
  scheduling and the existing gfx906 compatibility fixes.
- Unsloth DeepSeek-V4.1-Flash-1017 UD-Q8_K_XL, snapshot
  `60ad3651641b5c97679c807e064ab1d7a3ca1455`; routed experts MXFP4.
- Production's existing DSpark/vision pack, TP4, DSpark on/conf0.5/cum0.5,
  blocks on devices1/2/3, context196608, CPU56/NUMA2, reserve512, ring400,
  Engram256, mmap-experts off, native vision loaded, no CPU quota, 220Gi cap.
- Each engine starts from the same private expert-profile seed, SHA-256
  `83dff518ffa650d8350fc625c7bcf2a033f8792280007b4073c2b0949c6ef1b5`.
- Frozen Russian suite SHA-256
  `b880c6551696301e314e14ca8a1065563dfc8d8e8d0bb2195f5a4d63e7dd90a3`.
  Existing inputs and source/license records remain in
  `../ds41-running-spec-tmp/code-and-russian/russian-{cases,sources}.jsonl`.
- Every timing start runs 12 distinct PP2048/TG256 warmups and six distinct
  PP2048/4096/8192/TG256 measurements, in that order twice. Temperature0,
  independent inputs, no cross-request KV reuse, no approximate computation
  skips. DSpark remains enabled in all timing arms.

All **126 timing requests** completed TG256/finish=length, plus **12 separate
PP2K/PP4K diagnostic requests** of 16 tokens. Startup, warmups, logit dumps and
load-time byte checks are excluded from scored timing. Rates pool tokens/time;
native decode uses TG minus one. HTTP and network latency are not measured.

## Timing

| Start | PP2K | PP4K | PP8K | Pooled PP | Decode | Six-request wall, s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Stock A | 88.20 | 92.18 | 91.24 | 91.06 | 37.21 | 356.01 |
| PR520 B, chunk2048 | 182.83 | 199.71 | 205.71 | 200.41 | 35.45 | 186.25 |
| Fresh stock A | 89.92 | 92.17 | 93.58 | 92.64 | 36.27 | 351.71 |
| PR520+297, pruning off A | 197.19 | 206.44 | 206.17 | 204.91 | 37.77 | 180.46 |
| Same build, pruning on B | 184.17 | 194.94 | 197.82 | 194.94 | 36.68 | 188.82 |
| Same build, fresh pruning off A | 196.87 | 205.26 | 206.11 | 204.50 | 36.95 | 181.63 |
| Same build, pruning off, chunk4096 | 188.25 | 217.62 | 241.25 | 225.21 | 35.97 | 169.87 |

Throughputs are tokens/s. Each PP bucket contains two distinct requests, not
confidence intervals. Filesystem cache can survive process/pod restarts. These
are development inputs, not an untouched holdout or proof of a global optimum.

## Correctness and resource checks

- Actual TP4/context and native vision loading verified from READY, not flags
  alone. Every timing arm copied **10459/10459** CPU-lane experts into RAM.
- Direct transfer logs confirm approximately **195.9 GB** pinned for DMA.
  `DS4_COPY_PIN=0` fallback was checked in a separate fresh engine.
- Each patched diagnostic's native checker passed **32 expert-part byte
  comparisons**, covering RAM/file sources, all four members and rotations,
  with destination guards. Its independent reference is the original GGUF file.
  Four-member numerical TP comparisons passed for all four rotations.
- Stock versus compact staging, compact staging versus direct DMA, and pruning
  off versus on each produced **byte-identical complete logit dumps and the
  same 16 output tokens** for both diagnostic inputs. All captured logits were
  finite. This is bounded short-input parity with fixed expert placement
  (`--no-expert-cache`), not whole-engine adaptive or arbitrary-input bitwise
  determinism. Timing uses normal adaptive caching and can generate different
  sequences across starts.
- Pruning activation was real: each GPU skipped **3602** unpicked transfers at
  PP2048 and **6857** across PP4096's chunks. Reduced payload is not a speed gain
  when waiting for routing removes useful look-ahead overlap.
- No OOM or CPU throttling in any session. Maximum observed cgroup peak was
  **210.58 GiB**; chunk4096's pod peak reached **206.53 GiB**. Some peaks include
  earlier diagnostic sessions in the same pod. These are not minimum-RAM claims.
- The existing missing gfx906 hipBLASLt/Tensile/hipModuleLoad diagnostics remain
  in both stock and patched engines. Requests and checks passed, but this is not
  a clean backend-library validation or a fix for those diagnostics.
- No 64K/192K workload, actual image request, concurrency or task-quality suite
  was run in this experiment. Configured context and a loaded vision tower are
  not substitutes for those checks.

## Artifacts and deployment

Build patch directories:

- `../build-context/patch/v1.1.30-transfer/`: gfx906 fixes + transfer-only PR520.
- `../build-context/patch/v1.1.30-transfer-prune/`: the same + opt-in PR297 port.

Private images under `registry.arkprojects.space/apps/maya-gfx906`:

| Variant | Tag | Index digest |
| --- | --- | --- |
| Transfer only | `v1.1.30-rocm-10.1-transfer520-20261027-pp01-pre` | `sha256:a620d20efd4c717bc97f5cc8916c117fe5b30f4015c2d8d302dfadac108b9550` |
| Transfer + opt-in pruning | `v1.1.30-rocm-10.1-transfer520-prune297-20261027-pp01-pre` | `sha256:488bc84ebb935fed13cd396157060f3fbbbca08387a561aaf17d9ae46ceacc08` |

The exact measured chunk4096 candidate is the **second image with
`DS4_SKIP_UNPICKED=0`**, not pruning enabled. The lean first image was measured
at chunk2048 only; do not label its chunk4096 performance separately verified.

Bounded manifests, raw timing rows, diagnostic logs, comparison verdicts and
hashes are exported to [evidence/](evidence/). Full streamed events and binary
logits are retained in `/tmp/opencode/maya-prefill-20261027` and copied to the
git-ignored `../logs/prefill-transfer-20261027/`; large raw artifacts are not
committed. `analyze.py` independently recomputed all seven timing summaries.

The test pod was deleted. Before restoring serving, all four GPUs were idle,
approximately 10 MB used each. Deployment `maya-ds41` was restored to its original
one replica and **original public image/configuration**, not switched to a
candidate. Existing data and HF PVCs were mounted read-only throughout; only
small pack metadata, tokenizer and profile copies were made. No models were
downloaded, no release/public image was overwritten, and no GitHub push or
workflow dispatch was performed.

The restored deployment subsequently completed rollout: its original image
digest matches the captured baseline, one pod is Ready with zero restarts, and
the test pod is absent (`evidence/serving-restored.json`).
