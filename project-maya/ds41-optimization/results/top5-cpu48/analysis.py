"""CPU-only configuration and validation for five remaining candidates."""

import importlib.util
from pathlib import Path
import re

from memory_probe import cache_budget


ROOT = Path(__file__).resolve().parent
SINGLES = ROOT.parent / 'flags-cpu48'
spec = importlib.util.spec_from_file_location('single_flag_analysis', SINGLES / 'analysis.py')
single = importlib.util.module_from_spec(spec)
spec.loader.exec_module(single)
REPO, REFERENCE = single.REPO, SINGLES / 'control'
BASE_CONFIG, ACTIVE_CONFIG = SINGLES / 'baseline-config.json', single.ACTIVE_CONFIG
CASES, RUNNER, IMAGE = single.CASES, single.RUNNER, single.IMAGE
ORIGINAL, PREVIOUS = single.ORIGINAL, single.PREVIOUS
read_json, write_json, sha = single.read_json, single.write_json, single.sha
verify_hashes, delta = single.verify_hashes, single.delta
ARMS = {
    'draft-cost': {'MAYA_DS4_DRAFT_COST': '1'},
    'decode-trim': {'MAYA_DS4_DECODE_TRIM': '15'},
    'hc-mix': {'MAYA_DS4_HC_MIX_SPLIT': '1'},
    'engram-cache': {'DS4_ENGRAM_CACHE_MB': '4096'},
    'markov-q8': {'MAYA_DS4_MARKOV_Q8': '1'},
}


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
    assert pin, 'Missing expert pinning'
    assert int(copied) == int(total) > 0 and numa == '2'
    assert float(pin[1]) >= float(size) > 0
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
    layout = placement(log)
    if arm == 'engram-cache':
        assert layout == placement((REFERENCE / 'engine.log').read_text())
    assert len(re.findall(r'maya ds4 serve: prompt \d+ tokens', log)) == 22
    if arm == 'draft-cost':
        assert 'DS4_DRAFT_COST: DSpark' in log
        assert 0 < log.count('draft cost (DS4_DRAFT_COST)') <= 22
    elif arm == 'decode-trim':
        assert 'DS4_DECODE_TRIM=15:' in log
        for pattern in (
            r"CUDA(\d+) DS4_DECODE_TRIM check: \d+ runs [^\n]*old path's bit for bit, every guard intact",
            r"CUDA(\d+) DS4_DECODE_TRIM check: copy_regions [^\n]*runtime copies' bytes, every guard intact",
        ):
            assert set(re.findall(pattern, log)) == {'0', '1', '2', '3'}
        pairs = re.search(r"DS4_DECODE_TRIM check: the drafter's hand-offs by xfer, (\d+) device pairs [^\n]*every row as put", log)
        assert pairs and int(pairs[1]) > 0
    elif arm == 'hc-mix':
        assert '(DS4_HC_MIX_SPLIT=1)' in log
    elif arm == 'markov-q8':
        assert "the drafter's markov head as Q8_0 blocks" in log
    memory = read_json(out / 'memory.json')
    for phase in ('before', 'after'):
        assert memory[phase]['memory_max'] == metadata['cgroup_memory_max']
        assert memory[phase]['memory_current'] <= int(memory[phase]['memory_max'])
    for event in ('oom', 'oom_kill'):
        assert memory['after']['memory_events'][event] == memory['before']['memory_events'][event] == 0
    if arm == 'engram-cache':
        assert memory['cache_budget'] == cache_budget(memory['before'])
        assert memory['cache_budget']['allowed']
    return single.summary_module.summarize(CASES, out, 48)
