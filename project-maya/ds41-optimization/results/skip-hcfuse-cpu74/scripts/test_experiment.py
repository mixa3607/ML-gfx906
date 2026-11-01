"""CPU-only tests of the predeclared skip screening rule."""

import json
from pathlib import Path
import tempfile
import unittest

from experiment import REPO, select_skip


class ScreeningTests(unittest.TestCase):
    def arm(self, root, name, speed=1, decode=1, per_length=None, passes=None):
        path = root / name
        path.mkdir()
        keys = ('prefill_tokens_per_second', 'decode_tokens_per_second')
        pooled = dict(zip(keys, (200 * speed, 30 * decode)))
        by_pp = {str(pp): dict(pooled) for pp in (2048, 4096, 8192, 16384, 32768)}
        if per_length:
            by_pp['32768'][keys[0]] = 200 * per_length
        (path / 'summary.json').write_text(json.dumps({'pooled_measurement': pooled, 'by_pp': by_pp}))
        passes = passes or (speed, speed)
        rows = [{'phase': 'measurement', 'done': {'prompt_ms': 1000 / passes[i // 5]}} for i in range(10)]
        (path / 'results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        return path

    def decision(self, **kwargs):
        with tempfile.TemporaryDirectory(dir='/tmp/opencode') as tmp:
            root = Path(tmp)
            return select_skip(self.arm(root, 'control'), self.arm(root, 'candidate', **kwargs))

    def test_clear_gain(self):
        self.assertEqual(self.decision(speed=1.10)['selected_skip'], 1)

    def test_small_gain(self):
        self.assertEqual(self.decision(speed=1.04)['selected_skip'], 0)

    def test_decode_regression(self):
        self.assertEqual(self.decision(speed=1.10, decode=0.94)['selected_skip'], 0)

    def test_long_prompt_regression(self):
        self.assertEqual(self.decision(speed=1.10, per_length=0.94)['selected_skip'], 0)

    def test_inconsistent_passes(self):
        self.assertEqual(self.decision(speed=1.10, passes=(1.20, 0.99))['selected_skip'], 0)

    def test_repository_path(self):
        self.assertTrue((REPO / 'project-maya/benchmarking/run.py').is_file())


if __name__ == '__main__':
    unittest.main()
