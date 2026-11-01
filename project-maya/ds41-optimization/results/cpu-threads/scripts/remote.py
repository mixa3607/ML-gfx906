"""Use the frozen baseline preparation and run one CPU-thread candidate."""

import datetime
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys

from baseline_remote import DATA, OUT, ROOT, prepare, sha, write_json


def run(cpu):
    assert cpu in (56, 48)
    sys.path.insert(0, str(ROOT))
    from serve.server import child_env, engine_args

    config_path = DATA / 'maya-config.json'
    config = json.loads(config_path.read_text())
    runner, cases = DATA / 'input/run.py', DATA / 'input/cases.jsonl'
    env = child_env(config)
    args = engine_args(config)
    assert args[args.index('--cpu-threads') + 1] == str(cpu)
    assert env['STRATA_DS4_SLOT_KEEP'] == '0'
    resource.setrlimit(resource.RLIMIT_MEMLOCK, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
    cgroup_relative = Path('/proc/self/cgroup').read_text().strip().split('::', 1)[1]
    cgroup = Path('/sys/fs/cgroup') / cgroup_relative.lstrip('/')
    metadata = {
        'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'engine_args': [config['exe'], '--serve', *args],
        'effective_engine_env': {
            k: v for k, v in env.items()
            if (k.startswith(('MAYA_', 'STRATA_', 'DS4_', 'HIP_', 'ROCR_', 'HSA_', 'OMP_', 'HF_', 'TRANSFORMERS_'))
                or k == 'LD_LIBRARY_PATH')
            and not any(word in k for word in ('TOKEN', 'SECRET', 'PASSWORD', 'API_KEY'))
        },
        'request_controls': {'temperature': 0, 'spec': 1},
        'input_sha256': {'runner': sha(runner), 'cases': sha(cases), 'config': sha(config_path)},
        'engine_sha256': sha(Path(config['exe'])),
        'source_commit': (ROOT / 'SOURCE_COMMIT').read_text().strip(),
        'build_id': (ROOT / 'BUILD_ID').read_text().strip(),
        'maya_version': (ROOT / 'VERSION').read_text().strip(),
        'kernel': platform.release(),
        'process_limits': Path('/proc/self/limits').read_text(),
        'rocm_version_files': {
            str(p): p.read_text().strip()
            for p in Path('/opt/rocm/.info').glob('version*') if p.is_file()
        },
        'cpu_topology': subprocess.check_output(['lscpu'], text=True),
        'cpu_affinity': sorted(os.sched_getaffinity(0)),
        'numa_online': Path('/sys/devices/system/node/online').read_text().strip(),
        'smt_active': Path('/sys/devices/system/cpu/smt/active').read_text().strip(),
        'meminfo_before': Path('/proc/meminfo').read_text(),
        'cgroup_path': str(cgroup),
        'cgroup_memory_max': (cgroup / 'memory.max').read_text().strip(),
        'cgroup_cpu_max': (cgroup / 'cpu.max').read_text().strip(),
        'gpu_numa_nodes': {
            p.name: (p / 'numa_node').read_text().strip()
            for p in Path('/sys/bus/pci/devices').iterdir()
            if p.name in ('0000:33:00.0', '0000:36:00.0', '0000:4d:00.0', '0000:50:00.0')
        },
    }
    write_json(OUT / 'run-metadata.json', metadata)
    print(f"Starting CPU{cpu} suite: {metadata['started_utc']}", flush=True)
    with (OUT / 'results.jsonl').open('x') as results, (OUT / 'engine.log').open('x') as log:
        process = subprocess.Popen([
            '/opt/maya/.venv/bin/python', str(runner), '--maya-root', str(ROOT),
            '--config', str(config_path), str(cases),
        ], stdout=subprocess.PIPE, stderr=log, text=True)
        for line in process.stdout:
            results.write(line)
            results.flush()
            print(line, end='', flush=True)
        rc = process.wait()
    metadata['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    metadata['runner_exit_code'] = rc
    metadata['meminfo_after'] = Path('/proc/meminfo').read_text()
    write_json(OUT / 'run-metadata.json', metadata)
    shutil.copyfile(DATA / 'expert-profile.bin', OUT / 'expert-profile.final.bin')
    for name in ('lane-times.txt', 'lt-picks.txt'):
        path = DATA / 'ds4' / name
        if path.exists():
            shutil.copyfile(path, OUT / name)
    print(f"CPU{cpu} suite finished: rc={rc}, {metadata['finished_utc']}", flush=True)
    raise SystemExit(rc)


if __name__ == '__main__':
    if sys.argv[1] == 'prepare':
        prepare()
    elif sys.argv[1] == 'run':
        run(int(sys.argv[2]))
    else:
        raise SystemExit('Expected prepare or run CPU')
