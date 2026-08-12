# Environment

Captured on 2026-08-12.

## Access

```text
Kubernetes namespace: ns-vllm
Pod: llama-cpp-amd-7-14-llamacpp-0
Node: kube-worker6.arkprojects.lan
Pod privileges: privileged, UID/GID 0, unconfined seccomp
```

## Host and GPU

```text
OS: Ubuntu 24.04.4 LTS
Kernel: 6.8.0-137-generic
GPU count: 4
GPU: AMD Instinct MI50 32GB, gfx906, 60 CUs
PCI device: 1002:66a1 revision 02, subsystem 1002:0834
VBIOS: 113-D1631700-111
VBIOS build: Vega20 A1 SERVER XL D16317 Hynix/Samsung 32GB 8HI
SMC firmware: 40.60.00
MC firmware: 2.50.1.0
HBM vendor reported by tools: Hynix HBM2
```

Device mapping:

| ROCm/tool index | PCI BDF | DRM card | debugfs DRI |
|---:|---|---|---:|
| 0 | `0000:33:00.0` | `card4` | 4 / 131 |
| 1 | `0000:36:00.0` | `card5` | 5 / 132 |
| 2 | `0000:4d:00.0` | `card6` | 6 / 133 |
| 3 | `0000:50:00.0` | `card7` | 7 / 134 |

The numeric debugfs aliases can differ after reboot. Resolve them through
`/sys/kernel/debug/dri/*/name` rather than assuming fixed numbers.

## Software

```text
ROCm: 7.14.0
amd-smi: 26.5.0+2b22ab0195
llama.cpp build commit: 48d22e2
UPP: 0.2.4
ATITOOL: 1.14.0.10 (2019)
AMD Memory Tweak Linux CLI: 0.1.9 source base
```

AMD Memory Tweak required two local compatibility changes:

1. Add Vega20 MI50 device ID `0x66a1` to `IsRelevantDeviceID()`.
2. Fall back from `O_RDWR` to `O_RDONLY` when opening `amdgpu_regs`, allowing
   read-only inspection on kernels that do not expose writable debugfs files.

The test pod did expose register writes despite debugfs mode `0400`, because it
was privileged and root.

## Stock state

```text
PPT: 225 W
TDC GFX: 330 A
GFXCLK maximum: 1725 MHz
UCLK levels: 350, 800, 1000 MHz
FCLK maximum: 1278 MHz
SOCCLK maximum: 972 MHz (971 MHz reported at runtime)
PPTable size: 1730 bytes, revision 11
PPTable SHA-256: e34c8080e36a2a5478310268da36d21a8017e2409b4c66187f232351f8533efc
```

Stock HBM2 timing values relevant to this study:

```text
CL=24 RAS=29 RCDRD=16 RCDWR=14
RC=45 RP=16 RRDS=4 RRDL=4 RTP=7 FAW=16
CWL=8 WTRS=5 WTRL=6 WR=17
RREFD=8 RFCPB=120 RFC=350 REF=3900
RDRDDD=3 RDRDSD=2 RDRDSC=1 RDRDSCL=3
RDDATA=22 RDLAT=18
```

AMD Memory Tweak may print `Memory state: 1200MHz` for the stock register set.
That text decodes an internal strap ID and is not the actual UCLK. Runtime tools
and PPTable both confirmed stock UCLK was 1000 MHz.

## Tool limitations observed

- ATITOOL `-ppdpmforce` followed by `-ppdpmrestore` did not restore Vega20 DPM
  correctly under Linux.
- Calling undocumented ATITOOL `-mcac=<name>` without a value disabled DPM.
- PCI unbind of one MI50 caused the whole node to reboot.
- `amd-smi reset --gpureset` reported reset unsupported.
- `wolfamdctrl` and `ohgodatool` assumed the AMD device was `card0`; this mixed
  DRM system uses `card4` through `card7`.
- Direct UMC timing writes survive a PPTable reload. Restore timings explicitly
  or cold reboot.
