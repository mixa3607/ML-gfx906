#!/usr/bin/env python3
"""Extract the pinned PR 520 transfer-only delta; do not change quant formats."""
import argparse
import difflib
from pathlib import Path
import re
import shutil
import subprocess


def extract(repo):
    head = 'b5eb8ca76cce399121d1a15c7cc0f42895483c72'
    diff = subprocess.check_output(
        ['git', 'diff', head + '^', head, '--', 'src/ds4/ds4_model.cu'],
        cwd=repo, text=True)
    hunks = re.split(r'(?=^@@ )', diff, flags=re.MULTILINE)
    wanted = {2245, 3894, 3905, 3924, 5558, 5721, 8139, 8262}
    selected = [h for h in hunks[1:]
                if int(re.match(r'@@ -(\d+)', h)[1]) in wanted]
    if len(selected) != len(wanted):
        raise ValueError('Pinned PR hunk layout changed')
    header = '\n'.join(line for line in hunks[0].splitlines()
                       if not line.startswith('index ')) + '\n'
    return ("PR 520: transfer-only extraction, upstream head " + head + "\n"
            "Source: https://github.com/mw00/project-maya/pull/520\n"
            "Author: needmorevram. Quant/model support and arithmetic changes omitted.\n"
            "Rebased on v1.1.30; see the experiment README for scope and checks.\n\n"
            + header + ''.join(selected))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--bundle', action='store_true',
                        help='write a build patch directory including the existing gfx906 fixes')
    parser.add_argument('--worktree', type=Path)
    parser.add_argument('--prune-worktree', type=Path)
    args = parser.parse_args()
    if args.bundle:
        args.output.mkdir(parents=True, exist_ok=False)
        base = Path(__file__).resolve().parent.parent / 'build-context/patch/v1.1.25'
        for patch in sorted(base.glob('*.patch')):
            shutil.copyfile(patch, args.output / patch.name)
        # The worktree already has the two gfx906 patches applied. Exclude those files.
        delta = subprocess.check_output(
            ['git', 'diff', '--', 'src/ds4/ds4_model.cu'], cwd=args.worktree, text=True)
        (args.output / '30-pr520-transfer.patch').write_text(
            extract(args.repo).split('diff --git', 1)[0] + delta)
        if args.prune_worktree:
            name = 'src/ds4/ds4_model.cu'
            before = (args.worktree / name).read_text().splitlines(keepends=True)
            after = (args.prune_worktree / name).read_text().splitlines(keepends=True)
            diff = ''.join(difflib.unified_diff(before, after, 'a/' + name, 'b/' + name))
            (args.output / '40-pr297-prune.patch').write_text(
                'PR 297, 6f72b39cd0a793f5e4cd6037d37fe348dc7cdc4d, author LostVector.\n'
                'https://github.com/mw00/project-maya/pull/297\n'
                'Ported onto the PR 520 compact reader; no second read_mx_member.\n'
                'Only picked members stage/copy; counters are emitted by report_prefill.\n\n'
                'diff --git a/' + name + ' b/' + name + '\n' + diff)
    else:
        args.output.write_text(extract(args.repo))


if __name__ == '__main__':
    main()
