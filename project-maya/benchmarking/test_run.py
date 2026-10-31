import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import run


HELPERS = '''
import os

def engine_args(cfg):
    return cfg['args'] + ['--from-helper']

def child_env(cfg):
    return {**os.environ, **cfg['env']}
'''

ENGINE = '''
import json
import os
import sys
from pathlib import Path

with Path('commands.jsonl').open('w') as log:
    def record(value):
        log.write(json.dumps(value) + '\\n')
        log.flush()

    record({'args': sys.argv[1:], 'env': os.environ['BENCH_TEST']})
    print('engine diagnostics', file=sys.stderr)
    print('INFO engine=fake', flush=True)
    print('READY 4352 stop', flush=True)
    for line in sys.stdin:
        record(line.strip())
        if line == 'QUIT\\n':
            break
        if os.environ['BENCH_TEST'] == 'error':
            print('ERR request refused', flush=True)
            continue
        if os.environ['BENCH_TEST'] == 'exit':
            break
        print('PP 2 2 10.0 200.0 0', flush=True)
        print('T 42', flush=True)
        print('DONE 1 2 10.0 20.0 stop 0 0 0 0 0', flush=True)
'''


class RunnerTests(unittest.TestCase):
    def test_parse_done(self):
        self.assertEqual(run.parse_done('DONE 12 2048 1.5 2.75 length 3 4 5 6 7'), {
            'generated': 12,
            'prompt_tokens': 2048,
            'prompt_ms': 1.5,
            'decode_ms': 2.75,
            'finish': 'length',
            'drafts_accepted': 3,
            'drafts_offered': 4,
            'reused': 5,
            'hits': 6,
            'lookups': 7,
        })

    def invoke(self, mode):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'serve').mkdir()
            (root / 'serve/__init__.py').write_text('')
            (root / 'serve/server.py').write_text(HELPERS)
            exe = root / 'engine'
            exe.write_text(f'#!{sys.executable}\n' + ENGINE)
            exe.chmod(0o755)
            config = root / 'config.json'
            config.write_text(json.dumps({
                'exe': str(exe), 'cwd': str(root), 'args': ['--pack', '/unused'],
                'env': {'BENCH_TEST': mode},
            }))
            cases = root / 'cases.jsonl'
            cases.write_text(''.join(json.dumps({
                'id': phase, 'phase': phase, 'ids': [0, 123], 'tg': tg,
            }) + '\n' for phase, tg in [('warmup', 2), ('measurement', 3)]))
            result = subprocess.run([
                sys.executable, str(Path(__file__).with_name('run.py')),
                '--maya-root', str(root), '--config', str(config), str(cases),
            ], text=True, capture_output=True, timeout=10)
            commands = [json.loads(line) for line in (root / 'commands.jsonl').read_text().splitlines()]
            return result, commands

    def test_requests_and_launch_config(self):
        result, commands = self.invoke('ok')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands, [
            {'args': ['--serve', '--pack', '/unused', '--from-helper'], 'env': 'ok'},
            'GEN 2 temperature=0 spec=0 0,123',
            'GEN 3 temperature=0 spec=0 0,123',
            'QUIT',
        ])
        self.assertIn('engine diagnostics', result.stderr)
        self.assertEqual([json.loads(line) for line in result.stdout.splitlines()], [
            {'id': phase, 'phase': phase, 'done': {
                'generated': 1, 'prompt_tokens': 2, 'prompt_ms': 10.0, 'decode_ms': 20.0,
                'finish': 'stop', 'drafts_accepted': 0, 'drafts_offered': 0,
                'reused': 0, 'hits': 0, 'lookups': 0,
            }}
            for phase in ('warmup', 'measurement')
        ])

    def test_engine_error(self):
        result, commands = self.invoke('error')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ERR request refused', result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(len(commands), 2)

    def test_engine_exit(self):
        result, commands = self.invoke('exit')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('StopIteration', result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(len(commands), 2)


if __name__ == '__main__':
    unittest.main()
