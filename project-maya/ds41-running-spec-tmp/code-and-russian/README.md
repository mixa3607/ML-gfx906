# DSpark default: cache-local TypeScript, then mixed Russian prose

**Completed: fixed sequence 66/66 PP/TG-valid requests, no KV reuse. Code
decode 62.00/62.46 tok/s, acceptance 99.1%; mixed Russian decode 35.48 tok/s.
See [RESULTS.md](RESULTS.md). The pod is deleted; no more GPU runs are queued.**

Approved on 2026-10-26: first deliberately maximize expert-cache locality and
draft acceptance with **code only**, then automatically run the original
Russian multi-topic PP2K/4K/8K recipe. This approval includes the temporary
worker6 test pod, all three engine starts and cleanup, not serving changes.

Fixed setup is the runtime JSON in `../../ds41-running/dspark.yaml`: TP4,
CPU56, NUMA2, chunk2048, reserve1280, mmap-experts off, vision on, context196608,
220Gi, DSpark on/conf0.5/cum0.5/MAX0, blocks on `1,2,3`. Use the previously
tested image digest, saved original profile seed and read-only cached weights.
No parameter tuning, downloads of weights, logit dumps or expert skips.

## Frozen workloads and order

1. **code-1:** 12 warmups + 12 scored requests, PP2048/TG256. A synthetic
   TypeScript module with repetitive typed exports is cut to exact PP2048 and
   asks for a long continuation. All 24 requests intentionally use the **same
   code pattern**, with a distinct short leading nonce comment to prevent
   native KV-prefix restoration; temperature0/seed1/non-thinking. This is a
   requested favorable hot-path workload, not representative code throughput.
   Expert/runtime caches stay warm; **cross-request KV reuse remains off**.
2. **code-2:** the exact same schedule on a fresh engine, initialized from the
   same saved seed. Report reproducibility rather than choosing the faster run.
3. **russian:** a new engine/seed, no learned code profile carried over. Follow
   `../../benchmarking/CORPUS.md`: 12 distinct PP2048 warmups, then six distinct
   scored requests at **2048,4096,8192,2048,4096,8192**, all target TG256. Separate
   source articles across splits and no repeated source byte ranges.

The old full source/case files were temporary and are no longer available.
`freeze_sources.py` retains the six available archived Wikipedia revisions and
retrieves the remaining thirty pages from the original documented pool once.
`build_cases.py` reuses the original corpus builder with seed20261024. Preserve
revision URLs, license/attribution, sources, byte ranges, token IDs and hashes.
This is a **reconstruction of the original recipe**, not a byte-identical
replay or a directly paired comparison with historical TP2/TP4 results.

### Corrected harness attempt

The exact-prefix attempt stopped on its second warmup: native `DONE` reported
**2047 reused tokens** even with conversation slots disabled. `SLOT_KEEP=0`
disables stored conversations, not the live engine's own prefix checkpoints.
The native protocol has no RESET command; sending STOP does not reset those
checkpoints. No performance result is accepted from that attempt.

`run/`, `bench-attempt1.py` and `build_cases-attempt1.py` preserve this failure.
The second completed request is retained in the raw native protocol but not in
the old structured results, because validation raised before its row export.
`attempt1-native-done.json` recovers native DONE fields/output IDs only; it does
not invent missing delivery timestamps. The corrected reader exports a finished
invalid row before stopping on a validation failure.

The correction changes only a leading TypeScript nonce, while maintaining
PP2048, nearly identical code and the same long-continuation task. All 24
prefixes differ within their first 32 tokens. They are frozen before restarting
the code series from the original profile seed. The Russian cases are
unchanged. Corrected artifacts go to **`run-fixed/`**, not over the first attempt.

Both complete input files are frozen **before the first GPU request**. The
private regular drafter JSON plus cached BIN symlink uses the already-tested
preparation script `../coarse-2048-tg256/prepare.sh`. The serving PVC and HF cache
remain read-only; packs, profiles and outputs are private to the test pod.

## Validation and measurements

Report measured PP, TG and finish reason for every request. Natural EOS is
respected, never overridden; short outputs remain in the fixed schedule but
invalidate the complete TG256 suite rather than being replaced with favorable
prompts. Fatal engine/memory/hardware errors stop further GPU work. Performance
drift is reported, not used to expand this fixed run or tune its settings.

Pool **only scored requests**, with `sum(TG-1)/sum(native_decode_seconds)` and
`sum(PP)/sum(native_prefill_seconds)`. Retain separate Russian PP2K/4K/8K rates,
TTFT, wall time, acceptance, accepted/generated, native expert hits/lookups,
raw STAT values, memory, CPU and process I/O. DSpark delivers token bursts;
native timings exclude HTTP and event gaps are not per-token ITL.

Code expert-hit counters count a different routing workload than prose and
speculation changes the number of expert lookups. High acceptance alone is
not proof of higher throughput. Log output IDs and hashes to check actual
repeatability; greedy mode does not guarantee bit-identical answers on this
adaptive backend. Generated code is capped mid-completion, not a compile or
general quality test. Do not claim a global cache/acceptance maximum.

The acknowledged local collector exports every completed request and the
native logs before proceeding. `run-fixed/` survives pod failure. Cleanup is followed
by read-only verification of idle GPUs and unchanged serving replicas.
