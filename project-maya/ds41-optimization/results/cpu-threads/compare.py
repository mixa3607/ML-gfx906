"""Recompute and compare CPU74/56/48 artifacts without accessing Kubernetes."""

import json
from pathlib import Path

from scripts.run import BASELINE, CASES, ROOT, sha, validate
from summarize import summarize


def delta(value, baseline):
    return 100 * (value / baseline - 1)


def verify_hashes(directory):
    for name, expected in json.loads((directory / 'artifact-sha256.json').read_text()).items():
        assert sha(directory / name) == expected, (directory.name, name)
    source = json.loads((directory / 'source-state.json').read_text())
    for name, expected in source['script_sha256'].items():
        assert sha(directory / name) == expected, (directory.name, name)


def main():
    directories = {74: BASELINE, 56: ROOT / 'cpu56', 48: ROOT / 'cpu48'}
    summaries = {}
    rows = {}
    diagnostics = {}
    for cpu, directory in directories.items():
        verify_hashes(directory)
        recorded = json.loads((directory / 'summary.json').read_text())
        if cpu != 74:
            validate(directory, cpu)
            assert summarize(CASES, directory, cpu) == recorded
            assert json.loads((directory / 'gpu-static.json').read_text()) == json.loads((BASELINE / 'gpu-static.json').read_text())
        assert recorded['warmup_requests'] == 12
        assert recorded['pooled_measurement']['requests'] == 10
        summaries[cpu] = recorded
        rows[cpu] = [r for r in map(json.loads, (directory / 'results.jsonl').read_text().splitlines())
                     if r['phase'] == 'measurement']
        assert json.loads((directory / 'host-exit.json').read_text())['kubectl_exec_exit_code'] == 0
        for sample in ('gpu-before.txt', 'gpu-after-cleanup.txt'):
            text = (directory / sample).read_text()
            gpus = json.loads(text[text.index('['):])
            assert {g['gpu'] for g in gpus} == {0, 1, 2, 3}
            assert all(g['gfx']['value'] == 0 and g['vram_used']['value'] < 32 for g in gpus)
        log = (directory / 'engine.log').read_text()
        diagnostics[cpu] = {
            'rocblaslt_errors': log.count('rocblaslt error:'),
            'hip_module_load_failures': log.count('hipModuleLoad failed:'),
        }

    comparison = {'summaries': summaries, 'diagnostics': diagnostics, 'deltas_vs_cpu74': {}}
    for cpu in (56, 48):
        per_request = []
        for reference, candidate in zip(rows[74], rows[cpu]):
            assert (reference['id'], reference['phase']) == (candidate['id'], candidate['phase'])
            base, current = reference['done'], candidate['done']
            assert base['prompt_tokens'] == current['prompt_tokens']
            per_request.append({
                'id': candidate['id'],
                'prefill_percent': delta(current['prompt_tokens'] / current['prompt_ms'],
                                         base['prompt_tokens'] / base['prompt_ms']),
                'decode_percent': delta(current['generated'] / current['decode_ms'],
                                        base['generated'] / base['decode_ms']),
            })
        groups = {}
        for pp in [*summaries[74]['by_pp'], 'pooled']:
            base = summaries[74]['pooled_measurement'] if pp == 'pooled' else summaries[74]['by_pp'][pp]
            current = summaries[cpu]['pooled_measurement'] if pp == 'pooled' else summaries[cpu]['by_pp'][pp]
            groups[pp] = {
                'prefill_percent': delta(current['prefill_tokens_per_second'], base['prefill_tokens_per_second']),
                'decode_percent': delta(current['decode_tokens_per_second'], base['decode_tokens_per_second']),
            }
        comparison['deltas_vs_cpu74'][cpu] = {'groups': groups, 'per_request': per_request}

    (ROOT / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
    lines = []
    for label, metric, diff in (('Prefill', 'prefill_tokens_per_second', 'prefill_percent'),
                                ('Decode', 'decode_tokens_per_second', 'decode_percent')):
        lines += [f'## {label}', '',
                  '| PP | CPU74 tok/s | CPU56 tok/s | vs 74 | CPU48 tok/s | vs 74 |',
                  '| ---: | ---: | ---: | ---: | ---: | ---: |']
        for pp in [*summaries[74]['by_pp'], 'pooled']:
            values = [summaries[cpu]['pooled_measurement'][metric] if pp == 'pooled'
                      else summaries[cpu]['by_pp'][pp][metric] for cpu in (74, 56, 48)]
            d56, d48 = [comparison['deltas_vs_cpu74'][cpu]['groups'][pp][diff] for cpu in (56, 48)]
            lines.append(f'| {pp} | {values[0]:.2f} | {values[1]:.2f} | {d56:+.2f}% | {values[2]:.2f} | {d48:+.2f}% |')
        lines.append('')
    (ROOT / 'comparison.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
