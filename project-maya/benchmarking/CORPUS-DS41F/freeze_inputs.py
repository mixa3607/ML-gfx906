#!/usr/bin/env python3
"""Freeze the DS4.1F benchmark suite: 12 warmups + a two-round PP 2K-32K sweep.

Run this in the Maya container with the pinned Maya source (see README.md):

    MAYA_ROOT=/src python3 freeze_inputs.py \
        --source sources.jsonl --out-dir . --tokenizer /data/ds4/tokenizer

It writes, all from the frozen ``sources.jsonl``:

    cases.jsonl            the requests themselves (ids, text, passages, hashes)
    suite.json             the feed order, with human-readable fields
    cases.manifest.json    counts, protocol, tokenizer/source/file hashes
    CASES.md               one readable section per request
    SOURCES.md             the attributed source articles

The case ids, token ids and hashes are deterministic: rerunning with the same
inputs reproduces the files byte for byte.  A change to the suite means a new
corpus directory, not editing these files.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

SEED = 20261024
TG = 256
WARMUP_PP = 2048
WARMUP_COUNT = 12
MEASURE_PP = [2048, 4096, 8192, 16384, 32768]
ROUNDS = 2

# The 12 warmups are shared with project-maya/ds41-pr592 (same pool, seed and
# lengths), so old and new runs warm the engine on identical requests.  Pinning
# the first prompt's hash proves that this suite still reproduces them.
WARMUP_REFERENCE_SHA = '1429132bb086e222f8c578ef8c852712a05aaaafad09094fcdc5fedfad10a7c2'

# Provenance of the encoder that renders the prompts (checked by hand: v1.1.38
# reproduces the v1.1.35-era ds41-pr592 cases bit for bit).
ENCODER = {'project': 'project-maya', 'tag': 'v1.1.38',
           'commit': 'cf6472cc84489765791ad97bb55b395e8f442088'}

PROTOCOL = [
    'Load the model once and keep the process alive for the whole suite.',
    'Send the 12 warmup requests in file order, TG256 each; do not score them.',
    'In the same process, send the 10 measurement requests in file order, TG256 each.',
    'One request at a time, greedy, speculation off, approximate skips off.',
    'Zero cross-request prefix/KV reuse; ordinary KV caching inside one generation stays.',
    'Do not reload the model, clear its caches or change placement settings between phases.',
    'Keep incomplete requests; a natural EOS before 256 tokens is not a completed TG256 sample.',
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_atomic(path: Path, text: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f'{path} exists; pass --force to regenerate')
    path.write_text(text)


def load_corpus_module(root: Path):
    spec = importlib.util.spec_from_file_location('corpus', root / 'corpus.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_cases(cases, sources, split):
    documents = [json.loads(s) for s in sources.read_text().splitlines() if s.strip()]
    by_page = {d['pageid']: d for d in documents}
    assert len(by_page) == len(documents), 'duplicate source pages'
    assert len({tuple(c['ids']) for c in cases}) == len(cases), 'duplicate requests'
    used = {}
    for case in cases:
        assert len(case['ids']) == case['pp'], (case['id'], len(case['ids']), case['pp'])
        assert case['ids'][0] == 0, (case['id'], 'does not start with BOS')
        for p in case['passages']:
            doc = by_page[p['pageid']]
            assert 0 <= p['start_byte'] < p['end_byte'] <= len(doc['text'].encode()), (case['id'], p)
            key = (split, p['pageid'])
            assert p['start_byte'] >= used.get(key, 0), (case['id'], 'reuses a source range', p)
            used[key] = p['end_byte']


def render_text(tok, ids):
    """Exact prompt text; falls back to replacement if the cut split a character."""
    raw = b''.join(tok.token_bytes(t) for t in ids)
    try:
        text = raw.decode('utf-8')
        exact = True
    except UnicodeDecodeError:
        text = raw.decode('utf-8', 'replace')
        exact = False
    return text, exact


def markdown_preview(text, limit=320):
    """First characters of the prompt with the line structure kept visible."""
    body = re.sub(r'[ \t]*\n[ \t\n]*', ' ⏎ ', text)
    body = re.sub(r'[ \t]+', ' ', body)
    return body[:limit] + ('…' if len(body) > limit else '')


def cases_markdown(cases):
    out = [
        '# Suite cases',
        '',
        f'{len(cases)} requests: {WARMUP_COUNT} unscored warmups at PP{WARMUP_PP}, then '
        f'{len(cases) - WARMUP_COUNT} scored measurements in two rounds '
        f'({" -> ".join(str(p) for p in MEASURE_PP)} each). Every request asks for TG{TG}.',
        '',
        'PP is the complete tokenised input, including the chat template and the assistant '
        'header. The task is in front of the material; the source prose is cut only at the end '
        'so the token count is exact. See `README.md` for the protocol and `suite.json` for the '
        'machine-readable order.',
        '',
        'In the previews, `⏎` marks a line break and the `<｜...｜>` sequences are the chat '
        'template tokens that the engine actually receives.',
        '',
        '## Feed order',
        '',
        '| # | id | phase | PP | lead article | task |',
        '| ---: | --- | --- | ---: | --- | --- |',
    ]
    for n, c in enumerate(cases, 1):
        phase = 'warmup (unscored)' if c['phase'] == 'warmup' else 'measurement'
        out.append(f"| {n} | `{c['id']}` | {phase} | {c['pp']} | {c['lead_title']} | "
                   f"{c['task_index']}. {c['task_label']} |")
    out += ['', '## Case details', '']
    for n, c in enumerate(cases, 1):
        articles = ', '.join(f"{a['title']} (rev {a['revision']}, {a['bytes']:,} B)" for a in c['articles'])
        out += [
            f"### {n}. `{c['id']}`",
            '',
            f"- Phase: **{c['phase']}**" + (' (not scored: it warms the cache)' if c['phase'] == 'warmup' else ''),
            f"- Exact input length: **PP {c['pp']}** tokens; target output: **TG {TG}** tokens",
            f"- Lead article: **{c['lead_title']}**",
            f"- Task {c['task_index']}/6 ({c['task_label']}): {c['task']}",
            f"- Source passages: {articles}",
            f"- Prompt SHA-256: `{c['prompt_sha256']}`",
            f"- Prompt begins: \"{markdown_preview(c['rendered_text'])}\"",
            '',
        ]
    return '\n'.join(out)


def sources_markdown(documents):
    out = [
        '# Source articles',
        '',
        'Russian Wikipedia prose, frozen at the listed revision. The full text is in '
        '`sources.jsonl`; this table is for reading and attribution.',
        '',
        '| split | article | bytes | revision | text SHA-256 |',
        '| --- | --- | ---: | --- | --- |',
    ]
    for d in documents:
        out.append(f"| {d['split']} | {d['title']} | {len(d['text'].encode()):,} | "
                   f"[{d['revision']}]({d['url']}) | `{d['sha256'][:16]}` |")
    out += ['', 'License: CC BY-SA; follow the article history and Wikipedia terms when '
            'redistributing excerpts. Medical and legal texts are performance inputs, not advice.', '']
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', type=Path, required=True, help='frozen sources.jsonl')
    ap.add_argument('--out-dir', type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument('--tokenizer', default='/data/ds4/tokenizer')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    root = Path(__file__).resolve().parent
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    corpus = load_corpus_module(root)
    if not corpus.MAYA_ROOT.is_dir():
        raise SystemExit(f'MAYA_ROOT={corpus.MAYA_ROOT} is not a directory; mount the Maya source there')

    warmup = corpus.build_cases(args.source, 'warmup', [WARMUP_PP], WARMUP_COUNT, SEED, args.tokenizer)
    measurement = corpus.build_cases(args.source, 'dev', MEASURE_PP * ROUNDS, len(MEASURE_PP) * ROUNDS,
                                     SEED, args.tokenizer)
    if warmup[0]['prompt_sha256'] != WARMUP_REFERENCE_SHA:
        raise SystemExit('Warmup prompts differ from the ds41-pr592 suite; the pipe changed')
    check_cases(warmup, args.source, 'warmup')
    check_cases(measurement, args.source, 'dev')

    tok, _ = corpus.load_encoder(args.tokenizer)
    if tok.token_bytes(0).decode() != '<｜begin▁of▁sentence｜>':
        raise SystemExit('Token zero is not the expected BOS')
    rows, inexact = [], []
    for case in warmup + measurement:
        case = dict(case)
        case['phase'] = 'warmup' if case['phase'] == 'warmup' else 'measurement'
        case['ctx'] = case['pp']
        text, exact = render_text(tok, case['ids'])
        if exact and tok.encode(text, parse_special=True) != case['ids']:
            raise SystemExit(f"{case['id']}: rendered text does not tokenise back to its ids")
        if not exact:
            inexact.append(case['id'])
        case['rendered_text'] = text
        case['rendered_text_exact'] = exact
        rows.append(case)

    cases_text = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
    steps = [{'step': n, 'id': r['id'], 'phase': r['phase'],
              'scored': r['phase'] == 'measurement', 'pp': r['pp'], 'tg': TG,
              'lead_title': r['lead_title'], 'task_index': r['task_index'],
              'task_label': r['task_label'], 'prompt_sha256': r['prompt_sha256']}
             for n, r in enumerate(rows, 1)]
    tokenizer_files = {p.name: sha(p) for p in sorted(Path(args.tokenizer).iterdir()) if p.is_file()}
    suite = {'suite': 'ds41f-warm-cache-pp2k-32k', 'model': 'deepseek-v4.1-flash',
             'seed': SEED, 'tg': TG, 'encoder': ENCODER,
             'warmup': {'pp': WARMUP_PP, 'count': WARMUP_COUNT, 'scored': False},
             'measurement': {'pp': MEASURE_PP, 'rounds': ROUNDS,
                             'count': len(MEASURE_PP) * ROUNDS, 'scored': True},
             'tokenizer_files': tokenizer_files, 'steps': steps}

    # Write the data first: the manifest hashes it.
    write_atomic(out / 'cases.jsonl', cases_text, args.force)
    write_atomic(out / 'suite.json', json.dumps(suite, ensure_ascii=False, indent=2) + '\n', args.force)
    write_atomic(out / 'CASES.md', cases_markdown(rows), args.force)
    write_atomic(out / 'SOURCES.md', sources_markdown(
        [json.loads(s) for s in args.source.read_text().splitlines() if s.strip()]), args.force)
    hashed = ('cases.jsonl', 'suite.json', 'CASES.md', 'SOURCES.md', 'corpus.py', 'freeze_inputs.py')
    manifest = {
        'suite': suite['suite'],
        'model': suite['model'],
        'purpose': 'warm-cache prefill and decode throughput, one request at a time',
        'seed': SEED,
        'tg': TG,
        'order': [s['id'] for s in steps],
        'protocol': PROTOCOL,
        'encoder': ENCODER,
        'sources': {'file': 'sources.jsonl', 'sha256': sha(args.source),
                    'articles': {'warmup': 12, 'dev': 24}},
        'tokenizer_files': tokenizer_files,
        'files': {name: sha(out / name) for name in hashed},
        'rendered_text_exact': not inexact,
        'rendered_text_inexact_cases': inexact,
        'notes': [
            'The 12 warmups are identical to project-maya/ds41-pr592 (same pool, seed and PP).',
            'Sources are frozen Russian Wikipedia prose: page id, revision, URL and SHA-256 per article.',
            'The dev pool was used by earlier Maya tuning; this is a baseline corpus, not a blind holdout.',
            'The holdout article list in corpus.py is intentionally not part of sources.jsonl.',
            'PP is the complete tokenised input; only source prose is cut to reach it.',
            'TG256 is a request parameter, not part of the frozen files.',
            'README.md is documentation; it is not covered by the hashes above.',
        ],
    }
    write_atomic(out / 'cases.manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                 args.force)
    print(json.dumps({'cases': len(rows), 'warmups': WARMUP_COUNT,
                      'measurements': len(rows) - WARMUP_COUNT, 'tg': TG,
                      'files': manifest['files']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
