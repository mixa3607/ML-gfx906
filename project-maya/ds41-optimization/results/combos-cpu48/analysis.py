"""CPU-only configuration and validation for two pairs and all four flags."""

import importlib.util
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
SINGLES = ROOT.parent / 'flags-cpu48'
spec = importlib.util.spec_from_file_location('single_flag_analysis', SINGLES / 'analysis.py')
single = importlib.util.module_from_spec(spec)
spec.loader.exec_module(single)
REPO = single.REPO
REFERENCE = SINGLES / 'control'
BASE_CONFIG = SINGLES / 'baseline-config.json'
ACTIVE_CONFIG = single.ACTIVE_CONFIG
CASES, RUNNER, IMAGE = single.CASES, single.RUNNER, single.IMAGE
ORIGINAL, PREVIOUS = single.ORIGINAL, single.PREVIOUS
read_json, write_json, sha = single.read_json, single.write_json, single.sha
verify_hashes, delta = single.verify_hashes, single.delta
ARMS = {
    'skip-swizzle': {'DS4_SKIP_UNPICKED': '1', 'DS4_HIP_ATTN_SWIZZLE': '1'},
    'hc-route': {'MAYA_DS4_HC_FUSE': '2', 'MAYA_DS4_ROUTE_FUSE': '2'},
    'all': {
        'DS4_SKIP_UNPICKED': '1', 'DS4_HIP_ATTN_SWIZZLE': '1',
        'MAYA_DS4_HC_FUSE': '2', 'MAYA_DS4_ROUTE_FUSE': '2',
    },
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
    assert "10647 of the CPU lane's 10647 experts copied into RAM (200.2 GB, 2 NUMA parts)" in log
    assert 'the copied experts pinned (200.9 GB' in log
    assert len(re.findall(r'maya ds4 serve: prompt \d+ tokens', log)) == 22
    for flag, label, suffixes in (
        ('MAYA_DS4_HC_FUSE', 'HC', ('', ' (16 rows)')),
        ('MAYA_DS4_ROUTE_FUSE', 'route', ('', ' (3 rows)', ' (16 rows)')),
    ):
        if flag not in ARMS[arm]:
            continue
        for suffix in suffixes:
            pattern = rf'CUDA(\d+) {re.escape(label + " fuse check" + suffix)}: [^\n]*bit for bit, all finite, every guard intact'
            assert set(re.findall(pattern, log)) == {'0', '1', '2', '3'}, (flag, suffix)
    return single.summary_module.summarize(CASES, out, 48)
