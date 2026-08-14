# AMD Memory Tweak for MI50

Builds a Debian package from a vendored, minimally patched copy of AMD Memory
Tweak with the Vega20 MI50 device ID fix and structured JSON output.

The original AMD Memory Tweak was written by Elio VP and A. Solodovnikov:
https://github.com/Eliovp/amdmemorytweak. See `build-context/NOTICE` and the
copyright header in `build-context/AmdMemTweak.cpp`.

## Package contents

```text
/usr/bin/amdmemtweak
```

`amdmemtweak` reads and writes AMD memory-controller registers through
`amdgpu_regs` in debugfs. It requires root and direct GPU access.

## Build

Prerequisites:

- Docker with the `buildx` plugin
- Network access to Ubuntu package repositories

```bash
. preset.v0.1.9.1.sh
./build-and-push.deb.sh
```

Artifacts are written to `output/amt-<version>-<suffix>/`. Build logs are saved
under `logs/`.

Build variables:

| Variable | Default | Description |
|---|---|---|
| `AMT_VERSION` | `0.0.0` | Debian upstream version |
| `AMT_BASE_IMAGE` | `ubuntu:24.04` | Build container image |
| `AMT_PUSH` | `0` | Push the resulting deb over SCP |
| `AMT_FORCE_BUILD` | `0` | Rebuild an existing output directory |

## Install

> `amd-memory-tweak` is available from the [gfx906 APT repository](../README.md#add-the-repository-ubuntu-2404).

```bash
apt-get install ./amd-memory-tweak_*.deb
```

Mount debugfs if the host or privileged container does not already expose it:

```bash
mount -t debugfs debugfs /sys/kernel/debug
```

## Usage

Inspect GPU0 as text or JSONL:

```bash
amdmemtweak --i 0 --current
amdmemtweak --i 0 --current --json
```

Profiles and PPTable integration are provided by
[`../amd-tuning`](../amd-tuning), not by this package.

## Safety

- The profile was characterized on MI50 32GB cards with Hynix HBM2.
- It is not guaranteed stable on another card or memory stack.
- Corrected UMC errors mean the setting is unstable even if throughput rises.
- Never use `RCDRD=12` from this study; it produced corrected ECC errors.
- Never use `RDRDSCL=2`; it caused a GPU hang and host reboot.
- A cold reboot restores direct UMC register changes.
