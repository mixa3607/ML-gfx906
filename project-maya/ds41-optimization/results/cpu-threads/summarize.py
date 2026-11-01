"""Validate a frozen CPU-thread run; warmups are not scored. CPU only."""

import collections
import json
from pathlib import Path
import sys


def summarize(cases_path, results_dir, cpu):
    assert cpu in (56, 48)
    cases = [json.loads(line) for line in cases_path.read_text().splitlines()]
    rows = [json.loads(line) for line in (results_dir / 'results.jsonl').read_text().splitlines()]
    metadata = json.loads((results_dir / 'run-metadata.json').read_text())
    assert metadata['runner_exit_code'] == 0, metadata.get('runner_exit_code')
    assert metadata['request_controls'] == {'temperature': 0, 'spec': 1}
    assert metadata['effective_engine_env']['STRATA_DS4_SLOT_KEEP'] == '0'
    args = metadata['engine_args']
    assert args[args.index('--cpu-threads') + 1] == str(cpu)
    assert args[args.index('--tp') + 1] == '4'
    assert 'ds4 slots:' not in (results_dir / 'engine.log').read_text()
    assert len(rows) == len(cases) == 22, (len(rows), len(cases))
    groups = collections.defaultdict(list)
    for case, row in zip(cases, rows):
        assert (row['id'], row['phase']) == (case['id'], case['phase'])
        done = row['done']
        assert done['prompt_tokens'] == case['pp'], row
        assert done['reused'] == 0, row
        assert 0 < done['generated'] <= case['tg'], row
        assert done['prompt_ms'] > 0 and done['decode_ms'] > 0, row
        assert 0 <= done['drafts_accepted'] <= done['drafts_offered'], row
        if row['phase'] == 'measurement':
            groups[case['pp']].append(done)
    assert sorted(groups) == [2048, 4096, 8192, 16384, 32768]
    assert all(len(group) == 2 for group in groups.values())
    measured = [row['done'] for row in rows if row['phase'] == 'measurement']
    summary = {
        'warmup_requests': sum(row['phase'] == 'warmup' for row in rows),
        'by_pp': {str(pp): pool(group) for pp, group in sorted(groups.items())},
        'pooled_measurement': pool(measured),
        'timing_convention': 'Native DONE timings; sum(prompt_tokens)/sum(prompt_ms) and sum(generated)/sum(decode_ms). Not client TTFT.',
    }
    assert summary['warmup_requests'] == 12
    assert summary['pooled_measurement']['drafts_offered'] > 0, 'No measured draft offers'
    return summary


def pool(group):
    prompt_tokens = sum(row['prompt_tokens'] for row in group)
    generated = sum(row['generated'] for row in group)
    prompt_ms = sum(row['prompt_ms'] for row in group)
    decode_ms = sum(row['decode_ms'] for row in group)
    accepted = sum(row['drafts_accepted'] for row in group)
    offered = sum(row['drafts_offered'] for row in group)
    return {
        'requests': len(group), 'prompt_tokens': prompt_tokens,
        'generated': generated, 'prompt_ms': prompt_ms, 'decode_ms': decode_ms,
        'prefill_tokens_per_second': 1000 * prompt_tokens / prompt_ms,
        'decode_tokens_per_second': 1000 * generated / decode_ms,
        'drafts_accepted': accepted, 'drafts_offered': offered,
        'draft_acceptance': accepted / offered if offered else None,
        'finish_counts': dict(collections.Counter(row['finish'] for row in group)),
        'reused': sum(row['reused'] for row in group),
    }


if __name__ == '__main__':
    result_dir = Path(sys.argv[2])
    summary = summarize(Path(sys.argv[1]), result_dir, int(sys.argv[3]))
    (result_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('| PP | Requests | Generated | Prefill tok/s | Decode tok/s | Accepted / offered |')
    print('| ---: | ---: | ---: | ---: | ---: | ---: |')
    for pp, group in summary['by_pp'].items():
        print(f"| {pp} | {group['requests']} | {group['generated']} | {group['prefill_tokens_per_second']:.2f} | {group['decode_tokens_per_second']:.2f} | {group['drafts_accepted']} / {group['drafts_offered']} |")
    print(json.dumps(summary['pooled_measurement'], indent=2))
