"""CPU-only side-story report against the saved final four-flag result."""

import json

from analysis import (ARMS, REFERENCE, ROOT, best_of_two, combinations, delta,
                      placement, read_json, runtime_layout, validate, verify_hashes,
                      write_json)


def group_deltas(current, reference):
    groups = [(pp, current['by_pp'][pp], reference['by_pp'][pp]) for pp in reference['by_pp']]
    groups.append(('pooled', current['pooled_measurement'], reference['pooled_measurement']))
    return {pp: {f'{metric}_percent': delta(group[f'{metric}_tokens_per_second'],
                                          base[f'{metric}_tokens_per_second'])
                 for metric in ('prefill', 'decode')}
            for pp, group, base in groups}


def main():
    summaries, rows, best, runs, diagnostics, memory, layouts = {}, {}, {}, {}, {}, {}, {}
    for arm, out in [('final-four', REFERENCE), *[(arm, ROOT / arm) for arm in ARMS]]:
        verify_hashes(out)
        summary = combinations.validate(out, 'all') if arm == 'final-four' else validate(out, arm)
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
        layouts[arm] = {'experts': placement(log),
                        'runtime': runtime_layout(log, 2 if arm == 'tp2' else 4,
                                                  2048 if arm == 'chunk2048' else 4096)}
        diagnostics[arm] = {label: log.count(marker) for label, marker in (
            ('rocblaslt_errors', 'rocblaslt error:'), ('hip_module_load_failures', 'hipModuleLoad failed:'),
            ('hc_fuse_checks', 'HC fuse check'), ('route_fuse_checks', 'route fuse check'))}
        memory[arm] = read_json(out / 'memory.json') if arm in ARMS else None
        metadata = read_json(out / 'run-metadata.json')
        runs[arm] = {key: metadata[key] for key in ('started_utc', 'finished_utc', 'runner_exit_code')}

    diffs = {}
    for arm in ARMS:
        per_request = []
        for row, base in zip(rows[arm], rows['final-four']):
            assert (row['id'], row['phase']) == (base['id'], base['phase'])
            now, before = row['done'], base['done']
            assert now['prompt_tokens'] == before['prompt_tokens']
            per_request.append({'id': row['id'],
                                'prefill_percent': delta(now['prompt_tokens'] / now['prompt_ms'], before['prompt_tokens'] / before['prompt_ms']),
                                'decode_percent': delta(now['generated'] / now['decode_ms'], before['generated'] / before['decode_ms'])})
        diffs[arm] = {
            'groups': group_deltas(summaries[arm], summaries['final-four']),
            'per_request': per_request,
            'best_of_two': {pp: {f'{metric}_percent': delta(values[metric]['tokens_per_second'],
                                                          best['final-four'][pp][metric]['tokens_per_second'])
                                 for metric in ('prefill', 'decode')}
                            for pp, values in best[arm].items()},
        }
    write_json(ROOT / 'comparison.json', {
        'overrides': ARMS, 'runs': runs, 'summaries': summaries, 'best_of_two': best,
        'diagnostics': diagnostics, 'placement': layouts, 'memory': memory,
        'fresh_control': False, 'reference_source': '../combos-cpu48/all',
        'deltas_vs_saved_final': diffs, 'answer_parity_tested': False,
    })
    lines = ['# CPU48 side story: TP2 and prefill chunk 2048', '',
             'Two independent modifications of final-four; no new control or combined TP2/chunk2048 arm.',
             'TP2 retains all four GPUs and replaces group-local DRAFT_DEV with global DRAFT_GPU=1,2,3.',
             'The reference is older. Different TP/chunk arithmetic may change answers; no answer-parity test.',
             'No automatic baseline update or statistical-significance claim.', '',
             '## Primary pooled measurements', '',
             '| Arm | PP tok/s | vs saved final | TG tok/s | vs saved final | Draft accepted / offered | Peak GiB |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for arm, summary in summaries.items():
        group = summary['pooled_measurement']
        changes = diffs[arm]['groups']['pooled'] if arm in ARMS else None
        pp = f"{changes['prefill_percent']:+.2f}%" if changes else '—'
        tg = f"{changes['decode_percent']:+.2f}%" if changes else '—'
        peak = f"{memory[arm]['after']['memory_peak'] / 1024 ** 3:.2f}" if memory[arm] else '—'
        lines.append(f"| {arm} | {group['prefill_tokens_per_second']:.2f} | {pp} | {group['decode_tokens_per_second']:.2f} | {tg} | {group['drafts_accepted']} / {group['drafts_offered']} ({100 * group['draft_acceptance']:.2f}%) | {peak} |")
    lines += ['', 'Peak includes preparation and file cache; there is no equivalent record for saved final-four.']
    for mode in ('pooled', 'best-of-two'):
        lines += ['', f'## {mode} by prompt length']
        if mode == 'best-of-two':
            lines += ['', 'Independent PP/TG maxima of two different prompts, not repeated identical inputs.',
                      'PP and TG maxima may come from different requests; IDs are below and in comparison.json.']
        for label, metric in (('Prefill', 'prefill'), ('Decode', 'decode')):
            lines += ['', f'### {label}', '',
                      '| PP | saved final-four | tp2 | vs final | chunk2048 | vs final |',
                      '| ---: | ---: | ---: | ---: | ---: | ---: |']
            for pp in summaries['final-four']['by_pp']:
                values = []
                for arm in summaries:
                    speed = (summaries[arm]['by_pp'][pp][f'{metric}_tokens_per_second'] if mode == 'pooled'
                             else best[arm][pp][metric]['tokens_per_second'])
                    values.append(f'{speed:.2f}')
                    if arm in ARMS:
                        changes = diffs[arm]['groups' if mode == 'pooled' else 'best_of_two'][pp]
                        values.append(f"{changes[f'{metric}_percent']:+.2f}%")
                lines.append('| ' + ' | '.join([pp, *values]) + ' |')
    lines += ['', '## Best-of-two selection provenance', '',
              '| Arm | PP | Prefill case ID | Decode case ID |', '| --- | ---: | --- | --- |']
    for arm, groups in best.items():
        for pp, values in groups.items():
            lines.append(f"| {arm} | {pp} | {values['prefill']['case_id']} | {values['decode']['case_id']} |")
    (ROOT / 'comparison.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
