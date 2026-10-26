#!/usr/bin/env python3
"""Keep code-local inputs while defeating native in-process prefix restoration."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def main():
    sys.path[:0] = ['/opt/maya', '/opt/maya/tools']
    from strata_tokenizer import Tokenizer
    from serve.frontend import ChatTemplate
    tok = Tokenizer.from_dir('/data/ds4/tokenizer')
    template = ChatTemplate(Path('/data/ds4/tokenizer/chat_template.jinja'))
    source = (ROOT / 'typescript-source.ts').read_text()
    suffix = tok.encode('<｜Assistant｜></think>', parse_special=True)
    cases = []
    for index in range(24):
        phase = 'warmup' if index < 12 else 'measurement'
        content = f'// Request nonce: {index + 1:04d}\n' + source
        text = template.render([{'role': 'user', 'content': content}], reasoning_effort='none')
        ids = tok.encode(text, parse_special=True)
        if ids[-len(suffix):] != suffix or len(ids) < 2048:
            raise ValueError('Unexpected template or short source')
        ids = ids[:2048 - len(suffix)] + suffix
        raw = b''.join(tok.token_bytes(t) for t in ids)
        cases.append({'id': f'typescript-{phase}-{index % 12 + 1:02d}', 'phase': phase,
                      'lead_title': 'Cache-local TypeScript export continuation', 'pp': 2048,
                      'request_nonce': index + 1, 'ids': ids,
                      'prompt_sha256': hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
                      'rendered_bytes_hex': raw.hex(), 'rendered_text': raw.decode('utf-8'),
                      'intentional_same_code_pattern': True})
    for i, a in enumerate(cases):
        for b in cases[i + 1:]:
            first = next((j for j, (x, y) in enumerate(zip(a['ids'], b['ids'])) if x != y), None)
            if first is None or first >= 32:
                raise ValueError('Nonce must differ near the prompt start')
    out = ROOT / 'code-cases-nonce.jsonl'
    with out.open('x') as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')
    manifest = json.loads((ROOT / 'cases.manifest.json').read_text())
    manifest['code'].update(unique_prompts=24, nonce_policy='unique leading TypeScript comment; same code pattern',
                            correction='exact repeats restored 2047 KV tokens in attempt1')
    manifest['files'][out.name] = hashlib.sha256(out.read_bytes()).hexdigest()
    (ROOT / 'cases-nonce.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Frozen 24 PP2048 code prompts with distinct early nonces; Russian inputs unchanged')


if __name__ == '__main__':
    main()
