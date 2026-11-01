"""Run one baseline on real GPUs. Requires explicit cluster/hardware approval."""

import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile


HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPO = HERE.parents[4]
CASES = REPO / 'project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl'
RUNNER = REPO / 'project-maya/benchmarking/run.py'
CONFIG = REPO / 'project-maya/ds41-optimization/base-params/maya-config.json'
KUBE = ['kubectl', '-n', 'apps-ml']
POD = 'maya-ds41-baseline'
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


def validate():
    metadata = json.loads((OUT / 'run-metadata.json').read_text())
    pod = json.loads((OUT / 'pod.json').read_text())
    pack = json.loads((OUT / 'pack-metadata.json').read_text())
    assert pod['status']['containerStatuses'][0]['imageID'].endswith('@' + IMAGE)
    assert metadata['input_sha256'] == {
        'config': sha(CONFIG), 'runner': sha(RUNNER), 'cases': sha(CASES),
    }
    assert (OUT / 'maya-config.json').read_bytes() == CONFIG.read_bytes()
    assert metadata['request_controls'] == {'temperature': 0, 'spec': 1}
    args = metadata['engine_args']
    assert args[args.index('--tp') + 1] == '4'
    assert args[args.index('--cpu-threads') + 1] == '74'
    assert metadata['effective_engine_env']['STRATA_DS4_SLOT_KEEP'] == '0'
    assert metadata['source_commit'] == '6ecbd3cbc5330b57f70cd5cf8a5c42eb8ef950cc'
    assert metadata['smt_active'] == '0' and metadata['numa_online'] == '0-1'
    assert sha(OUT / 'expert-profile.seed.bin') == pack['expert_profile_seed_sha256']
    assert all(json.loads((OUT / 'patch-verification.json').read_text())['checks'].values())
    log = (OUT / 'engine.log').read_text()
    assert 'tensor parallel 4 ->' not in log and '576 to 576 a member' in log
    assert '; 74 threads' in log and 'ds4 slots:' not in log
    assert len(re.findall(r'maya ds4 serve: prompt \d+ tokens', log)) == 22


def main():
    assert Path.cwd().resolve() == REPO, f'Run from {REPO}'
    assert not (OUT / 'source-state.json').exists(), 'Do not overwrite a run'
    assert sha(CASES) == '3195a02e90078b366c00dce429652b386fe3616d879cdd25c1a6f288435b46c3'
    config = json.loads(CONFIG.read_text())
    assert config['env']['MAYA_DS4_SLOT_KEEP'] == '0'
    assert config['args'][config['args'].index('--cpu-threads') + 1] == '74'
    write_json(OUT / 'source-state.json', {
        'repository_head': capture(['git', 'rev-parse', 'HEAD']).strip(),
        'input_sha256': {'runner': sha(RUNNER), 'cases': sha(CASES), 'config': sha(CONFIG)},
        'script_sha256': {
            str(p.relative_to(OUT)): sha(p)
            for p in [*sorted(HERE.glob('*.py')), HERE / 'pod.yaml', OUT / 'summarize.py']
        },
    })
    gpu_sample(OUT / 'gpu-before.txt')
    (OUT / 'gpu-static.json').write_text(capture(KUBE + ['exec', 'rocm-toolkit-0', '--',
        'amd-smi', 'static', '-a', '-b', '-d', '-v', '-l', '-u', '--json']))
    created = False
    try:
        subprocess.run(KUBE + ['create', '-f', str(HERE / 'pod.yaml')], check=True)
        created = True
        subprocess.run(KUBE + ['wait', '--for=condition=Ready', f'pod/{POD}', '--timeout=600s'], check=True)
        (OUT / 'pod.json').write_text(capture(KUBE + ['get', 'pod', POD, '-o', 'json']))
        subprocess.run(KUBE + ['exec', POD, '--', 'mkdir', '/data/input'], check=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as tar:
            for source, target in ((CONFIG, 'config.json'), (RUNNER, 'run.py'),
                                   (CASES, 'cases.jsonl'), (HERE / 'remote.py', 'remote.py')):
                tar.add(source, arcname=target)
        subprocess.run(KUBE + ['exec', '-i', POD, '--', 'tar', '-xf', '-', '-C', '/data/input'],
                       input=archive.getvalue(), check=True)
        with (OUT / 'prepare.txt').open('w') as log:
            subprocess.run(KUBE + ['exec', POD, '--', PYTHON, '/data/input/remote.py', 'prepare'],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        rc = subprocess.call(KUBE + ['exec', POD, '--', PYTHON, '/data/input/remote.py', 'run'])
        write_json(OUT / 'host-exit.json', {'kubectl_exec_exit_code': rc})
    finally:
        if created:
            try:
                tar = subprocess.run(KUBE + ['exec', POD, '--', 'tar', '-cf', '-', '-C', '/data/results', '.'],
                                     stdout=subprocess.PIPE, check=True)
                with tarfile.open(fileobj=io.BytesIO(tar.stdout)) as archive:
                    archive.extractall(OUT, filter='data')
            finally:
                subprocess.run(KUBE + ['delete', 'pod', POD, '--wait=true', '--timeout=180s'], check=True)
                gpu_sample(OUT / 'gpu-after-cleanup.txt')
    metadata = json.loads((OUT / 'run-metadata.json').read_text())
    if rc != 0 or metadata['runner_exit_code'] != 0:
        raise SystemExit('Baseline failed; see engine.log and metadata')
    with (OUT / 'aggregation.txt').open('w') as output:
        subprocess.run([sys.executable, str(OUT / 'summarize.py'), str(CASES), str(OUT)],
                       stdout=output, check=True)
    validate()
    write_json(OUT / 'artifact-sha256.json', {
        p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != 'README.md'
    })
    print('Baseline validated: ' + json.dumps(json.loads((OUT / 'summary.json').read_text())['pooled_measurement']), flush=True)


if __name__ == '__main__':
    main()
