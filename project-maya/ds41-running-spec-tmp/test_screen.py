import copy
import unittest

from screen import parse_done, validate
from summarize import compare_tokens, pooled


class ProtocolTests(unittest.TestCase):
    def row(self):
        state = {'memory.events': {'oom_kill': 0}, 'cpu.stat': {'nr_throttled': 0}}
        return {'done': parse_done('DONE 256 2048 1000.0 1000.0 length 0 0 0 10 20'),
                'tokens': list(range(256)), 'stats': [], 'before': copy.deepcopy(state),
                'after': copy.deepcopy(state)}

    def test_baseline_and_speculation(self):
        row = self.row()
        validate(row, False)
        row['done'].update(drafted=100, accepted=70)
        validate(row, True)
        with self.assertRaises(ValueError):
            validate(row, False)

    def test_reuse_and_short_eos(self):
        row = self.row()
        row['done']['reused'] = 1
        with self.assertRaises(ValueError):
            validate(row, True)
        row = self.row()
        row['done'].update(tg=100, finish='stop')
        row['tokens'] = row['tokens'][:100]
        with self.assertRaises(ValueError):
            validate(row, True)

    def test_oom_throttling_skips_and_invalid_timing(self):
        for field in ('memory.events', 'cpu.stat'):
            row = self.row()
            key = next(iter(row['after'][field]))
            row['after'][field][key] = 1
            with self.assertRaises(ValueError):
                validate(row, True)
        row = self.row()
        row['stats'] = [{'skipped': '1'}]
        with self.assertRaises(ValueError):
            validate(row, True)
        row = self.row()
        row['done']['decode_ms'] = float('nan')
        with self.assertRaises(ValueError):
            validate(row, True)

    def test_bad_done_format(self):
        with self.assertRaises(ValueError):
            parse_done('DONE 256')

    def test_pool_excludes_warmups(self):
        rows = []
        for i in range(6):
            row = self.row()
            for side in ('before', 'after'):
                row[side].update({'memory.current': str(100 * 2**30), 'memory.peak': str(110 * 2**30)})
            row.update(id=str(i), phase='warmup' if i < 3 else 'measurement', valid=True,
                       wall_s=2, token_delivery_s=[0, 1], native_tg_tok_s=255)
            if i < 3:
                row['done'].update(prompt_ms=100000, decode_ms=100000)
            rows.append(row)
        result = pooled(rows)
        self.assertEqual(result['native_decode_tok_s'], 255)
        self.assertEqual(result['pp_tok_s'], 2048)
        self.assertEqual(result['wall_s'], 6)
        self.assertEqual(result['max_observed_memory_gib'], 100)
        rows.pop()
        with self.assertRaises(ValueError):
            pooled(rows)

    def test_token_comparison(self):
        a = [{'id': 'x', 'tokens': [1, 2, 3]}]
        b = [{'id': 'x', 'tokens': [1, 4, 3]}]
        self.assertTrue(compare_tokens(a, a)[0]['identical'])
        self.assertEqual(compare_tokens(a, b)[0]['first_different_token_zero_based'], 1)


if __name__ == '__main__':
    unittest.main()
