# MI50 HBM2 tuning

Reproducible notes and measurements for four AMD Instinct MI50 32 GB GPUs used
for llama.cpp workloads.

- `environment.md`: hardware, software and device mapping.
- `methodology.md`: benchmark and stability procedure.
- `results.csv`: machine-readable benchmark results.
- `profiles.sh`: reference commands for applying and reverting tested settings.

The current best error-free short-run experimental profile is:

```text
UCLK=1180 MHz
RFCPB=100 cycles
RCDRD=13 cycles
RFC=340 cycles
REF=4500 cycles
RP=15 cycles
RC=44 cycles
PPT=225 W
TDC_GFX=330 A
```

The final profile completed 6144 generated tokens at `67.338 +/- 0.052 t/s`
without reported UMC, GFX or SDMA RAS errors. On the dense Qwen3.5 9B Q8_0
benchmark it improved pp2048 by 1.51% and tg256 by 11.09% over stock. This is
characterization, not proof of production stability.

Do not set `RDRDSCL=2`: it caused an immediate GPU hang followed by a host
reboot. Stock `RDRDSCL=3` must be retained.

Do not use `RCDRD=12`: it accumulated 156000 corrected UMC errors in one short
benchmark. `RCDRD=13` is the lowest error-free value tested.

At the end of the recorded tests all four GPUs were returned to stock settings.
