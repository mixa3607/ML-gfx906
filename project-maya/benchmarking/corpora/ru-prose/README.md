# ru-prose

Model-independent Russian prose corpus for throughput suites: real Russian
Wikipedia articles and six writing tasks. It defines *what is read*; a suite
defines the model and the PP/TG schedule.

Rules for corpora and suites are in [`../../SUITES.md`](../../SUITES.md); the
measurement protocol is in [`../../README.md`](../../README.md).

## Pools

| Split | Articles | Used for | Shipped |
| --- | ---: | --- | --- |
| `warmup` | 12 | unscored warmup requests | yes |
| `dev` | 24 | measured requests | yes |
| `holdout` | 48 | final post-tuning check | **no** (titles only) |

Every split is disjoint: an article used for warmup is never used for a
measurement, and the holdout text is deliberately absent from
`sources.jsonl` so a suite built on this corpus cannot be tuned against it.
The dev pool is larger than one suite consumes, so long prompts continue into
another article instead of repeating paragraphs.

## Tasks

The six tasks are cycled in order within a split:

| # | Label | Task |
| ---: | --- | --- |
| 1 | explain to a layperson | Объясни содержание человеку без специальной подготовки. Разверни ответ: не менее 500 слов, с примерами и оговорками. |
| 2 | analytical memo | Подготовь подробную аналитическую записку: основные положения, причинные связи, ограничения и открытые вопросы. Не менее 500 слов. |
| 3 | tutorial dialogue | Составь развёрнутый учебный диалог: собеседник сомневается, эксперт отвечает и исправляет заблуждения. Не менее 500 слов. |
| 4 | talk plan with Q&A | Напиши подробный план выступления с пояснениями, примерами и ответами на возможные вопросы аудитории. Не менее 500 слов. |
| 5 | plain-language article | Преобразуй материал в ясную статью для неспециалиста. Разделяй установленные факты и предположения; не менее 500 слов. |
| 6 | critical review | Разбери материал критически: терминология, аргументы, возможные ошибки интерпретации и вопросы для проверки. Не менее 500 слов. |

The requested answer length exists so a TG budget is usually reached; natural
EOS is still respected. The tasks are performance inputs, not a quality
reference.

## Files

| File | Contents |
| --- | --- |
| `corpus.py` | `NAME`, `SOURCES`, `TASKS`, `TASK_LABELS`, `SOURCE_NOTE`, `LICENSE_NOTE`, `NOTES` |
| `sources.jsonl` | frozen articles: `split`, `title`, `pageid`, `revision`, `url`, `license`, `sha256`, `text` |
| `SOURCES.md` | human-readable article table (generated) |
| `README.md` | this file |

## Freezing and updating

```bash
cd project-maya/benchmarking

# download the shipped pools (warmup + dev); network, once per revision
python3 freeze.py fetch corpora/ru-prose

# regenerate the human-readable table from the frozen file
python3 freeze.py sources corpora/ru-prose
```

The shipped `sources.jsonl` is pinned in every suite's manifest by SHA-256, so
a suite records exactly which corpus text it read. To add the holdout, fetch it
into a **separate** corpus (or a separate file) and freeze a new suite; do not
add it to this file, or the baseline and the final check share text.

## Provenance and license

The articles are Russian Wikipedia prose, frozen per revision; `SOURCES.md`
links each revision and shows a text hash. License: CC BY-SA; follow the
article history and Wikipedia terms when redistributing excerpts.

## Limits

- Wikipedia prose is not chat, code, tool use, images or multi-turn dialogue.
- The `dev` pool was used by earlier Maya tuning. A suite built on it is a
  baseline, not a blind holdout; use the holdout pool for the final check.
- Medical and legal articles are performance inputs, not advice.
