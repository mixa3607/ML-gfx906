import ast
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

import yaml


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'ds41-running-tmp'))
from full_compute import runtime_configs


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.docs = {name: list(yaml.safe_load_all((ROOT / f'{name}.yaml').read_text()))
                     for name in ('prefill', 'decode')}

    def objects(self, profile):
        return {doc['kind']: doc for doc in self.docs[profile]}

    def test_complete_mutually_exclusive_bundles(self):
        identities = []
        for profile in self.docs:
            objects = self.objects(profile)
            self.assertEqual(len(self.docs[profile]), 4)
            self.assertEqual(set(objects), {'ConfigMap', 'PersistentVolumeClaim', 'Deployment', 'Service'})
            identities.append([(d['kind'], d['metadata']['namespace'], d['metadata']['name'])
                               for d in self.docs[profile]])
            deploy = objects['Deployment']['spec']
            self.assertEqual(deploy['replicas'], 1)
            self.assertEqual(deploy['strategy']['type'], 'Recreate')
            labels = deploy['template']['metadata']['labels']
            self.assertEqual(labels['profile'], profile)
            for key, value in objects['Service']['spec']['selector'].items():
                self.assertEqual(labels[key], value)
            for key, value in deploy['selector']['matchLabels'].items():
                self.assertEqual(labels[key], value)
            self.assertEqual(objects['Service']['spec']['type'], 'ClusterIP')
        self.assertEqual(*identities)

    def test_engine_settings_match_measured_candidates(self):
        for profile in self.docs:
            cfg = json.loads(self.objects(profile)['ConfigMap']['data']['maya-ds4-hip.json'])
            expected = copy.deepcopy(runtime_configs()['copy-c56-numa2-p4096'])
            expected['env']['DS4_TP_GGUF_UNEVEN'] = '1'
            if profile == 'prefill':
                expected['env'].update(DS4_FLOW_TP='1', DS4_FLOW_PUMP_WAIT='1')
            else:
                expected['args'][expected['args'].index('--tp') + 1] = '4'
            self.assertEqual(cfg['exe'], expected['exe'])
            self.assertEqual(cfg['cwd'], expected['cwd'])
            self.assertEqual(cfg['args'][:-2], expected['args'])
            self.assertEqual(cfg['args'][-2:], ['--expert-profile', f'/data/profiles/{profile}.bin'])
            env = dict(cfg['env'])
            self.assertEqual(env.pop('DS4_LANE_CAL'), f'/data/profiles/{profile}-lane-times.txt')
            self.assertEqual(env, expected['env'])
            self.assertEqual(cfg['backend'], 'hip')
            self.assertEqual(cfg['gpu'], [0, 1, 2, 3])
            self.assertEqual(cfg['tokenizer'], '/data/ds4/tokenizer')

    def test_scheduling_storage_and_memory(self):
        image = 'docker.io/mixa3607/maya-gfx906@sha256:d46312703b79af1cd70174ae9ef2faee23875db9c51f90353424aba6101ac2c1'
        for profile in self.docs:
            objects = self.objects(profile)
            pod = objects['Deployment']['spec']['template']['spec']
            self.assertEqual(pod['nodeSelector']['kubernetes.io/hostname'], 'kube-worker6.arkprojects.lan')
            self.assertEqual({t['key'] for t in pod['tolerations']},
                             {'feature.node.kubernetes.io/amd-gpu', 'feature.node.kubernetes.io/nvidia-gpu'})
            main, = pod['containers']
            init, = pod['initContainers']
            cap = '187Gi' if profile == 'prefill' else '199Gi'
            self.assertEqual(main['resources']['limits'], {'memory': cap})
            self.assertEqual(main['resources']['requests']['memory'], cap)
            self.assertTrue(main['securityContext']['privileged'])
            self.assertNotIn('livenessProbe', main)
            for container in (main, init):
                self.assertEqual(container['image'], image)
                self.assertNotIn('cpu', container['resources']['limits'])
                mounts = {m['name']: m for m in container['volumeMounts']}
                self.assertTrue(mounts['hf-cache']['readOnly'])
                self.assertEqual(mounts['hf-cache']['mountPath'], '/root/.cache/huggingface')
                self.assertEqual(mounts['data']['mountPath'], '/data')
                self.assertTrue(mounts['config']['readOnly'])
            self.assertFalse(any(m['name'].startswith('dev-') for m in init['volumeMounts']))
            volumes = {v['name']: v for v in pod['volumes']}
            self.assertEqual(volumes['data']['persistentVolumeClaim']['claimName'],
                             objects['PersistentVolumeClaim']['metadata']['name'])
            self.assertEqual(volumes['config']['configMap']['name'], objects['ConfigMap']['metadata']['name'])
            self.assertEqual(volumes['hf-cache']['persistentVolumeClaim'],
                             {'claimName': 'worker6-hf-cache', 'readOnly': True})
            self.assertEqual(volumes['dev-kfd']['hostPath']['path'], '/dev/kfd')
            self.assertEqual(volumes['dev-dri']['hostPath']['path'], '/dev/dri')
            self.assertEqual(volumes['shm']['emptyDir'], {'medium': 'Memory', 'sizeLimit': '8Gi'})

    def test_shared_scripts_are_identical_and_parse_without_execution(self):
        data = [self.objects(name)['ConfigMap']['data'] for name in self.docs]
        for script in ('prepare.sh', 'start.sh'):
            self.assertEqual(data[0][script], data[1][script])
            subprocess.run(['bash', '-n'], input=data[0][script], text=True, check=True)
        ast.parse(data[0]['start.sh'].split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0])
        prepare = data[0]['prepare.sh']
        self.assertIn('cp /etc/maya/maya-ds4-hip.json /data/config/maya-ds4-hip.json', prepare)
        self.assertIn('sha256sum --check', prepare)
        self.assertNotIn('hf download', prepare)
        self.assertIn('if [ ! -e "/data/profiles/$profile.bin" ]', prepare)


if __name__ == '__main__':
    unittest.main()
