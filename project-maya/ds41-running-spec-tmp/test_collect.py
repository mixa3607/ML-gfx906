import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from collect import destination, store, sync


class CollectorTests(unittest.TestCase):
    def test_path_allowlist(self):
        root = Path('/example')
        self.assertEqual(destination(root, 'A-none/engine.log'), root / 'A-none/engine.log')
        for name in ('/etc/passwd', '../escape', 'A-none/../../escape', 'baseline.json', 'A-none/other'):
            with self.assertRaises(ValueError):
                destination(root, name)

    def test_append_and_replace(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            for text, append in [('a', False), ('b', True), ('c', False)]:
                store(root, {'kind': 'artifact', 'path': 'A-none/protocol.log', 'data': text, 'append': append})
            sync(root)
            self.assertEqual((root / 'A-none/protocol.log').read_text(), 'c')

    def test_saved_result_survives_failed_remote_process(self):
        producer = '''
import json, os, sys
def emit(value):
    print('SCREEN_EVENT ' + json.dumps(value), flush=True)
emit({'kind':'artifact','path':'A-none/manifest.json','data':'{"complete":false}\\n','append':False})
emit({'kind':'artifact','path':'A-none/results.jsonl','data':'{"id":"saved"}\\n','append':True})
emit({'kind':'checkpoint','label':'A-none-saved-result'})
assert sys.stdin.readline().strip() == 'ACK A-none-saved-result'
os._exit(137)
'''
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory) / 'run'
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('collect.py')),
                                     '--out', str(root), '--', sys.executable, '-c', producer],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 137, result.stderr)
            self.assertEqual(json.loads((root / 'A-none/results.jsonl').read_text()), {'id': 'saved'})
            status = json.loads((root / 'exit.json').read_text())
            self.assertEqual(status['saved_results'], 1)
            self.assertFalse(status['complete'])


if __name__ == '__main__':
    unittest.main()
