"""Compare combinations with the earlier control/singles, without verdicts."""

import json

from analysis import (ARMS, ROOT, SINGLES, delta, read_json, single, validate,
                      verify_hashes, write_json)


CONSTITUENTS = {
    'skip-swizzle': ('skip', 'swizzle'),
    'hc-route': ('hcfuse', 'routefuse'),
    'all': ('skip', 'swizzle', 'hcfuse', 'routefuse'),
}


def group_deltas(current, reference):
    groups = [(pp, current['by_pp'][pp], reference['by_pp'][pp]) for pp in reference['by_pp']]
    groups.append(('pooled', current['pooled_measurement'], reference['pooled_measurement']))
    return {
        pp: {
            'prefill_percent': delta(group['prefill_tokens_per_second'], base['prefill_tokens_per_second']),
            'decode_percent': delta(group['decode_tokens_per_second'], base['decode_tokens_per_second']),
        } for pp, group, base in groups
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


def collect(out, summary):
    verify_hashes(out)
    assert summary == read_json(out / 'summary.json')
    assert read_json(out / 'host-exit.json')['kubectl_exec_exit_code'] == 0
    rows = [r for r in map(json.loads, (out / 'results.jsonl').read_text().splitlines())
            if r['phase'] == 'measurement']
    for name in ('gpu-before.txt', 'gpu-after-cleanup.txt'):
        text = (out / name).read_text()
        gpus = json.loads(text[text.index('['):])
        assert {r['gpu'] for r in gpus} == {0, 1, 2, 3}
        assert all(r['gfx']['value'] == 0 and r['vram_used']['unit'] == 'MB'
                   and r['vram_used']['value'] < 32 for r in gpus)
    log = (out / 'engine.log').read_text()
    diagnostics = {
        'rocblaslt_errors': log.count('rocblaslt error:'),
        'hip_module_load_failures': log.count('hipModuleLoad failed:'),
        'hc_fuse_checks': log.count('HC fuse check'),
        'route_fuse_checks': log.count('route fuse check'),
    }
    metadata = read_json(out / 'run-metadata.json')
    run = {key: metadata[key] for key in ('started_utc', 'finished_utc', 'runner_exit_code')}
    return summary, rows, diagnostics, run


def main():
    summaries, rows, diagnostics, runs = {}, {}, {}, {}
    for arm in single.ARMS:
        out = SINGLES / arm
        summaries[arm], rows[arm], diagnostics[arm], runs[arm] = collect(out, single.validate(out, arm))
    for arm in ARMS:
        out = ROOT / arm
        summaries[arm], rows[arm], diagnostics[arm], runs[arm] = collect(out, validate(out, arm))

    def against(arm, reference):
        return {'groups': group_deltas(summaries[arm], summaries[reference]),
                'per_request': request_deltas(rows[arm], rows[reference])}

    comparison = {
        'overrides': ARMS, 'runs': runs, 'summaries': summaries, 'diagnostics': diagnostics,
        'control_source': '../flags-cpu48/control', 'fresh_control': False,
        'deltas_vs_previous_control': {arm: against(arm, 'control') for arm in ARMS},
        'deltas_vs_single_flags': {
            arm: {flag: against(arm, flag) for flag in flags}
            for arm, flags in CONSTITUENTS.items()
        },
        'all_vs_pairs': {pair: against('all', pair) for pair in ('skip-swizzle', 'hc-route')},
    }
    write_json(ROOT / 'comparison.json', comparison)
    lines = ['# CPU48 combinations and recorded single-flag results', '',
             'No fresh control was run. Control and single-flag rows come from the preceding block.',
             'Differences may include drift between blocks; no performance verdict or baseline change is applied.', '',
             '| Arm | PP tok/s | vs saved control | TG tok/s | vs saved control | Accepted / offered |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for arm, summary in summaries.items():
        group = summary['pooled_measurement']
        diffs = group_deltas(summary, summaries['control'])['pooled']
        pp = f"{diffs['prefill_percent']:+.2f}%" if arm != 'control' else '—'
        tg = f"{diffs['decode_percent']:+.2f}%" if arm != 'control' else '—'
        lines.append(f"| {arm} | {group['prefill_tokens_per_second']:.2f} | {pp} | {group['decode_tokens_per_second']:.2f} | {tg} | {group['drafts_accepted']} / {group['drafts_offered']} ({100 * group['draft_acceptance']:.2f}%) |")
    lines += ['', '## Combinations versus constituent single-flag runs', '',
              '| Combination | Compared with | PP delta | TG delta |',
              '| --- | --- | ---: | ---: |']
    for arm, flags in comparison['deltas_vs_single_flags'].items():
        for flag, data in flags.items():
            diffs = data['groups']['pooled']
            lines.append(f"| {arm} | {flag} | {diffs['prefill_percent']:+.2f}% | {diffs['decode_percent']:+.2f}% |")
    lines += ['', '## All four versus each pair', '',
              '| Pair | PP delta | TG delta |', '| --- | ---: | ---: |']
    for pair, data in comparison['all_vs_pairs'].items():
        diffs = data['groups']['pooled']
        lines.append(f"| {pair} | {diffs['prefill_percent']:+.2f}% | {diffs['decode_percent']:+.2f}% |")
    for label, metric, change in (('Prefill', 'prefill_tokens_per_second', 'prefill_percent'),
                                  ('Decode', 'decode_tokens_per_second', 'decode_percent')):
        lines += ['', f'## {label} by prompt length', '',
                  '| PP | saved control | skip-swizzle | Δ | hc-route | Δ | all | Δ |',
                  '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        for pp, base in summaries['control']['by_pp'].items():
            cells = [pp, f'{base[metric]:.2f}']
            for arm in ARMS:
                value = summaries[arm]['by_pp'][pp][metric]
                diff = comparison['deltas_vs_previous_control'][arm]['groups'][pp][change]
                cells.extend((f'{value:.2f}', f'{diff:+.2f}%'))
            lines.append('| ' + ' | '.join(cells) + ' |')
    (ROOT / 'comparison.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
