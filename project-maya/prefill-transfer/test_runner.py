import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from collect import destination
from run import parse_done, pooled


class RunnerTests(unittest.TestCase):
    def test_native_done(self):
        done = parse_done('DONE 256 2048 20000 8000 length 128 160 0 900 1000')
        self.assertEqual(done['pp'], 2048)
        self.assertEqual(done['accepted'], 128)

    def test_reject_changed_protocol(self):
        with self.assertRaises(ValueError):
            parse_done('DONE 256 2048')

    def test_pooled_not_arithmetic_mean(self):
        rows = [{'valid': True, 'wall_s': 10,
                 'done': {'pp': pp, 'tg': 256, 'prompt_ms': ms, 'decode_ms': 1000,
                          'accepted': 12, 'drafted': 16}}
                for pp, ms in ((2048, 1000), (8192, 8000))]
        result = pooled(rows)
        self.assertAlmostEqual(result['prefill_tok_s'], 10240 / 9)
        self.assertEqual(result['decode_tok_s'], 255)
        self.assertEqual(result['accepted'], 24)

    def test_reject_incomplete(self):
        for rows in ([], [{'valid': False}]):
            with self.assertRaises(ValueError):
                pooled(rows)

    def test_artifact_paths(self):
        root = Path('/tmp/example')
        self.assertEqual(destination(root, 'baseline/results.jsonl'), root / 'baseline/results.jsonl')
        for path in ('/etc/passwd', '../manifest.json', 'baseline/../../config.json',
                     'manifest.json', 'baseline/secret.txt'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                destination(root, path)

    def collector(self, finished, exit_code):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'result'
            manifest = json.dumps({'complete': finished, 'saved_results': 1})
            events = [
                {'kind': 'artifact', 'path': 'test/manifest.json', 'data': manifest, 'append': False},
                {'kind': 'checkpoint', 'label': 'test-case-result'}]
            code = ('import json,sys\n'
                    f'events={events!r}\n'
                    'for event in events:\n'
                    ' print("BENCH_EVENT " + json.dumps(event), flush=True)\n'
                    ' if event["kind"] == "checkpoint":\n'
                    '  assert sys.stdin.readline().strip() == "ACK " + event["label"]\n'
                    f'sys.exit({exit_code})\n')
            proc = subprocess.run([sys.executable, str(Path(__file__).with_name('collect.py')),
                                   '--out', str(out), '--', sys.executable, '-c', code],
                                  capture_output=True, text=True, timeout=15)
            result = json.loads((out / 'exit.json').read_text())
            self.assertTrue((out / 'test/manifest.json').is_file())
            return proc.returncode, result

    def test_durable_success(self):
        code, result = self.collector(True, 0)
        self.assertEqual(code, 0)
        self.assertTrue(result['complete'])

    def test_nonzero_preserves_evidence(self):
        code, result = self.collector(False, 137)
        self.assertNotEqual(code, 0)
        self.assertEqual(result['saved_results'], 1)
        self.assertFalse(result['complete'])

    def test_zero_exit_incomplete_is_failure(self):
        code, result = self.collector(False, 0)
        self.assertNotEqual(code, 0)
        self.assertFalse(result['complete'])


if __name__ == '__main__':
    unittest.main()
