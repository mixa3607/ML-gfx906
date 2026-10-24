#!/usr/bin/env python3
"""Bounded full-context fact retrieval with natural EOS; not a TG256 benchmark."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import sys

from full_compute import validate_config, validate_limits
from native_bench import Engine, dump_hashes, emit_event, snapshot


MAX_PROBE_PP = 65536
YOCO_KEEP = 20 * (128 - 1) + 128  # Fixed model: layers 20–39, 128-row SWA.


def yoco_activation_verified(lines, lengths):
    expected = {n for n in lengths if n - YOCO_KEEP >= 1024}
    observed = set()
    for line in lines:
        match = re.search(r'prompt skip: layers (\d+)-(\d+) from CUDA\d+, (\d+) early rows KV-only, (\d+) kept', line)
        if not match:
            return False
        first, last, early, kept = map(int, match.groups())
        if (first, last, kept) != (20, 39, YOCO_KEEP):
            return False
        observed.add(early + kept)
    return bool(expected) and expected <= observed


def validate_probe_length(length):
    if length <= 0 or length % 2048 or length > MAX_PROBE_PP:
        raise ValueError('Context probe PP must be a positive multiple of 2048, at most 65536')


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def assemble(prefix, suffix, filler, facts, length):
    """Put whole fact spans near the beginning/middle/end, never cut them."""
    positions = (128, length // 2, length - len(suffix) - len(facts[-1]) - 128)
    ids = list(prefix)
    used, spans = 0, []
    for at, fact in zip(positions, facts):
        need = at - len(ids)
        if need < 0 or used + need > len(filler):
            raise ValueError('Insufficient source text or overlapping fact spans')
        ids += filler[used:used + need]
        used += need
        spans.append([len(ids), len(ids) + len(fact)])
        ids += fact
    need = length - len(suffix) - len(ids)
    if need < 0 or used + need > len(filler):
        raise ValueError('Insufficient unique source text; do not repeat filler')
    ids += filler[used:used + need] + suffix
    if len(ids) != length:
        raise ValueError('Incorrect complete prompt length')
    return ids, spans, used + need


def score(text, expected):
    plain = text.replace('*', '').replace('`', '')
    return {name: bool(re.search(re.escape(name) + r'\s*[:—–-]\s*' + re.escape(code) + r'\b',
                                 plain, re.IGNORECASE)) for name, code in expected.items()}


def prepare(a):
    sys.path[:0] = ['/opt/maya', '/opt/maya/tools']
    from strata_tokenizer import Tokenizer
    from serve.frontend import ChatTemplate

    tok = Tokenizer.from_dir('/data/ds4/tokenizer')
    template = ChatTemplate('/data/ds4/tokenizer/chat_template.jinja')
    docs = [json.loads(s) for s in a.source.read_text().splitlines() if s.strip()]
    # Synthetic QA uses development prose, not final holdout articles.
    docs = [d for d in docs if d['split'] == 'dev']
    random.Random(a.seed).shuffle(docs)
    filler = tok.encode('\n\n'.join(d['title'] + '\n' + d['text'] for d in docs), parse_special=False)
    cases, cursor = [], 0
    for index, length in enumerate(a.pp):
        validate_probe_length(length)
        rng = random.Random(a.seed + index)
        names = ('Ладога-17', 'Вега-43', 'Кедр-82')
        expected = {name: str(rng.randrange(100000, 1000000)) for name in names}
        facts = [tok.encode(f'\n\nКонтрольная запись «{name}»: код {code}.\n\n', parse_special=False)
                 for name, code in expected.items()]
        question = ('\n\nНайди в материалах три контрольные записи: ' + ', '.join(names) +
                    '. Верни только три строки в формате «название: код». Не придумывай коды.\n')
        lead = ('Северный' if index % 2 == 0 else 'Южный') + f' архив {a.seed + index}.\nМатериалы:\n'
        rendered = template.render([{'role': 'user', 'content': lead + '__DOCUMENTS__' + question}],
                                   reasoning_effort='none')
        before, after = rendered.split('__DOCUMENTS__')
        prefix = tok.encode(before, parse_special=True)
        suffix = tok.encode(after, parse_special=True)
        ids, spans, consumed = assemble(prefix, suffix, filler[cursor:], facts, length)
        cursor += consumed
        for (start, end), fact in zip(spans, facts):
            if ids[start:end] != fact:
                raise ValueError('Fact span was altered')
        cases.append({'id': f'context-{a.seed}-{index}-pp{length}', 'phase': 'functional',
                      'pp': length, 'expected': expected, 'fact_spans': spans,
                      'source_sha256': hashlib.sha256(a.source.read_bytes()).hexdigest(),
                      'prompt_sha256': hashlib.sha256(json.dumps(ids).encode()).hexdigest(), 'ids': ids})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('x') as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')
    print(f'Prepared {len(cases)} context probes, PP {a.pp}, {cursor} unique filler tokens', flush=True)


def run(a):
    sys.path.insert(0, '/opt/maya/tools')
    from strata_tokenizer import Tokenizer

    cfg = json.loads(a.config.read_text())
    eligibility = validate_config(cfg)
    validate_limits(snapshot())
    cases = [json.loads(s) for s in a.cases.read_text().splitlines() if s.strip()]
    if not cases or any(c['phase'] != 'functional' or len(c['ids']) != c['pp'] for c in cases):
        raise ValueError('Invalid context probe cases')
    for case in cases:
        validate_probe_length(case['pp'])
    a.out.mkdir(parents=True, exist_ok=False)
    save(a.out / 'config.json', cfg)
    manifest = {'cases_sha256': hashlib.sha256(a.cases.read_bytes()).hexdigest(),
                                 'config_sha256': hashlib.sha256(a.config.read_bytes()).hexdigest(),
                                 'seed_profile_sha256': hashlib.sha256(Path(cfg['seed_profile']).read_bytes()).hexdigest(),
                                 'source_commit': Path('/opt/maya/SOURCE_COMMIT').read_text().strip(),
                                 'build': json.loads(Path('/opt/maya/build-hip/MAYA-BUILD.json').read_text()),
                                 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                 'policy': eligibility, 'functional_not_tg256_benchmark': True}
    save(a.out / 'manifest.json', manifest)
    emit_event('manifest', manifest)
    tok = Tokenizer.from_dir('/data/ds4/tokenizer')
    results = []
    vision_checks = None
    engine = Engine(cfg, a.out, dump=True)
    try:
        ready = engine.ready(a.timeout)
        ready_record = {'lines': ready, 'snapshot': snapshot(engine.proc.pid)}
        save(a.out / 'ready.json', ready_record)
        emit_event('ready', ready_record)
        if (not any(line.startswith('READY 196608 ') for line in ready) or
                not any(line.startswith('INFO ') and 'vision=ds4 ' in line for line in ready)):
            raise RuntimeError('Full context or native vision unavailable')
        if cfg.get('require_full_copies'):
            match = re.search(r"(\d+) of the CPU lane's (\d+) experts copied into RAM",
                              (a.out / 'engine.log').read_text())
            if not match or match[1] != match[2]:
                raise RuntimeError('Incomplete RAM copies')
        with (a.out / 'results.jsonl').open('x') as f:
            for case in cases:
                print(f'START functional {case["id"]}', flush=True)
                row = engine.request(case, a.timeout, 128, benchmark=False)
                path = a.out / f'logits.{engine.count}.f32'
                row['logits'] = dump_hashes(path)
                if len(row['logits']['rows']) != row['done']['tg']:
                    raise RuntimeError('Missing functional logit rows')
                path.unlink()
                row['text'] = tok.decode(row['tokens'])
                row['retrieved'] = score(row['text'], case['expected'])
                results.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                f.flush()
                emit_event('result', row)
                print(json.dumps({'id': case['id'], 'retrieved': row['retrieved'], 'text': row['text']},
                                 ensure_ascii=False), flush=True)
        if a.vision:
            from vision_check import check_config, create_images, image_checks

            images = create_images(a.out)
            vision_rows = check_config(a.config, images, a.out / 'vision', engine=engine, ready=ready)
            vision_checks = image_checks(vision_rows)
    finally:
        engine.close()
    log = (a.out / 'engine.log').read_text()
    activation = re.findall(r'ds4: prompt skip:.*', log)
    active_required = cfg['env']['STRATA_DS4_PROMPT_SKIP'] == '1'
    verdict = {'all_facts_retrieved': all(all(r['retrieved'].values()) for r in results),
               'finite_on_tested_rows': True, 'prompt_skip_activation': activation,
               'activation_verified': yoco_activation_verified(activation, [c['pp'] for c in cases])
                                      if active_required else not activation,
               'expected_yoco_retention_rows': YOCO_KEEP if active_required else None,
               'vision_checks': vision_checks,
               'not_a_general_quality_proof': True}
    save(a.out / 'verdict.json', verdict)
    emit_event('verdict', verdict)
    if (not verdict['all_facts_retrieved'] or not verdict['activation_verified'] or
            (vision_checks is not None and not all(vision_checks.values()))):
        raise SystemExit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--source', type=Path, required=True)
    prep.add_argument('--pp', type=int, nargs='+', default=[65536])
    prep.add_argument('--seed', type=int, default=20261025)
    prep.add_argument('--out', type=Path, required=True)
    check = sub.add_parser('run')
    check.add_argument('--config', type=Path, required=True)
    check.add_argument('--cases', type=Path, required=True)
    check.add_argument('--out', type=Path, required=True)
    check.add_argument('--timeout', type=int, default=14400)
    check.add_argument('--vision', action='store_true', help='Also check images in the same loaded engine')
    a = p.parse_args()
    (prepare if a.command == 'prepare' else run)(a)


if __name__ == '__main__':
    main()
