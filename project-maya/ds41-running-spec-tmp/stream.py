"""Small acknowledged stdout transport; timings are captured before checkpoints."""
import json
import os
from pathlib import Path
import sys
import threading

ROOT = Path('/data/screen')
LOCK = threading.Lock()


def emit(record):
    if os.environ.get('BENCH_STREAM') == '1':
        with LOCK:
            print('SCREEN_EVENT ' + json.dumps(record, ensure_ascii=False), flush=True)


def artifact(path, data, append=False):
    emit({'kind': 'artifact', 'path': str(path.relative_to(ROOT)), 'data': data, 'append': append})


def write_json(path, value):
    text = json.dumps(value, indent=2) + '\n'
    path.write_text(text)
    artifact(path, text)


def progress(value):
    emit({'kind': 'progress', 'value': value})


def checkpoint(label):
    if os.environ.get('BENCH_STREAM') != '1':
        return
    emit({'kind': 'checkpoint', 'label': label})
    if sys.stdin.readline().strip() != 'ACK ' + label:
        raise RuntimeError('Collector disconnected or did not acknowledge durable evidence')
