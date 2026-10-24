# DS4.1 single-request tuning

See [REQUIREMENTS.md](REQUIREMENTS.md) for the fixed constraints. Runtime
candidates are experimental until functional and performance checks pass.

**Current policy (2026-10-25):** preserve model computation and context, allowing
ordinary floating-point/adaptive-cache differences. Identical generated text
is not required. The earlier strict parity failure remains historical evidence,
not a blocker under this policy and not a retrospective strict pass. Finalists
still need real long-context retrieval checks and image inference. See
[RESULTS.md](RESULTS.md) for completed versus pending validation.

## Full-compute comparison (current approach)

`full_compute.py` is separate from the historical strict timing gate. It only
accepts the fixed model/runtime/precision/context/vision/DSpark settings and an
explicit allowlist of RAM/NUMA/CPU/chunk/cache choices. It rejects unknown args,
expert skips (including AUTO), YOCO2, custom YOCO retention and quantization
options. The engine clears inherited `DS4_*`, `STRATA_DS4_*`, and `MAYA_DS4_*`
variables before applying the checked configuration. YOCO1 is allowed only via
`STRATA_DS4_PROMPT_SKIP=1`, with no retention override; it is **off** in the
initial runtime matrix. Flow is not yet allowlisted: inspect/validate it in a
separate approach before enabling it. No unsupported `DS4_SKIP_UNPICKED` flag.

With the existing approved pod/GPU run, reuse the already frozen development
history rather than regenerating inputs or accessing holdout for tuning:

```bash
python /data/bench/full_compute.py \
  --cases /data/runs/fair-copy48-time-01/cases.jsonl \
  --out /data/runs/full-compute-runtime-01 --run
```

Omit `--run` to prepare configs/plan without GPU work. The matrix uses full
RAM copies and Engram256 throughout: CPU48/NUMA1/chunk2048 control, then
CPU56/NUMA1/chunk2048, CPU56/NUMA2/chunk2048, CPU56/NUMA1/chunk4096,
CPU56/NUMA2/chunk4096, then a fresh control repeat. This isolates CPU/NUMA/chunk
comparisons without repeating the established mmap-versus-RAM experiment.
Each run has the same 12 warmups and six scored requests, an independent seed
profile and lane calibration, and no logit dumps. Timing eligibility in
`plan.json` is **not** quality/context validation or a claim that every numerical
difference is small. Strict verdicts and invalidation markers are untouched.
Engine errors, incomplete copies, reuse, speculation, expert skips, short EOS,
non-finite native times, OOM and CPU throttling fail the run. Compare paired
PP/TG/wall metrics with the repeated control; do not infer quality from speed.

### Functional checks for finalists

These are separate from TG256 performance and do not require identical text:

- `context_check.py prepare --source /data/wiki-final.jsonl --out <cases.jsonl>`
  creates one exact **PP65536** fact-retrieval probe (user-requested 64K ceiling).
  Three complete artificial
  name/code records sit near token128, halfway through the context, and near
  its end. The final question includes names but not answers. Development prose
  supplies non-repeated filler; no holdout articles are used for these probes.
- `context_check.py run --config <finalist.json> --cases <cases.jsonl> --out <run>`
  checks all three name/code associations and finite full-vocabulary logits,
  allows natural EOS up to 128 tokens, and preserves full PP/context. Use a
  checked config with trailing `--verbose` to log actual YOCO1 activation;
  enabling the flag alone is not evidence that the runtime used it.
  Add `--vision` to check the shapes/blank images in that same loaded engine,
  avoiding another full model load. Full-logit dumps are validation-only.
- `vision_check.py --functional --baseline <control.json> --candidate <finalist.json>
  --out <run>` sends real GENI images through the upstream image frontend:
  red rectangle/blue circle and a white blank control. It checks finite logits
  and descriptions, not parity. The conservative keyword checks require manual
  inspection if they fail; they are not a broad vision-quality evaluation.

Run the same context probes on the no-skip control and finalist. A retrieval
pass is bounded evidence, not proof of arbitrary-context quality. A failed
control cannot validate a candidate. Functional outputs/timings are never pooled
into TG256 performance results. The final frozen holdout timing suite remains a
separate check after selecting the configuration.
The prepared 128K/194K inputs are historical only: do not execute them. The
context probe runner rejects PP above 65536; keep the server capacity at 196608.

