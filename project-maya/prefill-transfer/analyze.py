#!/usr/bin/env python3
"""Independently verify completed timing rows and summarize the serial experiment."""
import argparse
import hashlib
import json
from pathlib import Path

from run import pooled


def verify(root, name, seed, cases):
    folder = root / name / name
    manifest = json.loads((folder / 'manifest.json').read_text())
    exit_record = json.loads((root / name / 'exit.json').read_text())
    rows = [json.loads(s) for s in (folder / 'results.jsonl').read_text().splitlines()]
    if not manifest['complete'] or not exit_record['complete']:
        raise ValueError('Incomplete session: ' + name)
    if manifest['seed_sha256'] != seed or manifest['cases_sha256'] != cases:
        raise ValueError('Different initial inputs: ' + name)
    expected = [2048] * 12 + [2048, 4096, 8192] * 2
    if len(rows) != 18 or [r['done']['pp'] for r in rows] != expected:
        raise ValueError('Incomplete PP schedule: ' + name)
    for row in rows:
        d = row['done']
        if not row['valid'] or d['tg'] != 256 or d['finish'] != 'length' or d['reused']:
            raise ValueError('Incomplete TG256 or reused input: ' + name)
        if d['tg'] != len(row['tokens']) or not 0 <= d['accepted'] <= d['drafted']:
            raise ValueError('Invalid native counters: ' + name)
    if [r['phase'] for r in rows] != ['warmup'] * 12 + ['measurement'] * 6:
        raise ValueError('Unexpected phases: ' + name)
    selected = rows[12:]
    metrics = pooled(selected)
    if metrics != manifest['metrics']:
        raise ValueError('Native pooled summary mismatch: ' + name)
    before, after = manifest['before'], manifest['after']
    for key in ('oom', 'oom_kill'):
        if before['memory.events'][key] != after['memory.events'][key]:
            raise ValueError('Resource failure: ' + name)
    if before['cpu.stat']['nr_throttled'] != after['cpu.stat']['nr_throttled']:
        raise ValueError('CPU throttling: ' + name)
    memory = max(int(r['snapshot']['memory.current']) for r in rows) / 2**30
    return {'name': name, **metrics, 'by_pp': manifest['by_pp'],
            'load_s': manifest['load_s'], 'post_request_memory_gib_max': memory,
            'known_blas_diagnostics': manifest.get('known_blas_diagnostics'),
            'full_copies': manifest['full_copies']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    initial = json.loads((args.root / 'before.json').read_text())
    cases = hashlib.sha256((args.root / 'input/cases.jsonl').read_bytes()).hexdigest()
    experiment = json.loads((args.root / 'experiment.json').read_text())
    sessions = [s['name'] for s in experiment['sessions']
                if not s['manifest']['arguments']['diagnostic']]
    results = [verify(args.root, name, initial['seed_sha256'], cases) for name in sessions]
    summary = {'complete': experiment['complete'], 'cleanup': experiment['cleanup'],
               'seed_sha256': initial['seed_sha256'], 'cases_sha256': cases, 'results': results}
    (args.root / 'verified-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('| Session | PP2K | PP4K | PP8K | Pooled PP | Decode | Wall s |')
    print('|---|---:|---:|---:|---:|---:|---:|')
    for r in results:
        pp = [r['by_pp'][str(n)]['prefill_tok_s'] for n in (2048, 4096, 8192)]
        values = [*pp, r['prefill_tok_s'], r['decode_tok_s'], r['wall_s']]
        print('| ' + r['name'] + ' | ' + ' | '.join(f'{v:.2f}' for v in values) + ' |')


if __name__ == '__main__':
    main()
