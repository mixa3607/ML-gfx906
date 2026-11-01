"""CPU-only configuration, validation and aggregation for the five-arm block."""

import hashlib
import importlib.util
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
REFERENCE = ROOT.parent / 'cpu-threads/cpu48'
PREVIOUS = ROOT.parent / 'cpu-threads'
ORIGINAL = ROOT.parent / 'baseline'
CASES = REPO / 'project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl'
RUNNER = REPO / 'project-maya/benchmarking/run.py'
ACTIVE_CONFIG = REPO / 'project-maya/ds41-optimization/base-params/maya-config.json'
IMAGE = 'sha256:50210b2fdec9c2e36b57fe0c8de2d3a9dd2d1fb33bb99757b37f229e824d51d2'
ARMS = {
    'control': {},
    'skip': {'DS4_SKIP_UNPICKED': '1'},
    'swizzle': {'DS4_HIP_ATTN_SWIZZLE': '1'},
    'hcfuse': {'MAYA_DS4_HC_FUSE': '2'},
    'routefuse': {'MAYA_DS4_ROUTE_FUSE': '2'},
}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


summary_module = load_module('cpu_summary', PREVIOUS / 'summarize.py')


def read_json(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def config_for(arm):
    config = read_json(ROOT / 'baseline-config.json')
    config['env'].update(ARMS[arm])
    return config


def expected_env(reference, arm):
    env = dict(reference)
    for key, value in ARMS[arm].items():
        env[key] = value
        if key.startswith('MAYA_'):
            env['STRATA_' + key[len('MAYA_'):]] = value
    return env


def validate_metadata(metadata, arm, reference):
    assert metadata['engine_args'] == reference['engine_args']
    assert metadata['effective_engine_env'] == expected_env(reference['effective_engine_env'], arm)
    for key in ('request_controls', 'source_commit', 'engine_sha256', 'build_id',
                'maya_version', 'rocm_version_files', 'cpu_affinity', 'numa_online',
                'smt_active', 'cgroup_memory_max', 'cgroup_cpu_max', 'gpu_numa_nodes'):
        assert metadata[key] == reference[key], key


def validate(out, arm):
    metadata = read_json(out / 'run-metadata.json')
    validate_metadata(metadata, arm, read_json(REFERENCE / 'run-metadata.json'))
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
    if arm in ('hcfuse', 'routefuse'):
        label = 'HC' if arm == 'hcfuse' else 'route'
        setting = 'HC' if arm == 'hcfuse' else 'ROUTE'
        devices = re.findall(rf'CUDA(\d+) {label} fuse check[^\n]*\(DS4_{setting}_FUSE=2\)', log)
        assert set(devices) == {'0', '1', '2', '3'}, devices
    return summary_module.summarize(CASES, out, 48)


def verify_hashes(out):
    for filename in ('artifact-sha256.json', 'source-state.json'):
        manifest = read_json(out / filename)
        hashes = manifest if filename == 'artifact-sha256.json' else manifest['script_sha256']
        for name, expected in hashes.items():
            assert sha(out / name) == expected, (out.name, name)


def delta(value, reference):
    return 100 * (value / reference - 1)
