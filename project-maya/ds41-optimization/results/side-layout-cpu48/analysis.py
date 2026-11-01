"""CPU-only validation of independent TP2 and chunk2048 side experiments."""

import collections
import importlib.util
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
SINGLES = ROOT.parent / 'flags-cpu48'
spec = importlib.util.spec_from_file_location('side_single_analysis', SINGLES / 'analysis.py')
single = importlib.util.module_from_spec(spec)
spec.loader.exec_module(single)
helpers = single.load_module('side_final_helpers', ROOT.parent / 'final-candidates-cpu48/analysis.py')
combinations = helpers.combinations
REFERENCE = ROOT.parent / 'combos-cpu48/all'
BASE_CONFIG, ACTIVE_CONFIG = REFERENCE / 'maya-config.json', single.ACTIVE_CONFIG
REPO, CASES, RUNNER, IMAGE = single.REPO, single.CASES, single.RUNNER, single.IMAGE
ORIGINAL, PREVIOUS = single.ORIGINAL, single.PREVIOUS
TOP5 = ROOT.parent / 'top5-cpu48'
read_json, write_json, sha = single.read_json, single.write_json, single.sha
verify_hashes, delta = single.verify_hashes, single.delta
placement, best_of_two = helpers.placement, helpers.best_of_two
ARMS = {
    'tp2': {'args': {'--tp': '2'},
            'remove_env': ['MAYA_DS4_DRAFT_DEV'], 'env': {'MAYA_DS4_DRAFT_GPU': '1,2,3'}},
    'chunk2048': {'args': {'--prefill-chunk': '2048'}, 'remove_env': [], 'env': {}},
}


def replace_args(args, overrides):
    result = list(args)
    for flag, value in overrides.items():
        assert result.count(flag) == 1, flag
        result[result.index(flag) + 1] = value
    return result


def config_for(arm):
    config = read_json(BASE_CONFIG)
    overrides = ARMS[arm]
    config['args'] = replace_args(config['args'], overrides['args'])
    for flag in overrides['remove_env']:
        del config['env'][flag]
    config['env'].update(overrides['env'])
    return config


def expected_env(reference, arm):
    env = dict(reference)
    for flag in ARMS[arm]['remove_env']:
        del env[flag]
        if flag.startswith('MAYA_'):
            del env['STRATA_' + flag[len('MAYA_'):]]
    for flag, value in ARMS[arm]['env'].items():
        env[flag] = value
        if flag.startswith('MAYA_'):
            env['STRATA_' + flag[len('MAYA_'):]] = value
    return env


def runtime_layout(log, tp, chunk):
    assert not re.search(r'tensor parallel \d+ ->', log), 'Unexpected TP fallback'
    width = 2304 // tp
    assert f'tensor parallel {tp}:' in log and f'{width} to {width} a member' in log
    assert f'prompts in chunks of {chunk})' in log
    matches = re.findall(r'ds4: CUDA(\d+) layers \[(\d+), (\d+)\] \(tensor parallel (\d+), part (\d+)\)', log)
    assert len(matches) == 4 and {row[0] for row in matches} == {'0', '1', '2', '3'}
    assert {int(row[3]) for row in matches} == {tp}
    assert collections.Counter(int(row[4]) for row in matches) == {
        part: 4 // tp for part in range(tp)
    }
    starts = collections.Counter(int(row[1]) for row in matches)
    assert len(starts) == 4 // tp and starts[0] == tp
    assert all(count == tp and 0 <= start < 40 for start, count in starts.items())
    return {'tp': tp, 'chunk': chunk, 'groups': 4 // tp,
            'devices': [{'gpu': int(gpu), 'first_layer': int(first), 'last_layer': int(last),
                         'tp': int(width), 'part': int(part)}
                        for gpu, first, last, width, part in matches]}


