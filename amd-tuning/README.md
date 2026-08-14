# AMD tuning profiles

YAML profile orchestration for UPP PowerPlay values and AMD Memory Tweak HBM2
timings.

## Debian package

> `amd-tuning` is available from the [gfx906 APT repository](../README.md#apt-repository-therock-build).

Build the package with the same buildx workflow as `amd-memory-tweak`:

```bash
. preset.v0.1.0.sh
./build-and-push.deb.sh
```

The artifact is written to `output/amd-tuning-<version>-<suffix>/`. Install it
after `amd-memory-tweak`:

```bash
apt-get install ./amd-memory-tweak_*.deb ./amd-tuning_*.deb
amd-tuning-deps-installer
```

`amd-tuning-deps-installer` must run as root. It installs missing base tools,
UPP through `pip`, and the current verified Mike Farah `yq` v4 binary. It is
safe to rerun and does not reinstall an already-valid `upp` or `yq`.

The package contains the CLI, its allowlists, and stock/OC examples under
`/usr/share/amd-tuning/examples/`.

## Dependencies

- `amdmemtweak` from [`../amd-memory-tweak`](../amd-memory-tweak)
- [UPP](https://github.com/sibradzic/upp): `pip install upp`
- Mike Farah [yq](https://github.com/mikefarah/yq), version 4

The CLI accepts any yq v4 version whose version output identifies the canonical
project, for example:

```text
yq (https://github.com/mikefarah/yq/) version v4.53.3
```

`amd-tuning-deps-installer` dynamically installs the latest GitHub release and
verifies its published SHA-256 checksum. No version is pinned.

## Profile format

```yaml
schemaVersion: 1
ppTable:
  smcPPTable/FreqTableUclk/2: 1180
memoryTweak:
  rrds: 4
```

Only keys listed in `pp-table-allowlist.txt` and
`memory-tweak-allowlist.txt` can be applied.

## Commands

```bash
amd-tuning validate --profile /usr/share/amd-tuning/examples/profile-mi50-hbm-oc.yaml
amd-tuning show --gpu 0
amd-tuning backup --gpu 0 --output profile-backup.yaml
amd-tuning diff --gpu 0 --profile /usr/share/amd-tuning/examples/profile-mi50-hbm-oc.yaml
amd-tuning apply --gpu 0 --profile /usr/share/amd-tuning/examples/profile-mi50-hbm-oc.yaml
```

`--bdf` may be supplied alongside `--gpu`. The CLI verifies that both identify
the same device rather than treating them as independent selectors.

Backups contain:

- `ppTable`: safe, directly applicable PPTable fields.
- `memoryTweak`: all structured HBM2 timings exposed by `amdmemtweak`.
- `ppTableDump`: complete UPP dump as a literal text block for diagnostics;
  ignored by `apply`.

There is currently no automatic rollback if an apply operation fails midway.
Apply a previously created backup explicitly to restore both PPTable policy and
direct UMC register values.
