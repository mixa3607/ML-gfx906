#!/usr/bin/env python3
"""Keep an existing exec process's pipes readable and await its exit via pidfd."""
import os
import selectors
import sys

pid = int(sys.argv[1])
selector = selectors.DefaultSelector()
pidfd = os.pidfd_open(pid)
selector.register(pidfd, selectors.EVENT_READ, 'exit')
for number in (1, 2):
    fd = os.open(f'/proc/{pid}/fd/{number}', os.O_RDONLY | os.O_NONBLOCK)
    selector.register(fd, selectors.EVENT_READ, 'pipe')
while True:
    events = selector.select()
    exited = any(key.data == 'exit' for key, _ in events)
    for key, _ in events:
        if key.data != 'pipe':
            continue
        try:
            data = os.read(key.fd, 65536)
        except BlockingIOError:
            continue
        if data:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        else:
            selector.unregister(key.fd)
            os.close(key.fd)
    if exited:
        break
selector.close()
os.close(pidfd)
