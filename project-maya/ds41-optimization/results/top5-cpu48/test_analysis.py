"""Synthetic CPU-only checks for the five candidates and memory accounting."""

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
from memory_probe import GIB, cache_budget


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
    if arm == 'draft-cost':
        log += 'maya-ds4: DS4_DRAFT_COST: DSpark enabled\n'
        log += 'maya ds4 serve: draft cost (DS4_DRAFT_COST)\n' * 22
    elif arm == 'decode-trim':
        log += 'ds4: DS4_DECODE_TRIM=15: enabled\n'
        for gpu in range(4):
            log += f"ds4: CUDA{gpu} DS4_DECODE_TRIM check: 10 runs old path's bit for bit, every guard intact\n"
            log += f"ds4: CUDA{gpu} DS4_DECODE_TRIM check: copy_regions runtime copies' bytes, every guard intact\n"
        log += "ds4: DS4_DECODE_TRIM check: the drafter's hand-offs by xfer, 12 device pairs every row as put\n"
    elif arm == 'hc-mix':
        log += 'ds4: enabled (DS4_HC_MIX_SPLIT=1)\n'
    elif arm == 'markov-q8':
        log += "ds4: the drafter's markov head as Q8_0 blocks\n"
    (out / 'engine.log').write_text(log)
    before = {'memory_max': str(220 * GIB), 'memory_current': GIB,
              'memory_peak': GIB, 'host_mem_available': 240 * GIB,
              'memory_events': {'oom': 0, 'oom_kill': 0}}
    after = {**before, 'memory_peak': 215 * GIB}
    memory = {'before': before, 'after': after}
    if arm == 'engram-cache':
        memory['cache_budget'] = cache_budget(before)
    analysis.write_json(out / 'memory.json', memory)


class ConfigurationTests(unittest.TestCase):
    def test_exact_five_variants_and_baseline(self):
        self.assertEqual(list(analysis.ARMS), ['draft-cost', 'decode-trim', 'hc-mix', 'engram-cache', 'markov-q8'])
        baseline = analysis.read_json(analysis.BASE_CONFIG)
        self.assertEqual(baseline, analysis.read_json(analysis.REFERENCE / 'maya-config.json'))
        for arm, overrides in analysis.ARMS.items():
            self.assertEqual(len(overrides), 1)
            expected = copy.deepcopy(baseline)
            expected['env'].update(overrides)
            self.assertEqual(analysis.config_for(arm), expected)
            self.assertNotIn('MAYA_DS4_HC_FUSE', expected['env'])
            self.assertNotIn('DS4_SKIP_UNPICKED', expected['env'])

    def test_memory_budget(self):
        ample = {'memory_max': str(220 * GIB), 'memory_current': GIB, 'host_mem_available': 240 * GIB}
        self.assertTrue(cache_budget(ample)['allowed'])
        self.assertFalse(cache_budget({**ample, 'host_mem_available': 200 * GIB})['allowed'])
        self.assertFalse(cache_budget({**ample, 'memory_current': 30 * GIB})['allowed'])


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp/opencode')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_all_five_and_warmup_exclusion(self):
        for arm in analysis.ARMS:
            out = self.root / arm
            prepare(out, arm)
            result = analysis.validate(out, arm)
            self.assertEqual(result['warmup_requests'], 12)
            self.assertEqual(result['pooled_measurement']['requests'], 10)

    def test_decode_trim_missing_device(self):
        out = self.root / 'decode-trim'
        prepare(out, 'decode-trim')
        text = (out / 'engine.log').read_text()
        (out / 'engine.log').write_text('\n'.join(line for line in text.splitlines()
            if 'CUDA3 DS4_DECODE_TRIM check: copy_regions' not in line) + '\n')
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'decode-trim')

    def test_cache_preserves_expert_placement(self):
        out = self.root / 'engram-cache'
        prepare(out, 'engram-cache')
        text = (out / 'engine.log').read_text().replace('10647 of the CPU lane\'s 10647', '10646 of the CPU lane\'s 10647')
        (out / 'engine.log').write_text(text)
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'engram-cache')

    def test_reject_oom_event(self):
        out = self.root / 'markov-q8'
        prepare(out, 'markov-q8')
        memory = analysis.read_json(out / 'memory.json')
        memory['after']['memory_events'] = {'oom': 1, 'oom_kill': 1}
        analysis.write_json(out / 'memory.json', memory)
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'markov-q8')

    def test_reject_unrelated_environment(self):
        out = self.root / 'draft-cost'
        prepare(out, 'draft-cost')
        metadata = analysis.read_json(out / 'run-metadata.json')
        metadata['effective_engine_env']['DS4_ENGRAM_RAM'] = '1'
        analysis.write_json(out / 'run-metadata.json', metadata)
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'draft-cost')

    def test_reject_kv_reuse(self):
        out = self.root / 'hc-mix'
        prepare(out, 'hc-mix')
        rows = [json.loads(line) for line in (out / 'results.jsonl').read_text().splitlines()]
        rows[0]['done']['reused'] = 1
        (out / 'results.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'hc-mix')


class ComparisonTests(unittest.TestCase):
    def test_complete_report_keeps_saved_control_and_memory(self):
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
            self.assertIsNone(report['memory']['control'])
            self.assertEqual(len(report['summaries']), 6)
            for data in report['deltas_vs_previous_control'].values():
                self.assertEqual(data['groups']['pooled'], {'prefill_percent': 0, 'decode_percent': 0})
                self.assertEqual(len(data['per_request']), 10)
            self.assertTrue((root / 'comparison.md').is_file())


if __name__ == '__main__':
    unittest.main()
