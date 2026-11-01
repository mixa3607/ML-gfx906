"""Prepare or run one approved experiment arm inside its isolated pod."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys


DATA = Path('/data')
ROOT = Path('/opt/maya')
OUT = DATA / 'results'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def prepare():
    OUT.mkdir()
    shutil.copyfile(DATA / 'input/config.json', DATA / 'maya-config.json')
    cache = Path('/root/.cache/huggingface/hub')
    model = cache / 'models--unsloth--DeepSeek-V4.1-Flash-1017-GGUF/snapshots/60ad3651641b5c97679c807e064ab1d7a3ca1455/UD-Q8_K_XL'
    draft = cache / 'models--peasantsmith--DeepSeek-V4.1-Flash-1017-Maya-GGUF/snapshots/d1fc01009f21e26157acb6858c315d0365483b72/dspark'
    vision = DATA / 'vision'
    vision.mkdir()
    for name in ('vision.bin', 'vision.json'):
        source = Path('/prepared/vision') / name
        if not source.is_file():
            raise RuntimeError(f'Missing prepared vision file: {source}; no fallback/download')
        (vision / name).symlink_to(source)
    drafter = DATA / 'drafter'
    drafter.mkdir()
    shutil.copyfile(draft / 'dspark.json', drafter / 'dspark.json')
    (drafter / 'dspark.bin').symlink_to(draft / 'dspark.bin')
    subprocess.run([
        '/opt/maya/.venv/bin/python', 'tools/ds4/pack_gguf.py',
        '--model', str(model), '--out', '/data/ds4', '--vision', str(vision),
        '--drafter', str(drafter / 'dspark.json'),
    ], cwd=ROOT, check=True)
    shutil.copyfile(ROOT / 'data/expert-profile-ds4.bin', DATA / 'expert-profile.bin')
    shutil.copyfile(DATA / 'expert-profile.bin', OUT / 'expert-profile.seed.bin')
    shutil.copyfile(DATA / 'maya-config.json', OUT / 'maya-config.json')
    files = list((DATA / 'ds4').glob('*.txt')) + [DATA / 'ds4/engram.bin']
    write_json(OUT / 'pack-metadata.json', {
        'pack_files_sha256': {str(p): sha(p) for p in files},
        'expert_profile_seed_sha256': sha(OUT / 'expert-profile.seed.bin'),
        'model_revision': '60ad3651641b5c97679c807e064ab1d7a3ca1455',
        'drafter_revision': 'd1fc01009f21e26157acb6858c315d0365483b72',
        'vision_manifest': json.loads((vision / 'vision.json').read_text()),
        'model_shards': [
            {'path': str(p), 'blob': str(p.resolve()), 'bytes': p.stat().st_size}
            for p in sorted(model.glob('*.gguf'))
        ],
    })
    model_source = ROOT / 'src/ds4/ds4_model.cu'
    latent_source = ROOT / 'src/kernels/cuda/glm_lat8.cuh'
    m, l = model_source.read_text(), latent_source.read_text()
    checks = {
        'gfx906_fusion_whitelist': 'constexpr std::array fusion_tested_archs = {"gfx906"}' in m,
        'wave64_fusion_gate': 'hc_fuse && !wave64_fusion_supported' in m,
        'gfx906_signed_zero': '!defined(__gfx906__)' in l,
    }
    write_json(OUT / 'patch-verification.json', {
        'checks': checks,
        'source_sha256': {str(p): sha(p) for p in (model_source, latent_source)},
    })
    if not all(checks.values()):
        raise RuntimeError(f'Expected gfx906 patches missing: {checks}')


def run():
    sys.path.insert(0, str(ROOT))
    from serve.server import child_env, engine_args

    config_path = DATA / 'maya-config.json'
    config = json.loads(config_path.read_text())
    runner, cases = DATA / 'input/run.py', DATA / 'input/cases.jsonl'
    env = child_env(config)
    args = engine_args(config)
    assert args[args.index('--cpu-threads') + 1] == '74'
    assert env['DS4_SKIP_UNPICKED'] in ('0', '1')
    assert env['STRATA_DS4_HC_FUSE'] in ('0', '1', '2')
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
    print(f"Starting suite: {metadata['started_utc']}", flush=True)
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
    print(f"Suite finished: rc={rc}, {metadata['finished_utc']}", flush=True)
    raise SystemExit(rc)


if __name__ == '__main__':
    {'prepare': prepare, 'run': run}[sys.argv[1]]()
