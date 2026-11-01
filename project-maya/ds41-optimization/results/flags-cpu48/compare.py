"""Recompute the five-arm comparison on CPU, without performance verdicts."""

import json

from analysis import (ARMS, REFERENCE, ROOT, delta, read_json, validate,
                      verify_hashes, write_json)


def group_deltas(current, reference):
    return {
        pp: {
            'prefill_percent': delta(group['prefill_tokens_per_second'], base['prefill_tokens_per_second']),
            'decode_percent': delta(group['decode_tokens_per_second'], base['decode_tokens_per_second']),
        }
        for pp, group, base in [
            *[(pp, current['by_pp'][pp], reference['by_pp'][pp]) for pp in reference['by_pp']],
            ('pooled', current['pooled_measurement'], reference['pooled_measurement']),
        ]
    }


def request_deltas(current, reference):
    assert len(current) == len(reference) == 10
    result = []
    for row, base in zip(current, reference):
        assert (row['id'], row['phase']) == (base['id'], base['phase'])
        now, before = row['done'], base['done']
        assert now['prompt_tokens'] == before['prompt_tokens']
        result.append({
            'id': row['id'],
            'prefill_percent': delta(now['prompt_tokens'] / now['prompt_ms'], before['prompt_tokens'] / before['prompt_ms']),
            'decode_percent': delta(now['generated'] / now['decode_ms'], before['generated'] / before['decode_ms']),
        })
    return result


def main():
    summaries, rows, diagnostics, runs = {}, {}, {}, {}
    for arm in ARMS:
        out = ROOT / arm
        verify_hashes(out)
        summary = validate(out, arm)
        assert summary == read_json(out / 'summary.json')
        summaries[arm] = summary
        rows[arm] = [r for r in map(json.loads, (out / 'results.jsonl').read_text().splitlines())
                     if r['phase'] == 'measurement']
        assert read_json(out / 'host-exit.json')['kubectl_exec_exit_code'] == 0
        for name in ('gpu-before.txt', 'gpu-after-cleanup.txt'):
            text = (out / name).read_text()
            gpus = json.loads(text[text.index('['):])
            assert {r['gpu'] for r in gpus} == {0, 1, 2, 3}
            assert all(r['gfx']['value'] == 0 and r['vram_used']['unit'] == 'MB'
                       and r['vram_used']['value'] < 32 for r in gpus)
        log = (out / 'engine.log').read_text()
        diagnostics[arm] = {
            'rocblaslt_errors': log.count('rocblaslt error:'),
            'hip_module_load_failures': log.count('hipModuleLoad failed:'),
            'hc_fuse_checks': log.count('HC fuse check'),
            'route_fuse_checks': log.count('route fuse check'),
        }
        metadata = read_json(out / 'run-metadata.json')
        runs[arm] = {key: metadata[key] for key in ('started_utc', 'finished_utc', 'runner_exit_code')}
    comparison = {
        'overrides': ARMS, 'runs': runs, 'summaries': summaries, 'diagnostics': diagnostics,
        'control_vs_prior_cpu48': group_deltas(summaries['control'], read_json(REFERENCE / 'summary.json')),
        'deltas_vs_control': {
            arm: {'groups': group_deltas(summaries[arm], summaries['control']),
                  'per_request': request_deltas(rows[arm], rows['control'])}
            for arm in ARMS if arm != 'control'
        },
    }
    write_json(ROOT / 'comparison.json', comparison)
    lines = ['# Five-arm CPU48 results', '',
             'No performance success/failure criteria or baseline changes are applied.', '',
             '| Arm | PP tok/s | vs control | TG tok/s | vs control | Accepted / offered |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for arm, summary in summaries.items():
        group = summary['pooled_measurement']
        diffs = comparison['deltas_vs_control'][arm]['groups']['pooled'] if arm != 'control' else None
        pp = f"{diffs['prefill_percent']:+.2f}%" if diffs else '—'
        tg = f"{diffs['decode_percent']:+.2f}%" if diffs else '—'
        lines.append(f"| {arm} | {group['prefill_tokens_per_second']:.2f} | {pp} | {group['decode_tokens_per_second']:.2f} | {tg} | {group['drafts_accepted']} / {group['drafts_offered']} ({100 * group['draft_acceptance']:.2f}%) |")
    drift = comparison['control_vs_prior_cpu48']['pooled']
    lines += ['', f"Fresh control vs recorded CPU48: PP {drift['prefill_percent']:+.2f}%, TG {drift['decode_percent']:+.2f}%."]
    for label, metric, change in (('Prefill', 'prefill_tokens_per_second', 'prefill_percent'),
                                  ('Decode', 'decode_tokens_per_second', 'decode_percent')):
        lines += ['', f'## {label} by prompt length', '',
                  '| PP | control | skip | Δ | swizzle | Δ | hcfuse | Δ | routefuse | Δ |',
                  '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        for pp, base in summaries['control']['by_pp'].items():
            cells = [pp, f'{base[metric]:.2f}']
            for arm in list(ARMS)[1:]:
                value = summaries[arm]['by_pp'][pp][metric]
                diff = comparison['deltas_vs_control'][arm]['groups'][pp][change]
                cells.extend((f'{value:.2f}', f'{diff:+.2f}%'))
            lines.append('| ' + ' | '.join(cells) + ' |')
    (ROOT / 'comparison.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
