# Warm-cache LLM throughput measurement

Engine-independent procedure for **one autoregressive text request at a time**.
It measures warmed prefill and generation, not concurrent serving capacity or
general model quality. PP is the complete tokenized input; TG is the number of
generated tokens.

## Quick procedure

1. Prepare and freeze **12 different PP2048 warmup prompts**, followed by
   **six different measurement prompts: PP2048, PP4096, PP8192, repeated twice**.
   Use the real prose and task templates described in [CORPUS.md](CORPUS.md),
   not duplicated paragraphs, random tokens or a repeated benchmark question.
2. Load the model once. Send the 12 warmup requests sequentially, each generating
   TG256. Keep the engine alive: do not clear its caches or reload the model
   between warmup and measurement.
3. In that **same engine process**, send the six measurement requests in their
   frozen order, also TG256. Exclude model loading and all 12 warmups from the
   scored result. Report PP and TG separately, plus complete-request wall time.

Twelve warmups are a reproducible **starting budget**, not proof of steady
state. Retain their individual timings and cache/I/O counters. If later warmups
still show systematic drift, increase the budget for the entire comparison,
not only for a selected engine or configuration.

## What warms the cache

Use ordinary inference requests through the **same execution path** as the
measurement. They exercise kernels, memory allocators and any adaptive runtime
caches, such as expert placement or token-embedding caches. Different articles
and tasks exercise more than one hot input. Depending on the implementation,
model loading already warms some filesystem pages.

Reading weight files with `cat`, downloading weights, or sending a health check
does not replace inference warmup. Repeatedly sending the measurement prompt can
instead warm its exact prefix or output cache and overstate general throughput.
Do not drop the machine's global page cache as part of this procedure.

Keep the distinction explicit:

- **Runtime warmup:** the 12 inference requests, with their caches retained.
- **Filesystem cache:** may already be warm and may survive engine restarts.
  Record this rather than calling every new process a cold-cache run.
- **Prefix/KV and response caches:** disable reuse across these independent
  requests; they must not replace the computation being measured. Ordinary KV
  caching *within* autoregressive generation remains enabled.

## Fixed workload and controls

- Batch/concurrency: one, no overlapping requests or other inference workloads
  on the same devices. Wait for each request to finish before sending the next.
- Sampling: greedy/deterministic; target **exactly 256 output tokens**, with
  speculation disabled. Fix thinking/reasoning mode and record it. Thinking and
  non-thinking requests are separate workloads.
- Respect natural EOS. A request ending before TG256 is not a completed TG256
  sample. Preserve and report it; do not continue past EOS or silently replace it
  after seeing its speed.
- Preserve the model, tokenizer, weight precision, full input and context
  capacity. Disable approximate computation skips and input truncation. Record
  attention/KV precision and any enabled acceleration that changes computation.
- Input PP includes system text, role markers, chat template and generation
  header. Tokenize using the actual engine's tokenizer/template, not a character
  count or another model's tokenizer. Confirm the engine's reported PP matches.
- Keep context capacity, runtime options, device topology, memory limit and CPU
  allocation fixed throughout a comparison unless that setting is the explicit
  subject of the experiment. Allow enough memory for caches and buffers.
- If the engine learns a persistent placement/profile between runs, initialize
  every engine start from the **same saved seed state**, using a private copy.
  Do not let candidate B inherit candidate A's learned profile. Record any
  automatic calibration policy and use it consistently.

Use fresh independent request/session state, but retain the loaded engine and
its general runtime caches. Disable automatic prefix matching explicitly where
supported: different articles alone do not prevent reuse of a common chat
header. Require zero cross-request reused input tokens, speculative tokens and
response-cache hits. If the engine cannot expose or disable these, disclose
that limitation; do not claim verified zero-reuse full-prefill throughput.

## Which tool to use

Prefer the engine's native benchmark or protocol client **if it can send a list
of distinct prompts without restarting or resetting the engine**. A benchmark
that starts a new process for each sample, or repeatedly times one prompt, does
not implement this protocol.

Otherwise use a persistent client against the already loaded server, with
streaming timestamps and serial requests. There is no universal launch command
or configuration across engines. The required client sequence is:

```text
start engine once; wait until model loading is complete
for each of the 12 frozen warmup requests:
    send independent request, target TG256; wait; save diagnostics
for each of the 6 frozen measurement requests:
    send independent request, target TG256; wait; save timings and diagnostics
stop engine after all results have been saved
```

Do not use logit/tensor dumps, numerical-checking modes, verbose per-token
tracing or heavyweight profilers during timing. Run correctness checks
separately. Collect lightweight timestamps/counters consistently across runs.

## Metrics

For each request retain actual PP and TG, finish reason, prefill duration,
request start/end, first/last generated-token timestamps and token intervals.

| Metric | Calculation |
| --- | --- |
| PP tok/s | `input_tokens / native_prefill_seconds` |
| TG tok/s | `(generated_tokens - 1) / (last_token_time - first_token_time)` |
| TTFT | `first_token_time - request_start` |
| Complete-request wall | `request_end - request_start` |
| ITL p50/p95/p99 | Percentiles of consecutive generated-token intervals |

The first output token is normally produced by prefill, so do not count it as a
decode step. Retain native engine timings too, but label them separately if the
engine uses another convention. A stream event can contain multiple tokens;
event timestamps alone are not per-token timestamps. Without token-level data,
use documented native decode metrics and disclose the missing ITL/TG precision.

Pool **measurement requests only**, both by PP length and over the six requests:

```text
pooled_PP = sum(input_tokens) / sum(native_prefill_seconds)
pooled_TG = sum(generated_tokens - 1) / sum(last_token_time - first_token_time)
suite_wall = sum(complete_request_wall_seconds)
```

Do not take the arithmetic mean of tok/s, score warmups, or combine PP and TG
into one throughput headline. A decode improvement can hide a prefill regression.
The pooled result describes this particular input/output-length mixture.

Native protocol timings exclude the HTTP frontend. API timings include the
chosen client/network path and possibly token batching. Label the boundary;
do not compare these as if they were the same metric. If native prefill time is
unavailable, report TTFT rather than presenting `PP / TTFT` as pure prefill speed.

## Accepting and reporting a run

A complete short run contains **18 requests: 12 unscored + 6 scored**. Require
the expected input/output lengths, no truncation, zero cross-request reuse or
speculation, no computation skips, no engine errors, OOM kills or CPU quota
throttling. Check that the requested devices/topology were actually used.
Preserve incomplete/failed runs, but do not promote partial warmup to a result.

Save the frozen inputs and hashes, model/tokenizer revisions, engine build,
runtime settings, hardware/topology, memory/CPU limits, load duration, request
order and raw measurements. Track memory including charged filesystem cache
and shared memory; on shared hosts, account for known retained cache charges
outside the measured process/container. Cache-hit and I/O counters help explain
drift but are not substitutes for timing.

For A/B comparisons, give each fresh engine the same warmup history and scored
inputs. Use **A → B → fresh A**, then reverse the order in a repeat to check
filesystem-cache/thermal carryover. Freeze any additional input orders before
running them; never select the fastest order after inspecting the results.

Six scored requests are a compact **2K–8K Russian-prose throughput sample**, not
a statistically established steady-state result or a general chat benchmark.
After tuning, use an untouched article/topic split for a separate final check;
do not tune on that result. Longer contexts, code, multilingual inputs, image
requests, thinking mode and concurrency require their own suites and validation.
