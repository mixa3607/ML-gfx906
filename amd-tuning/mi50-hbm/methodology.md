# Measurement methodology

## Goal

Characterize HBM2 frequency and timings for dense LLM inference without raising
the stock 225 W board power limit. Prompt processing and token generation are
measured separately because they have different compute and bandwidth limits.

## Benchmark workload

Primary workload:

```bash
HIP_VISIBLE_DEVICES=0 /app/llama-bench \
  --hf-repo unsloth/Qwen3.5-9B-GGUF:Q8_0 \
  -ngl 99 \
  -sm none \
  -fa on \
  -p 2048 \
  -n 256 \
  -r 5 \
  -o json
```

This is a dense 9B Q8_0 model. `HIP_VISIBLE_DEVICES=0` isolates physical GPU0,
and `-sm none` prevents model splitting across GPUs.

Longer stability workload:

```bash
HIP_VISIBLE_DEVICES=0 /app/llama-bench \
  --hf-repo unsloth/Qwen3.5-9B-GGUF:Q8_0 \
  -ngl 99 \
  -sm none \
  -fa on \
  -p 0 \
  -n 2048 \
  -r 3 \
  -o json
```

An earlier Gemma 4 31B Q4_K_L workload was used during tool bring-up. It is
retained in `results.csv`, but tuning decisions should prioritize the dense Qwen
results requested for memory characterization.

## Test sequence

1. Confirm no live KFD workload is using GPU0.
2. Save `/sys/bus/pci/devices/0000:33:00.0/pp_table`.
3. Record UCLK, GFXCLK, FCLK, SOCCLK, power, temperatures and RAS counters.
4. Run stock benchmark with five repetitions.
5. Change one frequency or timing group on GPU0 only.
6. Read the value back using UPP and/or AMD Memory Tweak.
7. Run the identical benchmark command.
8. Check corrected and uncorrected UMC, GFX, SDMA, MMHUB and PCIe RAS counters.
9. Reject a setting on errors, process failure, node/GPU reset, output anomaly,
   or inconsistent throughput.
10. Run a longer generation test on the best short-run setting.
11. Explicitly restore both PPTable and direct UMC timing values.

Only GPU0 was modified. GPU1 through GPU3 remained stock references.

## Parameter order

The initial search changed parameters in this order:

1. UCLK `1000 -> 1150 MHz` through PPTable.
2. `RFCPB 120 -> 116 -> 112` through UMC registers.
3. `RCDRD 16 -> 15 -> 14` through UMC registers.

The extended search established:

- UCLK 1180 MHz ran normally, while 1185 MHz and above produced a repeatable
  throughput cliff around 27.5 t/s without reporting ECC errors.
- RCDRD 13 completed the short benchmark without reported errors.
- RCDRD 12 produced 156000 corrected UMC errors and was rejected immediately.
- RFCPB below 100 did not improve throughput; 100 was retained.
- RFC 340 and REF 4500 produced the best short-run refresh result.
- RDRDSCL 2 caused an immediate GPU hang and host reboot. No further RDRD group
  tightening is permitted in this study.
- RP 15 and RC 44 improved decode; lower values did not improve performance.
- CL 23, RTP 6, RRDS/RRDL 3 and RAS 28 were error-free in short tests but all
  reduced throughput, so stock values were retained.

The final profile was validated with both the standard pp2048/tg256 test and
three repetitions of tg2048 (6144 generated tokens total). All exposed RAS
counters remained zero.

The order minimizes risk and targets read-heavy decode traffic. Write timings
were not tightened because model inference primarily streams weights from HBM.

## Interpretation

- `avg_ts` is throughput in tokens per second.
- `stddev_ts` is the standard deviation reported by llama-bench.
- Percent changes are computed against the full stock result for the same model.
- A faster short benchmark with zero RAS errors is not sufficient evidence of
  production stability. Silent corruption testing and multi-hour stress remain
  required.
- Sparse one-second power samples are useful for detecting a power-cap limit but
  are not energy measurements. Tokens per joule was not calculated.

## Monitoring

RAS check:

```bash
/opt/rocm/bin/rocm-smi --showrasinfo
```

Runtime telemetry:

```bash
/opt/rocm/bin/rocm-smi -d 0 \
  --showclocks --showpower --showtemp
```

The stock Gemma run reached approximately 225 W, 87 C hotspot and 76 C HBM.
GFXCLK occasionally moved from 1725 to 1606 MHz while at the board-power limit.
