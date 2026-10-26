import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import collect_tune
import tune
from screen import Engine


def row(case, rate=30, spec=True):
    return {'id': case['id'], 'phase': case['phase'], 'valid': True,
            'done': {'tg': 256, 'pp': 2048, 'decode_ms': 255000 / rate, 'prompt_ms': 20000,
                     'drafted': 100 if spec else 0, 'accepted': 80 if spec else 0},
            'native_tg_tok_s': rate, 'ttft_s': 20, 'wall_s': 20 + 255 / rate,
            'tokens': list(range(256))}


class FakeEngine:
    def request(self, case, spec, tuning):
        return row(case, 30 + 20 * (0.7 - abs(tuning['dspark_conf'] - 0.7)) if spec else 28, spec)


class DrySweep(tune.Sweep):
    def __init__(self):
        self.entries, self.sessions, self.controls = [], [], []
        self.current, self.engine = None, None
        self.saved_results = 0
        self.cases = [{'id': f'{phase}-{i}', 'phase': phase}
                      for phase in ('warmup', 'measurement') for i in range(3)]
        self.state = {'status': 'running', 'complete': False}
        self.exports = []

    def export(self, name, value):
        self.exports.append((name, copy.deepcopy(value)))

    def start(self, name, maximum=0, loaded=True, warm=None):
        self.finish()
        self.current = name
        (tune.ROOT / name).mkdir()
        self.sessions.append({'name': name, 'maximum': maximum})
        self.engine = FakeEngine()
        self.run_point(name + '-warmup', warm or tune.point(maximum=maximum, spec=loaded), warmup=True)

    def finish(self, error=None):
        self.current = None
        self.engine = None


class TuningTests(unittest.TestCase):
    def test_runtime_fixed_settings_and_no_drafter_on_none(self):
        base = json.loads((Path(__file__).parent.parent / 'baseline.json').read_text())
        config, env = tune.runtime(base, '01-none', 0, False)
        self.assertEqual(config['args'][config['args'].index('--prefill-chunk') + 1], '2048')
        self.assertEqual(config['args'][config['args'].index('--dspark') + 1], 'none')
        self.assertNotIn('DS4_DRAFT_DEV', env)
        config, env = tune.runtime(base, '03-max-1', 1, True)
        self.assertEqual(env['DS4_DRAFT_DEV'], '1,2,3')
        self.assertEqual(env['DS4_DSPARK_MAX'], '1')
        self.assertEqual(base['args'][base['args'].index('--prefill-chunk') + 1], '4096')

    def test_native_request_thresholds_and_zero_cumulative(self):
        engine = Engine.__new__(Engine)
        engine.proc = type('Process', (), {'pid': 42, 'stdin': io.BytesIO()})()
        lines = iter(['T 123', 'DONE 1 2048 1000 1000 stop 0 0 0 0 0'])
        engine.line = lambda deadline: next(lines)
        state = {'memory.events': {'oom_kill': 0}, 'cpu.stat': {'nr_throttled': 0}}
        with patch('screen.snapshot', return_value=state):
            result = engine.request({'id': 'x', 'phase': 'measurement', 'lead_title': 'x', 'ids': [1, 2]},
                                    True, {'dspark_conf': 0.3, 'dspark_cum': 0})
        self.assertEqual(engine.proc.stdin.getvalue(),
                         b'GEN 256 temperature=0 seed=1 spec=1 dspark_conf=0.3 dspark_cum=0 1,2\n')
        self.assertFalse(result['valid'])  # Natural EOS must not become a scored TG256 point.

    def test_pooling_and_invalid_rejection(self):
        rows = [row({'id': str(i), 'phase': 'measurement'}, rate) for i, rate in enumerate((10, 20, 40))]
        self.assertAlmostEqual(tune.score(rows)['decode_tok_s'], 3 / (1/10 + 1/20 + 1/40))
        rows[0]['valid'] = False
        with self.assertRaises(ValueError):
            tune.score(rows)

    def test_conservative_choice_and_interaction_budget(self):
        def entry(conf, rate):
            return {'point': tune.point(conf), 'metrics': {'decode_tok_s': rate}}
        self.assertEqual(tune.choose([entry(0.3, 31), entry(0.5, 30)])['point']['conf'], 0.5)
        self.assertEqual(tune.choose([entry(0.3, 33), entry(0.5, 30)])['point']['conf'], 0.3)
        seen = {tune.key(tune.point())}
        extra = tune.interactions(tune.point(), seen)
        self.assertLessEqual(len(extra), 2)
        self.assertTrue(all(tune.key(p) not in seen for p in extra))
        self.assertEqual(tune.shuffled([1, 2, 3], 4), tune.shuffled([1, 2, 3], 4))

    def test_complete_dry_sweep_with_restarts_and_frozen_schedules(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            with patch.object(tune, 'ROOT', Path(directory)), patch.object(tune, 'artifact'), \
                    patch.object(tune, 'checkpoint'), patch.object(tune, 'progress'):
                sweep = DrySweep()
                sweep.execute()
                sweep.finalize()
                self.assertTrue(sweep.state['complete'])
                self.assertEqual(sweep.state['status'], 'completed')
                self.assertEqual(len(sweep.sessions), 9)
                self.assertEqual(len(sweep.state['finalists']), 2)
                self.assertEqual(sweep.saved_results, 87)
                self.assertEqual({name for name, _ in sweep.exports if name.startswith('stage-')},
                                 {f'stage-{i}.json' for i in range(1, 7)})
                self.assertTrue(all(c['passes'] for c in sweep.controls))
                self.assertTrue(all(len(e['rows']) == 3 for e in sweep.entries))

    def test_drift_stops_without_following_stages(self):
        class Drifting(DrySweep):
            def run_point(self, label, p, **kwargs):
                entry = super().run_point(label, p, **kwargs)
                if label == 'confidence-control':
                    entry['metrics']['decode_tok_s'] *= 1.1
                return entry
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            with patch.object(tune, 'ROOT', Path(directory)), patch.object(tune, 'artifact'), \
                    patch.object(tune, 'checkpoint'), patch.object(tune, 'progress'):
                sweep = Drifting()
                with self.assertRaisesRegex(ValueError, 'Control drift'):
                    sweep.execute()
                self.assertEqual(sweep.state['status'], 'drift')
                self.assertFalse(sweep.state['complete'])
                self.assertEqual(len(sweep.sessions), 2)
                self.assertNotIn('stage-3.json', {name for name, _ in sweep.exports})

    def test_allowlist_and_durable_exit137(self):
        for name in ('../../escape', '/etc/passwd', '01-none/other', 'B-on-default/manifest.json'):
            with self.assertRaises(ValueError):
                collect_tune.destination(Path('/unused'), name)
        producer = '''
import json, os, sys
def emit(r): print('SCREEN_EVENT ' + json.dumps(r), flush=True)
emit({'kind':'artifact','path':'01-none/results.jsonl','data':'{"valid":true}\\n','append':True})
emit({'kind':'checkpoint','label':'saved-result'})
assert sys.stdin.readline().strip() == 'ACK saved-result'
os._exit(137)
'''
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory) / 'run'
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('collect_tune.py')),
                                     '--out', str(root), '--', sys.executable, '-c', producer],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 137, result.stderr)
            self.assertTrue(json.loads((root / '01-none/results.jsonl').read_text())['valid'])
            self.assertEqual(json.loads((root / 'exit.json').read_text())['saved_results'], 1)


if __name__ == '__main__':
    unittest.main()
