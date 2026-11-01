"""Read pod memory accounting and check the approved Engram-cache budget."""

from pathlib import Path


GIB = 1024 ** 3


def sample():
    relative = Path('/proc/self/cgroup').read_text().strip().split('::', 1)[1]
    group = Path('/sys/fs/cgroup') / relative.lstrip('/')
    meminfo = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    return {
        'cgroup_path': str(group),
        'memory_max': (group / 'memory.max').read_text().strip(),
        'memory_current': int((group / 'memory.current').read_text()),
        'memory_peak': int((group / 'memory.peak').read_text()),
        'memory_events': {k: int(v) for k, v in map(str.split, (group / 'memory.events').read_text().splitlines())},
        'memory_stat': {k: int(v) for k, v in map(str.split, (group / 'memory.stat').read_text().splitlines())},
        'host_mem_available': int(meminfo['MemAvailable'].split()[0]) * 1024,
    }


def cache_budget(before):
    # Rounded baseline pinning size, plus twice the requested payload for cache
    # data/index overhead, and a separate conservative allowance for other work.
    experts = 200_900_000_000
    cache = 4096 * 1024 ** 2
    other = 16 * GIB
    required = experts + 2 * cache + other
    limit = int(before['memory_max'])
    available = min(before['host_mem_available'], limit - before['memory_current'])
    result = {
        'expert_copies_estimate_bytes': experts,
        'cache_payload_bytes': cache,
        'cache_and_index_allowance_bytes': 2 * cache,
        'other_working_allowance_bytes': other,
        'estimated_required_bytes': required,
        'available_bytes': available,
        'allowed': available >= required,
    }
    return result
