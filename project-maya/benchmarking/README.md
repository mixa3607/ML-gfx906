# Warm-cache LLM benchmarking

How the benchmark suites in this directory are built, frozen and measured.
It measures **one autoregressive text request at a time** - warmed prefill and
decode on an already loaded engine - not concurrency, not answer quality and
not cold-start latency.

- [SUITES.md](SUITES.md) - how corpora and suites are structured and frozen.
- [benchkit.py](benchkit.py) - the shared implementation: fetch, exact-length
  cutting, checks, manifests, reports.
- [freeze.py](freeze.py) - the command line around it.
- `corpora/` - model-independent text: article pools, tasks, frozen sources.
- `suites/` - one directory per measured workload: model, encoder, schedule,
  frozen cases.

## Layout

```text
corpora/<corpus>/     corpus.py, sources.jsonl, SOURCES.md, README.md
suites/<suite>/       suite.py, cases.jsonl, suite.json, CASES.md,
                      cases.manifest.json, README.md
```

A **corpus** is text and tasks (what is read). A **suite** is a corpus plus a
model, tokenizer, chat encoder and PP/TG schedule (how it is measured). The
same corpus can feed several suites; every suite freezes its own token ids.

## Corpora

| Corpus | Language / domain | Pools | Used by |
| --- | --- | --- | --- |
| [ru-prose](corpora/ru-prose/) | Russian Wikipedia prose, six writing tasks | 12 warmup, 24 dev, 48 holdout (not shipped) | [ds41f-ru](suites/ds41f-ru/) |

## Suites

| Suite | Model | Warmup | Measured | TG |
| --- | --- | --- | --- | ---: |
| [ds41f-ru](suites/ds41f-ru/) | deepseek-v4.1-flash | 12 x PP2048 | 2 x (PP2048, PP4096, PP8192, PP16384, PP32768) | 256 |

Each suite directory has its own `README.md` (what and why), `CASES.md` (every
request in feed order, readable) and `suite.json` (the order for a runner). The
frozen requests themselves are in `cases.jsonl`.

## Terms

**PP** - prefill, the complete tokenised input: system text, chat template,
the question, the material and the assistant header. Not a character count and
not the context-size setting. A suite fixes PP per case and the generator cuts
only source prose to reach it.

**TG** - target generation (decode) tokens. It is a request parameter, not part
of the frozen data. Greedy decoding, speculation off. Natural EOS is respected:
a request that stops early is kept and reported, never topped up.

**Warmup** - ordinary inference requests sent before the scored ones, on the
same engine process and execution path. They warm kernels, allocators and any
adaptive caches (expert placement, embeddings, page cache). They are not
scored.

**Measurement** - the scored requests, sent after the warmups, with the engine
still loaded.

## Protocol

1. Load the model once and keep the process alive for the whole suite.
2. Send the warmup cases in `cases.jsonl` / `suite.json` order, at the suite's
   TG. Do not score them. Keep their diagnostics.
3. In the same process, send the measurement cases in order, same TG.
4. One request at a time. No other inference workload on the same devices.
   Wait for each request to finish before sending the next.
5. Greedy/deterministic decoding, speculation disabled. Fix the thinking mode
   and record it. Thinking and non-thinking are separate workloads.
6. Disable cross-request prefix/KV reuse and response caches; ordinary KV
   caching inside one generation stays. Require zero reused input tokens.
7. For a baseline, disable approximate computation skips, input truncation and
   precision changes. Record attention/KV precision and any enabled
   acceleration that changes the computation.
8. Keep model, tokenizer, weight precision, context capacity, device topology,
   memory limit and CPU allocation fixed unless one of them is the experiment.
9. If the engine learns a persistent placement or profile, start every run from
   the same saved seed state; never let run B inherit run A's learned profile.
10. Do not reload the model, clear its caches or change placement between the
    warmup and measurement phases.

What warms what:

- **Runtime warmup:** the warmup requests, whose caches are retained.
- **Filesystem cache:** may already be warm and may survive restarts. Record
  this instead of calling every fresh process a cold-cache run.
- **Prefix/KV and response caches:** must not replace the computation being
  measured. Different articles do not by themselves prevent reuse of a common
  chat header.

Reading weight files, downloading them or a health check do not replace
inference warmup. Repeatedly sending the measurement prompt would warm its
exact prefix and overstate throughput.

