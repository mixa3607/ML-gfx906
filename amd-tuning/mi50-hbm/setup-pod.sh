#!/usr/bin/env bash

set -euo pipefail

PATCH_FILE=${1:-/tmp/amdmemorytweak-mi50.patch}

pip install upp
apt-get update
apt-get install -y build-essential git libpci-dev

curl -fLO \
  https://static.arkprojects.space/public-data/wiki/AMD-GFX906/Tools/atitool.tar.xz
printf '%s  %s\n' \
  f6efc274e148c0b3b1f16df49791bb78d2ff57d314debe052646dd884cc2db0f \
  atitool.tar.xz | sha256sum -c -
tar -xJf atitool.tar.xz
chmod +x atitool

mkdir -p /sys/kernel/debug
mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true

rm -rf /tmp/amdmemorytweak
git clone https://github.com/Eliovp/amdmemorytweak.git /tmp/amdmemorytweak
patch -d /tmp/amdmemorytweak -p1 < "$PATCH_FILE"
g++ /tmp/amdmemorytweak/linux/AmdMemTweak.cpp \
  -lpci -lresolv -o /tmp/amdmemorytweak/linux/amdmemtweak

/tmp/amdmemorytweak/linux/amdmemtweak --i 0 --current
