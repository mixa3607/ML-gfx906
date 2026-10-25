import json
from pathlib import Path
import subprocess
import unittest

import yaml


ROOT = Path(__file__).resolve().parent


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.docs = {name: {doc['kind']: doc for doc in yaml.safe_load_all((ROOT / f'{name}.yaml').read_text())}
                     for name in ('prefill', 'decode')}

    def test_profile_switch_reuses_resources(self):
        identities = []
        for profile, objects in self.docs.items():
            self.assertEqual(set(objects), {'ConfigMap', 'PersistentVolumeClaim', 'Deployment', 'Service'})
            identities.append([(d['kind'], d['metadata']['namespace'], d['metadata']['name'])
                               for d in objects.values()])
            deploy = objects['Deployment']['spec']
            self.assertEqual(deploy['replicas'], 1)
            self.assertEqual(deploy['strategy']['type'], 'Recreate')
            labels = deploy['template']['metadata']['labels']
            self.assertEqual(labels['profile'], profile)
            self.assertEqual(objects['Service']['spec']['selector'], deploy['selector']['matchLabels'])
        self.assertEqual(identities[0], identities[1])

    def test_profile_settings(self):
        for profile, objects in self.docs.items():
            cfg = json.loads(objects['ConfigMap']['data']['maya-ds4-hip.json'])
            args = dict(zip(cfg['args'][::2], cfg['args'][1::2]))
            expected = {'--tp': '2' if profile == 'prefill' else '4',
                        '--max-context': '196608', '--cpu-threads': '56',
                        '--prefill-chunk': '4096', '--mmap-experts': 'off',
                        '--dspark': 'none', '--vision': 'on'}
            self.assertEqual({key: args[key] for key in expected}, expected)
            self.assertEqual(cfg['env']['DS4_TP_GGUF_UNEVEN'], '1')
            self.assertEqual(cfg['env']['DS4_COPY_NUMA'], '2')
            self.assertEqual(cfg['env'].get('DS4_FLOW_TP', '0'), '1' if profile == 'prefill' else '0')
            pod = objects['Deployment']['spec']['template']['spec']
            cap = '187Gi' if profile == 'prefill' else '199Gi'
            self.assertEqual(pod['containers'][0]['resources']['limits'], {'memory': cap})
            for container in pod['containers'] + pod['initContainers']:
                self.assertEqual(container['image'], 'docker.io/mixa3607/maya-gfx906:v1.1.27-rocm-10.1')
                self.assertNotIn('cpu', container['resources']['limits'])

    def test_shell_syntax(self):
        scripts = []
        for objects in self.docs.values():
            prepare = objects['ConfigMap']['data']['prepare.sh']
            scripts.append(prepare)
            main = objects['Deployment']['spec']['template']['spec']['containers'][0]
            for script in (prepare, main['args'][0]):
                subprocess.run(['bash', '-n'], input=script, text=True, check=True)
        self.assertEqual(scripts[0], scripts[1])


if __name__ == '__main__':
    unittest.main()
