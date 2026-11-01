"""CPU-only paired-candidate report: pooled primary and separate best-of-two."""

import json

from analysis import (ARMS, COMBOS, REFERENCE, ROOT, best_of_two, combinations,
                      delta, placement, read_json, single, validate, verify_hashes,
                      write_json)


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


def best_deltas(current, reference):
    return {pp: {f'{metric}_percent': delta(values[metric]['tokens_per_second'],
                                           reference[pp][metric]['tokens_per_second'])
                 for metric in ('prefill', 'decode')}
            for pp, values in current.items()}


def main():
    summaries, rows, best, diagnostics, runs, layouts, memory = {}, {}, {}, {}, {}, {}, {}
    sources = [('control', REFERENCE), ('four', COMBOS / 'all'), *[(arm, ROOT / arm) for arm in ARMS]]
    for arm, out in sources:
        verify_hashes(out)
        if arm == 'control':
            summary = single.validate(out, 'control')
        elif arm == 'four':
            summary = combinations.validate(out, 'all')
        else:
            summary = validate(out, arm)
        assert summary == read_json(out / 'summary.json')
        assert read_json(out / 'host-exit.json')['kubectl_exec_exit_code'] == 0
        summaries[arm] = summary
        raw = [json.loads(line) for line in (out / 'results.jsonl').read_text().splitlines()]
        rows[arm] = [row for row in raw if row['phase'] == 'measurement']
        best[arm] = best_of_two(raw)
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
            'decode_trim_checks': log.count('DS4_DECODE_TRIM check:'),
            'draft_cost_reports': log.count('draft cost (DS4_DRAFT_COST)'),
        }
        layouts[arm] = placement(log)
        memory[arm] = read_json(out / 'memory.json') if arm in ARMS else None
        metadata = read_json(out / 'run-metadata.json')
        runs[arm] = {key: metadata[key] for key in ('started_utc', 'finished_utc', 'runner_exit_code')}

    def against(arm, reference):
        return {'groups': group_deltas(summaries[arm], summaries[reference]),
                'per_request': request_deltas(rows[arm], rows[reference]),
                'best_of_two': best_deltas(best[arm], best[reference])}

    comparison = {
        'overrides': ARMS, 'runs': runs, 'summaries': summaries, 'best_of_two': best,
        'diagnostics': diagnostics, 'placement': layouts, 'memory': memory,
        'fresh_control': False, 'control_source': '../flags-cpu48/control',
        'four_source': '../combos-cpu48/all',
        'hc_mix_vs_six': against('six-hc-mix', 'six'),
        'deltas_vs_previous_control': {arm: against(arm, 'control') for arm in ARMS},
        'deltas_vs_previous_four': {arm: against(arm, 'four') for arm in ARMS},
    }
    write_json(ROOT / 'comparison.json', comparison)
    lines = ['# CPU48 six-flag candidates with and without HC mix/split', '',
             'Exactly two new runs, no fresh control. Control/four rows are earlier saved measurements.',
             'No automatic baseline change or statistical-significance claim.', '',
             '## Primary pooled measurements', '',
             '| Arm | PP tok/s | vs saved control | TG tok/s | vs saved control | Accepted / offered | Pod memory peak GiB |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for arm, summary in summaries.items():
        group = summary['pooled_measurement']
        diffs = group_deltas(summary, summaries['control'])['pooled']
        pp = f"{diffs['prefill_percent']:+.2f}%" if arm != 'control' else '—'
        tg = f"{diffs['decode_percent']:+.2f}%" if arm != 'control' else '—'
        peak = f"{memory[arm]['after']['memory_peak'] / 1024 ** 3:.2f}" if arm in ARMS else '—'
        lines.append(f"| {arm} | {group['prefill_tokens_per_second']:.2f} | {pp} | {group['decode_tokens_per_second']:.2f} | {tg} | {group['drafts_accepted']} / {group['drafts_offered']} ({100 * group['draft_acceptance']:.2f}%) | {peak} |")
    direct = comparison['hc_mix_vs_six']['groups']['pooled']
    lines += ['', f"HC mix added (second vs first): PP {direct['prefill_percent']:+.2f}%, TG {direct['decode_percent']:+.2f}%.",
              '', 'Pod memory peak includes preparation and file cache; old references have no equivalent record.']
    for mode in ('pooled', 'best-of-two'):
        lines += ['', f'## {mode} by prompt length']
        if mode == 'best-of-two':
            lines += ['', 'Independent PP/TG maxima from two different prompts, not repeated identical inputs.',
                      'Selected case IDs are retained in comparison.json; maxima need not be the same request.']
        for label, metric, change in (('Prefill', 'prefill', 'prefill_percent'), ('Decode', 'decode', 'decode_percent')):
            lines += ['', f'### {label}', '',
                      '| PP | saved control | saved four | six | six-hc-mix | HC mix vs six |',
                      '| ---: | ---: | ---: | ---: | ---: | ---: |']
            for pp in summaries['control']['by_pp']:
                if mode == 'pooled':
                    values = [summaries[arm]['by_pp'][pp][f'{metric}_tokens_per_second'] for arm in summaries]
                    diff = comparison['hc_mix_vs_six']['groups'][pp][change]
                else:
                    values = [best[arm][pp][metric]['tokens_per_second'] for arm in summaries]
                    diff = comparison['hc_mix_vs_six']['best_of_two'][pp][change]
                lines.append('| ' + ' | '.join([pp, *[f'{v:.2f}' for v in values], f'{diff:+.2f}%']) + ' |')
    (ROOT / 'comparison.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
