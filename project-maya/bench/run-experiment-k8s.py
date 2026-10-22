"""Run smoke and logit checks sequentially, with a pinned original binary."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import yaml


def kubectl(*args, value=None):
    return subprocess.check_output(['kubectl', '-n', 'apps-ml', *args],
                                   input=json.dumps(value).encode() if value is not None else None)


def collect(job, logs):
    code = '''from pathlib import Path
import json
base=next(Path('/proc/1/root/srv/ml/maya-gfx906-tests').glob(''' + repr(job + '-*') + '''))
files={str(p.relative_to(base)):p.read_text() for p in base.rglob('*') if p.is_file() and 'pack' not in p.relative_to(base).parts and p.suffix in ['.json','.log','.txt','.jsonl']}
print(json.dumps({'directory':base.name,'files':files}))
'''
    data = json.loads(subprocess.check_output(['kubectl', '-n', 'apps-ml', 'exec', '-i',
                      'rocm-toolkit-0', '--', 'python3', '-'], input=code.encode()))
    for relative, text in data['files'].items():
        p = logs / data['directory'] / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return data['directory']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', choices=['pr297', 'pr377', 'pr377-360'], required=True)
    parser.add_argument('--image', required=True, help='Test image, pinned by digest')
    parser.add_argument('--baseline', required=True, help='Reference runtime, pinned by digest')
    parser.add_argument('--mode', choices=['parity', 'flow-copy'], default='parity')
    args = parser.parse_args()
    assert '@sha256:' in args.image and '@sha256:' in args.baseline
    root = Path(__file__).resolve().parents[1]
    logs = root / 'logs'
    patch = root / 'build-context/patch/experiments' / (args.experiment + '.patch')
    job = yaml.safe_load((root / 'test-job.yaml').read_text())
    job['metadata']['generateName'] = 'maya-' + args.experiment + ('-flow-copy' if args.mode == 'flow-copy' else '') + '-verify-'
    job['spec'].update(activeDeadlineSeconds=7200, ttlSecondsAfterFinished=86400)
    spec = job['spec']['template']['spec']
    spec['nodeSelector'] = {'kubernetes.io/hostname': 'kube-worker6.arkprojects.lan'}
    c = spec['containers'][0]
    c['image'] = args.image
    c['name'] = 'verify'
    c['resources'] = {'requests': {'cpu': '1', 'memory': '8Gi'}, 'limits': {'memory': '192G'}}
    c['env'] = [
        {'name': 'POD_NAME', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.name'}}},
        {'name': 'MAYA_BENCH_OUT', 'value': '/results/$(POD_NAME)'},
        {'name': 'MAYA_BENCH_MODEL', 'value': '/hf/hub/models--unsloth--DeepSeek-V4.1-Flash-1017-GGUF/'
         'snapshots/60ad3651641b5c97679c807e064ab1d7a3ca1455/UD-Q8_K_XL'},
        {'name': 'HIP_VISIBLE_DEVICES', 'value': '0,1,2,3'},
        {'name': 'HSA_XNACK', 'value': '0'},
        {'name': 'DS4_ENGRAM_CACHE_MB', 'value': '256'},
        {'name': 'STRATA_DS4_RAM_TIER', 'value': '0'},
        {'name': 'STRATA_DS4_DISK_SKIP_W', 'value': '0'},
        {'name': 'STRATA_DS4_PROMPT_SKIP', 'value': '0'},
        {'name': 'MAYA_EXPERIMENT_EXPECTED', 'value': args.experiment},
        {'name': 'MAYA_EXPERIMENT_PATCH_SHA256', 'value': hashlib.sha256(patch.read_bytes()).hexdigest()},
    ]
    parity_script = 'ds41-flow-copy-parity.py' if args.mode == 'flow-copy' else 'ds41-parity.py'
    code = """import os,subprocess
