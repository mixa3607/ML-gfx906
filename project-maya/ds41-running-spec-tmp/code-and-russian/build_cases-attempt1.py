#!/usr/bin/env python3
"""Freeze one deliberately repetitive TS prefix and the original Russian recipe."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ts_source():
    header = '''// Continue this TypeScript module with the next 128 exports in the same pattern.
// Output only the continuation: no explanations, no Markdown, no repeated prefix.
export type Entry = Readonly<{ id: number; name: string; enabled: boolean }>;

'''
    return header + ''.join(f'export const entry{i:04d}: Entry = {{ id: {i}, name: "entry{i:04d}", enabled: true }};\n'
                            for i in range(200))


def main():
    sys.path[:0] = ['/opt/maya', '/opt/maya/tools']
    from strata_tokenizer import Tokenizer
    from serve.frontend import ChatTemplate
    tokenizer = Path('/data/ds4/tokenizer')
    tok = Tokenizer.from_dir(str(tokenizer))
    template = ChatTemplate(tokenizer / 'chat_template.jinja')
    source = ts_source()
    (ROOT / 'typescript-source.ts').write_text(source)
    suffix = tok.encode('<｜Assistant｜></think>', parse_special=True)
    rendered = template.render([{'role': 'user', 'content': source}], reasoning_effort='none')
    ids = tok.encode(rendered, parse_special=True)
    if ids[-len(suffix):] != suffix or len(ids) <= 2048:
        raise ValueError('Unexpected tokenizer/template or short TypeScript source')
    ids = ids[:2048 - len(suffix)] + suffix
    data = b''.join(tok.token_bytes(t) for t in ids)
    code = []
    for phase in ('warmup', 'measurement'):
        for i in range(12):
            code.append({'id': f'typescript-{phase}-{i + 1:02d}', 'phase': phase,
                         'lead_title': 'Repeated TypeScript export continuation', 'pp': 2048,
                         'ids': ids, 'prompt_sha256': digest(json.dumps(ids).encode()),
                         'rendered_bytes_hex': data.hex(), 'rendered_text': data.decode('utf-8'),
                         'intentional_exact_repetition': True})
    with (ROOT / 'code-cases.jsonl').open('x') as f:
        for case in code:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')
    spec = importlib.util.spec_from_file_location('original_corpus', ROOT.parents[1] / 'ds41-running-tmp/corpus.py')
    corpus = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(corpus)
    corpus.build_cases(ROOT / 'russian-sources.jsonl', ROOT / 'russian-warm.jsonl',
                       'warmup', [2048], 12, 20261024, str(tokenizer))
    corpus.build_cases(ROOT / 'russian-sources.jsonl', ROOT / 'russian-measurement.jsonl',
                       'dev', [2048, 4096, 8192], 6, 20261024, str(tokenizer))
    russian = []
    for file in ('russian-warm.jsonl', 'russian-measurement.jsonl'):
        for line in (ROOT / file).read_text().splitlines():
            case = json.loads(line)
            case['phase'] = 'warmup' if case['phase'] == 'warmup' else 'measurement'
            raw = b''.join(tok.token_bytes(t) for t in case['ids'])
            case.update(rendered_bytes_hex=raw.hex(), rendered_text=raw.decode('utf-8', errors='replace'))
            russian.append(case)
    with (ROOT / 'russian-cases.jsonl').open('x') as f:
        for case in russian:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')
    manifest = {'code': {'requests': 24, 'unique_prompts': 1, 'purpose': 'intentional hot-expert/high-acceptance workload'},
                'russian': {'requests': 18, 'warmups': 12, 'measurement_pp': [2048, 4096, 8192] * 2,
                            'seed': 20261024, 'original_full_corpus_available': False,
                            'policy': 'original recipe; retained six source revisions, refetched remaining thirty'},
                'files': {name: digest((ROOT / name).read_bytes()) for name in
                          ('code-cases.jsonl', 'russian-cases.jsonl', 'russian-sources.jsonl', 'typescript-source.ts')},
                'tokenizer_files': {p.name: digest(p.read_bytes()) for p in tokenizer.iterdir() if p.is_file()}}
    (ROOT / 'cases.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
