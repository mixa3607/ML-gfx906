"""Check compile provenance and smoke tests in an experimental test image."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

root = Path('/opt/maya')
build = root / 'build-hip'
expected = os.environ['MAYA_EXPERIMENT_EXPECTED']
assert (root / 'SOURCE_COMMIT').read_text().strip() == 'ffe2e5e53fd5254e7f3492a20e8ad2b51b26a197'
meta = json.loads((root / 'SOURCE_EXPERIMENT.json').read_text())
assert meta['name'] == expected
assert meta['patch_sha256'] == os.environ['MAYA_EXPERIMENT_PATCH_SHA256']
stamp = json.loads((build / 'MAYA-BUILD.json').read_text())
assert stamp['experiment'] == meta and stamp['archs'] == ['gfx906']
flags = '-mllvm -amdgpu-sched-strategy=max-ilp'
assert stamp['hip_flags'] == flags
assert 'CMAKE_HIP_FLAGS:STRING=' + flags + '\n' in (build / 'CMakeCache.txt').read_text()
commands = json.loads((build / 'compile_commands.json').read_text())
hip = [row for row in commands if row['file'].endswith('.cu')]
assert hip
for row in hip:
    args = shlex.split(row['command'])
    assert args[args.index('-mllvm') + 1] == '-amdgpu-sched-strategy=max-ilp', row['file']
print('COMPILE PROOF', json.dumps({'hip_units': len(hip), 'stamp': stamp,
      'ds4_sha256': hashlib.sha256((build / 'maya-ds4').read_bytes()).hexdigest()}), flush=True)
subprocess.run(['/usr/local/bin/maya-test'], cwd=root, check=True)
subprocess.run(['ctest', '--test-dir', str(build), '--output-on-failure', '--no-tests=error',
                '-R', '^ds4_(prefill_stats|ram_slice)_test$'], check=True)
