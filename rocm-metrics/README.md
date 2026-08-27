# Vega 20 Metrics Exporter

`vega20-metrics` is a Go Prometheus exporter for MI50/Vega 20. It combines
amdgpu sysfs data with direct RDI register telemetry.

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
- `vega20_gpu_up`
- `vega20_register_telemetry_up{gpu,backend}`
- `vega20_temperature_celsius{gpu,sensor}` for TMON RDI and HBM stacks
- `vega20_thermal_limit_celsius{gpu,limit="policy|hardware_ctf"}`
- `vega20_temperature_gradient_celsius`
- `vega20_clock_mhz{gpu,clock="dclk|vclk|eclk"}`
- `vega20_voltage_volts` and `vega20_current_amperes` with `--vbios`

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

## Run

```sh
go build ./cmd/vega20-metrics
sudo ./vega20-metrics --listen :9487 --register-backend debugfs
curl localhost:9487/metrics
```

Use `--sysfs PATH` with a mounted host sysfs when the exporter runs in a
container. `--register-backend debugfs` accesses
`/sys/kernel/debug/dri/<BDF>/amdgpu_regs`; debugfs must be mounted. Use
`--register-backend bar5` for direct `/dev/mem` BAR5 access, or `none` to
disable register telemetry.

HBM metrics temporarily write the volatile SMN index register and restore its
previous value. Provide a board-matching ROM with `--vbios ROM` to enable
calibrated SVI2 current metrics; do not use a ROM from another board.

Configure `OTEL_EXPORTER_OTLP_ENDPOINT` to enable OTLP/gRPC traces; without it,
no external OpenTelemetry collector is required.

## Debian Package And Image

Build a Debian package with Docker Buildx:

```sh
METRICS_PUSH=0 make deb
```

The package is written to
`output/rocm<version>/rocm-metrics-<package-version>/` and installs
`/usr/bin/vega20-metrics`. `build-and-push.deb.sh` pushes the package and its
`index.txt` by default; set `METRICS_PUSH=0` for a local build.

Build the container image from the locally built package:

```sh
METRICS_PUSH=0 make image
```

The image runs the exporter on `:9487` with the debugfs backend. Mount host
`/sys`, host debugfs, and grant the required device permissions when deploying
it. Set `METRICS_PACKAGES_SOURCE=fetch` to build an image from a published
package index instead of the local `output` directory.
