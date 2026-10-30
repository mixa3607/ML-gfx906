# Corpora and suites

Two layers, two lifetimes:

- A **corpus** is text and tasks. It is model-independent: article pools, the
  questions asked about them, attribution and a frozen `sources.jsonl`.
- A **suite** is a corpus plus a measured workload: model, tokenizer, chat
  encoder, seed, PP schedule and TG budget. Its frozen `cases.jsonl` holds the
  actual token ids.

The same corpus can feed several suites. A new model, tokenizer or schedule is
a new suite, not a new corpus; new articles or tasks are a new corpus, not an
edit of a suite. The measurement protocol and metrics are in
[README.md](README.md).

```text
corpora/<corpus>/     corpus.py     pools, tasks, attribution notes
                      sources.jsonl frozen article text
                      SOURCES.md    generated human view
                      README.md     what this corpus is
suites/<suite>/       suite.py      model, encoder, seed, PP schedule, TG, corpus name
                      cases.jsonl   frozen requests (token ids)
                      suite.json    machine-readable order
                      CASES.md      human-readable order and prompts
                      cases.manifest.json  hashes, protocol, provenance
                      README.md     what this suite is
```

## Corpus rules

Use real prose, not generated text, random tokens or a repeated question. The
shipped corpus uses Russian Wikipedia articles because they are long, attributed
and freely licensed; another corpus may choose another source, but the
principles stay:

- Acquire each article once, then freeze the text. Keep page id, revision URL,
  text SHA-256 and license/attribution data.
- Resolve redirects and compare page ids so an alias cannot leak an article into
  two splits.
- Use **different articles** for warmup and measurement, even when topics
  overlap. A warmed cache must not hide the cost of a measurement article.
- Keep a larger pool than a suite consumes, so longer prompts take additional
  unique prose instead of repeating paragraphs.
- Keep a disjoint **holdout** pool for the final post-tuning check. Its text must
  not be in a baseline corpus's `sources.jsonl`, or the check is not blind.
- Do not refetch current revisions per engine or per run.

`corpus.py` defines `NAME`, `SOURCES` (split -> article titles), `TASKS`,
`TASK_LABELS`, `SOURCE_NOTE`, `LICENSE_NOTE` and `NOTES`. `sources.jsonl` holds
one JSON object per article: `split`, `title`, `pageid`, `revision`, `url`,
`license`, `sha256`, `text`.

If the pool cannot cover a case at the requested PP, the answer is more unique
articles, not a shorter or repeated prompt.

## Case rules

A case is one request: a task, source material and the model's chat envelope,
tokenised to exactly **PP** tokens.

- Cycle through the corpus tasks and rotate the lead article, so a suite is not
  one question repeated.
- Put the task where the cut cannot remove it (front of the user message, or end
  when the cut is arranged to keep it).
- Render with the model's real chat template and tokenizer. PP includes BOS, the
  template, the task, the material and the assistant header.
- Cut **only source prose** at the end to reach PP. Never cut the task, template
  or generation header; never pad with repeated paragraphs.
- Consume source passages monotonically per article and record each byte range.
  No range may appear in two requests of a suite.
- Assert: exact length, unique token ids, ranges inside the source, no reused
  range, and that the stored text re-tokenises to the stored ids.

## Suite rules

`suite.py` defines `CORPUS = '<corpus name>'` and a `SUITE` dict: model, seed,
TG, warmup (split, PP, count), measurement (split, PP list, rounds), task
position, BOS text, assistant suffix, render kwargs, the chat encoder pin, and
optional protocol/notes. The split names must exist in the corpus.

A suite is one frozen workload. Changing any of the following makes a new suite:

- tokenizer or chat template (`tokenizer_files` in the manifest),
- chat encoder revision (`encoder`),
- seed, PP schedule, TG, task position,
- the corpus it names.

## What belongs where

| Part | Location | Why |
| --- | --- | --- |
| Article pools, tasks, labels, attribution notes | `corpora/<name>/corpus.py` | text and questions, no model |
| Frozen article text | `corpora/<name>/sources.jsonl` | shared by every suite of that corpus |
| Model, encoder pin, BOS/suffix, seed, PP/TG, splits | `suites/<name>/suite.py` | the measured workload |
| Fetching, cutting, checks, manifest, report writers | `benchkit.py` | same rules for every corpus and suite |
| Command line (`fetch`, `sources`, `freeze`) | `freeze.py` | one entry point |
| Measurement protocol, metrics, acceptance | `README.md` | applies to everything |

Generated files belong to whoever owns the inputs: `SOURCES.md` is written into
the corpus; `cases.jsonl`, `suite.json`, `CASES.md` and the manifest are written
into the suite.

## Freezing

1. Freeze the corpus sources: `freeze.py fetch corpora/<name>` (network, once
   per revision) or reuse a frozen `sources.jsonl` whose hash is recorded.
   `freeze.py sources corpora/<name>` regenerates `SOURCES.md`.
2. Freeze the suite: `freeze.py freeze suites/<name>`. It builds the configured
   phases, runs the checks and writes the suite's files.
3. The manifest pins the suite files, the corpus (`corpus.py` and
   `sources.jsonl`), the tokenizer files, the encoder revision and the hashes of
   `benchkit.py` / `freeze.py` used to build it.
4. Rerun into a scratch copy and compare hashes: identical output is the
   reproducibility claim; if it differs, the inputs differ.
5. Freeze before measuring any candidate. Never edit a frozen file by hand.

## Adding a corpus

1. Copy `corpora/ru-prose/` or create a directory with `corpus.py`.
2. Define the pools, tasks, labels and notes; keep warmup/measurement/holdout
   disjoint.
3. Run `freeze.py fetch corpora/<name>`; read `SOURCES.md` as a human.
4. Add the corpus to the table in [README.md](README.md).

## Adding a suite

1. Copy `suites/ds41f-ru/` or create a directory with `suite.py`.
2. Set `CORPUS` to an existing corpus and fill `SUITE`: model, encoder pin,
   BOS/suffix, render kwargs, seed, warmup/measurement splits, PP, TG.
3. Run `freeze.py freeze suites/<name>`; read `CASES.md` as a human: do the
   prompts look like real traffic, is the task present, are the articles
   distinct?
4. Add the suite to the table in [README.md](README.md).

## Limits

These prose corpora do not represent all chat traffic. Code, multilingual text,
tool calls, images, long multi-turn conversations and concurrency each need
their own corpus; changing only the engine while keeping the corpus is what
makes engine comparisons meaningful. Medical and legal texts are performance
inputs, not advice or quality references.
