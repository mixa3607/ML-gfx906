#!/usr/bin/env python3
"""Export bounded evidence without committing large raw logits or event streams."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    experiment = json.loads((args.root / 'experiment.json').read_text())
    for source, target in (('verified-summary.json', 'summary.json'), ('before.json', 'before.json'),
                           ('gpu-before.txt', 'gpu-before.txt'), ('gpu-after-tests.txt', 'gpu-after-tests.txt')):
        shutil.copyfile(args.root / source, args.output / target)
    for path in args.root.glob('*-vs-*.json'):
        shutil.copyfile(path, args.output / path.name)
    hashes = {}
    for entry in experiment['sessions']:
        name = entry['name']
        source = args.root / name / name
        target = args.output / name
        target.mkdir()
        for filename in ('manifest.json', 'config.json', 'results.jsonl', 'engine.log'):
            path = source / filename
            shutil.copyfile(path, target / filename.replace('.log', '.txt'))
            hashes[str(path.relative_to(args.root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        shutil.copyfile(args.root / name / 'exit.json', target / 'exit.json')
        for path in (args.root / name / 'raw').glob('*.f32'):
            hashes[str(path.relative_to(args.root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (args.output / 'artifact-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')


if __name__ == '__main__':
    main()
