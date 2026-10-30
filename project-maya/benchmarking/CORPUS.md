# Corpus rules

How to turn real prose into frozen benchmark requests. These rules apply to
every suite in this directory; the concrete article pools, tasks, seed and PP
schedule belong to a suite's own `suite.py`, not here. The measurement protocol
is in [README.md](README.md).

## Source material

Use real prose, not generated text, random tokens or a repeated question.
The shipped suites use Russian Wikipedia articles because they are long,
attributed and freely licensed; another suite may choose another source, but
the principles stay:

- Acquire each article once, then freeze the text. Keep the page id, the
  revision URL, the text SHA-256 and the license/attribution data.
- Resolve redirects and compare page ids so an alias cannot leak one article
  into two splits.
- Use **different articles** for warmup and for measurement, even when broad
  topics overlap. A warmed cache must not hide the cost of a measurement
  article.
- Keep a larger pool than the suite consumes, so longer prompts can take
  additional unique prose instead of repeating paragraphs.
- Keep a disjoint **holdout** pool for the final post-tuning check. Its text
  must not be part of a baseline suite's `sources.jsonl`, or the check is not
  blind.
- Do not refetch current revisions per engine or per run: a frozen corpus is
  what makes comparisons possible.

The frozen articles live in `sources.jsonl`, one JSON object per article:
`split`, `title`, `pageid`, `revision`, `url`, `license`, `sha256`, `text`.
`SOURCES.md` is the human-readable view of the same file.

## Cases

A case is one request: a task, source material and the model's chat envelope,
tokenised to exactly **PP** tokens.

- Cycle through several tasks so a suite is not one question repeated. Vary the
  task type (explain, analyse, teach, plan, rewrite, review) and rotate the lead
  article.
- Put the task where the cut cannot remove it (at the front of the user message,
  or at the end when the cut is arranged to keep it).
- Render with the model's real chat template and tokenizer. PP includes BOS,
  the template, the task, the material and the assistant header.
- Cut **only source prose** at the end to reach PP. Never cut the task, the
  template or the generation header; never pad with repeated paragraphs.
- Consume source passages monotonically per article and record each consumed
  byte range. No byte range may appear in two requests of a suite.
- Assert the result: exact length, unique token ids, ranges inside the source,
  no reused range, and that the stored text re-tokenises to the stored ids.

If the pool cannot cover a case at the requested PP, the answer is more unique
articles, not a shorter or repeated prompt.

## What belongs where

| Part | Location | Why |
| --- | --- | --- |
| Article pools, tasks, seed, PP schedule, TG, model/encoder pin, BOS and assistant suffix | `CORPUS-*/suite.py` | decides *what* is measured |
| `sources.jsonl` | `CORPUS-*/` | frozen, attributed source text |
| Fetching articles, cutting to exact PP, checks, `CASES.md`/`SOURCES.md`, manifest | `benchkit.py` | the same rules for every suite |
| Command line (`fetch`, `freeze`) | `freeze.py` | one entry point |
| Measurement protocol, metrics, acceptance | `README.md` | applies to every suite |
| Generated: `cases.jsonl`, `suite.json`, `CASES.md`, `SOURCES.md`, `cases.manifest.json` | `CORPUS-*/` | reproducible output of a freeze |

A suite's `README.md` describes that suite: model, sizes, what is specific, how
to regenerate and what its limits are. It must not restate the measurement
protocol.

## Freezing

1. Freeze the sources (`freeze.py fetch`), or reuse an already frozen file
   whose SHA-256 is recorded.
2. Run `freeze.py freeze SUITE_DIR`. It builds the configured phases, checks
   them and writes the generated files.
3. Record the hashes. The manifest pins:
   - the suite's `cases.jsonl`, `suite.json`, `CASES.md`, `SOURCES.md` and
     `suite.py`;
   - `sources.jsonl`;
   - the tokenizer files and the chat encoder revision;
   - the hashes of the shared `benchkit.py` and `freeze.py` for provenance.
4. Rerun the freeze into a scratch copy and compare hashes. Byte-identical
   output is the reproducibility claim; if it differs, the inputs differ.
5. Freeze before measuring any candidate. Never edit a frozen file by hand.

Changing the tokenizer, chat template, encoder, seed, source pool or PP
schedule means a **new suite directory**. Old and new results are then honestly
different workloads.

## Adding a suite

1. Copy an existing `CORPUS-*` directory, or create one with a `suite.py`.
2. In `suite.py`, define `SUITE`, `SOURCES`, `TASKS` and `TASK_LABELS`: model,
   seed, TG, warmup/measurement splits and lengths, task position, BOS text,
   assistant suffix, render kwargs and the encoder pin.
3. Fetch its sources and run the freeze.
4. Read `CASES.md` and `SOURCES.md` as a human: do the prompts look like real
   traffic, are the articles distinct, is the task present in every case?
5. Add the suite to the table in [README.md](README.md).

## Limits

These prose suites do not represent all chat traffic. Code, multilingual text,
tool calls, images, long multi-turn conversations and concurrency each need
their own corpus; changing only the engine while keeping the corpus is what
makes engine comparisons meaningful. Medical and legal texts are performance
inputs, not advice or quality references.
