# ds41f-ru

DeepSeek-V4.1-Flash, thinking off, reading the `ru-prose` corpus.
`suite.py` defines the schedule: 12 unscored PP2048 warmups, then
`[2048, 4096, 8192, 16384, 32768]` twice, with TG256 for all 22 requests.

`cases.jsonl` holds the requests in execution order. The task precedes the source
prose; input length includes the chat envelope and complete assistant header.
The encoder is Maya v1.1.38 (`cf6472cc84489765791ad97bb55b395e8f442088`).

Usage and regeneration: [benchmarking README](../../README.md).
