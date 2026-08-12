# AMD tuning profiles

YAML profile orchestration for UPP PowerPlay values and AMD Memory Tweak HBM2
timings.

## Dependencies

- `amdmemtweak` from [`../amd-memory-tweak`](../amd-memory-tweak)
- [UPP](https://github.com/sibradzic/upp): `pip install upp`
- Mike Farah [yq](https://github.com/mikefarah/yq), version 4

The CLI accepts any yq v4 version whose version output identifies the canonical
project, for example:

```text
yq (https://github.com/mikefarah/yq/) version v4.53.3
```

`install-yq.sh` dynamically installs the latest GitHub release and verifies its
published SHA-256 checksum. No version is pinned.

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
./amd-tuning validate --profile profile-mi50-hbm-oc.yaml
./amd-tuning show --gpu 0
./amd-tuning backup --gpu 0 --output profile-backup.yaml
./amd-tuning diff --gpu 0 --profile profile-mi50-hbm-oc.yaml
./amd-tuning apply --gpu 0 --profile profile-mi50-hbm-oc.yaml
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
