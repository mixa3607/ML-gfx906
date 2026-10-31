# LLM benchmarks

Prepare frozen requests and run them through Maya's native engine protocol.

- `corpora/<name>/corpus.py`: `ARTICLE_TITLES` and `INSTRUCTIONS`, independent of the model.
- `corpora/<name>/sources.jsonl`: frozen article text with revision URLs and attribution.
- `suites/<name>/suite.py`: corpus, seed, input lengths, output budget and chat settings.
- `suites/<name>/cases.jsonl`: ready-to-use requests in execution order.
- `freeze.py`: downloads articles or builds requests. No GPU needed.
- `run.py`: feeds requests to one resident engine using a Maya JSON config.

PP includes the chat template and assistant header; TG is the output token limit.

## Using the requests

Read `cases.jsonl` in file order. Each row contains `id`, `phase`, `pp`, `tg`,
`ids`, `prompt` and source `passages` (Wikipedia page id and UTF-8 byte ranges).
`ids` is the input to the engine; `prompt` is its decoded text for inspection
and may contain replacement characters if a token cut splits a UTF-8 character.

Keep one loaded engine, run warmups without scoring, then measure the remaining
requests one at a time. Use greedy decoding, thinking off, speculation on and
no cross-request prefix/KV reuse. Do not truncate inputs or reload between phases.
Respect natural EOS and record actual generated tokens and stop reasons.

Record engine/model versions, precision, runtime settings, hardware and raw timings.
Report prefill and decode separately; pool token counts over elapsed times rather
than averaging tok/s. For A/B runs, keep inputs, hardware and warmup history fixed.
This measures warm single-request throughput, not quality, concurrency or cold start.

## Running

Run this instead of the API server, not alongside another loaded engine:

```bash
python3 run.py --maya-root /opt/maya --config "$MAYA_CONFIG" \
  suites/ds41f-ru-smoke/cases.jsonl > results.jsonl 2> engine.log
```

The runner uses Maya's `engine_args()` and `child_env()` with the config's `exe`
and `cwd`. It waits for `READY`, sends each request with `temperature=0 spec=1`,
waits for `DONE`, and sends `QUIT` after the last request. It does not tokenise
text, start HTTP, change the config or decode the output. `ERR` or EOF aborts the run.
Use a config and pack with the drafter enabled; for DS4, retain `--dspark on`.
Record draft counters to establish whether speculation actually ran. Results
from the earlier runner that forced `spec=0` are not the same benchmark mode.

Each stdout JSONL row contains `id`, `phase` and a parsed `done` object; engine stderr
is inherited. Both warmup and measurement results are kept, without aggregation.
The native DS4 line is:

```text
DONE generated prompt_tokens prompt_ms decode_ms finish drafts_accepted drafts_offered reused hits lookups
```

`done` uses these field names: counters are integers, timings are floats and
`finish` is a string.

Timings are native engine milliseconds, not client TTFT or per-token latency.
The runner does not disable KV reuse; check `reused` before treating a result as
a no-reuse baseline. Context capacity must cover the largest `pp + tg`.

## Rebuilding requests

Use the Maya source checkout and the model pack's tokenizer directory
(with `vocab.json`, `merges.txt`, `token_type.json`, `tokenizer.json` and
`chat_template.jinja`). Python dependencies: `regex`, `jinja2`.

```bash
cd project-maya/benchmarking
python3 freeze.py freeze suites/ds41f-ru-smoke \
  --maya-root /path/to/project-maya --tokenizer /path/to/pack/tokenizer
```

This overwrites `cases.jsonl`. Use `--output /path/to/cases.jsonl` to inspect a
candidate without replacing the shipped file. Only source prose is cut; passages
are consumed without reuse. The same inputs produce the same file.

To download a new corpus revision, remove its old `sources.jsonl` first, then run:

```bash
python3 freeze.py fetch corpora/ru-prose
```

Fetch downloads the warmup/measurement articles listed in `ARTICLE_TITLES`. It creates
`sources.jsonl` exclusively; a failed download leaves a partial file to remove
before retrying. Reuse frozen sources for comparisons instead of fetching per run.

CPU tests (including a fake engine): `python3 -m unittest -v`.
