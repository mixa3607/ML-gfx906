# ds41f-ru

DeepSeek-V4.1-Flash reading the [`ru-prose`](../../corpora/ru-prose/) corpus:
12 unscored warmups at PP2048, then a two-round sweep through PP2048, 4096,
8192, 16384 and 32768, with **TG256** for every request.

The protocol, metrics and acceptance rules are in
[`../../README.md`](../../README.md); the corpus/suite rules are in
[`../../SUITES.md`](../../SUITES.md). This file describes only what is specific
to this suite.

## Specifics

- **Model:** `deepseek-v4.1-flash`, Maya's DeepSeek engine.
- **Corpus:** `ru-prose` — Russian Wikipedia prose, six writing tasks.
- **Chat encoder:** `project-maya` tag `v1.1.38`
  (`cf6472cc84489765791ad97bb55b395e8f442088`), rendered with
  `reasoning_effort=none`; the assistant header is `<｜Assistant｜></think>`.
- **BOS:** `<｜begin▁of▁sentence｜>` (token 0).
- **Seed:** `20261024`.
- **Warmups:** the 12 PP2048 requests are bit-identical to
  `project-maya/ds41-pr592` (same corpus, seed and lengths), so old and new runs
  warm the engine on the same input.

## Schedule

| Phase | Requests | PP | TG | Scored |
| --- | ---: | --- | ---: | --- |
| Warmup | 12 | 2048 | 256 | no |
| Measurement, round 1 | 5 | 2048, 4096, 8192, 16384, 32768 | 256 | yes |
| Measurement, round 2 | 5 | the same five sizes | 256 | yes |

PP is the complete tokenised input: BOS, the chat template, the task, the
material and the assistant header. The task is at the front of the user
message; only source prose is cut at the end, so each case is exactly its PP.
TG256 is a request parameter, not part of the frozen files.

The feed order and one readable section per request are in
[`CASES.md`](CASES.md); the same order for a runner is in
[`suite.json`](suite.json).

## Files

| File | For | Contents |
| --- | --- | --- |
| `suite.py` | regeneration | model, encoder pin, seed, splits, PP/TG, corpus name |
| `cases.jsonl` | runners and humans | the 22 requests: ids, readable prompt text, articles, hashes |
| `suite.json` | runners | seed, PP schedule, TG, encoder, corpus, tokenizer hashes, ordered steps |
| `cases.manifest.json` | verification | protocol, order, hashes of suite/corpus/tokenizer/kit |
| `CASES.md` | humans | feed order and a section per case |
| `README.md` | humans | this file |

The corpus text, its attribution and its own README live in
[`../../corpora/ru-prose/`](../../corpora/ru-prose/).

## Regenerating

The tokenizer and encoder come from Maya, so run the freeze inside a Maya image
(its Python environment provides `regex` and `jinja2`) with the pinned source
mounted:

```bash
cd project-maya/benchmarking
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -e MAYA_ROOT=/src -e PYTHONDONTWRITEBYTECODE=1 -w /work \
  --entrypoint python3 \
  -v "$PWD/..":/work \
  -v /path/to/project-maya:/src:ro \
  -v /path/to/ds4/tokenizer:/data/ds4/tokenizer:ro \
  YOUR_MAYA_IMAGE /work/freeze.py freeze suites/ds41f-ru \
  --tokenizer /data/ds4/tokenizer
```

`/path/to/project-maya` must be the pinned source (tag `v1.1.38`), not a newer
checkout whose chat encoder may have changed. Add `--force` to overwrite.

To verify the frozen files without a tokenizer:

```bash
cd project-maya/benchmarking/suites/ds41f-ru
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

The measured requests have not changed since the suite was introduced:
`cases.jsonl` is `8a33850a48e4e88c5fb35300c04732ccb5b97f58722260d5069ea8c177ec64dd`.
A rerun with the same corpus, tokenizer and encoder produces that file byte for
byte.

## Limits

- Russian Wikipedia prose only: no code, chat slang, tools, images or multi-turn.
- The corpus `dev` pool was used by earlier Maya tuning; this is a baseline
  suite, not a blind holdout.
- It measures warmed single-request prefill and decode, not concurrency,
  cold-server TTFT or answer quality. TG256 is a timing budget.
