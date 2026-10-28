#!/usr/bin/env python3
"""Freeze the existing attributed prose corpus for the requested context sweep."""
import hashlib
import importlib.util
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('corpus', root / 'corpus.py')
    corpus = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(corpus)
    corpus.build_cases(root / 'sources.jsonl', root / 'warmup.jsonl', 'warmup',
                       [2048], 12, 20261024, '/data/ds4/tokenizer')
    corpus.build_cases(root / 'sources.jsonl', root / 'measurement-prose.jsonl', 'dev',
                       [4096, 8192, 16384], 6, 20261024, '/data/ds4/tokenizer')
    warm = [json.loads(s) for s in (root / 'warmup.jsonl').read_text().splitlines()]
    measured = [json.loads(s) for s in (root / 'measurement-prose.jsonl').read_text().splitlines()]
    for case in warm:
        case['phase'] = 'warmup'
        case['ctx'] = case['pp']
    rows = list(warm)
    for case in measured:
        case.update(phase='measurement', ctx=case['pp'])
        rows.append(case)
    # A BOS-only request leaves a position-1 checkpoint. If followed by a longer
    # BOS-prefixed prompt, upstream restores that token even with SLOT_KEEP=0.
    for repeat in range(2):
        rows.append({'id': f'measurement-{repeat}-ctx0', 'phase': 'measurement',
                     'ctx': 0, 'pp': 1, 'ids': [0], 'lead_title': 'BOS-only, no user prompt'})
    import sys
    sys.path.insert(0, '/opt/maya/tools')
    from strata_tokenizer import Tokenizer
    tok = Tokenizer.from_dir('/data/ds4/tokenizer')
    if tok.token_bytes(0).decode() != '<｜begin▁of▁sentence｜>':
        raise ValueError('Token zero is not the expected BOS')
    for row in rows:
        row['prompt_sha256'] = hashlib.sha256(json.dumps(row['ids']).encode()).hexdigest()
        raw = b''.join(tok.token_bytes(t) for t in row['ids'])
        row['rendered_text'] = raw.decode('utf-8', errors='replace')
    with (root / 'cases.jsonl').open('x') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    manifest = {'warmups': 12, 'measurements': 8, 'tg': 256,
                'context_order': [4096, 8192, 16384] * 2 + [0, 0],
                'zero_context': 'BOS token 0; actual PP1, not a zero-token prefill',
                'files': {name: sha(root / name) for name in
                          ('cases.jsonl', 'sources.jsonl', 'corpus.py', 'freeze_inputs.py')},
                'tokenizer_files': {p.name: sha(p) for p in Path('/data/ds4/tokenizer').iterdir() if p.is_file()}}
    (root / 'cases.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == '__main__':
    main()
