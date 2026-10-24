#!/usr/bin/env python3
"""Pool scored native timings by PP length; never count warmup or average rates."""
import argparse
import json
from pathlib import Path


def pool(rows):
    if not rows or any(r['done']['reused'] or r['done']['tg'] != 256 for r in rows):
        raise ValueError('Expected nonempty zero-reuse TG256 measurements')
    pp = sum(r['done']['pp'] for r in rows)
    pp_s = sum(r['done']['prompt_ms'] / 1000 for r in rows)
    steps = sum(r['done']['tg'] - 1 for r in rows)
    decode_s = sum((r['done']['tg'] - 1) / r['tg_tok_s'] for r in rows)
    return {'requests': len(rows), 'pp_tok_s': pp / pp_s,
            'tg_tok_s': steps / decode_s, 'wall_s': sum(r['wall_s'] for r in rows),
            'native_ttft_mean_s': sum(r['ttft_s'] for r in rows) / len(rows)}


def summarize(rows):
    scored = [r for r in rows if r['phase'] != 'warmup']
    return {'warmup_requests': len(rows) - len(scored), 'overall': pool(scored),
            'by_pp': {pp: pool([r for r in scored if r['pp'] == pp])
                      for pp in sorted({r['pp'] for r in scored})}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('runs', type=Path, nargs='+')
    args = p.parse_args()
    output = []
    for run in args.runs:
        rows = [json.loads(s) for s in (run / 'results.jsonl').read_text().splitlines() if s.strip()]
        manifest = json.loads((run / 'manifest.json').read_text())
        output.append({'run': str(run), 'cases_sha256': manifest['cases_sha256'],
                       'validation_dumps_enabled': manifest['dump'], **summarize(rows)})
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
