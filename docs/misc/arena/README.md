# Neuro-Arena API runner

`run.py` extracts all questions from the embedded `const DATA` JSON in
`Bench.html`, without executing its JavaScript. The supplied benchmark contains
100 questions in 20 subjects. The HTML is not modified.

Requires Python 3.10+ on Linux and PyYAML:

```bash
cd docs/misc/arena
python3 -m pip install -r requirements.txt
cp config.example.yaml model.yaml
```

Edit `model.yaml`:

```yaml
baseUrl: https://aaa/v1
headers:
  Authorization: Bearer YOUR_TOKEN
systemPrompt: ""
chatTemplateKwargs:
  reasoning_effort: 95
model: ds41f
result: ds41f-rea95
```

- `baseUrl` is the API prefix; the runner appends `/chat/completions`.
- `headers` are arbitrary HTTP headers. No API key is required by the runner.
  Headers are neither logged nor copied into result/export files. Config files
  can contain credentials: keep them private and do not commit them.
- A nonempty `systemPrompt` becomes the first `system` message. Empty or omitted
  means no system message. Every question gets a fresh conversation with one
  `user` message; references and explanations are never sent to the model.
- `chatTemplateKwargs` is sent unchanged as `chat_template_kwargs` in the JSON
  request body, **not** as top-level generation parameters. The server must
  support those template options; the runner does not translate their values.
- `result` is a path relative to the config file, or an absolute path. `.json`
  is appended unless already present. Its basename without `.json` is the run
  name shown in the HTML history (e.g. `ds41f-rea95`, not just `ds41f`).

## Examine

```bash
python3 run.py examine model.yaml
# Optional source HTML and per-request socket timeout in seconds:
python3 run.py examine model.yaml --bench Bench.html --timeout 3600
```

Requests are sequential, non-streaming, and have no automatic retries. Progress
goes to stderr: completed/total, percentage, question ID and elapsed request
time. While waiting, the terminal refreshes every second; redirected logs get
a heartbeat every 30 seconds. Server errors, invalid responses and timeouts
stop the run with a nonzero exit code. Redirects are not followed, to avoid
forwarding credentials to another endpoint.

The result is initialized with **all** questions and `verdict: null` before the
first request. Each entry contains `question`, `reference`, `explanation`,
`answer`, `reasoning`, `usage`, the full API `response`, `elapsedSeconds` and
`answeredAt`. The full response preserves server-specific fields and finish
reasons, including truncated completions. `elapsedSeconds` measures the entire
HTTP request, not decoding time. Questions have stable IDs such as `math:0`.

Results are atomically replaced and flushed to disk after each answer. Ctrl+C
or SIGTERM stops the runner; restart the **same command** to continue. Entries
with a saved response are not requested again. A request interrupted before
saving may be repeated, even if the server already processed it. A sibling
`.json.lock` file prevents simultaneous runners from overwriting one result;
the OS releases its lock when the process exits, so the file may remain.

Resume checks the question data, model, API URL, system prompt and template
options. A mismatch stops without overwriting anything; choose another `result`
for a new run. Headers may change, allowing credentials to rotate. Changing
server-side model weights behind the same model name cannot be detected.

## Valudate (placeholder)

```bash
python3 run.py valudate model.yaml --validator validator.yaml
```

The spelling `valudate` is intentional. This command currently reports that
validation is unimplemented and exits with code 2. It does not read the configs,
send requests or modify files. Future LLM validation will use `validator.yaml`.
Until then, verdicts can be edited manually in the result JSON:

- `1`: correct;
- `0.5`: partially correct;
- `0`: incorrect;
- `null`: skipped (**Пропущено**), even when a model answer exists.

## Export

```bash
python3 run.py export model.yaml
# Optional explicit destination (relative to the working directory):
python3 run.py export model.yaml --output ds41f-import.json
```

By default this writes `ds41f-rea95.import.json` next to the result. Use the
history/table import button in `Bench.html` to import it. No API calls are made;
export also works with an incomplete run. The original result is not modified.

The page imports **history summaries only**, not individual answers or a
resumable quiz. Export produces its `{app, exported, hist: [...]}` format with
the run name, timestamp, score, judged/total counts and a note. `counts.skip`
and the note's `Пропущено` count include every `verdict: null`.

Scoring matches the page: `round(100 * sum(verdict * level) / sum(level))`, with
JavaScript's rounding. Skipped questions contribute zero but retain their
weight in the denominator; `done` counts non-null verdicts, not API responses.
An entirely unjudged run therefore exports as 0 points, 0/100 judged, 100 skipped.
`tps` is null: HTTP elapsed time does not measure decoding speed accurately.
Repeated exports keep the same history ID, so the page deduplicates imports;
to reimport edited verdicts, delete the old history row in the page first.

## Tests

```bash
python3 -m unittest discover -s docs/misc/arena -p 'test_*.py' -v
```

Run this from the repository root. Tests use only a local mock HTTP server;
they do not call a real inference API or use GPUs.
