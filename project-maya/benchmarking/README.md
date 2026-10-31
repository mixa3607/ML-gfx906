# Benchmark inputs

This directory prepares requests, not measurements. There is no benchmark runner.

- `corpora/<name>/corpus.py`: article titles and tasks, independent of the model.
- `corpora/<name>/sources.jsonl`: frozen article text with revision URLs and attribution.
- `suites/<name>/suite.py`: corpus, seed, input lengths, output budget and chat settings.
- `suites/<name>/cases.jsonl`: ready-to-use requests in execution order.
- `freeze.py`: downloads articles or builds requests. No GPU needed.

The shipped `ds41f-ru` suite uses DeepSeek-V4.1-Flash: 12 warmups at PP2048,
then two sweeps through PP2048, 4096, 8192, 16384 and 32768. Every request has TG256.
PP includes the chat template and assistant header; TG is the output token limit.

## Using the requests

Read `cases.jsonl` in file order. Each row contains `id`, `phase`, `pp`, `tg`,
`ids`, `prompt` and source `passages` (Wikipedia page id and UTF-8 byte ranges).
`ids` is the input to the engine; `prompt` is its decoded text for inspection
and may contain replacement characters if a token cut splits a UTF-8 character.

Keep one loaded engine, run warmups without scoring, then measure the remaining
requests one at a time. Use greedy decoding, thinking off, speculation off and
no cross-request prefix/KV reuse. Do not truncate inputs or reload between phases.
Respect natural EOS and record actual generated tokens and stop reasons.

Record engine/model versions, precision, runtime settings, hardware and raw timings.
Report prefill and decode separately; pool token counts over elapsed times rather
than averaging tok/s. For A/B runs, keep inputs, hardware and warmup history fixed.
This measures warm single-request throughput, not quality, concurrency or cold start.

## Rebuilding requests

Use the Maya revision named in `suite.py` and the model pack's tokenizer directory
(with `vocab.json`, `merges.txt`, `token_type.json`, `tokenizer.json` and
`chat_template.jinja`). Python dependencies: `regex`, `jinja2`.

```bash
cd project-maya/benchmarking
python3 freeze.py freeze suites/ds41f-ru \
  --maya-root /path/to/project-maya --tokenizer /path/to/pack/tokenizer
```

This overwrites `cases.jsonl`. Use `--output /path/to/cases.jsonl` to inspect a
candidate without replacing the shipped file. Only source prose is cut; passages
are consumed without reuse. The same inputs produce the same file.

To download a new corpus revision, remove its old `sources.jsonl` first, then run:

```bash
python3 freeze.py fetch corpora/ru-prose
```

Fetch downloads the configured warmup/dev pools, not `HOLDOUT`. It creates
`sources.jsonl` exclusively; a failed download leaves a partial file to remove
before retrying. Reuse frozen sources for comparisons instead of fetching per run.

CPU tests: `python3 -m unittest -v test_freeze.py`.
