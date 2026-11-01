"""CPU-only checks for six selected flags, with or without HC mix/split."""

import collections
import importlib.util
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
SINGLES = ROOT.parent / 'flags-cpu48'
TOP5 = ROOT.parent / 'top5-cpu48'
COMBOS = ROOT.parent / 'combos-cpu48'
spec = importlib.util.spec_from_file_location('single_flag_analysis', SINGLES / 'analysis.py')
single = importlib.util.module_from_spec(spec)
spec.loader.exec_module(single)
combinations = single.load_module('paired_flag_analysis', COMBOS / 'analysis.py')
REPO, REFERENCE = single.REPO, SINGLES / 'control'
BASE_CONFIG, ACTIVE_CONFIG = SINGLES / 'baseline-config.json', single.ACTIVE_CONFIG
CASES, RUNNER, IMAGE = single.CASES, single.RUNNER, single.IMAGE
ORIGINAL, PREVIOUS = single.ORIGINAL, single.PREVIOUS
read_json, write_json, sha = single.read_json, single.write_json, single.sha
verify_hashes, delta = single.verify_hashes, single.delta
SIX = {**combinations.ARMS['all'], 'MAYA_DS4_DRAFT_COST': '1', 'MAYA_DS4_DECODE_TRIM': '15'}
ARMS = {'six': SIX, 'six-hc-mix': {**SIX, 'MAYA_DS4_HC_MIX_SPLIT': '1'}}


def config_for(arm):
    config = read_json(BASE_CONFIG)
    config['env'].update(ARMS[arm])
    return config


def expected_env(reference, arm):
    env = dict(reference)
    for key, value in ARMS[arm].items():
        env[key] = value
        if key.startswith('MAYA_'):
            env['STRATA_' + key[len('MAYA_'):]] = value
    return env


def placement(log):
    match = re.search(r"(\d+) of the CPU lane's (\d+) experts copied into RAM \(([\d.]+) GB, (\d+) NUMA parts\)", log)
    assert match, 'Missing RAM-copy evidence'
    copied, total, size, numa = match.groups()
    pin = re.search(r'the copied experts pinned \(([\d.]+) GB', log)
    assert pin and float(pin[1]) >= float(size) > 0
    assert int(copied) == int(total) > 0 and numa == '2'
    return {'copied_experts': int(copied), 'cpu_lane_experts': int(total),
            'copied_gb': float(size), 'numa_parts': int(numa), 'pinned_gb': float(pin[1])}


def validate(out, arm):
    metadata = read_json(out / 'run-metadata.json')
    reference = read_json(REFERENCE / 'run-metadata.json')
    assert metadata['engine_args'] == reference['engine_args']
    assert metadata['effective_engine_env'] == expected_env(reference['effective_engine_env'], arm)
    for key in ('request_controls', 'source_commit', 'engine_sha256', 'build_id',
                'maya_version', 'rocm_version_files', 'cpu_affinity', 'numa_online',
                'smt_active', 'cgroup_memory_max', 'cgroup_cpu_max', 'gpu_numa_nodes'):
        assert metadata[key] == reference[key], key
    assert read_json(out / 'maya-config.json') == config_for(arm)
    assert metadata['input_sha256'] == {
        'config': sha(out / 'maya-config.json'), 'runner': sha(RUNNER), 'cases': sha(CASES),
    }
    pod = read_json(out / 'pod.json')
    assert pod['status']['containerStatuses'][0]['imageID'].endswith('@' + IMAGE)
    assert pod['spec']['nodeName'] == 'kube-worker6.arkprojects.lan'
    for name in ('pack-metadata.json', 'patch-verification.json', 'expert-profile.seed.bin', 'gpu-static.json'):
        assert (out / name).read_bytes() == (REFERENCE / name).read_bytes(), name
    log = (out / 'engine.log').read_text()
    assert 'tensor parallel 4 ->' not in log and '576 to 576 a member' in log
    assert '; 48 threads' in log and 'ds4 slots:' not in log
    placement(log)
    assert len(re.findall(r'maya ds4 serve: prompt \d+ tokens', log)) == 22
    assert 'DS4_DRAFT_COST: DSpark' in log and 0 < log.count('draft cost (DS4_DRAFT_COST)') <= 22
    assert 'DS4_DECODE_TRIM=15:' in log
    for pattern in (
        r"CUDA(\d+) DS4_DECODE_TRIM check: \d+ runs [^\n]*old path's bit for bit, every guard intact",
        r"CUDA(\d+) DS4_DECODE_TRIM check: copy_regions [^\n]*runtime copies' bytes, every guard intact",
    ):
        assert set(re.findall(pattern, log)) == {'0', '1', '2', '3'}
    pairs = re.search(r"DS4_DECODE_TRIM check: the drafter's hand-offs by xfer, (\d+) device pairs [^\n]*every row as put", log)
    assert pairs and int(pairs[1]) > 0
    for label, suffixes in (('HC', ('', ' (16 rows)')), ('route', ('', ' (3 rows)', ' (16 rows)'))):
        for suffix in suffixes:
            pattern = rf'CUDA(\d+) {re.escape(label + " fuse check" + suffix)}: [^\n]*bit for bit, all finite, every guard intact'
            assert set(re.findall(pattern, log)) == {'0', '1', '2', '3'}, (label, suffix)
    assert ('(DS4_HC_MIX_SPLIT=1)' in log) == (arm == 'six-hc-mix')
    memory = read_json(out / 'memory.json')
    for phase in ('before', 'after'):
        assert memory[phase]['memory_max'] == metadata['cgroup_memory_max']
        assert memory[phase]['memory_current'] <= int(memory[phase]['memory_max'])
    for event in ('oom', 'oom_kill'):
        assert memory['after']['memory_events'][event] == memory['before']['memory_events'][event] == 0
    return single.summary_module.summarize(CASES, out, 48)


def best_of_two(rows):
    groups = collections.defaultdict(list)
    for row in rows:
        if row['phase'] == 'measurement':
            groups[row['done']['prompt_tokens']].append(row)
    assert sorted(groups) == [2048, 4096, 8192, 16384, 32768]
    assert all(len(group) == 2 for group in groups.values())
    result = {}
    for pp, group in sorted(groups.items()):
        result[str(pp)] = {}
        for metric, tokens, elapsed in (('prefill', 'prompt_tokens', 'prompt_ms'), ('decode', 'generated', 'decode_ms')):
            selected = max(group, key=lambda row: 1000 * row['done'][tokens] / row['done'][elapsed])
            result[str(pp)][metric] = {
                'tokens_per_second': 1000 * selected['done'][tokens] / selected['done'][elapsed],
                'case_id': selected['id'],
            }
    return result
