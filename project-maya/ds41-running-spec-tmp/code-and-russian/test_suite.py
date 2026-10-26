import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import bench
import build_cases
from collect_suite import destination


def row(pp=2048, tg=256):
    state = {'memory.events': {'oom_kill': 0}, 'cpu.stat': {'nr_throttled': 0}}
    return {'done': {'pp': pp, 'tg': tg, 'reused': 0, 'accepted': 100, 'drafted': 120,
                     'prompt_ms': 1000, 'decode_ms': 1000, 'hits': 800, 'lookups': 1000},
            'tokens': list(range(tg)), 'before': copy.deepcopy(state), 'after': copy.deepcopy(state),
            'stats': [], 'valid': tg == 256, 'wall_s': 2, 'ttft_s': 1}


class SuiteTests(unittest.TestCase):
    def test_pp2k_4k_8k_and_validation_errors(self):
        for pp in (2048, 4096, 8192):
            bench.validate(row(pp), pp)
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            bench.validate(row(4096), 8192)
        for field, subfield in (('memory.events', 'oom_kill'), ('cpu.stat', 'nr_throttled')):
            r = row()
            r['after'][field][subfield] = 1
            with self.assertRaises(ValueError):
                bench.validate(r, 2048)
        r = row()
        r['done']['reused'] = 1
        with self.assertRaises(ValueError):
            bench.validate(r, 2048)

    def test_native_pp8k_and_short_eos_preserved(self):
        engine = bench.BenchEngine.__new__(bench.BenchEngine)
        engine.proc = type('Process', (), {'pid': 42, 'stdin': io.BytesIO()})()
        lines = iter(['T 123', 'DONE 1 8192 1000 1000 stop 0 0 0 0 0'])
        engine.line = lambda deadline: next(lines)
        state = row()['before']
        case = {'id': 'short', 'phase': 'measurement', 'lead_title': 'test', 'ids': [1] * 8192}
        with patch.object(bench, 'snapshot', return_value=state):
            result = engine.request(case)
        self.assertEqual(result['done']['pp'], 8192)
        self.assertEqual(result['done']['tg'], 1)
        self.assertFalse(result['valid'])
        self.assertIn('Natural EOS', result['error'])
        self.assertTrue(engine.proc.stdin.getvalue().startswith(
            b'GEN 256 temperature=0 seed=1 spec=1 dspark_conf=0.5 dspark_cum=0.5 '))

    def test_pooling_and_expert_counters(self):
        rows = [row(2048), row(8192)]
        rows[1]['done']['decode_ms'] = 2000
        result = bench.pooled(rows)
        self.assertEqual(result['decode_tok_s'], 510 / 3)
        self.assertEqual(result['prefill_tok_s'], 10240 / 2)
        self.assertEqual(result['expert_hit_ratio'], 0.8)
        self.assertEqual(result['acceptance'], 100 / 120)
        rows[0]['valid'] = False
        with self.assertRaises(ValueError):
            bench.pooled(rows)

    def test_reuse_failure_returns_finished_row_for_durable_export(self):
        engine = bench.BenchEngine.__new__(bench.BenchEngine)
        engine.proc = type('Process', (), {'pid': 42, 'stdin': io.BytesIO()})()
        lines = iter(['T 123'] * 256 + ['DONE 256 2048 1000 1000 length 1 1 2047 10 20'])
        engine.line = lambda deadline: next(lines)
        with patch.object(bench, 'snapshot', return_value=row()['before']):
            result = engine.request({'id': 'reuse', 'phase': 'warmup', 'lead_title': 'x', 'ids': [1] * 2048})
        self.assertTrue(result['fatal_validation_error'])
        self.assertFalse(result['valid'])
        self.assertEqual(result['done']['reused'], 2047)
        self.assertEqual(len(result['tokens']), 256)

    def test_code_nonces_and_distinct_russian_inputs(self):
        cases = [{'phase': 'warmup' if i < 12 else 'measurement', 'ids': [i] + [1] * 2047} for i in range(24)]
        bench.case_check(cases, 'code-cases-nonce.jsonl')
        cases[-1]['ids'] = cases[-2]['ids']
        with self.assertRaises(ValueError):
            bench.case_check(cases, 'code-cases-nonce.jsonl')
        prose = [{'phase': 'warmup' if i < 12 else 'measurement', 'ids': [i] * pp}
                 for i, pp in enumerate([2048] * 12 + [2048, 4096, 8192] * 2)]
        bench.case_check(prose, 'russian-cases.jsonl')
        prose[-1]['ids'] = prose[-4]['ids']
        with self.assertRaises(ValueError):
            bench.case_check(prose, 'russian-cases.jsonl')

    def test_ts_fixture_and_runtime_match_manifest(self):
        source = build_cases.ts_source()
        self.assertEqual(source.count('export const entry'), 200)
        self.assertIn('next 128 exports', source)
        import yaml
        path = Path(__file__).parent
        cfg = json.loads((path / 'runtime.json').read_text())
        manifest = next(yaml.safe_load_all((path.parents[1] / 'ds41-running/dspark.yaml').read_text()))
        self.assertEqual(cfg, json.loads(manifest['data']['maya-ds4-hip.json']))

    def test_all_three_sessions_in_order_even_after_short_eos(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root = Path(tmp)
            inputs = root / 'inputs'
            inputs.mkdir()
            (inputs / 'runtime.json').write_text('{}')
            (inputs / 'cases-nonce.manifest.json').write_text('{"files":{}}')
            for file in ('bench.py',):
                (inputs / file).write_text('source')
            for file in ('screen.py', 'stream.py'):
                (root / file).write_text('source')
            records = [{'name': name, 'saved_results': count, 'complete': name != 'code-1',
                        'stage': 'complete'} for name, _, count in bench.SESSIONS]
            with patch.object(bench, 'ROOT', root), patch.object(bench, 'INPUT', inputs), \
                    patch.object(bench, 'run_session', side_effect=records) as run, \
                    patch.object(bench, 'checkpoint'), patch('stream.artifact'), \
                    patch.dict('os.environ', {'BENCH_STREAM': '1'}):
                with self.assertRaises(SystemExit) as exit:
                    bench.main()
                self.assertEqual(exit.exception.code, 2)
                self.assertEqual([c.args[1] for c in run.call_args_list], ['code-1', 'code-2', 'russian'])
                result = json.loads((root / 'summary.json').read_text())
                self.assertEqual(result['saved_results'], 66)
                self.assertFalse(result['complete'])

    def test_collector_allowlist_and_exit137_durability(self):
        for name in ('/etc/passwd', '../escape', 'code-1/other', 'other/results.jsonl'):
            with self.assertRaises(ValueError):
                destination(Path('/unused'), name)
        producer = '''
import json, os, sys
def emit(r): print('SCREEN_EVENT ' + json.dumps(r), flush=True)
emit({'kind':'artifact','path':'code-1/results.jsonl','data':'{"valid":true}\\n','append':True})
emit({'kind':'checkpoint','label':'saved-result'})
assert sys.stdin.readline().strip() == 'ACK saved-result'
os._exit(137)
'''
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root = Path(tmp) / 'run'
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('collect_suite.py')),
                                     '--out', str(root), '--', sys.executable, '-c', producer],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 137, result.stderr)
            self.assertTrue(json.loads((root / 'code-1/results.jsonl').read_text())['valid'])
            self.assertEqual(json.loads((root / 'exit.json').read_text())['saved_results'], 1)


if __name__ == '__main__':
    unittest.main()
