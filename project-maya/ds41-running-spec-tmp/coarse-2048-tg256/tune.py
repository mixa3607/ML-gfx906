#!/usr/bin/env python3
"""Approved bounded DSpark sweep; timings and transport reuse the native screen."""
import json
import os
from pathlib import Path
import random
import re
import shutil
import sys
import threading
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from screen import Engine, sha, snapshot
from stream import artifact, checkpoint, progress, write_json
from summarize import compare_tokens

ROOT = Path('/data/screen')
SEED = 20261026
CASES_SHA = '946bb7aaf184329fb15cc0330fbcecc7cc67ea090bfcda05a1b84002f9fd6b80'
PROFILE_SHA = 'bcfd7697fc070b0ebcb0138c0ef029429ea0d4ff81ca60eeb7804e08efd0cd29'
SOURCE = '6afa525bbabc3a8f5fd165f89e9bc72155d9bd39'
SESSIONS = ('01-none', '02-thresholds', '03-max-1', '04-max-2', '05-max-3',
            '06-interactions', '07-finalist-1', '08-finalist-2', '09-none-repeat')


def point(conf=0.5, cum=0.5, maximum=0, spec=True):
    return {'conf': conf, 'cum': cum, 'maximum': maximum, 'spec': spec}


def key(p):
    return (p['conf'], p['cum'], p['maximum'], p['spec'])


def score(rows):
    if len(rows) != 3 or any(not r['valid'] or r['phase'] != 'measurement' for r in rows):
        raise ValueError('A point needs exactly three valid measurement requests')
    drafted = sum(r['done']['drafted'] for r in rows)
    accepted = sum(r['done']['accepted'] for r in rows)
    return {'decode_tok_s': sum(r['done']['tg'] - 1 for r in rows) /
            sum(r['done']['decode_ms'] / 1000 for r in rows),
            'prefill_tok_s': sum(r['done']['pp'] for r in rows) /
            sum(r['done']['prompt_ms'] / 1000 for r in rows),
            'wall_s': sum(r['wall_s'] for r in rows),
            'ttft_s': [r['ttft_s'] for r in rows],
            'case_decode_tok_s': [r['native_tg_tok_s'] for r in rows],
            'drafted': drafted, 'accepted': accepted,
            'acceptance': accepted / drafted if drafted else None,
            'accepted_per_generated': accepted / sum(r['done']['tg'] for r in rows)}


def drift(a, b):
    return 100 * (b['metrics']['decode_tok_s'] / a['metrics']['decode_tok_s'] - 1)


def choose(entries):
    """Within 5% of the fastest, prefer the default-nearest point, not noise."""
    best = max(e['metrics']['decode_tok_s'] for e in entries)
    tied = [e for e in entries if best / e['metrics']['decode_tok_s'] <= 1.05]
    return min(tied, key=lambda e: (abs(e['point']['conf'] - 0.5) + abs(e['point']['cum'] - 0.5),
                                   e['point']['maximum'] != 0, key(e['point'])))


def shuffled(values, stage):
    values = list(values)
    random.Random(SEED + stage).shuffle(values)
    return values


def interactions(p, seen):
    confs, cums = [0.3, 0.5, 0.7], [0, 0.3, 0.5, 0.7]
    ci, ui = confs.index(p['conf']), cums.index(p['cum'])
    choices = [point(c, u, p['maximum']) for i, c in enumerate(confs) for j, u in enumerate(cums)
               if abs(i - ci) <= 1 and abs(j - ui) <= 1 and (i != ci or j != ui)]
    choices = [q for q in choices if key(q) not in seen]
    choices.sort(key=lambda q: (abs(q['conf'] - p['conf']) + abs(q['cum'] - p['cum']), key(q)))
    return choices[:2]


def runtime(base, name, maximum, loaded):
    args = list(base['args'])
    for flag, value in (('--prefill-chunk', '2048'), ('--dspark', 'on' if loaded else 'none'),
                        ('--expert-profile', str(ROOT / name / 'expert-profile.bin'))):
        args[args.index(flag) + 1] = value
    overrides = dict(base['env'])
    overrides.update(DS4_DSPARK_MAX=str(maximum), STRATA_DS4_DSPARK_CUM='0.5')
    if loaded:
        overrides['DS4_DRAFT_DEV'] = '1,2,3'
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('DS4_', 'STRATA_', 'MAYA_', 'HSA_OVERRIDE_'))}
    env.update(overrides)
    config = {'exe': base['exe'], 'cwd': base['cwd'], 'args': args, 'env': overrides}
    return config, env


