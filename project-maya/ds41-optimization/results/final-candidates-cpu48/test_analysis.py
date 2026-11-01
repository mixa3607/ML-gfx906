"""Synthetic CPU-only candidate, native-check coverage and best-of-two tests."""

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
    for source in (analysis.SINGLES / 'hcfuse', analysis.SINGLES / 'routefuse', analysis.TOP5 / 'decode-trim'):
        log += '\n'.join(line for line in (source / 'engine.log').read_text().splitlines()
                         if 'fuse check' in line or 'DS4_DECODE_TRIM check:' in line or 'DS4_DECODE_TRIM=15:' in line) + '\n'
    log += 'maya-ds4: DS4_DRAFT_COST: DSpark enabled\n'
    log += 'maya ds4 serve: draft cost (DS4_DRAFT_COST)\n' * 22
    if arm == 'six-hc-mix':
        log += 'ds4: enabled (DS4_HC_MIX_SPLIT=1)\n'
    (out / 'engine.log').write_text(log)
    before = {'memory_max': str(220 * 1024 ** 3), 'memory_current': 1024 ** 3,
              'memory_peak': 1024 ** 3, 'memory_events': {'oom': 0, 'oom_kill': 0}}
    after = {**before, 'memory_peak': 219 * 1024 ** 3}
    analysis.write_json(out / 'memory.json', {'before': before, 'after': after})


class ConfigurationTests(unittest.TestCase):
    def test_exact_two_and_single_extra_flag(self):
        self.assertEqual(list(analysis.ARMS), ['six', 'six-hc-mix'])
        self.assertEqual(analysis.ARMS['six'], {
            'DS4_SKIP_UNPICKED': '1', 'DS4_HIP_ATTN_SWIZZLE': '1',
            'MAYA_DS4_HC_FUSE': '2', 'MAYA_DS4_ROUTE_FUSE': '2',
            'MAYA_DS4_DRAFT_COST': '1', 'MAYA_DS4_DECODE_TRIM': '15',
        })
        self.assertEqual(analysis.ARMS['six-hc-mix'], {**analysis.ARMS['six'], 'MAYA_DS4_HC_MIX_SPLIT': '1'})
        baseline = analysis.read_json(analysis.BASE_CONFIG)
        self.assertEqual(baseline, analysis.read_json(analysis.ACTIVE_CONFIG))
        for arm in analysis.ARMS:
            config = analysis.config_for(arm)
            expected = copy.deepcopy(baseline)
            expected['env'].update(analysis.ARMS[arm])
            self.assertEqual(config, expected)
            self.assertEqual(config['env']['DS4_ENGRAM_CACHE_MB'], '256')
            self.assertNotIn('MAYA_DS4_MARKOV_Q8', config['env'])


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp/opencode')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_both_candidates(self):
        for arm in analysis.ARMS:
            out = self.root / arm
            prepare(out, arm)
            summary = analysis.validate(out, arm)
            self.assertEqual(summary['warmup_requests'], 12)
            self.assertEqual(summary['pooled_measurement']['requests'], 10)

    def test_missing_fusion_or_trim_check(self):
        for index, marker in enumerate(('CUDA3 route fuse check (16 rows)', 'CUDA2 DS4_DECODE_TRIM check: copy_regions')):
            out = self.root / str(index)
            prepare(out, 'six')
            log = (out / 'engine.log').read_text()
            (out / 'engine.log').write_text('\n'.join(line for line in log.splitlines() if marker not in line) + '\n')
            with self.assertRaises(AssertionError):
                analysis.validate(out, 'six')

    def test_extra_markov_flag_rejected(self):
        out = self.root / 'six'
        prepare(out, 'six')
        metadata = analysis.read_json(out / 'run-metadata.json')
        metadata['effective_engine_env']['MAYA_DS4_MARKOV_Q8'] = '1'
        analysis.write_json(out / 'run-metadata.json', metadata)
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'six')

    def test_oom_rejected(self):
        out = self.root / 'six'
        prepare(out, 'six')
        memory = analysis.read_json(out / 'memory.json')
        memory['after']['memory_events'] = {'oom': 1, 'oom_kill': 1}
        analysis.write_json(out / 'memory.json', memory)
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'six')

    def test_reuse_rejected(self):
        out = self.root / 'six'
        prepare(out, 'six')
        rows = [json.loads(line) for line in (out / 'results.jsonl').read_text().splitlines()]
        rows[0]['done']['reused'] = 1
        (out / 'results.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'six')


class ComparisonTests(unittest.TestCase):
    def test_best_of_two_independent_maxima_and_no_warmups(self):
        rows = [json.loads(line) for line in (analysis.REFERENCE / 'results.jsonl').read_text().splitlines()]
        measured = [row for row in rows if row['phase'] == 'measurement' and row['done']['prompt_tokens'] == 2048]
        measured[0]['done'].update(prompt_ms=1000, decode_ms=2000)
        measured[1]['done'].update(prompt_ms=2000, decode_ms=1000)
        rows[0]['done'].update(prompt_ms=1, decode_ms=1)
        best = analysis.best_of_two(rows)['2048']
        self.assertEqual(best['prefill'], {'tokens_per_second': 2048, 'case_id': measured[0]['id']})
        self.assertEqual(best['decode'], {'tokens_per_second': 256, 'case_id': measured[1]['id']})

    def test_best_of_two_requires_two_cases(self):
        rows = [json.loads(line) for line in (analysis.REFERENCE / 'results.jsonl').read_text().splitlines()]
        with self.assertRaises(AssertionError):
            analysis.best_of_two(rows[:-1])

    def test_complete_report(self):
        with tempfile.TemporaryDirectory(dir='/tmp/opencode') as tmp:
            root = Path(tmp)
            for arm in analysis.ARMS:
                out = root / arm
                prepare(out, arm)
                analysis.write_json(out / 'summary.json', analysis.validate(out, arm))
                analysis.write_json(out / 'source-state.json', {'script_sha256': {}})
                analysis.write_json(out / 'artifact-sha256.json', {p.name: analysis.sha(p) for p in out.iterdir()})
            with patch.object(compare, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                compare.main()
            report = analysis.read_json(root / 'comparison.json')
            self.assertFalse(report['fresh_control'])
            self.assertEqual(len(report['summaries']), 4)
            self.assertEqual(report['hc_mix_vs_six']['groups']['pooled'], {'prefill_percent': 0, 'decode_percent': 0})
            self.assertEqual(len(report['hc_mix_vs_six']['per_request']), 10)
            self.assertIn('case_id', report['best_of_two']['six']['32768']['prefill'])
            self.assertTrue((root / 'comparison.md').is_file())


if __name__ == '__main__':
    unittest.main()
