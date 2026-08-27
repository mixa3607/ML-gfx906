# vega20-metrics-exporter

`vega20-metrics` is a Go Prometheus exporter for MI50/Vega 20. It combines
amdgpu sysfs telemetry with direct RDI register telemetry and serves metrics on
port `9487` by default.

## Requirements

- Linux host with an AMD Vega 20 GPU, such as MI50.
- A YAML configuration file. The Debian package installs one at
  `/etc/vega20-metrics-exporter/config.yaml`.
- `debugfs` mounted for the default `debugfs` register backend.
- A process permitted to read and write
  `/sys/kernel/debug/dri/<BDF>/amdgpu_regs` for register telemetry.
- Go 1.24 to build from source, or Docker with Buildx to build the package and
  image.

Set `providers.registers.enabled: false` when only amdgpu sysfs metrics are
required. `providers.registers.backend: bar5` maps GPU BAR5 through `/dev/mem`; it requires raw
I/O access and should be used only when debugfs is unavailable.

## Configuration

The exporter loads `/etc/vega20-metrics-exporter/config.yaml` by default. Use
`--config PATH` only to select another configuration file. Runtime settings are
not CLI flags.

```yaml
listen: ":9487"
devices:
  vendor_products:
    - vendor_id: "1002"
      product_id: "66a1"
  pci_devices: []          # empty: discover matching DRM devices automatically
providers:
  sysfs:
    enabled: true
    path: /sys
  registers:
    enabled: true
    backend: debugfs       # debugfs or bar5
    vbios_related_metrics:
      enabled: true
      vbios_source: pci_rom # file or pci_rom
      vbios_file: null
      vbios_device: "0000:33:00.0"
```

`devices.vendor_products` is an allowlist; add multiple vendor/product pairs
to collect more device variants. IDs may be written with or without `0x`.

Set `devices.pci_devices` to an explicit list of PCIe BDFs to disable automatic
discovery. Each configured BDF is exported even when it is absent or cannot be
read, with `vega20_provider_up{gpu="<BDF>",provider="sysfs"} 0`. An explicit
device must still match `vendor_products` before its other metrics are collected.

Provider `enabled` settings control metric export only. Device inventory remains
available for either provider. `providers.sysfs.path` is the sysfs root used for
both discovery and sysfs metrics. `providers.registers` controls direct RDI
register reads, which occur only when it is enabled.

`vbios_related_metrics` enables calibrated SVI2 voltage/current metrics for all
configured GPUs. `vbios_source: file` reads the shared ROM once at startup;
`vbios_source: pci_rom` reads the configured `vbios_device` ROM into memory once
at startup and immediately disables ROM decode. For `file`, set only
`vbios_file`; for `pci_rom`, set only `vbios_device`.

Environment variables overlay the YAML using .NET-style indexed keys: each key
overrides only its corresponding value, so unmentioned YAML array elements are
preserved.

```sh
VEGA20_PROVIDERS_REGISTERS_ENABLED=false
VEGA20_DEVICES_VENDOR_PRODUCTS_1_VENDOR_ID=1002
VEGA20_DEVICES_VENDOR_PRODUCTS_1_PRODUCT_ID=66a2
VEGA20_DEVICES_PCI_DEVICES_0=0000:33:00.0
VEGA20_DEVICES_PCI_DEVICES_1=0000:36:00.0
```

## Metrics

- `vega20_vram_bytes{gpu,state="total|used|free"}`
- `vega20_visible_vram_bytes{gpu,state="total|used|free"}` when exposed
- `vega20_gtt_bytes{gpu,state="total|used|free"}` when exposed
- `vega20_gfx_activity_percent` when exposed
- `vega20_gpu_info{gpu,card_vendor,card_model,card_series,driver_version,serial_number,vbios_version}`
- `vega20_fan_speed_percent` when hwmon exposes `pwm1` and `pwm1_max`
- `vega20_pcie_link_speed_gigatransfers_per_second{gpu,state="current|maximum"}` for the PCIe parent-chain bottleneck
- `vega20_pcie_link_width_lanes{gpu,state="current|maximum"}` for the PCIe parent-chain bottleneck
- `vega20_power_watts{gpu,source="average|instant"}` when hwmon exposes it
- `vega20_power_limit_watts{gpu,limit="current|minimum|maximum"}` when exposed
- `vega20_provider_up{gpu,provider="sysfs|registers"}`
- `vega20_temperature_celsius{gpu,sensor}` for TMON RDI and HBM stacks
- `vega20_thermal_limit_celsius{gpu,limit="policy|hardware_ctf"}`
- `vega20_temperature_gradient_celsius`
- `vega20_clock_mhz{gpu,clock="dclk|vclk|eclk"}`
- `vega20_voltage_volts` and `vega20_current_amperes` when
  `vbios_related_metrics` is enabled

Power files are in microwatts in sysfs and are exported as watts. GPU labels
use PCI BDFs, rather than mutable DRM card indices.

## Temperature And Clock Labels

`vega20_temperature_celsius` is composed of the following register telemetry:

- `hbm_stack0` through `hbm_stack3`: temperature of each HBM2 stack in whole
  degrees Celsius.