## Metrics

| Metric | Calculation |
| --- | --- |
| PP tok/s | `input_tokens / native_prefill_seconds` |
| TG tok/s | `(generated_tokens - 1) / (last_token_time - first_token_time)` |
| TTFT | `first_token_time - request_start` |
| Complete-request wall | `request_end - request_start` |
| ITL p50/p95/p99 | percentiles of consecutive generated-token intervals |

The first output token normally comes from prefill, so it is not a decode step.
Keep native engine timings too, but label them separately if the engine uses
another convention. An event can contain several tokens; event timestamps alone
are not per-token timestamps - without token-level data, use the engine's
documented decode metric and say so.

Pool the **measurement** requests only:

```text
pooled_PP = sum(input_tokens) / sum(native_prefill_seconds)
pooled_TG = sum(generated_tokens - 1) / sum(last_token_time - first_token_time)
suite_wall = sum(complete_request_wall_seconds)
```

Do not average tok/s values, do not score warmups, and do not merge PP and TG
into one headline: a decode gain can hide a prefill regression. State whether a
timing is native (engine protocol) or API (client/network path); they are not
comparable.

## Accepting a run

A run is complete only when all of its requests were executed with the expected
input lengths, no truncation, zero cross-request reuse or speculation, no
approximate skips, and no engine errors, OOM kills or CPU throttling. Check that
the requested devices and topology were actually used.

Preserve failed and incomplete runs, but do not promote partial warmup to a
result. Save the frozen inputs and their hashes, model/tokenizer revisions,
engine build, runtime settings, hardware/topology, limits, load duration,
request order and raw measurements.

For A/B comparisons, give each fresh engine the same warmup history and the
same scored inputs. Use **A -> B -> fresh A**, then reverse the order in a
repeat to expose filesystem-cache or thermal carry-over. Freeze any additional
input order before running it; never pick the fastest order after seeing the
results.

## Building or changing a corpus or suite

```bash
cd project-maya/benchmarking

# fill a corpus's sources.jsonl and SOURCES.md (network, once per revision)
python3 freeze.py fetch corpora/ru-prose

# regenerate SOURCES.md from an existing frozen file
python3 freeze.py sources corpora/ru-prose

# build a suite from its corpus (inside a Maya image; see below)
python3 freeze.py freeze suites/ds41f-ru --tokenizer /data/ds4/tokenizer
```

Inside a container, mount the benchmark tree and the pinned Maya source:

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -e MAYA_ROOT=/src -e PYTHONDONTWRITEBYTECODE=1 -w /work \
  --entrypoint python3 \
  -v "$PWD/..":/work -v /path/to/project-maya:/src:ro \
  -v /path/to/ds4/tokenizer:/data/ds4/tokenizer:ro \
  YOUR_MAYA_IMAGE /work/freeze.py freeze suites/ds41f-ru \
  --tokenizer /data/ds4/tokenizer
```

`freeze.py` writes `cases.jsonl`, `suite.json`, `CASES.md` and
`cases.manifest.json` into the suite, and `SOURCES.md` into the corpus. It
refuses to overwrite without `--force`, checks exact PP lengths, request
uniqueness, non-overlapping source byte ranges, that the prompt re-tokenises to
its ids, and that a suite's warmup reference still matches when one is pinned.
Rerunning with the same inputs produces byte-identical files.

The manifest hashes the suite's own files (`cases.jsonl`, `suite.json`,
`CASES.md`, `suite.py`), pins the corpus (`corpus.py`, `sources.jsonl`), the
tokenizer files and the chat encoder, and records the hashes of `benchkit.py`
and `freeze.py` used to build it. Documentation is not hashed.

A change to the tokenizer, chat template, encoder, seed or schedule is a new
suite; a change to the articles or tasks is a new corpus. Never hand-edit a
frozen file.

## Limits

- The shipped corpus is Russian Wikipedia prose and writing tasks. It says
  nothing about code, chat slang, tool calls, images or multi-turn behaviour.
- A corpus may have been touched by earlier tuning; a suite built on it is a
  baseline, not a blind holdout. A final check needs the disjoint pool listed in
  the corpus, fetched and frozen separately.
- These are single-request throughput samples, not a statistical steady state
  or a general model benchmark. Longer contexts, code, multilingual input,
  vision and concurrency need their own corpora and suites.
