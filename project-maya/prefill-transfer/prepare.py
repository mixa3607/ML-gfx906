#!/usr/bin/env python3
"""Capture non-secret experiment inputs and emit, but do not apply, a test pod."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def kube(*args):
    return subprocess.check_output(['kubectl', '-n', 'apps-ml', *args])


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    pod = json.loads(kube('get', 'pod', 'maya-ds41-6944678555-7hz6m', '-o', 'json'))
    deployment = json.loads(kube('get', 'deployment', 'maya-ds41', '-o', 'json'))
    name = pod['metadata']['name']
    config = json.loads(kube('exec', name, '-c', 'maya', '--', 'cat', '/data/config/maya-config.json'))
    # Only the known public runtime settings are retained, never API credentials.
    config = {k: config[k] for k in ('exe', 'cwd', 'args', 'env', 'tokenizer')}
    allowed = ('DS4_', 'STRATA_DS4_', 'MAYA_DS4_')
    config['env'] = {k: v for k, v in config['env'].items()
                     if k.startswith(allowed) or k in ('HIP_VISIBLE_DEVICES', 'LD_LIBRARY_PATH')}
    (out / 'runtime.json').write_text(json.dumps(config, indent=2) + '\n')
    seed = kube('exec', name, '-c', 'maya', '--', 'cat', '/data/expert-profile.bin')
    (out / 'seed-profile.bin').write_bytes(seed)
    image = pod['status']['containerStatuses'][0]['imageID']
    image = image.removeprefix('docker-pullable://')
    manifest = {'deployment': 'maya-ds41', 'replicas': deployment['spec']['replicas'],
                'image': image, 'config_sha256': hashlib.sha256((out / 'runtime.json').read_bytes()).hexdigest(),
                'seed_sha256': hashlib.sha256(seed).hexdigest()}
    (out / 'before.json').write_text(json.dumps(manifest, indent=2) + '\n')
    test = {
        'apiVersion': 'v1', 'kind': 'Pod',
        'metadata': {'name': 'maya-prefill-transfer', 'namespace': 'apps-ml'},
        'spec': {
            'automountServiceAccountToken': False, 'restartPolicy': 'Never',
            'terminationGracePeriodSeconds': 60,
            'nodeSelector': {'kubernetes.io/hostname': 'kube-worker6.arkprojects.lan'},
            'tolerations': [{'key': 'feature.node.kubernetes.io/' + gpu + '-gpu',
                             'operator': 'Equal', 'value': 'true', 'effect': 'NoSchedule'}
                            for gpu in ('amd', 'nvidia')],
            'imagePullSecrets': [{'name': 'harbor-registry-pull-secret'}],
            'containers': [{
                'name': 'bench', 'image': image, 'imagePullPolicy': 'IfNotPresent',
                'command': ['/bin/bash', '-ec', 'ulimit -l unlimited; exec sleep infinity'],
                'securityContext': {'privileged': True, 'runAsUser': 0},
                'env': [{'name': 'HIP_VISIBLE_DEVICES', 'value': '0,1,2,3'},
                        {'name': 'HF_HUB_OFFLINE', 'value': '1'},
                        {'name': 'TRANSFORMERS_OFFLINE', 'value': '1'}],
                'resources': {'requests': {'cpu': '4', 'memory': '220Gi'},
                              'limits': {'memory': '220Gi'}},
                'volumeMounts': [
                    {'name': 'hf', 'mountPath': '/root/.cache/huggingface', 'readOnly': True},
                    {'name': 'existing', 'mountPath': '/existing', 'readOnly': True},
                    {'name': 'data', 'mountPath': '/data'},
                    {'name': 'kfd', 'mountPath': '/dev/kfd'},
                    {'name': 'dri', 'mountPath': '/dev/dri'},
                    {'name': 'shm', 'mountPath': '/dev/shm'}]}],
            'volumes': [
                {'name': 'hf', 'persistentVolumeClaim': {'claimName': 'worker6-hf-cache', 'readOnly': True}},
                {'name': 'existing', 'persistentVolumeClaim': {'claimName': 'maya-ds41', 'readOnly': True}},
                {'name': 'data', 'emptyDir': {}},
                {'name': 'kfd', 'hostPath': {'path': '/dev/kfd'}},
                {'name': 'dri', 'hostPath': {'path': '/dev/dri'}},
                {'name': 'shm', 'emptyDir': {'medium': 'Memory', 'sizeLimit': '8Gi'}}]}}
    (out / 'pod.json').write_text(json.dumps(test, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
