# CORPUS-DS41F

Frozen inputs for **DeepSeek-V4.1-Flash** on Maya: 12 unscored warmups at
PP2048, then a two-round sweep through PP2048, 4096, 8192, 16384 and 32768, with
**TG256** for every request.

This suite only defines *what* is measured. The measurement protocol, metrics
and acceptance rules are in [`../README.md`](../README.md); the general corpus
rules are in [`../CORPUS.md`](../CORPUS.md). The shared machinery lives in
[`../benchkit.py`](../benchkit.py) and [`../freeze.py`](../freeze.py).

## What is specific here

- **Model:** `deepseek-v4.1-flash`, Maya's DeepSeek engine.
- **Chat encoder:** `project-maya` tag `v1.1.38`
  (`cf6472cc84489765791ad97bb55b395e8f442088`), rendered with
  `reasoning_effort=none`; the assistant header is `<｜Assistant｜></think>`.
- **BOS:** `<｜begin▁of▁sentence｜>` (token 0).
- **Sources:** Russian Wikipedia prose, 12 warmup + 24 measurement articles,
  frozen by revision and text hash.
- **Tasks:** six Russian writing tasks, cycled in order; the task is at the
  front of the user message.
- **Warmups:** the 12 PP2048 requests are bit-identical to
  `project-maya/ds41-pr592` (same pool, seed `20261024` and lengths), so old and
  new runs warm the engine on the same input.

The suite table:

| Phase | Requests | PP | TG | Scored |
| --- | ---: | --- | ---: | --- |
| Warmup | 12 | 2048 | 256 | no |
| Measurement, round 1 | 5 | 2048, 4096, 8192, 16384, 32768 | 256 | yes |
| Measurement, round 2 | 5 | the same five sizes | 256 | yes |

PP is the complete tokenised input: BOS, the chat template, the task, the
material and the assistant header. The generator cuts only source prose at the
end, so each case is exactly its PP. TG256 is a request parameter, not part of
the frozen files.

The feed order and one readable section per request are in
[`CASES.md`](CASES.md); the same order for a runner is in
[`suite.json`](suite.json).

## Files

| File | For | Contents |
| --- | --- | --- |
| `suite.py` | regeneration | this suite's configuration: pools, tasks, seed, sizes, encoder pin |
| `sources.jsonl` | regeneration | frozen article text with revision, URL and SHA-256 |
| `cases.jsonl` | runners and humans | the 22 requests: ids, readable prompt text, articles, hashes |
| `suite.json` | runners | seed, PP schedule, TG, encoder, tokenizer hashes, ordered steps |
| `cases.manifest.json` | verification | protocol, order, hashes of the suite files, tokenizer, sources and kit |
| `CASES.md` | humans | feed order and a section per case |
| `SOURCES.md` | humans | the attributed articles and revisions |

## Regenerating

The tokenizer and encoder come from Maya, so run the freeze inside a Maya image
(its Python environment provides `regex` and `jinja2`) with the pinned source
mounted:

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -e MAYA_ROOT=/src -e PYTHONDONTWRITEBYTECODE=1 -w /work \
  --entrypoint python3 \
  -v /path/to/project-maya:/src:ro \
  -v /path/to/ds4/tokenizer:/data/ds4/tokenizer:ro \
  -v "$PWD/..":/work \
  YOUR_MAYA_IMAGE /work/freeze.py freeze CORPUS-DS41F \
  --tokenizer /data/ds4/tokenizer
```

`/path/to/project-maya` must be the pinned source (tag `v1.1.38`), not a newer
checkout whose chat encoder may have changed. Add `--force` to overwrite.

To verify a directory without a tokenizer:

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

The measured requests have not changed since the suite was introduced:
`cases.jsonl` is `8a33850a48e4e88c5fb35300c04732ccb5b97f58722260d5069ea8c177ec64dd`.
A rerun with the same sources, tokenizer and encoder produces that file byte
for byte.

## What this suite is not

- It is Russian Wikipedia prose with six writing tasks. It says nothing about
  code, chat slang, tool calls, images or multi-turn behaviour.
- The measurement (`dev`) pool was already used during earlier Maya tuning.
  This is a baseline corpus, not a blind holdout; a final check needs the
  disjoint pool listed in `suite.py`, fetched and frozen separately.
- It measures warmed single-request prefill and decode, not concurrency,
  cold-server TTFT or answer quality. TG256 is a timing budget, not a quality
  reference.
