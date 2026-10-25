#!/usr/bin/env python3
"""Summarize completed screens without scoring warmups or incomplete runs."""
import argparse
import json
from pathlib import Path


def pooled(rows):
    scored = [row for row in rows if row['phase'] == 'measurement']
    if len(scored) != 3 or not all(row['valid'] for row in rows) or len(rows) != 6:
        raise ValueError('Expected six valid requests, including three scored requests')
    decode_s = sum(row['done']['decode_ms'] / 1000 for row in scored)
    delivery_s = sum(row['token_delivery_s'][-1] - row['token_delivery_s'][0] for row in scored)
    steps = sum(row['done']['tg'] - 1 for row in scored)
    drafted = sum(row['done']['drafted'] for row in scored)
    accepted = sum(row['done']['accepted'] for row in scored)
    return {'pp_tok_s': sum(row['done']['pp'] for row in scored) /
            sum(row['done']['prompt_ms'] / 1000 for row in scored),
            'native_decode_tok_s': steps / decode_s,
            'delivery_decode_tok_s': steps / delivery_s,
            'wall_s': sum(row['wall_s'] for row in scored),
            'drafts_offered': drafted, 'drafts_accepted': accepted,
            'acceptance': accepted / drafted if drafted else None,
            'accepted_per_generated': accepted / sum(row['done']['tg'] for row in scored),
            'max_observed_memory_gib': max(int(row[side]['memory.current']) / 2**30
                                           for row in rows for side in ('before', 'after')),
            'cumulative_cgroup_peak_gib': max(int(row['after']['memory.peak']) / 2**30 for row in rows),
            'warmup_native_decode_tok_s': [row['native_tg_tok_s'] for row in rows if row['phase'] == 'warmup']}


def compare_tokens(baseline, candidate):
    out = []
    for left, right in zip(baseline, candidate):
        if left['id'] != right['id']:
            raise ValueError('Mismatched case order')
        a, b = left['tokens'], right['tokens']
        first = next((i for i, pair in enumerate(zip(a, b)) if pair[0] != pair[1]), None)
        out.append({'id': left['id'], 'identical': a == b, 'first_different_token_zero_based': first})
    return out


def summarize(root):
    result = {'scope': 'coarse A/B/C, 3 warmups + 3 measurements per start, PP2048/TG256',
              'limitations': ['single fixed order; no reverse repeat', 'three warmups do not establish steady state',
                              'no general quality, image or long-context validation',
                              'native protocol, not HTTP; token delivery can be bursty',
                              'memory.peak is cumulative across all starts in the same cgroup'], 'runs': {}}
    rows_by_mode = {}
    for name in ('A-none', 'B-on-default', 'C-on-spread'):
        path = root / name
        if not (path / 'manifest.json').exists():
            result['runs'][name] = {'complete': False, 'error': 'No completed manifest'}
            continue
        manifest = json.loads((path / 'manifest.json').read_text())
        rows = [json.loads(line) for line in (path / 'results.jsonl').read_text().splitlines()] if (
            path / 'results.jsonl').exists() else []
        rows_by_mode[name] = rows
        record = {'complete': manifest['complete'], 'error': manifest.get('error'),
                  'cases_sha256': manifest['cases_sha256'], 'seed_profile_sha256': manifest['seed_profile_sha256'],
                  'load_s': manifest.get('load_s'), 'full_copies': manifest.get('full_copies')}
        if manifest['complete']:
            record.update(pooled(rows))
            if name != 'A-none' and not record['drafts_offered']:
                record.update(complete=False, error='No drafts offered: speculation not exercised')
        result['runs'][name] = record
    baseline = result['runs']['A-none']
    for name, record in result['runs'].items():
        if name == 'A-none' or not record['complete'] or not baseline['complete']:
            continue
        if record['cases_sha256'] != baseline['cases_sha256'] or record['seed_profile_sha256'] != baseline['seed_profile_sha256']:
            raise ValueError('Different cases or initial profiles')
        record['decode_gain_pct'] = 100 * (record['native_decode_tok_s'] / baseline['native_decode_tok_s'] - 1)
        record['wall_reduction_pct'] = 100 * (1 - record['wall_s'] / baseline['wall_s'])
        record['token_comparison'] = compare_tokens(rows_by_mode['A-none'], rows_by_mode[name])
        record['passes_10pct_screen'] = record['decode_gain_pct'] >= 10
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    result = summarize(args.root)
    (args.root / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
