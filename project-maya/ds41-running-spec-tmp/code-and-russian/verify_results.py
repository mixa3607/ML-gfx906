#!/usr/bin/env python3
"""Recompute the retained code/Russian metrics locally; never runs inference."""
import hashlib
import json
import math
from pathlib import Path

from bench import PROFILE_SHA, SESSIONS, case_check, pooled, sha, validate


def main():
    root = Path(__file__).resolve().parent
    run = root / 'run-fixed'
    frozen = json.loads((root / 'cases-nonce.manifest.json').read_text())
    experiment = json.loads((run / 'experiment.json').read_text())
    summary = json.loads((run / 'summary.json').read_text())
    for name, expected in frozen['files'].items():
        assert sha(root / name) == expected, name
    for name, expected in experiment['sources'].items():
        assert sha((root if name == 'bench.py' else root.parent) / name) == expected, name
    assert sha(root / 'runtime.json') == experiment['runtime_sha256']
    assert sha(root.parent / 'retry-220gi/seed-profile.bin') == PROFILE_SHA
    by_session = {}
    count = 0
    for name, file, expected_count in SESSIONS:
        cases = [json.loads(s) for s in (root / file).read_text().splitlines()]
        case_check(cases, file)
        manifest = json.loads((run / name / 'manifest.json').read_text())
        assert manifest == next(s for s in summary['sessions'] if s['name'] == name)
        assert manifest['cases_sha256'] == sha(root / file)
        assert manifest['seed_profile_sha256'] == PROFILE_SHA
        assert manifest['full_copies'][0] == manifest['full_copies'][1]
        assert manifest['before']['memory.events']['oom_kill'] == manifest['after']['memory.events']['oom_kill']
        assert manifest['before']['cpu.stat']['nr_throttled'] == manifest['after']['cpu.stat']['nr_throttled']
        assert not any(line.startswith('ERR ') for line in (run / name / 'protocol.log').read_text().splitlines())
        rows = [json.loads(s) for s in (run / name / 'results.jsonl').read_text().splitlines()]
        assert len(rows) == expected_count
        for case, row in zip(cases, rows):
            assert row['id'] == case['id'] and row['phase'] == case['phase']
            validate(row, len(case['ids']))
            assert sha_bytes(json.dumps(row['tokens']).encode()) == row['output_ids_sha256']
            assert row['complete_tg256'] == (row['done']['tg'] == 256 and row['done']['finish'] == 'length')
        scored = [r for r in rows if r['phase'] == 'measurement']
        print(name, 'TG:', [r['done']['tg'] for r in rows], 'unique_scored_outputs:',
              len({r['output_ids_sha256'] for r in scored}))
        if manifest['complete']:
            actual = pooled(scored)
            for metric in ('prefill_tok_s', 'decode_tok_s', 'wall_s', 'acceptance', 'expert_hit_ratio'):
                assert math.isclose(actual[metric], manifest['metrics'][metric], rel_tol=1e-12), metric
            print(name, json.dumps(actual))
            for pp in sorted({r['done']['pp'] for r in scored}):
                result = pooled([r for r in scored if r['done']['pp'] == pp])
                assert result == manifest['by_pp'][str(pp)]
                print(name, 'PP', pp, json.dumps(result))
            warm = rows[:12]
            if all(r['valid'] for r in warm):
                print(name, 'warmup_first3', json.dumps(pooled(warm[:3])))
                print(name, 'warmup_last3', json.dumps(pooled(warm[-3:])))
        by_session[name] = scored
        count += len(rows)
    for a, b in zip(by_session['code-1'], by_session['code-2']):
        first = next((i for i, (x, y) in enumerate(zip(a['tokens'], b['tokens'])) if x != y), None)
        print('code repeat', a['id'], 'identical:', a['tokens'] == b['tokens'], 'first_difference:', first)
    assert count == summary['saved_results'] == json.loads((run / 'exit.json').read_text())['saved_results'] == 66
    assert not json.loads((root / 'pods-after-cleanup.json').read_text())['items']
    assert (root / 'deployment-replicas-after.txt').read_text().strip() == '0'
    print('Verified frozen input/source hashes, all 66 durable request rows, pooled scores and cleanup.')


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


if __name__ == '__main__':
    main()
