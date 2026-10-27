# Neuro-Arena API runner

`run.py` extracts questions from the embedded `const DATA` JSON in `Bench.html`,
without executing its JavaScript. The supplied benchmark contains 100 questions
in 20 subjects. The HTML is not modified.

The workflow has three independent steps: collect answers, judge them with an
LLM, and export a browser history entry. Judgements never modify the answers.

`run.py` is the single CLI entry point. Implementations live in
`commands/examine.py`, `commands/validate.py` and `commands/export.py`;
`common.py` contains shared parsing, API access, progress and file handling.

Requires Python 3.10+ on Linux, PyYAML and jsonschema:

```bash
cd docs/misc/arena
python3 -m pip install -r requirements.txt
```

## Model configs

YAML files contain **only model settings**, not output paths. The same format
works with both `examine` and `validate`:

```yaml
baseUrl: https://aaa/v1
headers:
  Authorization: Bearer YOUR_TOKEN
systemPrompt: You are a helpful assistant.
chatTemplateKwargs:
  reasoning_effort: 50
model: ds41f
```

- `baseUrl` is the API prefix; the runner appends `/chat/completions`.
- `headers` are arbitrary HTTP headers. Headers are neither logged nor copied
  into results, validation or exports. Keep configs with credentials private.
- `systemPrompt` is used **exactly as configured in both modes**: no hidden
  instructions are added or substituted. Empty or omitted means no system
  message. Use a judge-specific config for meaningful validation.
- `chatTemplateKwargs` is sent unchanged as `chat_template_kwargs`, not as
  top-level generation parameters. The server must support the supplied values.

Included configs:

| Config | System prompt | Reasoning |
| --- | --- | --- |
| `configs/maya-ds41f-nothink.yaml` | General assistant | Disabled |
| `configs/maya-ds41f-rea50.yaml` | General assistant | 50 |
| `configs/maya-ds41f-judge.yaml` | Benchmark judge | 50 |

All CLI paths are relative to the **working directory**, not to the model YAML.
Files use the exact supplied names; extensions are not automatically appended.

## Examine

```bash
./run.py examine \
  --model configs/maya-ds41f-rea50.yaml \
  --answers configs/maya-ds41f-rea50.answers.json
```

Optional flags: `--bench Bench.html` selects the source HTML (the default is
next to `run.py`); `--timeout 3600` sets the per-request socket timeout in seconds.

Each question is a fresh conversation with the configured system prompt and
one user message. References and explanations are never sent during examination.
The answer file is initialized with **all** questions and `verdict: null` before
the first request. Entries contain `question`, `reference`, `explanation`,
`answer`, `reasoning`, `usage`, the full API `response`, `elapsedSeconds` and
`answeredAt`. Stable question IDs look like `math:0`.

The full response preserves server-specific fields and finish reasons, including
truncated exam answers. `elapsedSeconds` measures the entire HTTP request, not
decoding time. The history run name is the answer filename without `.json` and
an optional `.answers` suffix, e.g. `maya-ds41f-rea50`.

## Validate

```bash
./run.py validate \
  --model configs/maya-ds41f-judge.yaml \
  --answers configs/maya-ds41f-rea50.answers.json \
  --validation configs/maya-ds41f-rea50.validation.json
```

The `--model` config selects the **judge**, which can differ from the examined
model. Its system prompt, reasoning settings and endpoint are honored unchanged.
`--timeout` is also supported. There is no separate `validator.yaml` format.

Every saved exam answer gets a separate conversation. Its user message is JSON:

```json
{
  "question": "Original question",
  "candidateAnswer": "Answer being evaluated",
  "referenceAnswer": "Supplied reference",
  "referenceExplanation": "Optional reference explanation"
}
```

The examined model's identity, reasoning and raw API response are not sent to
the judge. The runner requests top-level `response_format: json_schema` with
`strict: true` and independently validates the returned content with jsonschema:

```json
{
  "verdict": 1,
  "referenceStatus": "accepted",
  "correctedAnswer": null,
  "explanation": "Brief reason for the assessment."
}
```

- `verdict`: `1` (correct), `0.5` (partially correct), `0` (incorrect), or `null`
  (the judge cannot reliably assess it; exported as **Пропущено**).
- `referenceStatus`: `accepted`, `disputed`, or `uncertain`.
- `correctedAnswer`: a nonempty proposed corrected reference when `disputed`;
  otherwise null. It never replaces the original reference automatically.
- `explanation`: a brief nonempty reason, not a detailed chain of thought.

