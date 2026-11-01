"""Four-arm GPU experiment. Requires explicit cluster/hardware approval."""

import copy
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
BASE = REPO / 'project-maya/ds41-optimization/base-params/maya-config.json'
SUMMARIZER = OUT.parent / 'baseline-spec1-tp4/summarize.py'
KUBE = ['kubectl', '-n', 'apps-ml']
POD = 'maya-ds41-tuning'
PYTHON = '/opt/maya/.venv/bin/python'
IMAGE = 'sha256:50210b2fdec9c2e36b57fe0c8de2d3a9dd2d1fb33bb99757b37f229e824d51d2'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(command):
    return subprocess.check_output(command, text=True)


def gpu_sample(path):
    text = capture(KUBE + ['exec', 'rocm-toolkit-0', '--', 'amd-smi', 'monitor',
                           '-u', '-v', '-t', '-w', '1', '-i', '1', '--json'])
    path.write_text(text.rstrip() + '\n')
    rows = json.loads(text[text.index('['):])
    assert {r['gpu'] for r in rows} == {0, 1, 2, 3}, rows
    assert all(r['gfx']['value'] == 0 and r['vram_used']['unit'] == 'MB'
               and r['vram_used']['value'] < 32 for r in rows), 'GPU is not idle'


def measured(path):
    return [json.loads(line) for line in (path / 'results.jsonl').read_text().splitlines()
            if json.loads(line)['phase'] == 'measurement']


def select_skip(control, candidate):
    before = json.loads((control / 'summary.json').read_text())
    after = json.loads((candidate / 'summary.json').read_text())
    ratios = {
        metric: after['pooled_measurement'][metric] / before['pooled_measurement'][metric]
        for metric in ('prefill_tokens_per_second', 'decode_tokens_per_second')
    }
    by_pp = {
        pp: {metric: after['by_pp'][pp][metric] / before['by_pp'][pp][metric]
             for metric in ratios}
        for pp in before['by_pp']
    }
    passes = []
    a, b = measured(control), measured(candidate)
    for start in (0, 5):
        # Same input lengths/tokens in each arm; a prompt-time ratio is a speed ratio.
        passes.append(sum(r['done']['prompt_ms'] for r in a[start:start + 5]) /
                      sum(r['done']['prompt_ms'] for r in b[start:start + 5]))
    checks = {
        'pooled_prefill_gain_at_least_5_percent': ratios['prefill_tokens_per_second'] >= 1.05,
        'pooled_decode_no_more_than_5_percent_regression': ratios['decode_tokens_per_second'] >= 0.95,
        'per_length_no_more_than_5_percent_regression': all(v >= 0.95 for row in by_pp.values() for v in row.values()),
        'prefill_direction_consistent_in_both_passes': all(r > 1 for r in passes),
    }
    return {
        'selected_skip': int(all(checks.values())), 'checks': checks,
        'pooled_speed_ratios': ratios, 'by_pp_speed_ratios': by_pp,
        'prefill_speed_ratios_by_pass': passes,
        'meaning': 'Provisional screening decision, not a significance test or an optimum.',
    }


def validate(path):
    metadata = json.loads((path / 'run-metadata.json').read_text())
    config = json.loads((path / 'maya-config.json').read_text())
    args = metadata['engine_args']
    assert args[args.index('--cpu-threads') + 1] == '74'
    assert args[args.index('--tp') + 1] == '4'
    assert metadata['input_sha256'] == {
        'config': sha(path / 'maya-config.json'), 'runner': sha(RUNNER), 'cases': sha(CASES),
    }
    assert metadata['request_controls'] == {'temperature': 0, 'spec': 1}
    assert metadata['smt_active'] == '0' and metadata['numa_online'] == '0-1'
    env = metadata['effective_engine_env']
    assert env['DS4_SKIP_UNPICKED'] == config['env']['DS4_SKIP_UNPICKED']
    assert env['STRATA_DS4_HC_FUSE'] == config['env']['MAYA_DS4_HC_FUSE']
    pod = json.loads((path / 'pod.json').read_text())
    assert pod['status']['containerStatuses'][0]['imageID'].endswith('@' + IMAGE)
    log = (path / 'engine.log').read_text()
    assert 'tensor parallel 4 ->' not in log and '576 to 576 a member' in log
    assert '; 74 threads' in log
    assert len(re.findall(r'maya ds4 serve: prompt \d+ tokens', log)) == 22
    if config['env']['MAYA_DS4_HC_FUSE'] != '0':
        assert 'HC_FUSE' in log
    rows = measured(path)
    assert all(r['done']['generated'] == 256 and r['done']['finish'] == 'length' for r in rows)
    reference = OUT.parent / 'baseline-spec1-tp4'
    old = json.loads((reference / 'run-metadata.json').read_text())
    assert metadata['engine_sha256'] == old['engine_sha256']
    assert (path / 'expert-profile.seed.bin').read_bytes() == (reference / 'expert-profile.seed.bin').read_bytes()
    assert all(json.loads((path / 'patch-verification.json').read_text())['checks'].values())


