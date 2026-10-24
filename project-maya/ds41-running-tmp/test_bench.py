import hashlib
import json
from pathlib import Path
import tempfile
import sys
import subprocess
import struct
import unittest

from corpus import SOURCES
from compare import compare
from summary import summarize
from native_bench import Engine, cgroup_dir, dump_hashes, parse_done, quantile, read_numbers


class BenchTests(unittest.TestCase):
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