def summarize(out, tp):
    cases = [json.loads(line) for line in CASES.read_text().splitlines()]
    rows = [json.loads(line) for line in (out / 'results.jsonl').read_text().splitlines()]
    metadata = read_json(out / 'run-metadata.json')
    assert metadata['runner_exit_code'] == 0
    assert metadata['request_controls'] == {'temperature': 0, 'spec': 1}
    args = metadata['engine_args']
    assert args[args.index('--cpu-threads') + 1] == '48'
    assert args[args.index('--tp') + 1] == str(tp)
    assert metadata['effective_engine_env']['STRATA_DS4_SLOT_KEEP'] == '0'
    assert 'ds4 slots:' not in (out / 'engine.log').read_text()
    assert len(rows) == len(cases) == 22
    groups = collections.defaultdict(list)
    for case, row in zip(cases, rows):
        assert (row['id'], row['phase']) == (case['id'], case['phase'])
        done = row['done']
        assert done['prompt_tokens'] == case['pp'] and done['reused'] == 0
        assert 0 < done['generated'] <= case['tg']
        assert done['prompt_ms'] > 0 and done['decode_ms'] > 0
        assert 0 <= done['drafts_accepted'] <= done['drafts_offered']
        if row['phase'] == 'measurement':
            groups[case['pp']].append(done)
    assert sorted(groups) == [2048, 4096, 8192, 16384, 32768]
    assert all(len(group) == 2 for group in groups.values())
    pool = single.summary_module.pool
    measured = [row['done'] for row in rows if row['phase'] == 'measurement']
    result = {'warmup_requests': sum(row['phase'] == 'warmup' for row in rows),
              'by_pp': {str(pp): pool(group) for pp, group in sorted(groups.items())},
              'pooled_measurement': pool(measured),
              'timing_convention': 'Native DONE timings; sum(prompt_tokens)/sum(prompt_ms) and sum(generated)/sum(decode_ms). Not client TTFT.'}
    assert result['warmup_requests'] == 12
    assert result['pooled_measurement']['drafts_offered'] > 0
    return result


def validate(out, arm):
    config = config_for(arm)
    tp = int(config['args'][config['args'].index('--tp') + 1])
    chunk = int(config['args'][config['args'].index('--prefill-chunk') + 1])
    metadata = read_json(out / 'run-metadata.json')
    reference = read_json(REFERENCE / 'run-metadata.json')
    assert metadata['engine_args'] == replace_args(reference['engine_args'], ARMS[arm]['args'])
    assert metadata['effective_engine_env'] == expected_env(reference['effective_engine_env'], arm)
    for key in ('request_controls', 'source_commit', 'engine_sha256', 'build_id',
                'maya_version', 'rocm_version_files', 'cpu_affinity', 'numa_online',
                'smt_active', 'cgroup_memory_max', 'cgroup_cpu_max', 'gpu_numa_nodes'):
        assert metadata[key] == reference[key], key
    assert read_json(out / 'maya-config.json') == config
    assert metadata['input_sha256'] == {
        'config': sha(out / 'maya-config.json'), 'runner': sha(RUNNER), 'cases': sha(CASES),
    }
    pod = read_json(out / 'pod.json')
    assert pod['status']['containerStatuses'][0]['imageID'].endswith('@' + IMAGE)
    assert pod['spec']['nodeName'] == 'kube-worker6.arkprojects.lan'
    for name in ('pack-metadata.json', 'patch-verification.json', 'expert-profile.seed.bin', 'gpu-static.json'):
        assert (out / name).read_bytes() == (REFERENCE / name).read_bytes(), name
    log = (out / 'engine.log').read_text()
    runtime_layout(log, tp, chunk)
    assert '; 48 threads' in log
    placement(log)
    assert len(re.findall(r'maya ds4 serve: prompt \d+ tokens', log)) == 22
    if arm == 'tp2':
        blocks = re.findall(r'DS4_DRAFT_GPU block (\d+) on CUDA(\d+) \(target group (\d+)\)', log)
        assert [(b, d) for b, d, _ in blocks] == [('0', '1'), ('1', '2'), ('2', '3')]
        assert 'DS4_DRAFT_DEV 1,2,3:' not in log
    else:
        assert 'DS4_DRAFT_DEV 1,2,3:' in log and 'DS4_DRAFT_GPU block' not in log
    for label, suffixes in (('HC', ('', ' (16 rows)')), ('route', ('', ' (3 rows)', ' (16 rows)'))):
        for suffix in suffixes:
            pattern = rf'CUDA(\d+) {re.escape(label + " fuse check" + suffix)}: [^\n]*bit for bit, all finite, every guard intact'
            assert set(re.findall(pattern, log)) == {'0', '1', '2', '3'}, (label, suffix)
    memory = read_json(out / 'memory.json')
    for phase in ('before', 'after'):
        assert memory[phase]['memory_max'] == metadata['cgroup_memory_max']
        assert memory[phase]['memory_current'] <= int(memory[phase]['memory_max'])
        assert all(value == 0 for value in memory[phase]['memory_events'].values())
    return summarize(out, tp)
