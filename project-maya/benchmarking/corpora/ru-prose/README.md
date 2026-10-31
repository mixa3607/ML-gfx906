# ru-prose

Russian Wikipedia prose and six writing tasks, defined in `corpus.py`.
`sources.jsonl` contains 12 warmup and 24 dev articles. The 48 `HOLDOUT` titles
are reserved for a separate final check; their text is not shipped or fetched.
The dev pool has already been used for Maya tuning and is not a blind holdout.

Each source record includes the page id, revision URL, license and article text.
License: CC BY-SA; follow the linked article history and Wikipedia terms when
redistributing excerpts. This is a prose throughput workload, not a quality test.

Commands and request format: [benchmarking README](../../README.md).
