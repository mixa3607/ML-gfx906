# Vega 20 metrics

`vega20-rdi` is a small standalone reader for the per-sensor thermal telemetry
of AMD Vega 20 / MI50 (`1002:66a1`). It does not invoke or link to `atitool`.

## Build and run

```sh
make
sudo ./vega20-rdi
```

Root access is required because the program maps each supported GPU's BAR5 via
`/dev/mem`. It discovers all matching PCI devices and prints 64 TMON RDI values
and four HBM stack temperatures for each one.

To include calibrated SVI2 voltage/current channels, provide the adapter's
VBIOS ROM explicitly:

```sh
sudo ./vega20-rdi --vbios /path/to/adapter.rom
```

The ROM is parsed for its AtomBIOS SMC DPM v4.4 calibration table. Do not use
a ROM from a different board: its current endpoints can differ.

## Register paths

- TMON 0 RDI: BAR5 dword indices `0x1660d` through `0x1662c`.
- TMON 1 RDI: BAR5 dword indices `0x16631` through `0x16650`.
- RDI decoding: `((value >> 12) & 0xfff) * 0.125 - 49.0` C when bit 11 is set.
- HBM temperatures: SMN offsets `0x57148 + stack * 0x200000`; the unsigned
  value in bits 23:16 is degrees C.

HBM reads use BAR5's volatile SMN indirect index/data dwords `0x0e` and
`0x0f`. The reader preserves and restores the original SMN index after reading
the four stacks. It does not write any persistent GPU configuration.

The optional SVI2 output reads plane0/channel1 `0x16803`, plane0/channel0
`0x16804`, plane1/channel0 `0x16805`, and plane1/channel1 `0x16806`. Voltage
is `1.55 - byte2 * 0.00625` V. Current calibration is derived from the ROM's
raw-code-zero and raw-code-255 endpoints.

The reverse-engineering notes and test-bench observations are in
[`RESEARCH.md`](RESEARCH.md).
