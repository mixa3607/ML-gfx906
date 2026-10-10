# Router child wrapper (Linux PoC)

No llama.cpp source changes are needed. The preload library intercepts
`posix_spawn` and `posix_spawnp` when the executable path exactly matches
`readlink("/proc/self/exe")` and `M36_LLAMA_CHILD_WRAPPER` is nonempty.
Other spawns are passed through unchanged. Bare names searched through `PATH`,
relative paths and symlink aliases are not matched.

The image builds `/app/child-wrapper/spawn-hook.so`. Its entrypoint adds this
library to `LD_PRELOAD` only when `M36_LLAMA_CHILD_WRAPPER` is set, preserving
existing preload entries.

For example, add this environment variable to your usual router container run:

```bash
-e M36_LLAMA_CHILD_WRAPPER=/app/child-wrapper/example.sh
```

For a custom wrapper, mount an executable script and set the variable to its
absolute container path. A missing/nonexecutable wrapper causes spawn to fail;
there is no silent fallback. The script must have a shebang.

The wrapper receives the original executable as `$1`, followed by its arguments
(excluding the original `argv[0]`). File actions, spawn attributes and the child
environment are forwarded unchanged. Use `exec "$binary" "$@"` to preserve the
child PID. Unset `M36_LLAMA_CHILD_WRAPPER` in the wrapper to disable interception
in descendants. Do not consume stdin or write diagnostics to stdout: these are
used by the router protocol. Send diagnostics to stderr instead.

This PoC requires a dynamically linked Linux executable. It does not intercept
fork/exec-based launch paths or static binaries.

Run the standalone tests (requires Python 3 and a C compiler):

```bash
python3 llama.cpp/build-context/extra/child-wrapper/test_spawn_hook.py
```
