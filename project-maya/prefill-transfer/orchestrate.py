#!/usr/bin/env python3
"""Run the approved serial experiment; always delete the test pod and restore serving."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
POD = 'maya-prefill-transfer'


def command(args, **kwargs):
    print('+ ' + ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def kube(*args, **kwargs):
    return command(['kubectl', '-n', 'apps-ml', *args], **kwargs)


def output(path, *args):
    with path.open('w') as f:
        kube(*args, stdout=f)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--transfer-image', required=True)
    parser.add_argument('--prune-image', required=True)
    args = parser.parse_args()
    root = args.root
    initial = json.loads((root / 'before.json').read_text())
    pod = json.loads((root / 'pod.json').read_text())
    inputs = root / 'input'
    inputs.mkdir(exist_ok=False)
    for name in ('runtime.json', 'seed-profile.bin'):
        shutil.copyfile(root / name, inputs / name)
    shutil.copyfile(HERE / 'run.py', inputs / 'run.py')
    old = HERE.parent / 'ds41-running-spec-tmp/code-and-russian'
    for name, dest in (('russian-cases.jsonl', 'cases.jsonl'),
                       ('russian-sources.jsonl', 'sources.jsonl'),
                       ('cases-nonce.manifest.json', 'historical-input-manifest.json')):
        shutil.copyfile(old / name, inputs / dest)
    expected = 'b880c6551696301e314e14ca8a1065563dfc8d8e8d0bb2195f5a4d63e7dd90a3'
    if hashlib.sha256((inputs / 'cases.jsonl').read_bytes()).hexdigest() != expected:
        raise ValueError('Frozen corpus changed')
    state = {'complete': False, 'sessions': [], 'cleanup': False}
    active = False

    def create(image, label):
        nonlocal active
        pod['spec']['containers'][0]['image'] = image
        path = root / (label + '-pod.json')
        path.write_text(json.dumps(pod, indent=2) + '\n')
        kube('apply', '-f', path)
        active = True
        kube('wait', '--for=condition=Ready', 'pod/' + POD, '--timeout=600s')
        output(root / (label + '-pod-start.json'), 'get', 'pod', POD, '-o', 'json')
        kube('exec', POD, '--', 'bash', '-ec',
             'mkdir -p /data/ds4 /data/input /data/runs; '
             'cp /existing/ds4/ds4.txt /existing/ds4/tensors.txt /existing/ds4/engram.bin /data/ds4/; '
             'cp -a /existing/ds4/tokenizer /data/ds4/; '
             'ln -s /existing/vision /data/vision; ln -s /existing/drafter /data/drafter')
        kube('cp', str(inputs) + '/.', POD + ':/data/input')

    def remove(label):
        nonlocal active
        output(root / (label + '-pod-end.json'), 'get', 'pod', POD, '-o', 'json')
        kube('delete', 'pod', POD, '--wait=true', '--timeout=180s')
        active = False

    def run(name, *flags):
        command([sys.executable, HERE / 'collect.py', '--out', root / name, '--',
                 'kubectl', '-n', 'apps-ml', 'exec', '-i', POD, '--',
                 'python', '/data/input/run.py', '--name', name, *flags])
        manifest = json.loads((root / name / name / 'manifest.json').read_text())
        state['sessions'].append({'name': name, 'manifest': manifest})
        (root / 'experiment.json').write_text(json.dumps(state, indent=2) + '\n')
        if '--diagnostic' in flags:
            target = root / name / 'raw'
            target.mkdir()
            for index in (1, 2):
                kube('cp', f'{POD}:/data/runs/{name}/logits.{index}.f32', target / f'logits.{index}.f32')

    def compare(a, b):
        ar = [json.loads(s) for s in (root / a / a / 'results.jsonl').read_text().splitlines()]
        br = [json.loads(s) for s in (root / b / b / 'results.jsonl').read_text().splitlines()]
        rows = [{'case': x['id'], 'first_row_identical':
                 x['logits']['first_row_sha256'] == y['logits']['first_row_sha256'],
                 'output_identical': x['tokens'] == y['tokens']} for x, y in zip(ar, br)]
        (root / (a + '-vs-' + b + '.json')).write_text(json.dumps(rows, indent=2) + '\n')
        if len(rows) != 2 or not all(r['first_row_identical'] for r in rows):
            raise ValueError('Diagnostic prefill logits differ; inspect before timing')

    try:
        kube('scale', 'deployment/maya-ds41', '--replicas=0')
        kube('wait', '--for=delete', 'pod/maya-ds41-6944678555-7hz6m', '--timeout=240s')
        output(root / 'gpu-before.txt', 'exec', 'rocm-toolkit-0', '--',
               'amd-smi', 'monitor', '-u', '-v', '-t', '-w', '1', '-i', '1')
        gpu_rows = [s for s in (root / 'gpu-before.txt').read_text().splitlines()
                    if re.match(r'^\d+\s+\d+\s+\d+\s', s)]
        if len(gpu_rows) != 4 or any(not re.search(r'\s0\s%\s+\d+\sMB', s) for s in gpu_rows):
            raise RuntimeError('Other GPU workloads are active; refusing overlap')
        create(initial['image'], 'stock-1')
        run('stock-diagnostic', '--diagnostic')
        run('stock-1')
        remove('stock-1')
        create(args.transfer_image, 'transfer')
        run('transfer-staged-check', '--diagnostic', '--transfer', '--pin-off')
        run('transfer-direct-check', '--diagnostic', '--transfer')
        compare('stock-diagnostic', 'transfer-staged-check')
        compare('transfer-staged-check', 'transfer-direct-check')
        run('transfer-1', '--transfer')
        remove('transfer')
        create(initial['image'], 'stock-2')
        run('stock-2')
        remove('stock-2')
        create(args.prune_image, 'prune')
        run('prune-off-check', '--diagnostic', '--transfer')
        run('prune-on-check', '--diagnostic', '--transfer', '--prune')
        compare('prune-off-check', 'prune-on-check')
        run('prune-off-1', '--transfer')
        run('prune-on-1', '--transfer', '--prune')
        run('prune-off-2', '--transfer')
        run('chunk4096-check', '--diagnostic', '--transfer', '--chunk', '4096')
        run('chunk4096', '--transfer', '--chunk', '4096')
        state['complete'] = True
    finally:
        if active:
            # Export state even if the container cannot be entered after an OOM.
            subprocess.run(['kubectl', '-n', 'apps-ml', 'get', 'pod', POD, '-o', 'json'],
                           stdout=(root / 'pod-final.json').open('w'))
            kube('delete', 'pod', POD, '--wait=true', '--timeout=180s')
        output(root / 'gpu-after-tests.txt', 'exec', 'rocm-toolkit-0', '--',
               'amd-smi', 'monitor', '-u', '-v', '-t', '-w', '1', '-i', '1')
        kube('scale', 'deployment/maya-ds41', '--replicas=' + str(initial['replicas']))
        state['cleanup'] = True
        (root / 'experiment.json').write_text(json.dumps(state, indent=2) + '\n')
        output(root / 'deployment-after.json', 'get', 'deployment', 'maya-ds41', '-o', 'json')
    raise SystemExit(0 if state['complete'] else 1)


if __name__ == '__main__':
    main()
