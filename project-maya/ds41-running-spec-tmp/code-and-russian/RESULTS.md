# DSpark default: 62 tok/s on cache-local TypeScript, 35.48 on mixed Russian

## Outcome

The corrected sequence completed **66/66 requests**, all with **TG256**, full
requested PP and **zero cross-request KV reuse**. It contains two independent
code starts (12 warmups + 12 measurements each), then a separately seeded
Russian start (12 warmups + six PP2K/4K/8K measurements). No settings were tuned.

The intentionally favorable code workload achieved **62.00 / 62.46 decode
tok/s**, **99.14 / 99.18% draft acceptance** and **98.69 / 98.70% native decode
VRAM-expert hit ratio**. Fresh-start decode difference was **+0.73%**. All
**48 code outputs were token-identical**, including warmups, despite the small
input nonce differences. This is bounded evidence of a predictable, cache-local
hot path, **not representative TypeScript throughput or a global maximum**.

The requested Russian multi-topic suite then completed automatically:
**35.479 pooled decode tok/s**, **81.00% acceptance**, with prefill
**89.20 / 88.38 / 89.74 tok/s at PP2K / PP4K / PP8K**. It validates the fixed
TG256 workload, not arbitrary output quality, vision or long-context behavior.

## Code: favorable expert locality and acceptance

| Fresh start | Scored requests | PP | TG | Prefill tok/s | Decode tok/s | Acceptance | Decode VRAM expert hits | Scored wall, s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| code-1 | 12 | 2048 | 256 | 88.327 | 62.004 | 2544/2566 = 99.14% | 752903/762900 = 98.69% | 327.624 |
| code-2 | 12 | 2048 | 256 | 92.483 | 62.458 | 2544/2565 = 99.18% | 752716/762660 = 98.70% | 314.760 |

Accepted drafts supplied **82.8125%** of generated code tokens in each scored
start. Per-request measured decode ranged **60.70-62.59** and **62.01-62.88
tok/s**. Decode reproduced closely; prefill and full-request wall were less
stable, so the +0.73% decode repeat does not establish identical overall timing.

The source is a synthetic TypeScript module containing a type definition and
many same-shaped numbered exports. The task requests 128 further exports.
Exact PP2048 prefixes use the same pattern, with a unique short leading
TypeScript comment. Adjacent prefixes differ at token index **8 or 9**, which
prevents native prefix-checkpoint restoration without deliberately diversifying
the expert-routing workload. Both starts use the same frozen ordered inputs.

The output consistently continues `entry0079`, `entry0080`, etc. It is capped
at 256 tokens mid-module, so this is **not a compile or functional code test**.
The code source, rendered inputs, output IDs/text and hashes are retained.

### Observed warmup

| Start | First three warmups, decode tok/s | Last three warmups, decode tok/s | First-three expert hit ratio | Last-three expert hit ratio |
| --- | ---: | ---: | ---: | ---: |
| code-1 | 46.90 | 62.44 | 58.41% | 98.58% |
| code-2 | 47.48 | 62.36 | 58.35% | 98.55% |

Acceptance was already about 99.1% in the first three warmups. Rising routed
expert VRAM hits alongside higher decode throughput is consistent with cache
warming on this workload; no cache-off comparison was run to isolate causality.
The same favorable pattern was exercised intentionally during warmup and
measurement. This does not follow the separate-input general-traffic protocol
and must not be presented as an independent code holdout.

## Russian: full PP2K / PP4K / PP8K timing suite

Twelve distinct PP2048 warmups preceded six scored requests in the order
**2048,4096,8192,2048,4096,8192**. All 18 prompts and outputs were distinct.

| Actual PP | Scored requests | Actual TG per request | Prefill tok/s | Decode tok/s | Acceptance | Decode expert hit ratio | Scored wall, s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | 2 | 256 | 89.200 | 34.161 | 82.45% | 90.79% | 60.853 |
| 4096 | 2 | 256 | 88.376 | 39.523 | 79.84% | 88.99% | 105.602 |
| 8192 | 2 | 256 | 89.738 | 33.352 | 81.02% | 89.68% | 197.877 |
| All scored | 6 | 256 | 89.268 | 35.479 | 793/979 = 81.00% | 89.81% | 364.331 |

Accepted drafts supplied **51.63%** of generated tokens. Per-request decode
ranged **32.81-40.24 tok/s**. Different topics/tasks and outputs are paired
with the different PP lengths, so this table is not an isolated context-length
scaling experiment. In particular, the higher PP4K decode is not proof that
longer input makes decoding faster.

