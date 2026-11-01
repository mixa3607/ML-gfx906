"""CPU-only synthetic checks; never start an engine or call Kubernetes."""

import contextlib
import copy
import io
import json
from pathlib import Path
import re
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
    metadata['engine_args'] = analysis.replace_args(metadata['engine_args'], analysis.ARMS[arm]['args'])
    analysis.write_json(out / 'run-metadata.json', metadata)
    log = (analysis.REFERENCE / 'engine.log').read_text()
    if arm == 'tp2':
        log = log.replace('tensor parallel 4', 'tensor parallel 2').replace('576 to 576', '1152 to 1152')
        log = re.sub(r'ds4: DS4_DRAFT_DEV[^\n]*', '\n'.join(
            f'ds4: DS4_DRAFT_GPU block {block} on CUDA{block + 1} (target group {0 if block == 0 else 1})'
            for block in range(3)), log)

        def layout(match):
            gpu = int(match[1])
            first, last = (0, 18) if gpu < 2 else (19, 39)
            if gpu > 0:
                last = 39 + gpu
            return f'ds4: CUDA{gpu} layers [{first}, {last}] (tensor parallel 2, part {gpu % 2})'

        log = re.sub(r'ds4: CUDA(\d+) layers \[\d+, \d+\] \(tensor parallel 2, part \d+\)', layout, log)
    else:
        log = log.replace('prompts in chunks of 4096)', 'prompts in chunks of 2048)')
    (out / 'engine.log').write_text(log)
    before = {'memory_max': metadata['cgroup_memory_max'], 'memory_current': 1024 ** 3,
              'memory_peak': 1024 ** 3, 'memory_events': {'max': 0, 'oom': 0, 'oom_kill': 0}}
    analysis.write_json(out / 'memory.json', {'before': before,
                                             'after': {**before, 'memory_peak': 219 * 1024 ** 3}})


class ConfigurationTests(unittest.TestCase):
    def test_exact_independent_variants_and_unchanged_final(self):
        self.assertEqual(list(analysis.ARMS), ['tp2', 'chunk2048'])
        final = analysis.read_json(analysis.BASE_CONFIG)
        self.assertEqual(final, analysis.read_json(analysis.ACTIVE_CONFIG))
        tp2 = copy.deepcopy(final)
        tp2['args'][tp2['args'].index('--tp') + 1] = '2'
        del tp2['env']['MAYA_DS4_DRAFT_DEV']
        tp2['env']['MAYA_DS4_DRAFT_GPU'] = '1,2,3'
        self.assertEqual(analysis.config_for('tp2'), tp2)
        chunk = copy.deepcopy(final)
        chunk['args'][chunk['args'].index('--prefill-chunk') + 1] = '2048'
        self.assertEqual(analysis.config_for('chunk2048'), chunk)
        self.assertEqual(analysis.read_json(analysis.BASE_CONFIG), final)

    def test_both_drafter_aliases_replaced_only_in_tp2(self):
        reference = analysis.read_json(analysis.REFERENCE / 'run-metadata.json')['effective_engine_env']
        env = analysis.expected_env(reference, 'tp2')
        for prefix in ('MAYA_', 'STRATA_'):
            self.assertNotIn(prefix + 'DS4_DRAFT_DEV', env)
            self.assertEqual(env[prefix + 'DS4_DRAFT_GPU'], '1,2,3')
        self.assertEqual(analysis.expected_env(reference, 'chunk2048'), reference)
        self.assertIn('MAYA_DS4_DRAFT_DEV', reference)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp/opencode')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_both_variants(self):
        for arm in analysis.ARMS:
            out = self.root / arm
            prepare(out, arm)
            summary = analysis.validate(out, arm)
            self.assertEqual(summary['warmup_requests'], 12)
            self.assertEqual(summary['pooled_measurement']['requests'], 10)
            layout = analysis.runtime_layout((out / 'engine.log').read_text(),
                                             2 if arm == 'tp2' else 4,
                                             2048 if arm == 'chunk2048' else 4096)
            self.assertEqual(layout['groups'], 2 if arm == 'tp2' else 1)

    def test_fallback_and_wrong_chunk_rejected(self):
        for index, replacement in enumerate((('tensor parallel 2:', 'tensor parallel 2 -> 1:'),
                                              ('prompts in chunks of 4096)', 'prompts in chunks of 2048)'))):
            out = self.root / str(index)
            prepare(out, 'tp2')
            log = (out / 'engine.log').read_text().replace(*replacement)
            (out / 'engine.log').write_text(log)
            with self.assertRaises(AssertionError):
                analysis.validate(out, 'tp2')

    def test_missing_device_or_fusion_check_rejected(self):
        for index, marker in enumerate(('ds4: CUDA3 layers', 'CUDA2 route fuse check (16 rows)')):
            out = self.root / str(index)
            prepare(out, 'tp2')
            lines = (out / 'engine.log').read_text().splitlines()
            (out / 'engine.log').write_text('\n'.join(line for line in lines if marker not in line) + '\n')
            with self.assertRaises(AssertionError):
                analysis.validate(out, 'tp2')

    def test_drafter_physical_placement_required(self):
        out = self.root / 'tp2'
        prepare(out, 'tp2')
        log = (out / 'engine.log').read_text().replace('DS4_DRAFT_GPU block 2 on CUDA3', 'DS4_DRAFT_GPU block 2 on CUDA0')
        (out / 'engine.log').write_text(log)
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'tp2')

    def test_extra_environment_change_rejected(self):
        out = self.root / 'chunk2048'
        prepare(out, 'chunk2048')
        metadata = analysis.read_json(out / 'run-metadata.json')
        metadata['effective_engine_env']['DS4_COPY_NUMA'] = '1'
        analysis.write_json(out / 'run-metadata.json', metadata)
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'chunk2048')

    def test_oom_rejected(self):
        out = self.root / 'tp2'
        prepare(out, 'tp2')
        memory = analysis.read_json(out / 'memory.json')
        memory['after']['memory_events']['oom'] = 1
        analysis.write_json(out / 'memory.json', memory)
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'tp2')

    def test_reuse_rejected(self):
        out = self.root / 'tp2'
        prepare(out, 'tp2')
        rows = [json.loads(line) for line in (out / 'results.jsonl').read_text().splitlines()]
        rows[0]['done']['reused'] = 1
        (out / 'results.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'tp2')

    def test_partial_ram_residency_rejected(self):
        out = self.root / 'tp2'
        prepare(out, 'tp2')
        log = (out / 'engine.log').read_text().replace('10647 of the CPU lane', '10646 of the CPU lane')
        (out / 'engine.log').write_text(log)
        with self.assertRaises(AssertionError):
            analysis.validate(out, 'tp2')


class ComparisonTests(unittest.TestCase):
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
            self.assertFalse(report['answer_parity_tested'])
            self.assertEqual(len(report['summaries']), 3)
            for arm in analysis.ARMS:
                self.assertEqual(report['deltas_vs_saved_final'][arm]['groups']['pooled'],
                                 {'prefill_percent': 0, 'decode_percent': 0})
                self.assertEqual(len(report['deltas_vs_saved_final'][arm]['per_request']), 10)
                self.assertIn('case_id', report['best_of_two'][arm]['32768']['prefill'])
            self.assertTrue((root / 'comparison.md').is_file())


if __name__ == '__main__':
    unittest.main()