All four fields are required; additional fields, wrong types, invalid enum
values, duplicate JSON keys and Markdown fences are rejected. The judge must
finish with `finish_reason: stop`; truncated judgements are not saved even if
their content happens to be valid JSON. Server-side support varies: requesting
strict schema output does not guarantee constrained decoding or a correct verdict.

The validation file contains:

- `sourceRunId` and the SHA-256 of the **exact bytes** of the answer file;
- judge settings and the requested response schema, without HTTP headers;
- `answers`, a mapping from question ID to the four judgement fields, the full
  judge `response` (including reasoning and usage), elapsed time and timestamp.

Only successfully judged entries appear in this mapping. A saved `verdict: null`
is a completed assessment and is not requested again. Unanswered exam questions
are not sent to the judge. Partial exams can be validated, but later additions
to the answer file invalidate its hash: use a new validation file after finishing
the exam. Even whitespace-only changes invalidate the source hash.

Use separate validation files for different judges, prompts or settings. Review
disputed/uncertain references manually; an LLM judgement is not ground truth.
Export uses the saved verdict, including for disputed references.

## Progress and resume

Both API modes use sequential, non-streaming requests with no automatic retries.
Progress goes to stderr: completed/total, percentage, question ID and elapsed
time. The terminal refreshes every second; redirected logs get a heartbeat
every 30 seconds. Server errors, invalid responses and timeouts stop the run
with a nonzero exit code. Redirects are not followed, protecting configured headers.

Each completed answer or judgement is atomically saved and flushed to disk.
After Ctrl+C, SIGTERM or an error, rerun the **same command** to resume. An
interrupted request may be repeated if the server processed it before local
saving. Sibling `.json.lock` files prevent conflicting commands and are removed
on completion, errors, Ctrl+C and SIGTERM. Cleanup happens while the lock is
still held; inode checks prevent contenders from using an old unlinked lock.
Validation holds the answer file's lock as well, preventing a simultaneous exam
from changing its source. SIGKILL, a crash or a power failure may leave a lock
file behind; the OS releases the lock, and the next command safely reuses the
file and removes it on exit. Do not manually delete an actively held lock.

Exam resume checks questions and model settings. Validation resume checks source
identity/hash, judge settings and response schema. Mismatches stop without
overwriting progress. HTTP headers may rotate. Changes to server-side model
weights behind the same model name cannot be detected.

## Export

```bash
./run.py export \
  --answers configs/maya-ds41f-rea50.answers.json \
  --validation configs/maya-ds41f-rea50.validation.json \
  --output configs/maya-ds41f-rea50.import.json
```

No model config or API access is needed. Both input files remain unchanged.
`--validation` is optional: without it, export uses verdicts in the answer file
(all null in new exams). With it, **only that validation file** supplies verdicts;
missing judgements and null verdicts are skipped. The source hash must match.
`--output` defaults to `<answer run name>.import.json` next to the answer file.

Use the history/table import button in `Bench.html`. The page imports **summaries
only**, not individual answers or a resumable quiz. Export produces its
`{app, exported, hist: [...]}` format with run name, timestamp, score, judged/total
counts and a note. `counts.skip` and the note's `Пропущено` count include missing
and null verdicts.

Scoring matches the page: `round(100 * sum(verdict * level) / sum(level))`, with
JavaScript's rounding. Skipped questions contribute zero but retain their weight
in the denominator. `done` counts non-null verdicts, not API responses. An entirely
unjudged run exports as 0 points, 0/100 judged, 100 skipped. `tps` remains null
because HTTP elapsed time does not accurately measure decoding speed.

Exports retain a stable ID per validation run (or exam when no validation is
selected). Different validation runs can coexist in the page. Repeated imports
of the same run are deduplicated; delete its old history row before reimporting
an updated export.

## Migrating existing runs

The old positional CLI and `valudate` placeholder are replaced by the commands
above. Remove `result` from custom model configs; pass output paths explicitly.
Existing schema-version-1 answer files remain readable without conversion:

```bash
./run.py validate \
  --model configs/maya-ds41f-judge.yaml \
  --answers configs/maya-ds41f-rea50.json \
  --validation configs/maya-ds41f-rea50.validation.json
```

Existing files are not automatically renamed or copied. An already completed
exam can be resumed with `examine --model ... --answers <existing-file>` without
new requests when its model settings match.

## Tests

From the repository root:

```bash
python3 -m unittest discover -s docs/misc/arena -p 'test_*.py' -v
```

Tests use only a local mock HTTP server, not a real inference API or GPUs.