The user-built v1.1.27 image has a separate digest-pinned manifest,
`pod.v1.1.27.yaml`. Its 8Gi memory request is only a scheduling reservation;
the approved retry cap is 187Gi, leaving up to 5Gi for the stopped old pod, and there
is no CPU quota. Never run GPU engines
in both test pods concurrently. Account for shared file-cache charges retained
by the old pod before treating a cross-pod comparison as a verified 192Gi result.
Set `BENCH_PEER_CGROUP` to that pod's cgroup path for the v1.1.27 runs. Snapshots
record peer charges and reject a new-pod limit plus peer usage above 192Gi.
This accounts for the known peer pod, not arbitrary unrelated host cache users.
**The earlier 185Gi attempt OOMKilled during warmup.** That configuration is
retained in commit `c6312af`; the current manifest is the explicitly approved
187Gi retry, not a validated memory recommendation. See RESULTS.md for outcomes.

### Durable capture outside the pod

Enable `BENCH_STREAM_EVENTS=1` for the remote runner and execute it through
the local collector, for example:

```bash
python3 capture_run.py --out /tmp/opencode/ds41-v127-time-02 \
  --expected-results 18 -- kubectl -n apps-ml exec maya-ds41-bench-v127 -- \
  env BENCH_STREAM_EVENTS=1 BENCH_PEER_CGROUP="$OLD_POD_CGROUP" \
  python /data/bench-retry-187gi/native_bench.py \
  --config /data/finalist-timing.json --cases /data/frozen-dev.jsonl \
  --out /data/runs/finalist-v127-time-02
```

The collector fsyncs manifest, READY metadata, complete request records, and
functional vision/verdict records on the local machine as they arrive. A pod
OOM cannot delete those copies. It preserves nonzero remote exit status and
rejects an apparently successful run with fewer than the expected requests.
Record emission happens after each request's timings are captured; performance
dumps remain off. Completed records survive, but an in-flight killed request
cannot be reconstructed. Keep the original frozen configs/cases locally too.
`OLD_POD_CGROUP` must be set to the inspected old pod's `/sys/fs/cgroup/...` path.

### YOCO1 as a separate approach