def run_arm(name, skip, fuse):
    path = OUT / name
    path.mkdir()
    gpu_sample(path / 'gpu-before.txt')
    config = copy.deepcopy(json.loads(BASE.read_text()))
    assert config['args'][config['args'].index('--cpu-threads') + 1] == '74'
    config['env'].update({'DS4_SKIP_UNPICKED': str(skip), 'MAYA_DS4_HC_FUSE': str(fuse)})
    write_json(path / 'requested-config.json', config)
    created = False
    print(f'Starting arm {name}: CPU74 skip={skip} hcfuse={fuse}', flush=True)
    try:
        subprocess.run(KUBE + ['create', '-f', str(HERE / 'pod.yaml')], check=True)
        created = True
        subprocess.run(KUBE + ['wait', '--for=condition=Ready', f'pod/{POD}', '--timeout=600s'], check=True)
        (path / 'pod.json').write_text(capture(KUBE + ['get', 'pod', POD, '-o', 'json']))
        subprocess.run(KUBE + ['exec', POD, '--', 'mkdir', '/data/input'], check=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as tar:
            for source, target in ((path / 'requested-config.json', 'config.json'),
                                   (RUNNER, 'run.py'), (CASES, 'cases.jsonl'),
                                   (HERE / 'remote.py', 'remote.py')):
                tar.add(source, arcname=target)
        subprocess.run(KUBE + ['exec', '-i', POD, '--', 'tar', '-xf', '-', '-C', '/data/input'],
                       input=archive.getvalue(), check=True)
        with (path / 'prepare.txt').open('w') as log:
            subprocess.run(KUBE + ['exec', POD, '--', PYTHON, '/data/input/remote.py', 'prepare'],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        rc = subprocess.call(KUBE + ['exec', POD, '--', PYTHON, '/data/input/remote.py', 'run'])
        write_json(path / 'host-exit.json', {'kubectl_exec_exit_code': rc})
    finally:
        if created:
            try:
                # Export before deletion even on startup/parity failure.
                tar = subprocess.run(KUBE + ['exec', POD, '--', 'tar', '-cf', '-', '-C', '/data/results', '.'],
                                     stdout=subprocess.PIPE, check=True)
                with tarfile.open(fileobj=io.BytesIO(tar.stdout)) as archive:
                    archive.extractall(path, filter='data')
            finally:
                subprocess.run(KUBE + ['delete', 'pod', POD, '--wait=true', '--timeout=180s'], check=True)
                gpu_sample(path / 'gpu-after-cleanup.txt')
    metadata = json.loads((path / 'run-metadata.json').read_text())
    if rc != 0 or metadata['runner_exit_code'] != 0:
        print(f'Arm {name} FAILED; artifacts retained at {path}', flush=True)
        return False
    with (path / 'aggregation.txt').open('w') as output:
        subprocess.run([sys.executable, str(SUMMARIZER), str(CASES), str(path)], stdout=output, check=True)
    validate(path)
    write_json(path / 'artifact-sha256.json', {
        p.name: sha(p) for p in sorted(path.iterdir()) if p.is_file()
    })
    print(f'Arm {name} validated: ' + json.dumps(json.loads((path / 'summary.json').read_text())['pooled_measurement']), flush=True)
    return True


def main():
    assert Path.cwd().resolve() == REPO, f'Run from {REPO}'
    assert sha(CASES) == '3195a02e90078b366c00dce429652b386fe3616d879cdd25c1a6f288435b46c3'
    write_json(OUT / 'source-state.json', {
        'repository_head': capture(['git', 'rev-parse', 'HEAD']).strip(),
        'input_sha256': {'runner': sha(RUNNER), 'cases': sha(CASES), 'base_config': sha(BASE)},
        'script_sha256': {p.name: sha(p) for p in sorted(HERE.iterdir()) if p.is_file()},
    })
    (OUT / 'gpu-static.json').write_text(capture(KUBE + ['exec', 'rocm-toolkit-0', '--',
        'amd-smi', 'static', '-a', '-b', '-d', '-v', '-l', '-u', '--json']))
    for name, skip in (('control', 0), ('skip1', 1)):
        if not run_arm(name, skip, 0):
            raise SystemExit(f'{name} failed; selection stopped')
    decision = select_skip(OUT / 'control', OUT / 'skip1')
    write_json(OUT / 'decision.json', decision)
    print('Skip screening: ' + json.dumps(decision), flush=True)
    outcomes = {}
    for fuse in (1, 2):
        outcomes[f'hcfuse{fuse}'] = run_arm(f'hcfuse{fuse}', decision['selected_skip'], fuse)
    write_json(OUT / 'outcomes.json', outcomes)
    if not all(outcomes.values()):
        raise SystemExit('One or more fusion arms failed; see retained artifacts')


if __name__ == '__main__':
    main()
