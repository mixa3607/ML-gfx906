#!/usr/bin/env python3
"""Pool completed scored requests, never warmups or incomplete TG256 samples."""
import argparse
import json
from pathlib import Path


def pool(rows):
    d = [r['done'] for r in rows]
    return {'requests': len(rows),
            'pp_tok_s': sum(x['pp'] for x in d) / sum(x['prompt_ms'] / 1000 for x in d),
            'native_decode_tok_s': sum(x['tg'] - 1 for x in d) / sum(x['decode_ms'] / 1000 for x in d),
            'mean_ttft_s': sum(r['ttft_s'] for r in rows) / len(rows),
            'wall_s': sum(r['wall_s'] for r in rows),
            'drafted': sum(x['drafted'] for x in d), 'accepted': sum(x['accepted'] for x in d)}


def session(path):
    manifest = json.loads((path / 'manifest.json').read_text())
    rows = [json.loads(s) for s in (path / 'results.jsonl').read_text().splitlines()]
    warm = [r for r in rows if r['phase'] == 'warmup']
    valid_warmup = len(warm) == 12 and all(r['complete_tg256'] and not r.get('validation_error') for r in warm)
    result = {'manifest': manifest, 'valid_warmup': valid_warmup, 'by_context': {},
              'warmups': [{k: r[k] for k in ('id', 'done', 'complete_tg256')} for r in warm]}
    for ctx in (0, 4096, 8192, 16384):
        scored = [r for r in rows if r['phase'] == 'measurement' and r['ctx'] == ctx]
        valid = (valid_warmup and len(scored) == 2 and
                 all(r['complete_tg256'] and not r.get('validation_error') for r in scored))
        result['by_context'][str(ctx)] = {'valid': valid, 'actual_tg': [r['done']['tg'] for r in scored],
                                          'metrics': pool(scored) if valid else None}
    return result, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root', type=Path)
    args = ap.parse_args()
    result, raw = {}, {}
    for name in ('A-baseline', 'B-pr592', 'A2-baseline'):
        path = args.root / name
        if (path / 'results.jsonl').exists():
            result[name], raw[name] = session(path)
    comparisons = {}
    for name in ('B-pr592', 'A2-baseline'):
        if name not in result or 'A-baseline' not in result:
            continue
        for field in ('cases_sha256', 'seed_profile_sha256'):
            if result[name]['manifest'][field] != result['A-baseline']['manifest'][field]:
                raise ValueError(f'Comparison has different {field}')
        comparisons[name] = {}
        reference = {r['id']: r for r in raw['A-baseline']}
        for ctx in (0, 4096, 8192, 16384):
            key = str(ctx)
            a, b = result['A-baseline']['by_context'][key], result[name]['by_context'][key]
            scored = [r for r in raw[name] if r['phase'] == 'measurement' and r['ctx'] == ctx]
            item = {'output_tokens_match': (all(r['tokens'] == reference[r['id']]['tokens'] for r in scored)
                                            if scored else None), 'pairs': len(scored),
                    'first_token_mismatch': [next((i for i, (x, y) in enumerate(zip(r['tokens'], reference[r['id']]['tokens']))
                                                   if x != y), None) for r in scored]}
            if a['valid'] and b['valid']:
                item['delta_pct'] = {metric: 100 * (b['metrics'][metric] / a['metrics'][metric] - 1)
                                     for metric in ('pp_tok_s', 'native_decode_tok_s', 'wall_s')}
            comparisons[name][key] = item
    summary = {'sessions': result, 'comparisons': comparisons}
    gate = args.root / 'startup-pr592/result.json'
    if gate.exists():
        summary['candidate_gate'] = json.loads(gate.read_text())
        summary['status'] = ('candidate_gate_failed_no_speed_comparison' if not summary['candidate_gate']['complete']
                             else 'candidate_gate_passed')
    (args.root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'comparisons': comparisons, 'metrics':
                     {name: item['by_context'] for name, item in result.items()}}, indent=2))


if __name__ == '__main__':
    main()
