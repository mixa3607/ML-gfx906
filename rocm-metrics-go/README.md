# Vega 20 Metrics Exporter

`vega20-metrics` is a Go Prometheus exporter for MI50/Vega 20. It combines
amdgpu sysfs data with the RDI telemetry previously exposed by `vega20-rdi`.

## Metrics

- `vega20_vram_bytes{gpu,state="total|used|free"}`
- `vega20_visible_vram_bytes{gpu,state="total|used|free"}` when exposed
- `vega20_gtt_bytes{gpu,state="total|used|free"}` when exposed
- `vega20_gfx_activity_percent` when exposed
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
