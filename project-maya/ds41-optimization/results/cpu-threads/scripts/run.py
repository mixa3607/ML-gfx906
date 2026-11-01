"""Run CPU56 or CPU48 on real GPUs after explicit cluster/hardware approval."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[4]
BASELINE = ROOT.parent / 'baseline'
CASES = REPO / 'project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl'
RUNNER = REPO / 'project-maya/benchmarking/run.py'
CONFIG = REPO / 'project-maya/ds41-optimization/base-params/maya-config.json'
KUBE = ['kubectl', '-n', 'apps-ml']
PYTHON = '/opt/maya/.venv/bin/python'
IMAGE = 'sha256:50210b2fdec9c2e36b57fe0c8de2d3a9dd2d1fb33bb99757b37f229e824d51d2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def capture(command):
    return subprocess.check_output(command, text=True)


def gpu_sample(path):
    text = capture(KUBE + ['exec', 'rocm-toolkit-0', '--', 'amd-smi', 'monitor',
                           '-u', '-v', '-t', '-w', '1', '-i', '1', '--json'])
    path.write_text(text.rstrip() + '\n')
    rows = json.loads(text[text.index('['):])
    assert {r['gpu'] for r in rows} == {0, 1, 2, 3}
    assert all(r['gfx']['value'] == 0 and r['vram_used']['unit'] == 'MB'
               and r['vram_used']['value'] < 32 for r in rows), 'GPU is not idle'


def cpu_config(cpu):
    assert cpu in (56, 48)
    config = json.loads(CONFIG.read_text())
    assert config == json.loads((BASELINE / 'maya-config.json').read_text())
    assert config['env']['MAYA_DS4_SLOT_KEEP'] == '0'
    index = config['args'].index('--cpu-threads') + 1
    assert config['args'][index] == '74'
    config['args'][index] = str(cpu)
    return config


def validate(out, cpu):
    metadata = json.loads((out / 'run-metadata.json').read_text())
    base = json.loads((BASELINE / 'run-metadata.json').read_text())
    pod = json.loads((out / 'pod.json').read_text())
    assert pod['status']['containerStatuses'][0]['imageID'].endswith('@' + IMAGE)
    assert json.loads((out / 'maya-config.json').read_text()) == cpu_config(cpu)
    assert metadata['input_sha256'] == {
        'config': sha(out / 'maya-config.json'), 'runner': sha(RUNNER), 'cases': sha(CASES),
    }
    args = list(metadata['engine_args'])
    assert args[args.index('--cpu-threads') + 1] == str(cpu)
    args[args.index('--cpu-threads') + 1] = '74'
    assert args == base['engine_args']
    for key in ('effective_engine_env', 'request_controls', 'source_commit',
                'engine_sha256', 'build_id', 'maya_version', 'rocm_version_files',
                'cpu_affinity', 'numa_online', 'smt_active', 'cgroup_memory_max',
                'cgroup_cpu_max', 'gpu_numa_nodes'):
        assert metadata[key] == base[key], key
    assert (out / 'pack-metadata.json').read_bytes() == (BASELINE / 'pack-metadata.json').read_bytes()
    assert (out / 'expert-profile.seed.bin').read_bytes() == (BASELINE / 'expert-profile.seed.bin').read_bytes()
    assert (out / 'patch-verification.json').read_bytes() == (BASELINE / 'patch-verification.json').read_bytes()
    log = (out / 'engine.log').read_text()
    assert 'tensor parallel 4 ->' not in log and '576 to 576 a member' in log
    assert f'; {cpu} threads' in log and 'ds4 slots:' not in log
    assert "10647 of the CPU lane's 10647 experts copied into RAM (200.2 GB, 2 NUMA parts)" in log
    assert 'the copied experts pinned (200.9 GB' in log
    assert len(re.findall(r'maya ds4 serve: prompt \d+ tokens', log)) == 22


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cpu', type=int, choices=(56, 48))
    cpu = parser.parse_args().cpu
    assert Path.cwd().resolve() == REPO, f'Run from {REPO}'
    assert sha(CASES) == '3195a02e90078b366c00dce429652b386fe3616d879cdd25c1a6f288435b46c3'
    config = cpu_config(cpu)
    out = ROOT / f'cpu{cpu}'
    out.mkdir()
    write_json(out / 'maya-config.json', config)
    pod = f'maya-ds41-cpu{cpu}'
    manifest = (BASELINE / 'scripts/pod.yaml').read_text().replace('maya-ds41-baseline', pod)
    (out / 'pod.yaml').write_text(manifest)
    scripts = [HERE / 'run.py', HERE / 'remote.py', ROOT / 'summarize.py',
               BASELINE / 'scripts/remote.py', BASELINE / 'scripts/pod.yaml']
    write_json(out / 'source-state.json', {
        'repository_head': capture(['git', 'rev-parse', 'HEAD']).strip(),
        'cpu_threads': cpu,
        'input_sha256': {'runner': sha(RUNNER), 'cases': sha(CASES),
                         'config': sha(out / 'maya-config.json')},
        'script_sha256': {os.path.relpath(p, out): sha(p) for p in scripts},
    })
    gpu_sample(out / 'gpu-before.txt')
    (out / 'gpu-static.json').write_text(capture(KUBE + ['exec', 'rocm-toolkit-0', '--',
        'amd-smi', 'static', '-a', '-b', '-d', '-v', '-l', '-u', '--json']))
    created = False
    rc = None
    try:
        subprocess.run(KUBE + ['create', '-f', str(out / 'pod.yaml')], check=True)
        created = True
        subprocess.run(KUBE + ['wait', '--for=condition=Ready', f'pod/{pod}', '--timeout=600s'], check=True)
        (out / 'pod.json').write_text(capture(KUBE + ['get', 'pod', pod, '-o', 'json']))
        subprocess.run(KUBE + ['exec', pod, '--', 'mkdir', '/data/input'], check=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as tar:
            for source, target in ((out / 'maya-config.json', 'config.json'), (RUNNER, 'run.py'),
                                   (CASES, 'cases.jsonl'), (HERE / 'remote.py', 'remote.py'),
                                   (BASELINE / 'scripts/remote.py', 'baseline_remote.py')):
                tar.add(source, arcname=target)
        subprocess.run(KUBE + ['exec', '-i', pod, '--', 'tar', '-xf', '-', '-C', '/data/input'],
                       input=archive.getvalue(), check=True)
        with (out / 'prepare.txt').open('w') as log:
            subprocess.run(KUBE + ['exec', pod, '--', PYTHON, '/data/input/remote.py', 'prepare'],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        rc = subprocess.call(KUBE + ['exec', pod, '--', PYTHON, '/data/input/remote.py', 'run', str(cpu)])
        write_json(out / 'host-exit.json', {'kubectl_exec_exit_code': rc})
    finally:
        if created:
            try:
                tar = subprocess.run(KUBE + ['exec', pod, '--', 'tar', '-cf', '-', '-C', '/data/results', '.'],
                                     stdout=subprocess.PIPE, check=True)
                with tarfile.open(fileobj=io.BytesIO(tar.stdout)) as archive:
                    archive.extractall(out, filter='data')
            finally:
                subprocess.run(KUBE + ['delete', 'pod', pod, '--wait=true', '--timeout=180s'], check=True)
                gpu_sample(out / 'gpu-after-cleanup.txt')
    metadata = json.loads((out / 'run-metadata.json').read_text())
    if rc != 0 or metadata['runner_exit_code'] != 0:
        raise SystemExit(f'CPU{cpu} failed; see engine.log and metadata')
    with (out / 'aggregation.txt').open('w') as output:
        subprocess.run([sys.executable, str(ROOT / 'summarize.py'), str(CASES), str(out), str(cpu)],
                       stdout=output, check=True)
    validate(out, cpu)
    write_json(out / 'artifact-sha256.json', {
        p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'artifact-sha256.json'
    })
    print(f'CPU{cpu} validated: ' + json.dumps(json.loads((out / 'summary.json').read_text())['pooled_measurement']), flush=True)


if __name__ == '__main__':
    main()