class Sweep:
    def __init__(self):
        self.base = json.loads((ROOT / 'baseline.json').read_text())
        self.cases = [json.loads(s) for s in (ROOT / 'cases.jsonl').read_text().splitlines()]
        if sha(ROOT / 'cases.jsonl') != CASES_SHA or sha(ROOT / 'seed-profile.bin') != PROFILE_SHA:
            raise ValueError('Frozen inputs/profile differ')
        if [c['phase'] for c in self.cases] != ['warmup'] * 3 + ['measurement'] * 3:
            raise ValueError('Expected three warmup and three measurement cases')
        if any(len(c['ids']) != 2048 for c in self.cases):
            raise ValueError('Expected PP2048')
        self.entries = []
        self.sessions = []
        self.controls = []
        self.engine = None
        self.current = None
        self.saved_results = 0
        self.state = {'complete': False, 'status': 'running', 'seed': SEED,
                      'cases_sha256': CASES_SHA, 'seed_profile_sha256': PROFILE_SHA,
                      'sessions': self.sessions, 'points': [], 'controls': self.controls}

    def export(self, filename, value):
        write_json(ROOT / filename, value)
        checkpoint(filename.removesuffix('.json'))

    def freeze(self, stage, schedule, **extra):
        self.export(f'stage-{stage}.json', {'seed': SEED + stage, 'schedule': schedule, **extra})

    def save_state(self):
        self.state['points'] = [{k: v for k, v in e.items() if k != 'rows'} for e in self.entries]
        self.state['saved_results'] = self.saved_results
        self.export('summary.json', self.state)

    def start(self, name, maximum=0, loaded=True, warm=None):
        self.finish()
        self.current = name
        out = ROOT / name
        out.mkdir(exist_ok=False)
        shutil.copyfile(ROOT / 'seed-profile.bin', out / 'expert-profile.bin')
        config, env = runtime(self.base, name, maximum, loaded)
        write_json(out / 'config.json', config)
        record = {'name': name, 'maximum': maximum, 'loaded': loaded, 'before': snapshot(),
                  'complete': False, 'stage': 'starting', 'cases_sha256': CASES_SHA,
                  'seed_profile_sha256': sha(out / 'expert-profile.bin'),
                  'source_commit': Path('/opt/maya/SOURCE_COMMIT').read_text().strip(),
                  'build': json.loads(Path('/opt/maya/build-hip/MAYA-BUILD.json').read_text())}
        self.sessions.append(record)
        write_json(out / 'manifest.json', record)
        checkpoint(name + '-starting')
        if (record['before']['memory.max'] != str(220 * 2**30) or
                not record['before']['cpu.max'].startswith('max ') or
                record['before']['cpuset.cpus.effective'] != '0-75' or record['source_commit'] != SOURCE):
            raise ValueError('Unexpected cgroup, cpuset or source revision')
        config['env'] = env
        started = time.monotonic()
        self.engine = Engine(config, out)
        record['ready'] = self.engine.ready()
        record['load_s'] = time.monotonic() - started
        self.engine.copies_logged.wait(5)
        log = (out / 'engine.log').read_text()
        copies = re.search(r"(\d+) of the CPU lane's (\d+) experts copied into RAM", log)
        if not copies or copies[1] != copies[2]:
            raise ValueError('Incomplete CPU expert copies')
        record['full_copies'] = list(map(int, copies.groups()))
        vram = [dict(s.split('=', 1) for s in line.split()[1:] if '=' in s)
                for line in record['ready'] if line.startswith('VRAM ')]
        if (len(vram) != 4 or any(v.get('tp_n') != '4' or v.get('ctx') != '196608' for v in vram)
                or not any('vision=ds4 ' in line for line in record['ready'])):
            raise ValueError('TP4/context/vision not verified')
        if loaded and 'DS4_DRAFT_DEV 1,2,3' not in log:
            raise ValueError('Drafter placement not verified')
        record.update(stage='ready', ready_snapshot=snapshot(self.engine.proc.pid))
        write_json(out / 'manifest.json', record)
        checkpoint(name + '-ready')
        progress(f'READY {name}: {record["load_s"]:.1f}s, copies={record["full_copies"]}')
        self.run_point(name + '-warmup', warm or point(maximum=maximum, spec=loaded), warmup=True)

    def finish(self, error=None):
        if not self.current:
            return
        name, record = self.current, self.sessions[-1]
        if self.engine:
            self.engine.close()
            self.engine = None
        record['after'] = snapshot()
        if record['after']['memory.events']['oom_kill'] != record['before']['memory.events']['oom_kill']:
            error = error or 'Session OOM'
        if record['after']['cpu.stat']['nr_throttled'] != record['before']['cpu.stat']['nr_throttled']:
            error = error or 'Session CPU throttling'
        record.update(complete=error is None, stage='error' if error else 'complete')
        if error:
            record['error'] = error
        write_json(ROOT / name / 'manifest.json', record)
        checkpoint(name + '-finished')
        self.current = None
        if error:
            raise RuntimeError(error)

    def run_point(self, label, p, warmup=False, role='candidate'):
        if p['maximum'] != self.sessions[-1]['maximum']:
            raise ValueError('MAX mismatch with loaded engine')
        self.export('point.json', {'label': label, 'point': p, 'session': self.current,
                                   'warmup': warmup, 'role': role})
        rows = []
        for case in self.cases[:3] if warmup else self.cases[3:]:
            row = self.engine.request(case, p['spec'], {'dspark_conf': p['conf'], 'dspark_cum': p['cum']})
            row.update(point_label=label, point=p, session=self.current, role=role)
            path = ROOT / self.current / 'results.jsonl'
            text = json.dumps(row, ensure_ascii=False) + '\n'
            with path.open('a') as f:
                f.write(text)
                f.flush()
            artifact(path, text, append=True)
            checkpoint(label + '-' + case['id'] + '-result')
            self.saved_results += 1
            progress({'point': label, 'case': case['id'], 'decode_tok_s': row['native_tg_tok_s'],
                      'valid': row['valid']})
            if not row['valid']:
                raise ValueError(row['error'])
            rows.append(row)
        if warmup:
            return None
        metrics = score(rows)
        if p['spec'] and not metrics['drafted']:
            raise ValueError('No drafts offered at enabled point')
        entry = {'label': label, 'session': self.current, 'point': p, 'role': role,
                 'metrics': metrics, 'rows': rows}
        self.entries.append(entry)
        self.save_state()
        return entry

    def check_control(self, label, a, b):
        if key(a['point']) != key(b['point']):
            raise ValueError('Nonidentical control tuples')
        delta = drift(a, b)
        self.controls.append({'label': label, 'before': a['label'], 'after': b['label'],
                              'decode_delta_pct': delta, 'passes': abs(delta) <= 5})
        self.save_state()
        if abs(delta) > 5:
            self.state.update(status='drift', blocked_stage=label)
            raise ValueError(f'Control drift {label}: {delta:+.2f}% exceeds 5%; stop without expanding run')

    def unique_candidates(self):
        entries = {}
        for entry in self.entries:
            if entry['point']['spec'] and entry['role'] == 'candidate':
                entries.setdefault(key(entry['point']), entry)
        return list(entries.values())

    def execute(self):
        self.freeze(1, [{'label': 'none', 'point': point(spec=False)},
                        {'label': 'loaded-off', 'point': point(spec=False)},
                        {'label': 'default', 'point': point()}])
        self.start('01-none', loaded=False)
        baseline = self.run_point('none', point(spec=False), role='baseline')
        self.start('02-thresholds')
        self.run_point('loaded-off', point(spec=False), role='baseline')
        default = self.run_point('default', point())

        confs = shuffled([0.3, 0.7], 2)
        self.freeze(2, [point(conf=c) for c in confs], reused_default=default['label'],
                    opening_control=default['label'], closing_control=point())
        conf_entries = [default] + [self.run_point(f'confidence-{c}', point(conf=c)) for c in confs]
        closing = self.run_point('confidence-control', point(), role='control')
        self.check_control('confidence', default, closing)
        conf = choose(conf_entries)['point']['conf']

        cums = shuffled([0, 0.3, 0.7], 3)
        self.freeze(3, [point(conf, u) for u in cums], selected_confidence=conf,
                    reused_cumulative_05=next(e['label'] for e in conf_entries if e['point']['conf'] == conf),
                    opening_control=closing['label'], closing_control=point())
        cum_entries = [e for e in conf_entries if e['point']['conf'] == conf]
        cum_entries += [self.run_point(f'cumulative-{u}', point(conf, u)) for u in cums]
        after = self.run_point('cumulative-control', point(), role='control')
        self.check_control('cumulative', closing, after)
        selected = choose(cum_entries)
        cum = selected['point']['cum']

        caps = shuffled([1, 2, 3], 4)
        self.freeze(4, [point(conf, cum, cap) for cap in caps],
                    reused_maximum_0=selected['label'], selected_thresholds=[conf, cum])
        max_entries = [selected]
        for cap in caps:
            name = {1: '03-max-1', 2: '04-max-2', 3: '05-max-3'}[cap]
            p = point(conf, cum, cap)
            self.start(name, cap, warm=p)
            max_entries.append(self.run_point(f'maximum-{cap}', p))
        selected = choose(max_entries)

        extra = interactions(selected['point'], {key(e['point']) for e in self.unique_candidates()})
        self.freeze(5, extra, selected_point=selected['point'],
                    opening_control=selected['label'], closing_control=selected['point'])
        self.start('06-interactions', selected['point']['maximum'], warm=selected['point'])
        before = self.run_point('interaction-opening-control', selected['point'], role='control')
        self.check_control('selected-MAX-restart', selected, before)
        for i, p in enumerate(extra):
            self.run_point(f'interaction-{i + 1}', p)
        after = self.run_point('interaction-closing-control', selected['point'], role='control')
        self.check_control('interaction', before, after)

        ranked = sorted(self.unique_candidates(), key=lambda e: e['metrics']['decode_tok_s'], reverse=True)
        finalists = ranked[:2]
        self.freeze(6, [e['point'] for e in finalists] + [point(spec=False)],
                    finalist_labels=[e['label'] for e in finalists], baseline=baseline['label'])
        confirmations = []
        for i, entry in enumerate(finalists, 1):
            p = entry['point']
            self.start(f'0{6 + i}-finalist-{i}', p['maximum'], warm=p)
            confirmation = self.run_point(f'finalist-{i}', p, role='confirmation')
            confirmations.append({'original': entry['label'], 'repeat': confirmation['label'],
                                  'decode_delta_pct': drift(entry, confirmation),
                                  'passes': abs(drift(entry, confirmation)) <= 5})
        self.start('09-none-repeat', loaded=False)
        last = self.run_point('none-repeat', point(spec=False), role='baseline')
        self.finish()
        self.state['finalist_confirmation'] = confirmations
        self.check_control('none-fresh-repeat', baseline, last)
        self.state.update(complete=True, status='completed' if all(c['passes'] for c in confirmations)
                          else 'inconclusive-confirmation')
        self.state['ranked_candidates'] = [e['label'] for e in ranked]
        self.state['finalists'] = [e['point'] for e in finalists]

    def finalize(self):
        baseline = next((e for e in self.entries if e['label'] == 'none'), None)
        if baseline:
            for e in self.entries:
                e['decode_gain_pct'] = 100 * (e['metrics']['decode_tok_s'] / baseline['metrics']['decode_tok_s'] - 1)
                e['token_comparison'] = compare_tokens(baseline['rows'], e['rows'])
        self.save_state()


