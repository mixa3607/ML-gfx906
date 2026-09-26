# Benchmark profiles

`build-bench-command.py` renders a shell command from a named YAML/JSON profile
for `llama-bench`. The profile controls the command, wrappers such as `numactl`,
environment variables, benchmark matrices, and output redirection.

## Usage

Requires Python 3.10+ and PyYAML. From this directory:

```bash
python3 build-bench-command.py --version
python3 build-bench-command.py \
  --source-dir ./profiles \
  --bench gemma-4-31B-it \
  --output ./bench.sh
bash ./bench.sh
```

Use `--output -` to preview the result on stdout. Generating a file does not run
the benchmark. The output contains only the rendered `command`, with a final
newline; no shebang, comments, or shell options are added automatically. The
generator does not set the executable bit. Run it with `bash`, or add a shebang
to `command` and run `chmod +x` yourself.

The destination directory is created if needed, and the output file is replaced
atomically. Parse/render errors leave an existing output file intact and return
a nonzero exit status.

In the container, the generator is at
`/app/bench-profiles/build-bench-command.py`. Invoke it explicitly; the entrypoint
does not generate or run benchmark commands. Relative paths in the generated
command are resolved when it runs, so run the supplied sample from `/app` where
`./llama-bench` is located.

## Profile format and inheritance

The source directory is searched recursively for `.yaml`, `.yml`, and `.json`
files, in sorted path order. All are parsed with `yaml.safe_load_all`, including
support for multiple documents separated by `---`. Files ending in `.sample`
are ignored; copy them into your profiles directory without the `.sample` suffix
to activate them.

Each document maps benchmark names to profiles. Names must be unique across
files and documents. Each profile accepts `command`, `env`, and `args`:

```yaml
"*":
  command: |
    #!/usr/bin/env bash
    set -eo pipefail
    {env} ./llama-bench {args} | tee {profile}.txt
  env:
    HIP_VISIBLE_DEVICES: "0,1"
  args:
    offline: true
    lazy-mode: "off"
    threads: 16

my-bench:
  env:
    HIP_VISIBLE_DEVICES: "1,0"
  args:
    model: /models/model.gguf
    threads: [16, 32]
    offline: null
    flash-attn: true
```

The selected profile is recursively merged over `"*"`:

- Mappings merge by key; lists and scalars replace inherited values.
- `null` removes a key. For example, `args.offline: null` removes the inherited
  option, while `args: null` removes all inherited arguments.
- An empty mapping does not clear inherited settings.
- `command` is inherited unless replaced or removed. The merged profile must
  have a non-empty command.
- `"*"` is reserved for defaults and cannot be selected with `--bench`.

Removing an `env` key omits its assignment from the command; it does not unset a
variable already present in the launching shell's environment. Use `unset` or
`env -u` in `command` if needed.

Quote YAML strings such as `"on"` and `"off"` to prevent PyYAML from treating them
as booleans. Boolean values are rendered as `1` / `0`, except for flag-only
arguments described below.

## Command template

Three markers are substituted in a single pass:

| Marker      | Replacement                                                                  |
| ----------- | ---------------------------------------------------------------------------- |
| `{env}`     | Space-separated `NAME=value` assignments with shell-quoted values            |
| `{args}`    | Arguments generated from the merged `args` mapping, with shell-quoted values |
| `{profile}` | Shell-quoted name selected with `--bench`                                    |

Place markers directly in shell syntax, without surrounding quotes:

```yaml
command: "{env} numactl --membind=0 ./llama-bench {args} | tee {profile}.txt"
```

Arguments and environment assignments appear only where their markers occur;
nothing is prepended or appended automatically. Inserted values are not scanned
again for markers. Other braces are preserved, including shell groups, ordinary
`awk` expressions, and `${env}`, `${args}`, or `${profile}` shell expansions.
The three bare markers themselves are reserved, even inside shell quotes.

Shell expansion in `command` happens when the output is executed. Values in
`env` and `args` are quoted as literal data, so a value such as `$HOME/model.gguf`
does not expand to the home directory.

Use a YAML `|` block to include a shebang, comments, `set -eo pipefail`, or any
other shell setup. In the example above, `pipefail` makes a benchmark failure
propagate through `tee`; this is controlled by the template, not the generator.

## Arguments and benchmark matrices

Use long option names without the `--` prefix. Names are passed through rather
than checked against a complete llama-bench schema. Unlike server profiles,
nested option names are not flattened.

- `help`, `offline`, `verbose`, `progress`, `no-warmup`, and `list-devices` are
  flag-only options: `true` emits the flag, `false` omits it.
- Other booleans produce a value, for example `flash-attn: true` produces
  `--flash-attn 1`, and `no-kv-offload: false` produces `--no-kv-offload 0`.
- Lists describe comma-separated matrix candidates. For example,
  `threads: [16, 32]` produces `--threads 16,32`.
- Nested lists describe compound candidates, joined with `;` by default.
  For `device`, the inner separator is `/`.
- Ready-made strings are preserved. Use them for formats such as numeric ranges
  or other option-specific syntax. Options not supported through the mapping,
  such as the short-only `-pg`, can be written directly in `command`.

Examples (values shown before shell quoting):

| YAML                                | CLI value                    |
| ----------------------------------- | ---------------------------- |
| `n-depth: [0, 16384, 32768]`        | `--n-depth 0,16384,32768`    |
| `device: [[ROCm0, ROCm1], [ROCm0]]` | `--device ROCm0/ROCm1,ROCm0` |
| `tensor-split: [[1, 1], [3, 1]]`    | `--tensor-split 1;1,3;1`     |

llama-bench expands the combinations across its matrix options; the generator
emits one command, not one command per combination. Not every option accepts a
matrix: for example, `repetitions` expects one integer. Choose values supported
by your llama-bench build.

### Tensor overrides

`override-tensor` accepts a ready-made string or a list of variants. Each variant
is a list of groups; each group contains exactly `tensors` and `target`:

```yaml
my-bench:
  args:
    override-tensor:
      - [] # Baseline: no tensor overrides
      - - tensors: ['blk\.0\.ffn_(up|down)_exps\.weight']
          target: CPU
        - tensors: ['blk\.1\.ffn_(up|down)_exps\.weight']
          target: CPU
```

Variants are separated by `,`, groups within a variant by `;`, and tensor
patterns within a group by `|` inside parentheses. An empty variant represents
the baseline without overrides. Regex patterns are not escaped or rewritten.

Shell quoting preserves characters such as spaces, `#`, `;`, and newlines in
argument values. It does not escape llama-bench's own separators: commas in
matrix values, `/` in device groups, and `;` / `=` in tensor overrides are still
interpreted by llama-bench. Use values compatible with that syntax.

See [global.json.sample](global.json.sample) and
[gemma-4-31b-it.yaml.sample](gemma-4-31b-it.yaml.sample). Adjust model paths,
CPU/NUMA placement, device names, and benchmark sizes for your machine.
