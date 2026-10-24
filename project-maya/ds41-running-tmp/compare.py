#!/usr/bin/env python3
"""Compare matching benchmark histories; bit-exact validation never uses tolerance."""
import argparse
import json
from pathlib import Path
import statistics


def load(path):
    rows = [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError(f'Duplicate requests in {path}')
    return rows


def compare(a, b, require_logits=False):
    if not a or not b:
        raise ValueError('Empty benchmark history')
    if [r['id'] for r in a] != [r['id'] for r in b]:
        raise ValueError('Request histories or order differ')
    differences = []
    ratios = {}
    for left, right in zip(a, b):
        if left['prompt_sha256'] != right['prompt_sha256']:
            raise ValueError(f'Inputs differ: {left["id"]}')
        if left['tokens'] != right['tokens']:
            differences.append({'id': left['id'], 'kind': 'tokens'})
        if require_logits:
            if not left.get('logits') or not right.get('logits'):
                raise ValueError('Both runs need --dump; token equality is not bit-exact proof')
            if left['logits']['rows'] != right['logits']['rows']:
                x, y = left['logits']['rows'], right['logits']['rows']
                first = next((i for i, (p, q) in enumerate(zip(x, y)) if p != q), min(len(x), len(y)))
                differences.append({'id': left['id'], 'kind': 'logits', 'first_row': first})
        if left['phase'] != 'warmup':
            group = ratios.setdefault(left['pp'], {'pp': [], 'tg': [], 'ttft': []})
            group['pp'].append(right['pp_tok_s'] / left['pp_tok_s'])
            group['tg'].append(right['tg_tok_s'] / left['tg_tok_s'])
            group['ttft'].append(right['ttft_s'] / left['ttft_s'])
    return {'bit_exact_on_tested_rows': not differences if require_logits else None,
            'differences': differences,
            'paired_median_ratios': {pp: {k: statistics.median(v) for k, v in g.items()}
                                     for pp, g in ratios.items()}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline', type=Path)
    p.add_argument('candidate', type=Path)
    p.add_argument('--require-logits', action='store_true')
    a = p.parse_args()
    result = compare(load(a.baseline), load(a.candidate), a.require_logits)
    print(json.dumps(result, indent=2))
    if result['differences']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