subprocess.run(['python','/bench/verify-experiment.py'],check=True,env=dict(os.environ,HIP_VISIBLE_DEVICES='0',OMP_NUM_THREADS='2'))
""" + f"subprocess.run(['python','/bench/{parity_script}'],check=True)\n"
    c['command'] = ['python', '-c', code]
    names = ['ds41-tune.py', parity_script, 'verify-experiment.py']
    cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'namespace': 'apps-ml',
          'generateName': job['metadata']['generateName']},
          'data': {name: (root / 'bench' / name).read_text() for name in names}}
    cm_name = json.loads(kubectl('create', '-f', '-', '-o', 'json', value=cm))['metadata']['name']
    c['volumeMounts'] += [
        {'name': 'hf', 'mountPath': '/hf', 'readOnly': True},
        {'name': 'results', 'mountPath': '/results'},
        {'name': 'bench', 'mountPath': '/bench', 'readOnly': True},
        {'name': 'baseline', 'mountPath': '/baseline', 'readOnly': True},
    ]
    spec['volumes'] += [
        {'name': 'hf', 'hostPath': {'path': '/srv/ml/shared-hf-cache', 'type': 'Directory'}},
        {'name': 'results', 'hostPath': {'path': '/srv/ml/maya-gfx906-tests', 'type': 'DirectoryOrCreate'}},
        {'name': 'bench', 'configMap': {'name': cm_name}},
        {'name': 'baseline', 'emptyDir': {}},
    ]
    spec['initContainers'] = [{'name': 'original-binary', 'image': args.baseline,
        'command': ['python', '-c', "import shutil; shutil.copy2('/opt/maya/build-hip/maya-ds4','/baseline/maya-ds4'); shutil.copy2('/opt/maya/build-hip/MAYA-BUILD.json','/baseline/MAYA-BUILD.json')"],
        'resources': {'requests': {'cpu': '1', 'memory': '128Mi'}, 'limits': {'memory': '1Gi'}},
        'volumeMounts': [{'name': 'baseline', 'mountPath': '/baseline'}]}]
    created = json.loads(kubectl('create', '-f', '-', '-o', 'json', value=job))
    name = created['metadata']['name']
    logs.mkdir(exist_ok=True)
    (logs / (name + '-spec.json')).write_text(json.dumps(created, indent=2))
    Path('/tmp/opencode/maya-experiment-verify-job').write_text(name)
    kubectl('patch', 'configmap', cm_name, '--type=merge', '-p', json.dumps({'metadata': {
        'ownerReferences': [{'apiVersion': 'batch/v1', 'kind': 'Job', 'name': name,
                             'uid': created['metadata']['uid']}]}}))
    print('VERIFY JOB', name, flush=True)
    selector = 'batch.kubernetes.io/job-name=' + name
    kubectl('wait', '--for=create', 'pod', '-l', selector, '--timeout=60s')
    kubectl('wait', '--for=jsonpath={.status.containerStatuses[0].containerID}',
            'pod', '-l', selector, '--timeout=15m')
    with (logs / (name + '.log')).open('wb') as log:
        proc = subprocess.Popen(['kubectl', '-n', 'apps-ml', 'logs', '-f', 'job/' + name, '-c', 'verify'],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in proc.stdout:
            log.write(line)
            log.flush()
            print(line.decode(), end='', flush=True)
        if proc.wait():
            raise RuntimeError('kubectl logs failed')
    kubectl('wait', '--for=jsonpath={.status.containerStatuses[0].state.terminated.reason}',
            'pod', '-l', selector, '--timeout=90s')
    pods = json.loads(kubectl('get', 'pods', '-l', selector, '-o', 'json'))
    state = pods['items'][0]['status']['containerStatuses'][0]['state']
    print('VERIFY EXIT', json.dumps(state), flush=True)
    directory = collect(name, logs)
    print('VERIFY ARTIFACTS', directory, flush=True)
    if state['terminated']['exitCode'] != 0:
        raise SystemExit(state['terminated']['exitCode'])


if __name__ == '__main__':
    main()