`variants.py --yoco1-only --out <configs>` generates the CPU56/NUMA2/chunk4096
finalist with only `STRATA_DS4_PROMPT_SKIP=1` changed. `yoco1-validation.json`
also enables verbose logging for the real 64K/vision gate; `yoco1.json` keeps
the original timing arguments. No `DS4_YOCO_KEEP` override or mode2 is allowed.
The functional gate requires an actual log entry for layers 20–39, **2668 kept
rows** (the model's default dependency-safe calculation), and early+kept equal
to the complete PP65536. A flag alone or a short-prompt no-op is not a pass.
Only after this gate passes should the frozen warm development suite be timed.
Compare with the existing v1.1.27 control at the same memory partition; do not
use diagnostic dump-enabled prefill times as the benchmark headline.

## Fixed workload

- One request at a time, TG256, greedy sampling, no speculative decoding.
- Text cases use DeepSeek's chat/non-thinking mode (`reasoning_effort=none`).
  Thinking workloads need separate measurements; this fixed workload choice
  is not an optimization attributed to RAM copies.
- PP is the **complete tokenized prompt**, including the DeepSeek chat header,
  and is a multiple of 2048. Current test lengths: 2048, 4096, 8192, 16384,
  32768, 65536. The previously prepared 131072/194560 cases are not to be run.
- Every runtime allocates for context 196608 and loads the native vision tower.
  Vision-enabled text timing is not proof of successful image inference.
- Pod memory limit: 192 **GiB**, including charged file cache and shared memory.
  No CPU quota. CPU requests are scheduling/weight hints, not a performance
  guarantee; inspect competing work and all ancestor cgroups.
- Keep quantization, source revision, model computation, and GPU topology fixed
  while testing storage/cache/CPU scheduling changes first.

## Warm, without memorizing the test

Keep the engine alive between requests, preserving experts and Engram rows.
Do not repeat the same prompt to warm it. Use separate warmup, development,
and held-out articles; shuffle topics using a recorded seed. Ordinary Russian
vocabulary can overlap; exact source passages must not. `corpus.py` records
source byte ranges and consumes each passage at most once in a case file.
Source article IDs must also be disjoint across the three splits.

The first corpus is Russian Wikipedia prose with varied requested output forms
(explanation, critical analysis, dialogue, presentation, etc.). This is **not**
a validated sample of all Russian chat, slang, code, or document workloads.
Extend with those genres before claiming general-purpose results. Medical and
legal articles are performance inputs, not advice or correctness references.
Sources include revision URLs, text hashes, and attribution/license metadata.

Use a fixed warmup budget for every candidate. Record the first/cold requests
separately. A two-request screening warmup is **not steady-state evidence**.
For the full comparison start with 12 distinct PP2048/TG256 warmup requests,
then development requests; compare the warmup's trajectory to detect remaining
drift. If that budget is insufficient, revise it for **all** variants, not just
the slower one. Use multiple frozen orders for finalists. Do not tune on the
held-out results. Include a separate held-out-domain/topic-switch stress slice.

The native protocol automatically reuses matching KV prefixes. There is no
generic `RESET` command. Independent prompts differ early, and the runner
**rejects any request reporting nonzero reused tokens**. Conversation slots,
disk expert skipping are explicitly disabled. Prompt skipping is off in the
runtime matrix; only dependency-safe YOCO1 may be tested separately. Natural EOS
is respected: a short answer fails TG256 rather than being counted as TG256 or
continued past EOS. No output-cache hits or speculative tokens are accepted.

## Reproduction

The pod is pinned to the inspected v1.1.26 image digest (Git commit
`f26d8bab43f9b10f0475986b541dc46ada45285e`, patched engine-source fingerprint
`d755c2b1d3c8f655`), ROCm 10.1, gfx906. Read the test-stand skill and obtain
permission before creating it or running GPU work. The HF PVC is read-only;
pack/vision conversion and results go to the pod's own `/data`. Never copy GGUF
blobs, drop the node's global page cache, or modify another pod for this test.

```bash
# Local: small HTTP downloads only, with source attribution. --resume can
# continue an interrupted acquisition without overwriting saved source texts.
python3 corpus.py fetch --out /tmp/opencode/ds41-wiki.jsonl

# After explicit Kubernetes/GPU approval:
kubectl apply -f pod.yaml
kubectl -n apps-ml wait --for=condition=Ready pod/maya-ds41-bench --timeout=300s
kubectl -n apps-ml exec -i maya-ds41-bench -- bash < prepare.sh
kubectl -n apps-ml cp . maya-ds41-bench:/data/bench
kubectl -n apps-ml cp /tmp/opencode/ds41-wiki.jsonl maya-ds41-bench:/data/wiki.jsonl
```

Inside the benchmark pod:

```bash
python /data/bench/corpus.py build --source /data/wiki.jsonl \
  --out /data/warm.jsonl --split warmup --count 12 --pp 2048
python /data/bench/corpus.py build --source /data/wiki.jsonl \
  --out /data/dev.jsonl --split dev --count 8 --pp 2048 4096
cat /data/warm.jsonl /data/dev.jsonl > /data/cases.jsonl
python /data/bench/native_bench.py --config /data/bench/baseline.json \
  --cases /data/cases.jsonl --out /data/runs/baseline-01
```

Long cases need enough **unused real text**. The builder fails if the corpus is
too small; do not fill the gap by repeating documents. A complete long-context
suite may need additional articles. Freeze source/case manifests before a
comparison. Do not regenerate a new random corpus for each candidate.
For the existing `/data/heldout-final-01/cases.jsonl`, create a new filtered
case file retaining warmups and holdout requests only through PP65536. Preserve
the original file and record both hashes; do not execute its larger cases.

For the final held-out long suite, `--task-position end` keeps the actual
question after the documents when truncating to exact PP. This avoids putting
up to 194K tokens between the task and generation, matching document-then-question
usage. It changes neither existing frozen inputs nor the front-task development
timing suite. Cases record the placement; held-out performance is not a direct
paired comparison with differently formatted development cases. The final
held-out run uses seed 20261025 (a different warmup/source order) after the
configuration is selected, with no further tuning on those results.

`variants.py --out /data/configs` generates one-factor screening candidates:
4 GiB Engram cache, 56 CPU threads, 38 threads confined to NUMA node 0's CPUs,
or 64 GB of protected CPU expert copies (one NUMA part, keeping the full row
reduction). CPU affinity is **not** a strict NUMA memory policy. All four
inspected GPUs attach to node 0 over PCIe 4.0 x16.
Do not run any candidates concurrently. Each run starts with its own copy of
the same seed expert profile and an independent PCIe lane calibration file.

The C++ binary consumes legacy `STRATA_DS4_*` names directly; `maya.py` normally
translates the public `MAYA_DS4_*` names. `baseline.json` uses the native names
deliberately rather than silently leaving computation skips enabled.

## Historical strict numerical gate

The following scripts describe approach 1, committed as `467e6d2`. They retain
their strict criteria and rejection markers for reproduction; use the separate
full-compute entry point above for the current policy, not a bypass of this gate.

Run a baseline replay **against itself first**, then compare candidates on the
same ordered input history. Use `--dump` in separate numerical-validation runs:
every prompt-last/output-step f32 logits row is SHA-256 hashed. Raw dumps are
removed after hashing; hashes and generated token IDs remain in results.

```bash
python /data/bench/native_bench.py --config /data/bench/baseline.json \
  --cases /data/cases.jsonl --out /data/runs/validate-a --dump
# Repeat as validate-b, then compare:
python /data/bench/compare.py /data/runs/validate-a/results.jsonl \
  /data/runs/validate-b/results.jsonl --require-logits
```

Token equality alone, a tolerance/KL test, or an identical final answer does
not satisfy the bit-exact gate. Passing finite checks is evidence for those
tested rows, not a mathematical proof for arbitrary prompts or contexts.
History-dependent cache placement may itself affect numerics: if baseline
replay fails, investigate before calling a candidate bit-exact. Changing TP,
prefill chunk shape, or CPU/GPU computation placement is not automatically safe.

After the baseline replay passes, `bash /data/bench/screening.sh` runs the four
one-factor candidates sequentially on the frozen short case file. Each gets a
separate numerical verdict; rejected candidates are not timing finalists.
Engine/load failures stop the batch rather than running more work on a device
whose state might be unknown. This screening does not establish steady-state
speed or long-context parity.

`variants.py --full-copy-only --out /data/full-copy-configs` prepares the
historical RAM-copy strategy without lowering context or turning vision off.
The two candidates use one/two NUMA parts; both must match baseline logits.
The runner rejects silent partial-copy fallback. Unlike the upstream strict
RAM test switch, this does not override the engine's RAM safety budget.
See [RESULTS.md](RESULTS.md) for the old branch's actual 2K/8K measurements
and the important differences in corpus, repetition, and configuration.

After the full single-part copy gate passes, `bash /data/bench/extended-gate.sh`
tests CPU56, then a 4 GiB Engram cache, then chunk4096, all with full single-part
copies. It adds fresh PP4096/8192 development inputs to the short parity history
and runs a new mmap reference. It does not use the held-out corpus for tuning.
Even a combination of independently accepted changes must pass again.

`bash /data/bench/timing.sh` benchmarks **only** accepted gate configs, verifying
their saved hashes before use and recording their tested PP coverage in
`eligibility.json`. By default it selects the extended-gate shortlist. It
creates a new frozen case
file: 12 distinct PP2048/TG256 warmups, then six scored development requests
(two each at PP2048/4096/8192). Dumps are off. Run order is mmap control,
accepted candidates sequentially, then a fresh mmap control. Outputs are also
compared for token consistency across the complete history. No warmup is scored.
`BENCH_RUN` selects a fresh output directory; `BENCH_SEED` selects a recorded
source order for a repeat (default 20261024). This longer batch can take hours
on the test stand; do not run a second GPU job alongside it. A second control
is needed to assess carryover rather than claiming a gain from one fast sample.

The accepted CPU48 full-copy point can instead be selected explicitly:

```bash
BENCH_GATE=/data/runs/full-copy-screen-01 \
BENCH_CANDIDATES=copy-all-numa1 BENCH_RUN=fair-copy48-time-01 \
  bash /data/bench/timing.sh
```

Its original full-logit gate covers PP2048, not PP4096/8192; the recorded
coverage must not be silently upgraded by a token-consistency timing run.
Rejected CPU56 combinations remain rejected.

`timing.sh` also refuses a gate directory containing `invalidation.json` from
a later failure. Historical successful verdicts remain intact for provenance.
The CPU48 selection example above is now blocked by that marker.

`bash /data/bench/diagnose-cache.sh` is a separate diagnostic: mmap and full
copies with `--no-expert-cache` are compared on PP2048/8192, then the stock
expert-swap byte checker is exercised with adaptive caching enabled. Freezing
placement changes the reference policy; a pass there is **not** permission to
claim parity with the original adaptive run or to waive a failed comparison.

Pool scored rates reproducibly, excluding warmup and exposing dump-enabled runs:

```bash
python /data/bench/summary.py \
  /data/runs/fair-copy48-time-01/control-a \
  /data/runs/fair-copy48-time-01/copy-all-numa1 \
  /data/runs/fair-copy48-time-01/control-b
```

Timing runs must have dumps **off**. Report PP tok/s from native prefill time;
TG tok/s as `(N-1)/(last_token_time-first_token_time)`, excluding the first token
already computed by prefill. Also retain the engine's native DONE times, TTFT,
wall time, ITL p50/p95/p99, per-request expert/cache/I/O stats, cgroup memory,
OOM events and CPU throttling. Native TTFT excludes the HTTP frontend, so label
it accordingly. No combined PP/TG headline that hides a regression in one phase.
Use paired comparisons by PP length and fixed order, then reverse run order to
check persistent file-cache/thermal carryover. Do not count warmup as scored.

The reboot gives an initial cold-cache reference. Later runs share the pod's
charged file cache: report that explicitly rather than claiming each run is
cold. Cgroup `file` and `memory.current` must be tracked alongside host memory
because shared pages charged to other cgroups can otherwise mask the RAM cap.

Copy results to local storage before any approved pod deletion; `/data` is an
ephemeral volume. Stop the engine after each run and verify idle GPUs. Pod
deletion is a separate Kubernetes write requiring approval.

## Local checks

```bash
python3 -m unittest discover -s . -p 'test_*.py' -v
bash -n prepare.sh
```