Scored lead articles were **Пищеварение, Иммунная система, Спектроскопия,
Страхование, Волейбол, Русская литература**. Other articles supplied unused
material when needed. The original builder, task templates and seed20261024
follow `../../benchmarking/CORPUS.md`. Source byte ranges do not overlap and
warmup/development page IDs are disjoint.

The full historical frozen corpus was no longer available. Six archived source
revisions were retained; the remaining thirty pages were fetched once from
the original documented pool. Therefore this is a **reconstruction of the
original recipe**, not a byte-identical rerun or a matched performance comparison
with the historical `prefill.yaml`/`decode.yaml` results. All source text,
revision/attribution/license records, source hashes and tokenized cases now
live in this directory rather than temporary storage.

## First attempt and correction

The initial exact-prefix attempt executed two warmups, then stopped because
the second request reused **2047 KV tokens**. Conversation slots being off did
not disable the live native engine's own prefix restoration. This attempt is
**not scored** and was not mixed into either corrected code result.

`run/` retains its original manifest/logs and first structured row. The old
reader raised before exporting the second completed row; both requests' native
DONE fields and output IDs were recovered from the protocol into
`attempt1-native-done.json`, without inventing delivery timestamps.
`bench-attempt1.py` matches that attempt's recorded runner hash.

The nonce correction was frozen before restarting, and the two code starts
plus Russian suite were then run from the common original seed. Corrected
artifacts are in **`run-fixed/`**. Including the failed attempt, four engines
were loaded and **68 requests** completed; only the fixed 66-request sequence
constitutes this result. There were no additional performance retries, grid
searches or EOS overrides.

## Runtime, validation and evidence

- Runtime settings match `../../ds41-running/dspark.yaml`: four MI50 32 GB on
  worker6, TP4/uneven whole-block split, CPU56/NUMA2, chunk2048, reserve1280,
  mmap-experts off, Engram256/ring400, vision on, context196608, native FP4 KV,
  DSpark on/conf0.5/cum0.5/MAX0, drafter blocks on `1,2,3`, 220Gi, no CPU quota.
- Same tested image digest
  `sha256:3cf3dba357c941a190630b0fcf33efd501fe693d9510fa7332522f4b072e30d3`,
  source `6afa525bbabc3a8f5fd165f89e9bc72155d9bd39`, same model/tokenizer/drafter
  revisions and prepared pack hashes as the prior DSpark screens.
- Every start used a private copy of the original saved seed profile, SHA-256
  `bcfd7697fc070b0ebcb0138c0ef029429ea0d4ff81ca60eeb7804e08efd0cd29`.
  The Russian engine did not inherit a code-trained profile. General filesystem
  cache can persist across starts; no cold-cache claim is made.
- All corrected requests reported full PP and `TG=256, finish=length`, with
  zero reuse. Full **10631/10631 CPU-expert copies**, effective TP4/context/vision
  and drafter placement were verified. No OOM, CPU throttling or native `ERR`;
  approximate skips were disabled and none were reported.
- Every engine still emitted the known missing gfx906 rocBLASLt/Tensile/
  hipModuleLoad diagnostics. All requests completed, but this is not a clean
  backend/library validation or a general correctness proof.
- Post-request anon+shmem+kernel was approximately **198.08-198.99Gi** across
  the fixed starts. Charged current memory, including file cache, reached
  about **217.84Gi** in the saved request snapshots; these are not memory-minimum
  measurements and do not validate a 200Gi deployment.
- Rates pool scored tokens over native time; first-token generation is excluded
  from decode via `TG-1`. Native timing excludes HTTP. DSpark emits bursts, so
  event gaps are not per-token ITL. Expert hit ratios are the native DONE
  **decode routed-experts-in-VRAM / all decode routed experts**, not CPU-cache,
  filesystem-cache or response-cache hits. Acceptance is accepted/offered drafts.
- **17 CPU-only tests passed** after the correction. `verify_results.py`
  independently recomputes pooled/by-PP metrics, checks all 66 raw rows, source
  and input hashes, output identity, session counters and cleanup. Its output
  is `verification-output.txt`.
- `run-fixed/summary.json`, per-session configs/manifests/results/native logs
  and chronological events preserve the full evidence. Local fsync/ACK
  checkpoints and 15-second memory snapshots survived independently of emptyDir.

The pod was deleted; all four GPUs returned to 0% activity/about 10 MB used.
The serving Deployment remained at zero and its manifest/PVC and HF cache were
not modified. Cleanup evidence is `cleanup.txt`, `pods-after-cleanup.json`,
`gpu-after-cleanup.txt`, `processes-after-fixed-run.txt` and
`deployment-replicas-after.txt`.
