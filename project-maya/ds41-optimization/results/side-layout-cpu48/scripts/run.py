"""Run exactly one approved side-layout arm and clean up its isolated pod."""

import argparse
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from analysis import (ACTIVE_CONFIG, ARMS, BASE_CONFIG, CASES, ORIGINAL, PREVIOUS,
                      REFERENCE, REPO, ROOT, RUNNER, SINGLES, TOP5, config_for,
                      read_json, sha, single, validate, write_json)


utilities = single.load_module('side_cpu_utilities', PREVIOUS / 'scripts/run.py')
KUBE = ['kubectl', '-n', 'apps-ml']
PYTHON = '/opt/maya/.venv/bin/python'


def run(arm):
    assert Path.cwd().resolve() == REPO, f'Run from {REPO}'
    assert read_json(ACTIVE_CONFIG) == read_json(BASE_CONFIG)
    assert sha(CASES) == '3195a02e90078b366c00dce429652b386fe3616d879cdd25c1a6f288435b46c3'
    out = ROOT / arm
    out.mkdir()
    write_json(out / 'maya-config.json', config_for(arm))
    pod = f'maya-ds41-side-{arm}'
    manifest = (ORIGINAL / 'scripts/pod.yaml').read_text().replace('maya-ds41-baseline', pod)
    (out / 'pod.yaml').write_text(manifest)
    scripts = [HERE / 'run.py', ROOT / 'analysis.py', SINGLES / 'analysis.py', BASE_CONFIG,
               ROOT.parent / 'final-candidates-cpu48/analysis.py',
               ROOT.parent / 'combos-cpu48/analysis.py',
               TOP5 / 'scripts/remote.py', TOP5 / 'memory_probe.py',
               PREVIOUS / 'scripts/run.py', PREVIOUS / 'scripts/remote.py', PREVIOUS / 'summarize.py',
               ORIGINAL / 'scripts/remote.py', ORIGINAL / 'scripts/pod.yaml']
    write_json(out / 'source-state.json', {
        'repository_head': utilities.capture(['git', 'rev-parse', 'HEAD']).strip(),
        'arm': arm, 'overrides': ARMS[arm], 'fresh_control': False,
        'comparison_reference': os.path.relpath(REFERENCE, out),
        'input_sha256': {'runner': sha(RUNNER), 'cases': sha(CASES), 'config': sha(out / 'maya-config.json')},
        'script_sha256': {os.path.relpath(p, out): sha(p) for p in scripts},
    })
    utilities.gpu_sample(out / 'gpu-before.txt')
    (out / 'gpu-static.json').write_text(utilities.capture(KUBE + ['exec', 'rocm-toolkit-0', '--',
        'amd-smi', 'static', '-a', '-b', '-d', '-v', '-l', '-u', '--json']))
    created = False
    rc = None
    print(f'Preparing side experiment: {arm}, overrides: {ARMS[arm]}', flush=True)
    try:
        subprocess.run(KUBE + ['create', '-f', str(out / 'pod.yaml')], check=True)
        created = True
        subprocess.run(KUBE + ['wait', '--for=condition=Ready', f'pod/{pod}', '--timeout=600s'], check=True)
        (out / 'pod.json').write_text(utilities.capture(KUBE + ['get', 'pod', pod, '-o', 'json']))
        subprocess.run(KUBE + ['exec', pod, '--', 'mkdir', '/data/input'], check=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as tar:
            for source, target in ((out / 'maya-config.json', 'config.json'), (RUNNER, 'run.py'),
                                   (CASES, 'cases.jsonl'), (TOP5 / 'scripts/remote.py', 'remote.py'),
                                   (TOP5 / 'memory_probe.py', 'memory_probe.py'),
                                   (PREVIOUS / 'scripts/remote.py', 'cpu_remote.py'),
                                   (ORIGINAL / 'scripts/remote.py', 'baseline_remote.py')):
                tar.add(source, arcname=target)
        subprocess.run(KUBE + ['exec', '-i', pod, '--', 'tar', '-xf', '-', '-C', '/data/input'],
                       input=archive.getvalue(), check=True)
        with (out / 'prepare.txt').open('w') as log:
            subprocess.run(KUBE + ['exec', pod, '--', PYTHON, '/data/input/remote.py', 'prepare'],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        rc = subprocess.call(KUBE + ['exec', pod, '--', PYTHON, '/data/input/remote.py', 'run', arm])
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
                utilities.gpu_sample(out / 'gpu-after-cleanup.txt')
    write_json(out / 'artifact-sha256.json', {
        p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'artifact-sha256.json'
    })
    metadata = read_json(out / 'run-metadata.json')
    if rc != 0 or metadata['runner_exit_code'] != 0:
        raise SystemExit(f'{arm}: runtime failed; artifacts exported; no retry or fallback')
    summary = validate(out, arm)
    write_json(out / 'summary.json', summary)
    write_json(out / 'artifact-sha256.json', {
        p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'artifact-sha256.json'
    })
    print(f'{arm}: validated artifacts, no performance verdict: ' + str(summary['pooled_measurement']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arm', choices=ARMS)
    run(parser.parse_args().arm)
