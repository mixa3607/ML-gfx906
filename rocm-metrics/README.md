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

## Register paths

- TMON 0 RDI: BAR5 dword indices `0x1660d` through `0x1662c`.
- TMON 1 RDI: BAR5 dword indices `0x16631` through `0x16650`.
- RDI decoding: `((value >> 12) & 0xfff) * 0.125 - 49.0` C when bit 11 is set.
- HBM temperatures: SMN offsets `0x57148 + stack * 0x200000`; the unsigned
  value in bits 23:16 is degrees C.

HBM reads use BAR5's volatile SMN indirect index/data dwords `0x0e` and
`0x0f`. The reader preserves and restores the original SMN index after reading
the four stacks. It does not write any persistent GPU configuration.

The reverse-engineering notes and test-bench observations are in
[`RESEARCH.md`](RESEARCH.md).
