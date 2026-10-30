# CORPUS-DS41F

Frozen inputs for measuring **DeepSeek-V4.1-Flash** one request at a time:
12 unscored warmups followed by a two-round prefill sweep from **PP2048 to
PP32768**, with **TG256** for every request.

This directory is meant to be read by people as well as by scripts:

- [`README.md`](README.md) (this file) explains what the suite is and how to run it.
- [`CASES.md`](CASES.md) lists all 22 requests in feed order, with the article,
  the task and the beginning of each prompt.
- [`SOURCES.md`](SOURCES.md) lists the attributed Wikipedia articles and revisions.
- [`suite.json`](suite.json) is the same order in machine-readable form.
- [`cases.jsonl`](cases.jsonl) holds the actual requests: token ids, readable
  prompt text, source byte ranges and hashes.
- [`cases.manifest.json`](cases.manifest.json) pins the hashes, the protocol and
  the generator version.

## The suite

| Phase | Requests | PP | TG | Scored |
| --- | ---: | --- | ---: | --- |
| Warmup | 12 | 2048 each | 256 | no |
| Measurement, round 1 | 5 | 2048, 4096, 8192, 16384, 32768 | 256 | yes |
| Measurement, round 2 | 5 | 2048, 4096, 8192, 16384, 32768 | 256 | yes |

**PP** is the complete tokenised input: BOS, the chat template, the task, the
material and the assistant header. It is *not* a character count and not a
"context size" setting. The generator cuts only source prose at the end, so
every case is exactly its PP; the task and the template are never truncated.

**TG256** is a request parameter, not part of the frozen files: ask for at most
256 generated tokens, greedy, speculation off. Natural EOS is respected, so a
request that ends early is kept and reported, not topped up.

Two rounds are deliberate: the second pass through the sizes shows whether a
warm process drifts (expert placement, allocator, page cache) without relying
on one number per length. The order is frozen and must not be re-sorted after
looking at results.

The 12 warmups are **the same requests as the older `project-maya/ds41-pr592`
suite** (same article pool, same seed `20261024`, same PP). Only the measured
part is new: it now includes 2K and 32K.

## How to feed it

1. Load the model once and keep the engine process alive for the whole suite.
2. Send the 12 warmup cases in `cases.jsonl` order, TG256 each. They are not scored.
3. Send the 10 measurement cases in the same order, TG256 each.
4. One request at a time; no other inference on the devices.
5. Disable cross-request prefix/KV reuse and approximate skips for the baseline;
   ordinary KV caching inside a single generation stays enabled.
6. Do not reload the model or change placement/topology settings between phases.
7. Check that the engine reports the same PP and zero reused input tokens, and
   that no request was truncated.

`suite.json` carries the same list as `steps`, each with `id`, `phase`, `pp`,
`tg`, `scored`, lead article and task, so a runner can read either file. A
request is sent from the `ids` field of the matching case; `rendered_text` is
for humans and for hash checks, not the transport.

The measurement procedure, pooling rules and acceptance criteria are in
[`../README.md`](../README.md); the corpus recipe (pools, tasks, freezing rules)
is in [`../CORPUS.md`](../CORPUS.md).

## What the prompts look like

Every prompt is built by Maya's own DeepSeek chat encoder with
`reasoning_effort=none`, so the engine receives exactly what a normal client
would:

```text
<BOS><User>Название статьи. Задание

Материалы:
Название статьи
<уникальный фрагмент статьи>

<следующая статья, если нужно>
<её фрагмент>
<Assistant></think>
```

The task is at the front, so the cut at the end never removes it. Each case
records which article bytes it consumed (`articles`/`passages`), and no byte
range is used by two requests anywhere in the suite. `CASES.md` shows the
beginning of each prompt with `⏎` for a line break.

## Files

| File | For | Contents |
| --- | --- | --- |
| `cases.jsonl` | runners and humans | one JSON object per request: `id`, `phase`, `pp`, `tg`-related fields, `task`, `articles`, `prompt_sha256`, `ids`, `rendered_text` |
| `suite.json` | runners | seed, PP schedule, TG, encoder, tokenizer hashes, ordered `steps` |
| `cases.manifest.json` | verification | counts, protocol, order, SHA-256 of every generated file and of the tokenizer |
| `CASES.md` | humans | feed-order table and one readable section per case |
| `SOURCES.md` | humans | source articles, byte sizes, revision links, text hashes |
| `sources.jsonl` | regeneration | the frozen article text with revision, URL and SHA-256 |
| `corpus.py` | regeneration | fetch/build logic; `MAYA_ROOT` points at the Maya source |
| `freeze_inputs.py` | regeneration | fixes the suite, writes everything above |

## Frozen means frozen

- Sources are pinned per article by page id, revision id, URL and text SHA-256;
  the whole `sources.jsonl` is pinned in the manifest
  (`f9d8d2dd91eeccbddff09d50139a3f762f31106ea8f0004187ebd95d595c14e9`).
- The tokenizer and chat template are pinned by file hashes in the manifest;
  they match `/data/ds4/tokenizer` of the DeepSeek-V4.1-Flash pack.
- Prompts were rendered and tokenised with the Maya source at tag `v1.1.38`
  (`cf6472cc84489765791ad97bb55b395e8f442088`). That encoder reproduces the
  12 warmups from `ds41-pr592` bit for bit, which is checked while freezing.
- Rerunning the freeze with the same inputs produces byte-identical files; the
  checked hashes are in the manifest.

If the tokenizer, the chat template, the seed or the source pool changes, this
is a **new corpus directory**, not an edit of this one. Never hand-edit
`cases.jsonl`.

## Regenerating

The tokenizer and encoder come from Maya, so run the freeze inside a Maya image
(the image's Python environment provides `regex` and `jinja2`):

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -e MAYA_ROOT=/src -e PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint python3 \
  -v /path/to/project-maya:/src:ro \
  -v /path/to/ds4/tokenizer:/data/ds4/tokenizer:ro \
  -v "$PWD":/work \
  YOUR_MAYA_IMAGE /work/freeze_inputs.py \
  --source /work/sources.jsonl --out-dir /work \
  --tokenizer /data/ds4/tokenizer
```

`/path/to/project-maya` must be the pinned source (tag `v1.1.38`), not a newer
checkout whose chat encoder may have changed. The output includes the hashes of
`corpus.py` and `freeze_inputs.py`, so both must be the versions in this
directory. Add `--force` to overwrite an existing output.

To verify an existing directory without a tokenizer:

```bash
python3 - <<'PY'
import hashlib, json
from pathlib import Path
here = Path('.')
m = json.loads((here / 'cases.manifest.json').read_text())
for name, want in m['files'].items():
    got = hashlib.sha256((here / name).read_bytes()).hexdigest()
    print('OK  ' if got == want else 'DIFF', name)
PY
```

## What this corpus is not

- It is Russian Wikipedia prose with six writing tasks. It says nothing about
  code, chat slang, tool calls, images or multi-turn behaviour.
- The `dev` article pool was already used during earlier Maya tuning. This is a
  baseline corpus, not a blind holdout; a final check needs a disjoint pool
  (`corpus.py` lists one, but its text is intentionally not shipped here).
- It measures warmed single-request prefill and decode, not concurrency, TTFT of
  a cold server, answer quality or agent throughput.
- TG256 is a generation budget for timing, not a quality reference; the tasks
  ask for long answers only so the budget is usually reached.
