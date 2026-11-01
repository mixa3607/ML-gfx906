"""CPU-only comparison of the four completed experiment arms."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
METRICS = ('prefill_tokens_per_second', 'decode_tokens_per_second')


def compare():
    control = json.loads((ROOT / 'control/summary.json').read_text())
    comparison = {}
    for name in ('control', 'skip1', 'hcfuse1', 'hcfuse2'):
        path = ROOT / name
        summary = json.loads((path / 'summary.json').read_text())
        rows = [json.loads(line) for line in (path / 'results.jsonl').read_text().splitlines()]
        measured = [r['done'] for r in rows if r['phase'] == 'measurement']
        assert len(measured) == 10
        passes = []
        for start in (0, 5):
            group = measured[start:start + 5]
            passes.append({
                'prefill_tokens_per_second': 1000 * sum(r['prompt_tokens'] for r in group) / sum(r['prompt_ms'] for r in group),
                'decode_tokens_per_second': 1000 * sum(r['generated'] for r in group) / sum(r['decode_ms'] for r in group),
            })
        comparison[name] = {
            'pooled_measurement': summary['pooled_measurement'],
            'pooled_speed_delta_percent_vs_control': {
                metric: 100 * (summary['pooled_measurement'][metric] / control['pooled_measurement'][metric] - 1)
                for metric in METRICS
            },
            'by_pp': summary['by_pp'],
            'by_pp_speed_delta_percent_vs_control': {
                pp: {metric: 100 * (values[metric] / control['by_pp'][pp][metric] - 1) for metric in METRICS}
                for pp, values in summary['by_pp'].items()
            },
            'by_measurement_pass': passes,
        }
    (ROOT / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
    print('| Arm | PP tok/s | PP delta | TG tok/s | TG delta |')
    print('| --- | ---: | ---: | ---: | ---: |')
    for name, arm in comparison.items():
        pp, tg = (arm['pooled_measurement'][m] for m in METRICS)
        dpp, dtg = (arm['pooled_speed_delta_percent_vs_control'][m] for m in METRICS)
        print(f'| {name} | {pp:.2f} | {dpp:+.2f}% | {tg:.2f} | {dtg:+.2f}% |')
    return comparison


if __name__ == '__main__':
    compare()
