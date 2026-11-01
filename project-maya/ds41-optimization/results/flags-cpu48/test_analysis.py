"""Synthetic CPU-only tests; never start engines or access Kubernetes."""

import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analysis
import compare
from compare import group_deltas, request_deltas


class ConfigurationTests(unittest.TestCase):
    def test_order_and_isolated_overrides(self):
        self.assertEqual(list(analysis.ARMS), ['control', 'skip', 'swizzle', 'hcfuse', 'routefuse'])
        baseline = analysis.read_json(analysis.ROOT / 'baseline-config.json')
        self.assertEqual(baseline, analysis.read_json(analysis.ACTIVE_CONFIG))
        self.assertEqual(baseline, analysis.read_json(analysis.REFERENCE / 'maya-config.json'))
        for arm, overrides in analysis.ARMS.items():
            config = analysis.config_for(arm)
            expected = copy.deepcopy(baseline)
            expected['env'].update(overrides)
            self.assertEqual(config, expected)
            self.assertLessEqual(len(overrides), 1)
            self.assertNotIn('DS4_ENGRAM_RAM', config['env'])

    def test_aliases_and_no_accumulation(self):
        base = {'MAYA_DS4_SLOT_KEEP': '0', 'STRATA_DS4_SLOT_KEEP': '0'}
        env = analysis.expected_env(base, 'hcfuse')
        self.assertEqual(env['MAYA_DS4_HC_FUSE'], '2')
        self.assertEqual(env['STRATA_DS4_HC_FUSE'], '2')
        self.assertEqual(analysis.expected_env(base, 'swizzle'), {**base, 'DS4_HIP_ATTN_SWIZZLE': '1'})
        self.assertEqual(base, {'MAYA_DS4_SLOT_KEEP': '0', 'STRATA_DS4_SLOT_KEEP': '0'})


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp/opencode')
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        for name in ('pod.json', 'pack-metadata.json', 'patch-verification.json',
                     'expert-profile.seed.bin', 'gpu-static.json', 'results.jsonl'):
            (self.out / name).write_bytes((analysis.REFERENCE / name).read_bytes())
        self.base = analysis.read_json(analysis.REFERENCE / 'run-metadata.json')
        self.metadata = copy.deepcopy(self.base)
        self.log = (analysis.REFERENCE / 'engine.log').read_text()

    def prepare(self, arm='control'):
        analysis.write_json(self.out / 'maya-config.json', analysis.config_for(arm))
        self.metadata['input_sha256']['config'] = analysis.sha(self.out / 'maya-config.json')
        self.metadata['effective_engine_env'] = analysis.expected_env(self.base['effective_engine_env'], arm)
        analysis.write_json(self.out / 'run-metadata.json', self.metadata)
        (self.out / 'engine.log').write_text(self.log)

    def test_control_and_nonfusion_arms(self):
        for arm in ('control', 'skip', 'swizzle'):
            self.prepare(arm)
            result = analysis.validate(self.out, arm)
            self.assertEqual(result['pooled_measurement']['requests'], 10)
            self.assertEqual(result['warmup_requests'], 12)

    def test_fusion_requires_native_checks_on_all_devices(self):
        for arm, label, setting in (('hcfuse', 'HC', 'HC'), ('routefuse', 'route', 'ROUTE')):
            self.prepare(arm)
            with self.assertRaises(AssertionError):
                analysis.validate(self.out, arm)
            checks = ''.join(f'ds4: CUDA{gpu} {label} fuse check: bit for bit (DS4_{setting}_FUSE=2)\n'
                             for gpu in range(4))
            (self.out / 'engine.log').write_text(self.log + checks)
            analysis.validate(self.out, arm)

    def test_reject_unrelated_environment_change(self):
        self.prepare('skip')
        self.metadata['effective_engine_env']['DS4_ENGRAM_CACHE_MB'] = '1024'
        analysis.write_json(self.out / 'run-metadata.json', self.metadata)
        with self.assertRaises(AssertionError):
            analysis.validate(self.out, 'skip')

    def test_reject_wrong_cpu(self):
        self.prepare()
        args = self.metadata['engine_args']
        args[args.index('--cpu-threads') + 1] = '74'
        analysis.write_json(self.out / 'run-metadata.json', self.metadata)
        with self.assertRaises(AssertionError):
            analysis.validate(self.out, 'control')

    def test_reject_slots(self):
        self.prepare()
        (self.out / 'engine.log').write_text(self.log + 'ds4 slots: saved\n')
        with self.assertRaises(AssertionError):
            analysis.validate(self.out, 'control')

    def test_reject_kv_reuse(self):
        self.prepare()
        rows = [json.loads(line) for line in (self.out / 'results.jsonl').read_text().splitlines()]
        rows[0]['done']['reused'] = 1
        (self.out / 'results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        with self.assertRaises(AssertionError):
            analysis.validate(self.out, 'control')

    def test_reject_seed_drift(self):
        self.prepare()
        (self.out / 'expert-profile.seed.bin').write_bytes(b'wrong seed')
        with self.assertRaises(AssertionError):
            analysis.validate(self.out, 'control')


class ComparisonTests(unittest.TestCase):
    def test_complete_report_on_synthetic_identical_runs(self):
        with tempfile.TemporaryDirectory(dir='/tmp/opencode') as tmp:
            root = Path(tmp)
            for arm in analysis.ARMS:
                out = root / arm
                out.mkdir()
                for name in ('pod.json', 'pack-metadata.json', 'patch-verification.json',
                             'expert-profile.seed.bin', 'gpu-static.json', 'results.jsonl',
                             'gpu-before.txt', 'gpu-after-cleanup.txt', 'host-exit.json'):
                    (out / name).write_bytes((analysis.REFERENCE / name).read_bytes())
                analysis.write_json(out / 'maya-config.json', analysis.config_for(arm))
                metadata = analysis.read_json(analysis.REFERENCE / 'run-metadata.json')
                metadata['input_sha256']['config'] = analysis.sha(out / 'maya-config.json')
                metadata['effective_engine_env'] = analysis.expected_env(metadata['effective_engine_env'], arm)
                analysis.write_json(out / 'run-metadata.json', metadata)
                log = (analysis.REFERENCE / 'engine.log').read_text()
                if arm in ('hcfuse', 'routefuse'):
                    label, setting = ('HC', 'HC') if arm == 'hcfuse' else ('route', 'ROUTE')
                    log += ''.join(f'ds4: CUDA{gpu} {label} fuse check: bit for bit (DS4_{setting}_FUSE=2)\n'
                                   for gpu in range(4))
                (out / 'engine.log').write_text(log)
                analysis.write_json(out / 'summary.json', analysis.validate(out, arm))
                analysis.write_json(out / 'source-state.json', {'script_sha256': {}})
                analysis.write_json(out / 'artifact-sha256.json', {
                    p.name: analysis.sha(p) for p in out.iterdir()
                })
            with patch.object(compare, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                compare.main()
            report = analysis.read_json(root / 'comparison.json')
            self.assertEqual(list(report['summaries']), list(analysis.ARMS))
            for data in report['deltas_vs_control'].values():
                self.assertEqual(len(data['per_request']), 10)
                self.assertEqual(data['groups']['pooled'], {'prefill_percent': 0, 'decode_percent': 0})
            self.assertTrue((root / 'comparison.md').is_file())

    def test_zero_deltas_and_measurement_schedule(self):
        summary = analysis.read_json(analysis.REFERENCE / 'summary.json')
        diffs = group_deltas(summary, summary)
        self.assertEqual(len(diffs), 6)
        for group in diffs.values():
            self.assertEqual(group, {'prefill_percent': 0, 'decode_percent': 0})
        rows = [r for r in map(json.loads, (analysis.REFERENCE / 'results.jsonl').read_text().splitlines())
                if r['phase'] == 'measurement']
        self.assertEqual(len(request_deltas(rows, rows)), 10)
        changed = copy.deepcopy(rows)
        changed[0]['id'] = 'wrong id'
        with self.assertRaises(AssertionError):
            request_deltas(changed, rows)

    def test_speedup_and_slowdown_have_no_verdict(self):
        baseline = analysis.read_json(analysis.REFERENCE / 'summary.json')
        candidate = copy.deepcopy(baseline)
        candidate['pooled_measurement']['prefill_tokens_per_second'] *= 1.1
        candidate['pooled_measurement']['decode_tokens_per_second'] *= 0.9
        diffs = group_deltas(candidate, baseline)['pooled']
        self.assertAlmostEqual(diffs['prefill_percent'], 10)
        self.assertAlmostEqual(diffs['decode_percent'], -10)
        self.assertEqual(set(diffs), {'prefill_percent', 'decode_percent'})


if __name__ == '__main__':
    unittest.main()
