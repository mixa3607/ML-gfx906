"""CPU-only top-five comparison against the saved control; no verdicts."""

import json

from analysis import (ARMS, REFERENCE, ROOT, delta, placement, read_json, single,
                      validate, verify_hashes, write_json)


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


def main():
    summaries, rows, diagnostics, runs, layouts, memory = {}, {}, {}, {}, {}, {}
    for arm, out in [('control', REFERENCE), *[(arm, ROOT / arm) for arm in ARMS]]:
        verify_hashes(out)
        summary = single.validate(out, 'control') if arm == 'control' else validate(out, arm)
        assert summary == read_json(out / 'summary.json')
        assert read_json(out / 'host-exit.json')['kubectl_exec_exit_code'] == 0
        summaries[arm] = summary
        rows[arm] = [r for r in map(json.loads, (out / 'results.jsonl').read_text().splitlines())
                     if r['phase'] == 'measurement']
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
            'decode_trim_checks': log.count('DS4_DECODE_TRIM check:'),
            'draft_cost_reports': log.count('draft cost (DS4_DRAFT_COST)'),
        }
        layouts[arm] = placement(log)
        memory[arm] = None if arm == 'control' else read_json(out / 'memory.json')
        metadata = read_json(out / 'run-metadata.json')
        runs[arm] = {key: metadata[key] for key in ('started_utc', 'finished_utc', 'runner_exit_code')}
    comparison = {
        'overrides': ARMS, 'runs': runs, 'summaries': summaries,
        'diagnostics': diagnostics, 'placement': layouts, 'memory': memory,
        'control_source': '../flags-cpu48/control', 'fresh_control': False,
        'deltas_vs_previous_control': {
            arm: {'groups': group_deltas(summaries[arm], summaries['control']),
                  'per_request': request_deltas(rows[arm], rows['control'])}
            for arm in ARMS
        },
    }
    write_json(ROOT / 'comparison.json', comparison)
    lines = ['# Five remaining candidates on CPU48', '',
             'No fresh control was run; the saved control is from the earlier single-flag block.',
             'Differences may include drift. No performance verdict or baseline/best-tested change is applied.', '',
             '| Arm | PP tok/s | vs saved control | TG tok/s | vs saved control | Accepted / offered | Pod memory peak GiB |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for arm, summary in summaries.items():
        group = summary['pooled_measurement']
        diffs = group_deltas(summary, summaries['control'])['pooled']
        pp = f"{diffs['prefill_percent']:+.2f}%" if arm != 'control' else '—'
        tg = f"{diffs['decode_percent']:+.2f}%" if arm != 'control' else '—'
        peak = f"{memory[arm]['after']['memory_peak'] / 1024 ** 3:.2f}" if arm != 'control' else '—'
        lines.append(f"| {arm} | {group['prefill_tokens_per_second']:.2f} | {pp} | {group['decode_tokens_per_second']:.2f} | {tg} | {group['drafts_accepted']} / {group['drafts_offered']} ({100 * group['draft_acceptance']:.2f}%) | {peak} |")
    lines += ['', 'Pod memory peak includes preparation and charged file cache, not just resident anonymous weights.']
    for label, metric, change in (('Prefill', 'prefill_tokens_per_second', 'prefill_percent'),
                                  ('Decode', 'decode_tokens_per_second', 'decode_percent')):
        lines += ['', f'## {label} by prompt length', '',
                  '| PP | saved control | ' + ' | '.join(f'{arm} | Δ' for arm in ARMS) + ' |',
                  '| ' + ' | '.join('---:' for _ in range(2 + 2 * len(ARMS))) + ' |']
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
