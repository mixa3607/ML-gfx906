"""Reuse the recorded CPU48 runner, adding memory accounting and preflight."""

import sys

from cpu_remote import OUT, prepare, run
from baseline_remote import write_json
from memory_probe import cache_budget, sample


if __name__ == '__main__':
    if sys.argv[1] == 'prepare':
        prepare()
    elif sys.argv[1] == 'run':
        arm = sys.argv[2]
        memory = {'before': sample()}
        if arm == 'engram-cache':
            memory['cache_budget'] = cache_budget(memory['before'])
        write_json(OUT / 'memory.json', memory)
        if arm == 'engram-cache' and not memory['cache_budget']['allowed']:
            raise SystemExit('Insufficient estimated RAM budget for cache=4096; no engine run or fallback')
        try:
            run(48)
        finally:
            memory['after'] = sample()
            write_json(OUT / 'memory.json', memory)
    else:
        raise SystemExit('Expected prepare or run ARM')
