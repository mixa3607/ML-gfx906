import hashlib
import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import sys
import subprocess
import struct
import unittest
from unittest.mock import patch

from corpus import SOURCES
from compare import compare
from summary import summarize
from context_check import assemble, score, validate_probe_length, yoco_activation_verified
from vision_check import image_checks
from full_compute import engine_env, runtime_configs, topology_evidence, validate_config, validate_limits
from flow_check import check_log
from tp_check import check_log as check_tp_log
from native_bench import Engine, cgroup_dir, dump_hashes, emit_event, parse_done, peer_budget, quantile, read_numbers


class BenchTests(unittest.TestCase):
    def test_tp4_candidates_have_matched_tp2_control(self):
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([sys.executable, str(Path(__file__).with_name('variants.py')),
                            '--tp4-only', '--out', directory], check=True)
            paths = sorted(Path(directory).glob('*.json'))
            self.assertEqual(len(paths), 3)
            configs = {p.stem: json.loads(p.read_text()) for p in paths}
            for name, cfg in configs.items():
                self.assertEqual(validate_config(cfg)['requested_tp'], 2 if name.startswith('tp2') else 4)
                self.assertEqual(cfg['env']['DS4_TP_GGUF_UNEVEN'], '1')
                self.assertEqual(cfg['env']['STRATA_DS4_PROMPT_SKIP'], '0')
                self.assertNotIn('DS4_FLOW_TP', cfg['env'])
                self.assertTrue(cfg['require_full_copies'])
            a, b = configs['tp2-whole-block'], configs['tp4']
            self.assertEqual(a['env'], b['env'])
            args = list(a['args'])
            args[args.index('--tp') + 1] = '4'
            self.assertEqual(args, b['args'])
            self.assertEqual(configs['tp4-diagnostic']['env']['DS4_TP_CHECK'], '1')

    def test_tp4_rejects_fallback_or_unvalidated_combinations(self):
        cfg = runtime_configs()['copy-c56-numa2-p4096']
        cfg['args'][cfg['args'].index('--tp') + 1] = '4'
        with self.assertRaises(ValueError):
            validate_config(cfg)
        cfg['env']['DS4_TP_GGUF_UNEVEN'] = '1'
        validate_config(cfg)
        for change in ({'STRATA_DS4_PROMPT_SKIP': '1'},
                       {'DS4_FLOW_TP': '1', 'DS4_FLOW_PUMP_WAIT': '1'}):
            bad = copy.deepcopy(cfg)
            bad['env'].update(change)
            with self.assertRaises(ValueError):
                validate_config(bad)

    def test_effective_topology_not_nominal_cli(self):
        four = [f'VRAM dev={i} tp_n=4 ctx=196608 layers=0-39' for i in range(4)]
        self.assertTrue(topology_evidence(four, 4)['verified'])
        two = [f'VRAM dev={i} tp_n=2 ctx=196608 layers={"0-19" if i < 2 else "20-39"}' for i in range(4)]
        self.assertTrue(topology_evidence(two, 2)['verified'])
        self.assertFalse(topology_evidence(two, 4)['verified'])
        self.assertFalse(topology_evidence(four[:-1], 4)['verified'])
        self.assertFalse(topology_evidence([four[0]] * 4, 4)['verified'])
        self.assertFalse(topology_evidence([four[0].replace('0-39', '0-19'), *four[1:]], 4)['verified'])
        self.assertFalse(topology_evidence([s.replace('196608', '8192') for s in four], 4)['verified'])

    def test_tp4_gate_requires_four_member_numerical_checks(self):
        line = "ds4: TP check: MXFP4 (layer 0): 4 members' parts summed against the whole - routed 0.0001, shared 0.0001"
        log = '\n'.join([line] * 4 + ['ds4: TP check passed (4 expert formats and rotations, all the split layers have)'])
        self.assertTrue(check_tp_log(log)['passed'])
        self.assertFalse(check_tp_log(log.replace('4 members', '2 members'))['passed'])
        self.assertFalse(check_tp_log(line)['passed'])
        self.assertFalse(check_tp_log(log + '\nTP check FAILED')['passed'])
        self.assertFalse(check_tp_log('')['passed'])

    def test_flow_gate_requires_real_checks_and_all_devices(self):
        log = """ds4: tensor-parallel members on the prompt path's flow: CUDA0, CUDA1, CUDA2, CUDA3 - each streams
ds4: TP check: guards intact (DS4_FLOW_TP)
ds4: TP check: guards intact (DS4_FLOW_TP)
ds4: TP check: the flow's copies passed (2 of the formats', rotations' and members' copies) (DS4_FLOW_TP)
ds4: TP check passed (2 expert formats and rotations, all the split layers have) (DS4_TP_CHECK)
""" + '\n'.join(f'ds4 prompt stream, CUDA{i}: 2048 tokens' for i in range(4))
        self.assertTrue(check_log(log)['passed'])
        self.assertTrue(check_log(log, prompt_tokens=2048)['passed'])
        self.assertFalse(check_log(log, prompt_tokens=65536)['passed'])
        self.assertFalse(check_log(log.replace('CUDA3:', 'CUDA2:'))['passed'])
        self.assertFalse(check_log(log.replace('guards intact', 'guards differ'))['passed'])
        self.assertFalse(check_log(log + '\nTP check FAILED')['passed'])
        self.assertFalse(check_log('')['passed'])

    def test_flow_candidates_are_separate_from_yoco(self):
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([sys.executable, str(Path(__file__).with_name('variants.py')),
                            '--flow-only', '--out', directory], check=True)
            paths = sorted(Path(directory).glob('*.json'))
            self.assertEqual(len(paths), 2)
            for path in paths:
                cfg = json.loads(path.read_text())
                self.assertEqual(validate_config(cfg)['flow_tp'], '1')
                self.assertEqual(cfg['env']['STRATA_DS4_PROMPT_SKIP'], '0')
                self.assertEqual(cfg['env']['DS4_TP_CHECK'], '1')
                self.assertTrue(cfg['require_full_copies'])
                cfg['env']['STRATA_DS4_PROMPT_SKIP'] = '1'
                with self.assertRaises(ValueError):
                    validate_config(cfg)

    def test_yoco1_requires_full_default_retention_and_actual_activation(self):
        line = 'ds4: prompt skip: layers 20-39 from CUDA2, 62868 early rows KV-only, 2668 kept'
        self.assertTrue(yoco_activation_verified([line], [65536]))
        self.assertFalse(yoco_activation_verified([], [65536]))
        self.assertFalse(yoco_activation_verified([line.replace('2668 kept', '128 kept')], [65536]))
        self.assertFalse(yoco_activation_verified([line], [32768]))

    def test_yoco1_candidates_change_only_approved_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([sys.executable, str(Path(__file__).with_name('variants.py')),
                            '--yoco1-only', '--out', directory], check=True)
            paths = sorted(Path(directory).glob('*.json'))
            self.assertEqual(len(paths), 2)
            base = runtime_configs()['copy-c56-numa2-p4096']
            for path in paths:
                cfg = json.loads(path.read_text())
                validate_config(cfg)
                expected = base['env'] | {'STRATA_DS4_PROMPT_SKIP': '1'}
                self.assertEqual(cfg['env'], expected)
                self.assertEqual(cfg['args'], base['args'] + (['--verbose'] if 'validation' in path.stem else []))
                self.assertTrue(cfg['require_full_copies'])

    def test_opt_in_stream_event(self):
        value = {'id': 'probe', 'text': 'Код: 123456\n'}
        for enabled in ('0', '1'):
            output = io.StringIO()
            with patch.dict('os.environ', {'BENCH_STREAM_EVENTS': enabled}), contextlib.redirect_stdout(output):
                emit_event('result', value)
            if enabled == '1':
                self.assertEqual(json.loads(output.getvalue().removeprefix('BENCH_EVENT ')),
                                 {'kind': 'result', 'value': value})
            else:
                self.assertEqual(output.getvalue(), '')

    def test_stream_collector_retains_records_after_failure(self):
        script = Path(__file__).with_name('capture_run.py')
        for remote_code, expected, code in ((0, 1, 0), (137, 2, 137), (0, 2, 1)):
            with self.subTest(remote_code=remote_code, expected=expected), tempfile.TemporaryDirectory() as directory:
                out = Path(directory) / 'captured'
                fake = f'''
import json, sys
print('START fake', flush=True)
print('BENCH_EVENT ' + json.dumps({{'kind': 'manifest', 'value': {{'dump': False}}}}), flush=True)
print('BENCH_EVENT ' + json.dumps({{'kind': 'result', 'value': {{'id': 'fake', 'tokens': [42]}}}}), flush=True)
sys.exit({remote_code})
'''
                result = subprocess.run([sys.executable, str(script), '--out', str(out),
                                         '--expected-results', str(expected), '--',
                                         sys.executable, '-u', '-c', fake], capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(json.loads((out / 'manifest.json').read_text()), {'dump': False})
                self.assertEqual(json.loads((out / 'results.jsonl').read_text())['tokens'], [42])
                self.assertEqual(len((out / 'events.jsonl').read_text().splitlines()), 2)
                self.assertIn('START fake', (out / 'console.log').read_text())
                self.assertNotIn('BENCH_EVENT', result.stdout)
                self.assertEqual(json.loads((out / 'exit.json').read_text())['complete'], code == 0)

    def test_peer_pod_cache_counted_in_192gi_budget(self):
        self.assertEqual(peer_budget(185 * 2**30, 7 * 2**30), 192 * 2**30)
        self.assertEqual(peer_budget(187 * 2**30, 5 * 2**30), 192 * 2**30)
        self.assertEqual(peer_budget(190 * 2**30, 2 * 2**30), 192 * 2**30)
        with self.assertRaises(RuntimeError):
            peer_budget(190 * 2**30, 2 * 2**30 + 1)
        with self.assertRaises(RuntimeError):
            peer_budget(185 * 2**30, 7 * 2**30 + 1)

    def test_context_probes_capped_at_user_requested_64k(self):
        for length in (2048, 32768, 65536):
            validate_probe_length(length)
        for length in (0, -2048, 65535, 67584, 131072, 194560):
            with self.subTest(length=length), self.assertRaises(ValueError):
                validate_probe_length(length)

    def test_context_fact_spans_and_unique_filler(self):
        filler = list(range(10000, 13000))
        facts = [[-1, -2], [-3, -4], [-5, -6]]
        ids, spans, used = assemble([1, 2], [3, 4], filler, facts, 2048)
        self.assertEqual(len(ids), 2048)
        self.assertEqual([ids[a:b] for a, b in spans], facts)
        self.assertEqual([x for x in ids if x >= 10000], filler[:used])
        self.assertEqual(spans[0][0], 128)
        self.assertEqual(spans[1][0], 1024)
        self.assertGreater(spans[-1][0], 1800)
        with self.assertRaises(ValueError):
            assemble([1], [2], filler[:5], facts, 2048)

    def test_context_score_requires_name_code_association(self):
        expected = {'Ладога-17': '582913', 'Вега-43': '291826'}
        self.assertTrue(all(score('**Ладога-17**: 582913\nВега-43 — 291826', expected).values()))
        self.assertFalse(any(score('582913 291826', expected).values()))
        self.assertFalse(any(score('Ладога-17: 291826\nВега-43: 582913', expected).values()))

    def test_vision_functional_score(self):
        shapes = {'case': 'shapes', 'text': 'Красный прямоугольник и синий круг.'}
        blank = {'case': 'blank', 'text': 'Белое пустое изображение.'}
        self.assertTrue(all(image_checks([shapes, blank]).values()))
        blank['text'] = shapes['text']
        self.assertFalse(image_checks([shapes, blank])['blank_recognized'])

    def test_functional_request_respects_natural_eos(self):
        fake = '''
import sys
print('READY 196608 stop', flush=True)
for line in sys.stdin:
    if line.strip() == 'QUIT': break
    if line.startswith('GEN '):
        print('T 42', flush=True)
        print('STAT skipped=0', flush=True)
        print('DONE 1 2048 1000.0 1.0 stop 0 0 0 0 0', flush=True)
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            seed = path / 'seed.bin'
            seed.write_bytes(b'profile')
            cfg = {'exe': sys.executable, 'args': ['-u', '-c', fake], 'cwd': directory,
                   'env': {}, 'seed_profile': str(seed)}
            engine = Engine(cfg, path)
            try:
                engine.ready(5)
                case = {'id': 'functional', 'ids': list(range(2048))}
                row = engine.request(case, 5, 128, benchmark=False)
                self.assertEqual(row['done']['tg'], 1)
                self.assertIsNone(row['tg_tok_s'])
                with self.assertRaisesRegex(RuntimeError, 'TG limit'):
                    engine.request(case, 5, 256)
            finally:
                engine.close()

    def test_full_compute_runtime_matrix(self):
        configs = runtime_configs()
        self.assertEqual(len(configs), 5)
        for cfg in configs.values():
            result = validate_config(cfg)
            self.assertTrue(result['timing_eligible'])
            self.assertFalse(result['quality_and_long_context_validated'])
            self.assertFalse(result['bit_exact_required'])
        cfg = next(iter(configs.values()))
        cfg['env']['STRATA_DS4_PROMPT_SKIP'] = '1'
        self.assertEqual(validate_config(cfg)['prompt_skip'], '1')
        cfg['args'].append('--verbose')
        self.assertTrue(validate_config(cfg)['timing_eligible'])

    def test_full_compute_rejects_approximation_and_unknown_options(self):
        base = next(iter(runtime_configs().values()))
        for key, value in [('STRATA_DS4_DISK_SKIP_W', 'AUTO'),
                           ('STRATA_DS4_DISK_SKIP_W', '0.01'),
                           ('STRATA_DS4_PROMPT_SKIP', '2'),
                           ('STRATA_DS4_SLOT_KEEP', '128'),
                           ('DS4_YOCO_KEEP', '128'), ('DS4_YOCO', '1'),
                           ('DS4_SKIP_UNPICKED', '1'), ('DS4_FLOW_TP', '1')]:
            cfg = copy.deepcopy(base)
            cfg['env'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_config(cfg)
        for key, value in [('--max-context', '8192'), ('--vision', 'off'),
                           ('--dspark', 'auto'), ('--pack', '/other-model')]:
            cfg = copy.deepcopy(base)
            cfg['args'][cfg['args'].index(key) + 1] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_config(cfg)
        for extra in (['--no-expert-cache'], ['--quant', 'q4']):
            cfg = copy.deepcopy(base)
            cfg['args'] += extra
            with self.assertRaises(ValueError):
                validate_config(cfg)
        cfg = copy.deepcopy(base)
        cfg['require_full_copies'] = False
        with self.assertRaises(ValueError):
            validate_config(cfg)

    def test_full_compute_clears_inherited_knobs(self):
        cfg = next(iter(runtime_configs().values()))
        env = engine_env(cfg, {'DS4_YOCO_KEEP': '128', 'DS4_YOCO': '2',
                              'MAYA_DS4_PROMPT_SKIP': '2', 'STRATA_DS4_DISK_SKIP_W': 'AUTO',
                              'DS4_SKIP_UNPICKED': '1', 'PATH': '/bin'})
        self.assertEqual(env['PATH'], '/bin')
        self.assertEqual(env['STRATA_DS4_DISK_SKIP_W'], '0')
        for key in ('DS4_YOCO_KEEP', 'DS4_YOCO', 'MAYA_DS4_PROMPT_SKIP', 'DS4_SKIP_UNPICKED'):
            self.assertNotIn(key, env)

    def test_full_compute_resource_limits(self):
        validate_limits({'cpu.max': 'max 100000', 'memory.max': str(192 * 2**30)})
        for cpu, memory in [('100000 100000', str(192 * 2**30)),
                            ('max 100000', 'max'), ('max 100000', str(193 * 2**30))]:
            with self.assertRaises(ValueError):
                validate_limits({'cpu.max': cpu, 'memory.max': memory})

    def test_pooled_rates_exclude_warmup(self):
        a = {'id': 'a', 'phase': 'dev', 'pp': 2048, 'done': {'pp': 2048, 'tg': 256,
             'reused': 0, 'prompt_ms': 100}, 'tg_tok_s': 10, 'ttft_s': 2, 'wall_s': 3}
        b = {**a, 'id': 'b', 'done': {**a['done'], 'prompt_ms': 300},
             'tg_tok_s': 20, 'ttft_s': 4, 'wall_s': 5}
        warm = {**a, 'id': 'warm', 'phase': 'warmup', 'wall_s': 999}
        result = summarize([warm, a, b])
        self.assertEqual(result['warmup_requests'], 1)
        self.assertEqual(result['overall']['requests'], 2)
        self.assertEqual(result['overall']['pp_tok_s'], 10240)
        self.assertAlmostEqual(result['overall']['tg_tok_s'], 40 / 3)
        self.assertEqual(result['overall']['wall_s'], 8)
        self.assertEqual(result['overall']['native_ttft_mean_s'], 3)

    def test_combined_candidates_preserve_requirements(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(__file__).with_name('variants.py')
            subprocess.run([sys.executable, str(script), '--out', directory, '--combined-only'], check=True)
            paths = sorted(Path(directory).glob('*.json'))
            self.assertEqual(len(paths), 3)
            for path in paths:
                cfg = json.loads(path.read_text())
                args = dict(zip(cfg['args'][::2], cfg['args'][1::2]))
                self.assertEqual(args['--max-context'], '196608')
                self.assertEqual(args['--vision'], 'on')
                self.assertEqual(args['--dspark'], 'none')
                self.assertEqual(args['--mmap-experts'], 'off')
                self.assertEqual(args['--cpu-threads'], '56')
                self.assertEqual(cfg['env']['DS4_COPY_NUMA'], '1')
                self.assertTrue(cfg['require_full_copies'])

    def test_full_copy_candidates_preserve_requirements(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(__file__).with_name('variants.py')
            subprocess.run([sys.executable, str(script), '--out', directory, '--full-copy-only'], check=True)
            paths = sorted(Path(directory).glob('*.json'))
            self.assertEqual(len(paths), 2)
            for path in paths:
                cfg = json.loads(path.read_text())
                args = dict(zip(cfg['args'][::2], cfg['args'][1::2]))
                self.assertEqual(args['--max-context'], '196608')
                self.assertEqual(args['--vision'], 'on')
                self.assertEqual(args['--mmap-experts'], 'off')
                self.assertEqual(args['--prefill-chunk'], '2048')
                self.assertTrue(cfg['require_full_copies'])
                self.assertNotIn('DS4_REQUIRE_ALL_RAM', cfg['env'])

    def test_protocol_and_reuse_guard_without_gpu(self):
        fake = '''
import sys
print('READY 196608 stop', flush=True)
for line in sys.stdin:
    if line.strip() == 'QUIT': break
    if not line.startswith('GEN '): continue
    reused = int(sys.argv[1])
    for i in range(256): print('T', i, flush=True)
    print('STAT disk_mb=0 skipped=0', flush=True)
    print(f'DONE 256 2048 1000.0 5100.0 length 0 0 {reused} 100 200', flush=True)
'''
        for reused in (0, 1):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                seed = path / 'seed.bin'
                seed.write_bytes(b'profile')
                cfg = {'exe': sys.executable, 'args': ['-u', '-c', fake, str(reused)],
                       'cwd': directory, 'env': {}, 'seed_profile': str(seed)}
                engine = Engine(cfg, path)
                try:
                    engine.ready(5)
                    case = {'id': 'fake', 'phase': 'dev', 'pp': 2048, 'ids': list(range(2048))}
                    if reused:
                        with self.assertRaisesRegex(RuntimeError, 'KV reuse'):
                            engine.request(case, 5, 256)
                    else:
                        result = engine.request(case, 5, 256)
                        self.assertEqual(result['done']['tg'], 256)
                        self.assertEqual(len(result['tokens']), 256)
                finally:
                    engine.close()

    def test_bit_exact_is_not_token_equality(self):
        row = {'id': 'dev-0', 'phase': 'dev', 'pp': 2048, 'prompt_sha256': 'a',
               'tokens': [42], 'pp_tok_s': 10, 'tg_tok_s': 5, 'ttft_s': 2}
        with self.assertRaises(ValueError):
            compare([row], [row], require_logits=True)
        left = row | {'logits': {'rows': ['abcd']}}
        right = row | {'logits': {'rows': ['abce']}}
        self.assertFalse(compare([left], [right], True)['bit_exact_on_tested_rows'])
        self.assertTrue(compare([left], [left], True)['bit_exact_on_tested_rows'])

    def test_empty_comparison_rejected(self):
        with self.assertRaises(ValueError):
            compare([], [], True)

    def test_done(self):
        result = parse_done('DONE 256 2048 1000.0 5100.0 length 0 0 0 100 200')
        self.assertEqual(result['tg'], 256)
        self.assertEqual(result['pp'], 2048)
        self.assertEqual(result['reused'], 0)
        self.assertEqual(result['finish'], 'length')

    def test_unknown_protocol_rejected(self):
        with self.assertRaises(ValueError):
            parse_done('DONE 256 2048 1000.0')

    def test_nearest_rank(self):
        self.assertEqual(quantile([3, 1, 2], .5), 2)
        self.assertEqual(quantile([1, 2, 3], .99), 3)
        self.assertIsNone(quantile([], .5))

    def test_logit_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'logits.f32'
            p.write_bytes(b'12345678abcdefgh')
            hashes = dump_hashes(p, vocab=2)
            self.assertEqual(hashes['sha256'], hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertEqual(len(hashes['rows']), 2)
            p.write_bytes(b'123')
            with self.assertRaises(RuntimeError):
                dump_hashes(p, vocab=2)
            p.write_bytes(b'')
            with self.assertRaises(RuntimeError):
                dump_hashes(p, vocab=2)
            for value in (float('inf'), float('nan')):
                p.write_bytes(struct.pack('<f', value))
                with self.assertRaisesRegex(RuntimeError, 'Non-finite'):
                    dump_hashes(p, vocab=1)

    def test_number_file(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'cpu.stat'
            self.assertEqual(read_numbers(p), {})
            p.write_text('nr_throttled 0\nusage_usec 42\n')
            self.assertEqual(read_numbers(p)['usage_usec'], 42)

    def test_no_shared_article_titles(self):
        titles = [t for split in SOURCES.values() for t in split]
        self.assertEqual(len(titles), len(set(titles)))

    def test_baseline_requirements(self):
        cfg = json.loads(Path(__file__).with_name('baseline.json').read_text())
        args = dict(zip(cfg['args'][::2], cfg['args'][1::2]))
        self.assertEqual(args['--max-context'], '196608')
        self.assertEqual(args['--vision'], 'on')
        self.assertEqual(args['--dspark'], 'none')
        self.assertEqual(cfg['env']['STRATA_DS4_DISK_SKIP_W'], '0')
        self.assertEqual(cfg['env']['STRATA_DS4_PROMPT_SKIP'], '0')

    def test_cgroup_path(self):
        self.assertTrue(str(cgroup_dir()).startswith('/sys/fs/cgroup'))


if __name__ == '__main__':
    unittest.main()
