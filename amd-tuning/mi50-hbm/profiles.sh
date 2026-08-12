#!/usr/bin/env bash

set -euo pipefail

GPU_INDEX=${GPU_INDEX:-0}
GPU_BDF=${GPU_BDF:-0000:33:00.0}
PPTABLE="/sys/bus/pci/devices/${GPU_BDF}/pp_table"
AMDMEMTWEAK=${AMDMEMTWEAK:-/tmp/amdmemorytweak/linux/amdmemtweak}

case "${1:-}" in
  apply)
    # Keep stock PPT/TDC while changing only the top UCLK state.
    upp -p "$PPTABLE" set --write \
      smcPPTable/FreqTableUclk/2=1180 \
      smcPPTable/FreqTableUclk/3=1180
    sleep 2
    "$AMDMEMTWEAK" --i "$GPU_INDEX" \
      --rfcpb 100 --rcdrd 13 --rfc 340 --ref 4500 --rp 15 --rc 44
    ;;
  restore-timings)
    "$AMDMEMTWEAK" --i "$GPU_INDEX" \
      --cl 24 --ras 29 --rcdrd 16 --rcdwr 14 \
      --rc 45 --rp 16 --rrds 4 --rrdl 4 --rtp 7 \
      --rdrdsd 2 --rdrdsc 1 --rdrdscl 3 --rdrddd 3 \
      --rfcpb 120 --rfc 350 --ref 3900
    ;;
  show)
    upp -p "$PPTABLE" get \
      SmallPowerLimit1 \
      smcPPTable/SocketPowerLimitAc0 \
      smcPPTable/TdcLimitGfx \
      smcPPTable/FreqTableUclk/2 \
      smcPPTable/FreqTableUclk/3
    "$AMDMEMTWEAK" --i "$GPU_INDEX" --current
    /opt/rocm/bin/rocm-smi --showrasinfo
    ;;
  *)
    echo "Usage: $0 {apply|restore-timings|show}" >&2
    echo "Restoring UCLK requires writing a previously saved stock PPTable or rebooting." >&2
    exit 2
    ;;
esac
