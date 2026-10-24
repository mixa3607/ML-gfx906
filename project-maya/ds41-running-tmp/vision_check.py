#!/usr/bin/env python3
"""Native GENI vision smoke/parity with the upstream image frontend, not a TG benchmark."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from native_bench import Engine, dump_hashes, parse_done, snapshot


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def check_config(config, images, directory):
    sys.path[:0] = ['/opt/maya', '/opt/maya/tools']
    from serve.ds4_vision import Geometry, Vision
    from serve.frontend import ChatTemplate, openai_to_messages
    from strata_tokenizer import Tokenizer

    directory.mkdir()
    cfg = json.loads(config.read_text())
    save(directory / 'config.json', cfg)
    engine = Engine(cfg, directory, dump=True)
    results = []
    try:
        ready = engine.ready(1800)
        info = {}
        for line in ready:
            if line.startswith('INFO '):
                for item in line.split()[1:]:
                    k, v = item.split('=', 1)
                    info[k] = int(v) if v.lstrip('-').isdigit() else v
        if info.get('vision') != 'ds4' or 'READY 196608 stop' not in ready:
            raise RuntimeError('Native vision or context 196608 not available')
        if cfg.get('require_full_copies'):
            log = (directory / 'engine.log').read_text()
            counts = re.search(r"(\d+) of the CPU lane's (\d+) experts copied into RAM", log)
            if not counts or counts[1] != counts[2]:
                raise RuntimeError('Incomplete expert copies')
        save(directory / 'ready.json', {'lines': ready, 'snapshot': snapshot(engine.proc.pid)})
        tok = Tokenizer.from_dir('/data/ds4/tokenizer')
        template = ChatTemplate('/data/ds4/tokenizer/chat_template.jinja')
        vision = Vision(Geometry.from_info(info), directory,
                        lambda uri: base64.b64decode(uri.split(',', 1)[1]))
        for image in images:
            uri = 'data:image/png;base64,' + base64.b64encode(image.read_bytes()).decode()
            body = {'messages': [{'role': 'user', 'content': [
                {'type': 'image_url', 'image_url': {'url': uri}},
                {'type': 'text', 'text': 'Опиши изображение по-русски. Назови цвета и формы видимых фигур, если они есть.'}]}],
                'reasoning_effort': 'none', 'temperature': 0, 'seed': 1, 'max_tokens': 256}
            messages, tools, kwargs = openai_to_messages(body, deepseek=True)
            ids = tok.encode(template.render(messages, tools=tools, **kwargs), parse_special=True)
            picture = vision.picture(uri)
            ids, starts = vision.expand(ids, [picture])
            dsi = vision.write(directory / f'{image.stem}.dsi', [picture], starts)
            engine.count += 1
            tokens, stats = [], []
            started = time.monotonic()
            line = f'GENI 256 temperature=0 seed=1 spec=0 {dsi} ' + ','.join(map(str, ids)) + '\n'
            engine.proc.stdin.write(line.encode())
            engine.proc.stdin.flush()
            while True:
                line = engine.line(started + 1800)
                if line.startswith('T '):
                    tokens.append(int(line.split()[1]))
                elif line.startswith('STAT '):
                    stats.append(line)
                elif line.startswith('ERR '):
                    raise RuntimeError(line)
                elif line.startswith('DONE '):
                    done = parse_done(line)
                    break
            if not tokens or done['tg'] != len(tokens) or done['pp'] != len(ids):
                raise RuntimeError(f'Incomplete image response: {done}')
            if done['reused'] or done['drafted'] or done['accepted'] or done['finish'] not in ('stop', 'length'):
                raise RuntimeError(f'Invalid image smoke: {done}')
            path = directory / f'logits.{engine.count}.f32'
            hashes = dump_hashes(path)
            if len(hashes['rows']) != len(tokens):
                raise RuntimeError('Image logit row count differs from output token count')
            path.unlink()
            row = {'case': image.stem, 'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
                   'prompt_tokens': len(ids), 'resized_pixels': [picture.width, picture.height],
                   'image_tokens': picture.tokens, 'tokens': tokens, 'text': tok.decode(tokens),
                   'done': done, 'logits': hashes, 'stats': stats, 'snapshot': snapshot(engine.proc.pid)}
            results.append(row)
            save(directory / f'{image.stem}.json', row)
            print(json.dumps({'config': cfg['name'], 'case': image.stem, 'text': row['text']},
                             ensure_ascii=False), flush=True)
    finally:
        engine.close()
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    from PIL import Image, ImageDraw

    blank = Image.new('RGB', (512, 512), 'white')
    shapes = blank.copy()
    draw = ImageDraw.Draw(shapes)
    draw.rectangle((30, 80, 230, 430), fill='red')
    draw.ellipse((280, 150, 490, 360), fill='blue')
    shapes.save(a.out / 'shapes.png')
    blank.save(a.out / 'blank.png')
    images = [a.out / 'shapes.png', a.out / 'blank.png']
    left = check_config(a.baseline, images, a.out / 'reference')
    right = check_config(a.candidate, images, a.out / 'candidate')
    repeat = check_config(a.baseline, images, a.out / 'reference-repeat')
    cases = [{'case': x['case'], 'tokens_equal': x['tokens'] == y['tokens'],
              'full_logits_equal': x['logits']['rows'] == y['logits']['rows'],
              'reference_repeat_equal': x['tokens'] == z['tokens'] and
               x['logits']['rows'] == z['logits']['rows']}
             for x, y, z in zip(left, right, repeat)]
    verdict = {'cases': cases, 'bit_exact_on_tested_images':
               all(r['tokens_equal'] and r['full_logits_equal'] and r['reference_repeat_equal'] for r in cases)}
    save(a.out / 'verdict.json', verdict)
    print(json.dumps(verdict, indent=2), flush=True)
    if not verdict['bit_exact_on_tested_images']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
