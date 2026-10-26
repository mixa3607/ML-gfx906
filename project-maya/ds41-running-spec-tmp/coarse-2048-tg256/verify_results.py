#!/usr/bin/env python3
"""Recompute point scores and check the retained evidence without GPU access."""
import collections
import json
import math
from pathlib import Path

from tune import CASES_SHA, PROFILE_SHA, SOURCE, score, sha


def main():
    root = Path(__file__).resolve().parent
    run = root / 'run'
    summary = json.loads((run / 'summary.json').read_text())
    experiment = json.loads((run / 'experiment.json').read_text())
    assert sha(root.parent / 'cases.jsonl') == CASES_SHA == summary['cases_sha256']
    assert sha(root.parent / 'retry-220gi/seed-profile.bin') == PROFILE_SHA == summary['seed_profile_sha256']
    for name, expected in experiment['sources'].items():
        assert sha((root if name == 'tune.py' else root.parent) / name) == expected, name
    by_point = collections.defaultdict(list)
    count = 0
    for session in summary['sessions']:
        directory = run / session['name']
        manifest = json.loads((directory / 'manifest.json').read_text())
        assert manifest == session
        assert manifest['source_commit'] == SOURCE
        assert manifest['cases_sha256'] == CASES_SHA and manifest['seed_profile_sha256'] == PROFILE_SHA
        assert manifest['full_copies'][0] == manifest['full_copies'][1]
        before, after = manifest['before'], manifest['after']
        assert before['memory.events']['oom_kill'] == after['memory.events']['oom_kill']
        assert before['cpu.stat']['nr_throttled'] == after['cpu.stat']['nr_throttled']
        config = json.loads((directory / 'config.json').read_text())
        assert config['args'][config['args'].index('--prefill-chunk') + 1] == '2048'
        assert config['env'].get('DS4_DRAFT_DEV') == ('1,2,3' if manifest['loaded'] else None)
        assert not any(line.startswith('ERR ') for line in (directory / 'protocol.log').read_text().splitlines())
        rows = [json.loads(line) for line in (directory / 'results.jsonl').read_text().splitlines()]
        for row in rows:
            assert row['valid'] and row['done']['pp'] == 2048 and row['done']['tg'] == 256
            assert row['done']['reused'] == 0
            assert all(float(st.get('skipped', 0)) == 0 for st in row['stats'])
            if row['phase'] == 'measurement':
                by_point[row['point_label']].append(row)
        count += len(rows)
        print(f'{session["name"]}: {len(rows)} valid requests, full expert copies, no OOM/throttling/native ERR')
    for entry in summary['points']:
        recomputed = score(by_point[entry['label']])
        for metric in ('decode_tok_s', 'prefill_tok_s', 'wall_s'):
            assert math.isclose(entry['metrics'][metric], recomputed[metric], rel_tol=1e-12)
        print(f'{entry["label"]}: {recomputed["decode_tok_s"]:.4f} decode tok/s')
    assert count == summary['saved_results'] == json.loads((run / 'exit.json').read_text())['saved_results'] == 60
    assert summary['status'] == 'drift' and not summary['complete']
    assert summary['blocked_stage'] == 'selected-MAX-restart'
    assert not summary['controls'][-1]['passes']
    assert not (run / 'stage-6.json').exists()
    assert not json.loads((root / 'pods-after-cleanup.json').read_text())['items']
    assert (root / 'deployment-replicas-after.txt').read_text().strip() == '0'
    print('Verified frozen inputs/source hashes, 60 durable rows, recomputed scores, planned drift stop and cleanup.')


if __name__ == '__main__':
    main()
