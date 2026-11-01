"""CPU-only checks; never create pods or start an engine."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import compare
from summarize import summarize


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CASES = REPO / 'project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl'
spec = importlib.util.spec_from_file_location('cpu_launcher', HERE / 'scripts/run.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
launcher.CONFIG = launcher.BASELINE / 'maya-config.json'


class SummaryTests(unittest.TestCase):
    def test_selected_baseline_matches_cpu48(self):
        active = REPO / 'project-maya/ds41-optimization/base-params/maya-config.json'
        captured = HERE / 'cpu48/maya-config.json'
        self.assertEqual(json.loads(active.read_text()), json.loads(captured.read_text()))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp/opencode')
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.rows = [
            {'id': case['id'], 'phase': case['phase'], 'done': {
                'generated': 256, 'prompt_tokens': case['pp'],
                'prompt_ms': 5 * case['pp'], 'decode_ms': 12800,
                'finish': 'length', 'drafts_accepted': 64,
                'drafts_offered': 80, 'reused': 0,
            }} for case in map(json.loads, CASES.read_text().splitlines())
        ]
        self.metadata = {
            'runner_exit_code': 0, 'request_controls': {'temperature': 0, 'spec': 1},
            'effective_engine_env': {'STRATA_DS4_SLOT_KEEP': '0'},
            'engine_args': ['--cpu-threads', '56', '--tp', '4'],
        }
        (self.out / 'engine.log').write_text('')

    def result(self, cpu=56):
        (self.out / 'run-metadata.json').write_text(json.dumps(self.metadata))
        (self.out / 'results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
        return summarize(CASES, self.out, cpu)

    def test_cpu_config_changes_only_thread_count(self):
        original = json.loads(launcher.CONFIG.read_text())
        for cpu in (56, 48):
            candidate = launcher.cpu_config(cpu)
            index = candidate['args'].index('--cpu-threads') + 1
            self.assertEqual(candidate['args'][index], str(cpu))
            candidate['args'][index] = '74'
            self.assertEqual(candidate, original)
        with self.assertRaises(AssertionError):
            launcher.cpu_config(64)

    def test_both_candidates_and_pooling(self):
        for cpu in (56, 48):
            self.metadata['engine_args'][1] = str(cpu)
            summary = self.result(cpu)
            self.assertEqual(summary['warmup_requests'], 12)
            pooled = summary['pooled_measurement']
            self.assertEqual(pooled['requests'], 10)
            self.assertEqual(pooled['prompt_tokens'], 126976)
            self.assertEqual(pooled['generated'], 2560)
            self.assertEqual(pooled['prefill_tokens_per_second'], 200)
            self.assertEqual(pooled['decode_tokens_per_second'], 20)

    def test_reject_reuse(self):
        self.rows[0]['done']['reused'] = 1
        with self.assertRaises(AssertionError):
            self.result()

    def test_reject_slots(self):
        (self.out / 'engine.log').write_text('ds4 slots: save\n')
        with self.assertRaises(AssertionError):
            self.result()

    def test_reject_wrong_cpu(self):
        self.metadata['engine_args'][1] = '74'
        with self.assertRaises(AssertionError):
            self.result()

    def test_reject_tp2(self):
        self.metadata['engine_args'][-1] = '2'
        with self.assertRaises(AssertionError):
            self.result()

    def test_reject_disabled_spec(self):
        self.metadata['request_controls']['spec'] = 0
        with self.assertRaises(AssertionError):
            self.result()

    def test_reject_no_measured_offers(self):
        for row in self.rows:
            if row['phase'] == 'measurement':
                row['done']['drafts_accepted'] = row['done']['drafts_offered'] = 0
        with self.assertRaises(AssertionError):
            self.result()

    def test_reject_changed_schedule(self):
        self.rows[-1]['id'] = self.rows[0]['id']
        with self.assertRaises(AssertionError):
            self.result()


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp/opencode')
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        for name in ('pod.json', 'pack-metadata.json', 'expert-profile.seed.bin', 'patch-verification.json'):
            (self.out / name).write_bytes((launcher.BASELINE / name).read_bytes())
        (self.out / 'maya-config.json').write_text(json.dumps(launcher.cpu_config(56)))
        self.metadata = json.loads((launcher.BASELINE / 'run-metadata.json').read_text())
        args = self.metadata['engine_args']
        args[args.index('--cpu-threads') + 1] = '56'
        self.metadata['input_sha256']['config'] = launcher.sha(self.out / 'maya-config.json')
        log = (launcher.BASELINE / 'engine.log').read_text().replace('; 74 threads', '; 56 threads')
        (self.out / 'engine.log').write_text(log)

    def validate(self):
        (self.out / 'run-metadata.json').write_text(json.dumps(self.metadata))
        launcher.validate(self.out, 56)

    def test_matching_baseline(self):
        self.validate()

    def test_reject_environment_drift(self):
        self.metadata['effective_engine_env']['DS4_ENGRAM_CACHE_MB'] = '1024'
        with self.assertRaises(AssertionError):
            self.validate()

    def test_reject_seed_drift(self):
        (self.out / 'expert-profile.seed.bin').write_bytes(b'wrong seed')
        with self.assertRaises(AssertionError):
            self.validate()


class ComparisonTests(unittest.TestCase):
    def test_delta(self):
        self.assertAlmostEqual(compare.delta(110, 100), 10)
        self.assertAlmostEqual(compare.delta(90, 100), -10)

    def test_baseline_equal_candidates(self):
        with tempfile.TemporaryDirectory(dir='/tmp/opencode') as tmp:
            root = Path(tmp)
            for cpu in (74, 56, 48):
                directory = root / ('baseline' if cpu == 74 else f'cpu{cpu}')
                directory.mkdir()
                for name in ('summary.json', 'results.jsonl', 'host-exit.json', 'engine.log',
                             'gpu-before.txt', 'gpu-after-cleanup.txt', 'gpu-static.json'):
                    (directory / name).write_bytes((launcher.BASELINE / name).read_bytes())
                (directory / 'artifact-sha256.json').write_text(json.dumps({
                    p.name: launcher.sha(p) for p in directory.iterdir()
                }))
                (directory / 'source-state.json').write_text('{"script_sha256": {}}')
            recorded = json.loads((launcher.BASELINE / 'summary.json').read_text())
            with patch.multiple(compare, BASELINE=root / 'baseline', ROOT=root), \
                    patch.object(compare, 'validate'), patch.object(compare, 'summarize', return_value=recorded), \
                    contextlib.redirect_stdout(io.StringIO()):
                compare.main()
            result = json.loads((root / 'comparison.json').read_text())
            for cpu in ('56', '48'):
                for group in result['deltas_vs_cpu74'][cpu]['groups'].values():
                    self.assertEqual(group, {'prefill_percent': 0, 'decode_percent': 0})
                self.assertEqual(len(result['deltas_vs_cpu74'][cpu]['per_request']), 10)
            self.assertTrue((root / 'comparison.md').is_file())


if __name__ == '__main__':
    unittest.main()