def main():
    if os.environ.get('BENCH_STREAM') != '1':
        raise RuntimeError('Durable acknowledged collector is required')
    sweep = Sweep()
    source_dir = Path(__file__).resolve().parent
    source_files = {'tune.py': source_dir / 'tune.py', 'screen.py': source_dir.parent / 'screen.py',
                    'stream.py': source_dir.parent / 'stream.py', 'summarize.py': source_dir.parent / 'summarize.py'}
    sweep.export('experiment.json', {'seed': SEED, 'cases_sha256': CASES_SHA,
                                    'seed_profile_sha256': PROFILE_SHA,
                                    'sources': {name: sha(path) for name, path in source_files.items()},
                                    'policy': 'stop on invalid request or >5% control drift; no retries'})
    stop = threading.Event()

    def heartbeat():
        while not stop.wait(15):
            text = json.dumps({'session': sweep.current, 'snapshot': snapshot()}) + '\n'
            path = ROOT / 'heartbeat.jsonl'
            with path.open('a') as f:
                f.write(text)
            artifact(path, text, append=True)

    monitor = threading.Thread(target=heartbeat, daemon=True)
    monitor.start()
    try:
        sweep.execute()
    except Exception:
        error = traceback.format_exc()
        sweep.state['error'] = error
        if sweep.state['status'] == 'running':
            sweep.state['status'] = 'failed'
        progress(error)
        try:
            sweep.finish(error)
        except RuntimeError:
            pass
    finally:
        stop.set()
        monitor.join(timeout=5)
        sweep.finalize()
    raise SystemExit(0 if sweep.state['complete'] else 2)


if __name__ == '__main__':
    main()
