import copy
import json
from pathlib import Path
import unittest

from bench import parse_done, validate
from summarize import session


class BenchTests(unittest.TestCase):
    def row(self):
        snapshot = {'memory.events': 'oom_kill 0', 'cpu.stat': 'nr_throttled 0'}
        return {'done': parse_done('DONE 256 4096 40000 8000 length 30 60 0 100 200'),
                'tokens': [2] * 256, 'stats': [], 'before': snapshot, 'after': copy.deepcopy(snapshot)}

    def test_good_sample(self):
        validate(self.row(), 4096)

    def test_eos_is_retained(self):
        row = self.row()
        row['done'].update(tg=1, finish='stop', decode_ms=0)
        row['tokens'] = [1]
        validate(row, 4096)

    def test_reject_reuse(self):
        row = self.row()
        row['done']['reused'] = 1
        with self.assertRaisesRegex(ValueError, 'reuse'):
            validate(row, 4096)

    def test_reject_oom_throttle_and_skip(self):
        for changed in ('oom', 'throttle', 'skip'):
            with self.subTest(changed=changed):
                row = self.row()
                if changed == 'oom':
                    row['after']['memory.events'] = 'oom_kill 1'
                elif changed == 'throttle':
                    row['after']['cpu.stat'] = 'nr_throttled 1'
                else:
                    row['stats'] = [{'skipped': '1'}]
                with self.assertRaises(ValueError):
                    validate(row, 4096)

    def test_bad_done(self):
        with self.assertRaises(ValueError):
            parse_done('DONE 256')

    def test_frozen_order_and_unchanged_inputs(self):
        root = Path(__file__).resolve().parent
        current = [json.loads(s) for s in (root / 'cases.jsonl').read_text().splitlines()]
        self.assertEqual([c['ctx'] for c in current], [2048] * 12 + [4096, 8192, 16384] * 2 + [0, 0])
        original = [json.loads(s) for s in (root / 'attempt1/cases.jsonl').read_text().splitlines()]
        self.assertEqual({c['id']: c['ids'] for c in current}, {c['id']: c['ids'] for c in original})

    def test_incomplete_zero_context_not_scored(self):
        summary, rows = session(Path(__file__).resolve().parent / 'A-baseline')
        self.assertTrue(summary['valid_warmup'])
        self.assertEqual(len(rows), 20)
        self.assertFalse(summary['by_context']['0']['valid'])
        self.assertIsNone(summary['by_context']['0']['metrics'])
        for ctx in ('4096', '8192', '16384'):
            self.assertTrue(summary['by_context'][ctx]['valid'])


if __name__ == '__main__':
    unittest.main()
