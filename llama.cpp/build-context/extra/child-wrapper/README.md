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

## Server profiles wrapper

Set `M36_LLAMA_CHILD_WRAPPER=/app/server-profiles/profiles-wrapper.py` to use
`child-wrapper` options from the YAML/JSON server profiles. The entrypoint
exports the resolved `M36_LLAMA_MODELS_PRESETS_DIR` for the wrapper. Profiles
are reread on each child launch using the INI generator's loader.
`child-wrapper` is omitted from the generated INI.

```yaml
my-model:
  hf-repo: owner/model-GGUF
  child-wrapper:
    env:
      LLAMA_ARG_LOG_VERBOSITY: "4"
      HIP_VISIBLE_DEVICES: null
    command: "{env} numactl --interleave=all {exe} {args}"
```

The preset is selected by `--alias NAME`, `--alias=NAME` or `-a NAME`.
Model-specific environment keys and command override defaults from `*`.
Unknown aliases use only `*`; without an alias, the wrapper launches the binary
directly. Disabled profiles are ignored.

Environment values are converted to strings; `null` removes a variable.
Omit `command` for a direct launch, or use `command: null` to clear an inherited
command. Templates require `{exe}` and `{args}`; leave them unquoted because
the wrapper shell-quotes the substitutions. `{env}` expands to an empty string:
environment updates are applied directly.

Commands are trusted Bash templates. Use a single command, not pipelines or
background jobs: the wrapper prefixes it with `exec` to preserve the child PID.

```bash
python3 llama.cpp/build-context/extra/server-profiles/test_profiles_wrapper.py
```

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
