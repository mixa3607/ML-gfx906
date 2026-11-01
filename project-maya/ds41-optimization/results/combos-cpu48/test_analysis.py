"""Synthetic CPU-only validation and report tests; no engines or Kubernetes."""

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analysis
import compare


def prepare(out, arm):
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
    for flag, source in (('MAYA_DS4_HC_FUSE', 'hcfuse'), ('MAYA_DS4_ROUTE_FUSE', 'routefuse')):
        if flag in analysis.ARMS[arm]:
            log += '\n'.join(line for line in (analysis.SINGLES / source / 'engine.log').read_text().splitlines()
                             if 'fuse check' in line) + '\n'
    (out / 'engine.log').write_text(log)


class ConfigurationTests(unittest.TestCase):
    def test_pairs_partition_four_flags(self):
        pairs = [analysis.ARMS[name] for name in ('skip-swizzle', 'hc-route')]
        self.assertEqual(list(analysis.ARMS), ['skip-swizzle', 'hc-route', 'all'])
        self.assertEqual([len(pair) for pair in pairs], [2, 2])
        self.assertFalse(set(pairs[0]) & set(pairs[1]))
        self.assertEqual(pairs[0] | pairs[1], analysis.ARMS['all'])
        baseline = analysis.read_json(analysis.BASE_CONFIG)
        self.assertEqual(baseline, analysis.read_json(analysis.REFERENCE / 'maya-config.json'))
        for arm in analysis.ARMS:
            config = analysis.config_for(arm)
            expected = copy.deepcopy(baseline)
            expected['env'].update(analysis.ARMS[arm])
            self.assertEqual(config, expected)

    def test_final_baseline_matches_measured_four_flags(self):
        active = analysis.read_json(analysis.ACTIVE_CONFIG)
        self.assertEqual(active, analysis.config_for('all'))
        self.assertEqual(active, analysis.read_json(analysis.ROOT / 'all/maya-config.json'))
        self.assertEqual(active['args'][active['args'].index('--cpu-threads') + 1], '48')
        self.assertEqual(active['args'][active['args'].index('--tp') + 1], '4')
        self.assertEqual(active['env']['DS4_ENGRAM_CACHE_MB'], '256')
        self.assertEqual(active['env']['MAYA_DS4_SLOT_KEEP'], '0')
        for flag in ('MAYA_DS4_DRAFT_COST', 'MAYA_DS4_DECODE_TRIM',
                     'MAYA_DS4_HC_MIX_SPLIT', 'MAYA_DS4_MARKOV_Q8'):
            self.assertNotIn(flag, active['env'])

    def test_both_fusion_aliases(self):
        env = analysis.expected_env({}, 'all')
        for flag in ('HC', 'ROUTE'):
            self.assertEqual(env[f'MAYA_DS4_{flag}_FUSE'], '2')
            self.assertEqual(env[f'STRATA_DS4_{flag}_FUSE'], '2')
        self.assertEqual(len(env), 6)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp/opencode')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'all'
        prepare(self.out, 'all')

    def test_valid_all_and_warmup_exclusion(self):
        result = analysis.validate(self.out, 'all')
        self.assertEqual(result['warmup_requests'], 12)
        self.assertEqual(result['pooled_measurement']['requests'], 10)
        self.assertEqual(result['pooled_measurement']['prompt_tokens'], 126976)

    def test_each_combination(self):
        for arm in ('skip-swizzle', 'hc-route'):
            out = self.root / arm
            prepare(out, arm)
            analysis.validate(out, arm)

    def test_missing_one_fusion_check(self):
        log = (self.out / 'engine.log').read_text()
        (self.out / 'engine.log').write_text('\n'.join(line for line in log.splitlines()
            if 'CUDA3 route fuse check (16 rows)' not in line) + '\n')
        with self.assertRaises(AssertionError):
            analysis.validate(self.out, 'all')

    def test_reject_missing_flag(self):
        metadata = analysis.read_json(self.out / 'run-metadata.json')
        del metadata['effective_engine_env']['DS4_HIP_ATTN_SWIZZLE']
        analysis.write_json(self.out / 'run-metadata.json', metadata)
        with self.assertRaises(AssertionError):
            analysis.validate(self.out, 'all')

    def test_reject_unrelated_env_change(self):
        metadata = analysis.read_json(self.out / 'run-metadata.json')
        metadata['effective_engine_env']['DS4_ENGRAM_RAM'] = '1'
        analysis.write_json(self.out / 'run-metadata.json', metadata)
        with self.assertRaises(AssertionError):
            analysis.validate(self.out, 'all')

    def test_reject_reuse(self):
        rows = [json.loads(line) for line in (self.out / 'results.jsonl').read_text().splitlines()]
        rows[0]['done']['reused'] = 1
        (self.out / 'results.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaises(AssertionError):
            analysis.validate(self.out, 'all')


class ComparisonTests(unittest.TestCase):
    def test_report_retains_old_control_and_single_comparisons(self):
        with tempfile.TemporaryDirectory(dir='/tmp/opencode') as tmp:
            root = Path(tmp)
            for arm in analysis.ARMS:
                out = root / arm
                prepare(out, arm)
                analysis.write_json(out / 'summary.json', analysis.validate(out, arm))
                analysis.write_json(out / 'source-state.json', {'script_sha256': {}})
                analysis.write_json(out / 'artifact-sha256.json', {
                    p.name: analysis.sha(p) for p in out.iterdir()
                })
            with patch.object(compare, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                compare.main()
            result = analysis.read_json(root / 'comparison.json')
            self.assertFalse(result['fresh_control'])
            self.assertEqual(len(result['summaries']), 8)
            for data in result['deltas_vs_previous_control'].values():
                self.assertEqual(data['groups']['pooled'], {'prefill_percent': 0, 'decode_percent': 0})
                self.assertEqual(len(data['per_request']), 10)
            self.assertEqual(set(result['deltas_vs_single_flags']['all']), {'skip', 'swizzle', 'hcfuse', 'routefuse'})
            self.assertEqual(set(result['all_vs_pairs']), {'skip-swizzle', 'hc-route'})
            self.assertTrue((root / 'comparison.md').is_file())


if __name__ == '__main__':
    unittest.main()