- `tmon_0_rdil0` through `tmon_0_rdil15` and `tmon_0_rdir0` through
  `tmon_0_rdir15`: 32 valid RDI readings from TMON block 0.
- `tmon_1_rdil0` through `tmon_1_rdil15` and `tmon_1_rdir0` through
  `tmon_1_rdir15`: 32 valid RDI readings from TMON block 1.

TMON readings use Vega 20's RDI hardware labels: `rdil` and `rdir` denote its
two directional banks and the final number is the lane within that bank. The
public hardware documentation does not map these lanes to named physical
locations, so they are not labelled as edge, hotspot, or memory temperatures.
An invalid RDI lane is omitted. Valid values have 0.125 C resolution.

`vega20_thermal_limit_celsius{limit="policy"}` is the firmware thermal-policy
field. `limit="hardware_ctf"` is the hardware critical-thermal-fault limit.
`vega20_temperature_gradient_celsius` is the hottest valid TMON 0 RDI reading
minus `tmon_0_rdil0`.

`vega20_clock_mhz` exposes auxiliary measured clock counters, in MHz:

- `dclk`: display clock.
- `vclk`: video decode clock.
- `eclk`: video encode clock.

These are not GFXCLK, memory clock, or SoC clock. They remain useful on a
headless MI50 as hardware clock-counter telemetry.

## Run From Source

```sh
(cd build-context && go build -o ../vega20-metrics ./cmd/vega20-metrics)
sudo ./vega20-metrics --config build-context/config.yaml
curl localhost:9487/metrics
```

Set `providers.sysfs.path` in the YAML to a mounted host sysfs when the exporter
runs in a container. The `debugfs` backend accesses
`/sys/kernel/debug/dri/<BDF>/amdgpu_regs`; debugfs must be mounted. Use
`providers.registers.backend: bar5` for direct `/dev/mem` BAR5 access, or set
`providers.registers.enabled: false` to disable register telemetry.

HBM metrics temporarily write the volatile SMN index register and restore its
previous value. Enable `vbios_related_metrics` with a board-matching shared ROM
to export calibrated SVI2 metrics; do not use a ROM from another board.

Configure `OTEL_EXPORTER_OTLP_ENDPOINT` to enable OTLP/gRPC traces; without it,
no external OpenTelemetry collector is required.

## Debian Package

Build the package with Docker Buildx:

```sh
METRICS_PUSH=0 ./build-and-push.deb.sh
```

The package is written to
`output/vega20-metrics-exporter-<package-version>/` and installs
`/usr/bin/vega20-metrics`. `build-and-push.deb.sh` pushes the package and its
`index.txt` by default; set `METRICS_PUSH=0` for a local build.

Install a locally built package with:

```sh
sudo apt install ./output/vega20-metrics-exporter-*/*.deb
```

## Container Image

The image is based on Ubuntu 24.04 and starts the exporter with the `debugfs`
backend. Build it from the locally built package:

```sh
METRICS_PUSH=0 ./build-and-push.image.sh
```

Buildx must push the image (`METRICS_PUSH=1`) or otherwise export it before it
can be run outside the Buildx cache. A debugfs deployment needs the host sysfs
and debugfs mounts. The following example uses `--privileged` because the RDI
interface requires read/write driver-debugfs access; reduce privileges only
after verifying the required device policy on the target host.

With `METRICS_IS_RELEASE=1`, the image receives
`$METRICS_IMAGE:$METRICS_VERSION-$REPO_GIT_REF` and
`$METRICS_IMAGE:$METRICS_VERSION`. Otherwise (`METRICS_IS_RELEASE=0`, the
default), it receives only `$METRICS_IMAGE:$METRICS_VERSION-$REPO_GIT_REF-pre`.

```sh
docker run --rm --network host --privileged \
  --mount type=bind,src=/sys,dst=/sys,readonly \
  --mount type=bind,src=/sys/kernel/debug,dst=/sys/kernel/debug \
  docker.io/mixa3607/vega20-metrics-exporter:<tag>
```

Mount a configuration file with `providers.registers.enabled: false` for a
container that should expose only sysfs metrics. `METRICS_PACKAGES_SOURCE=apt` is reserved for an APT package source
and currently exits with a not-implemented error.

- [Run with Docker or Docker Compose](./docs/docker.md)
- [Deploy to Kubernetes](./docs/kubernetes.md)

## Build Variables

Defaults are defined in [`env.sh`](./env.sh). Export a variable to override it.

| Variable | Default | Description |
| --- | --- | --- |
| `METRICS_VERSION` | `0.1.0` | Exporter version included in package and image tags |
| `METRICS_IMAGE` | `docker.io/mixa3607/vega20-metrics-exporter` | Destination image name |
| `METRICS_IS_RELEASE` | `0` | `1` publishes image release tags; otherwise only a `-pre` tag |
| `METRICS_PUSH` | `1` | Set to `0` for a local package/image build without publishing |
| `METRICS_FORCE_BUILD` | *(unset)* | Set to `1` to rebuild an existing output directory or image tag |
| `METRICS_PACKAGES_SOURCE` | `context` | Image package input; `apt` is not implemented |
| `REPO_GIT_REF` | *(git tag, else short SHA)* | Build revision appended to the version suffix |
