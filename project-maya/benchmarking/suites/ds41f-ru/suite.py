#!/usr/bin/env python3
"""The ``ds41f-ru`` suite: DeepSeek-V4.1-Flash reading the ``ru-prose`` corpus.

A suite is model-specific and schedule-specific; the text it reads is a corpus
(``../corpora/ru-prose/``).  This file fixes:

- the model and the pinned chat encoder, tokenizer settings and assistant header;
- the seed, the warmup and measurement splits, the PP schedule and the TG budget;
- the parts of the harness protocol that differ from the shared default.

The shared machinery is ``../benchkit.py``; the command line is ``../freeze.py``.
"""
from benchkit import PROTOCOL

# Corpus directory under benchmarking/corpora/.
CORPUS = 'ru-prose'

SUITE = {
    'name': 'ds41f-ru-warm-cache-pp2k-32k',
    'model': 'deepseek-v4.1-flash',
    'purpose': 'warm-cache prefill and decode throughput, one request at a time',
    'seed': 20261024,
    'tg': 256,
    'warmup': {'split': 'warmup', 'pp': 2048, 'count': 12},
    'measurement': {'split': 'dev', 'pp': [2048, 4096, 8192, 16384, 32768], 'rounds': 2},
    'task_position': 'front',
    # Maya's DeepSeek chat encoder, with thinking off, ends the user turn with
    # the assistant header and a closed think block.
    'assistant_suffix': '<｜Assistant｜></think>',
    'render_kwargs': {'reasoning_effort': 'none'},
    'bos_text': '<｜begin▁of▁sentence｜>',
    'encoder': {'project': 'project-maya', 'tag': 'v1.1.38',
                'commit': 'cf6472cc84489765791ad97bb55b395e8f442088'},
    'warmup_reference_sha': '1429132bb086e222f8c578ef8c852712a05aaaafad09094fcdc5fedfad10a7c2',
    'protocol': PROTOCOL + [
        'Baseline: approximate prompt skips off, dense and expert precision unmodified.',
    ],
    'notes': [
        'The 12 warmups are identical to project-maya/ds41-pr592 (same pool, seed and PP).',
        'PP is the complete tokenised input; only source prose is cut to reach it.',
        'TG256 is a request parameter, not part of the frozen files.',
        'README.md is documentation; it is not covered by the file hashes in the manifest.',
    ],
}
