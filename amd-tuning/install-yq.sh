#!/bin/bash
set -euo pipefail

INSTALL_PATH=${INSTALL_PATH:-/usr/local/bin/yq}
ARCH=${ARCH:-amd64}
REPO=https://github.com/mikefarah/yq

tag=$(curl -fsSL https://api.github.com/repos/mikefarah/yq/releases/latest |
  sed -n 's/.*"tag_name": "\([^"]*\)".*/\1/p' | head -n 1)
if [ "$tag" = "" ]; then
  echo "Unable to determine the latest yq release." >&2
  exit 1
fi

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
asset="yq_linux_${ARCH}"
curl -fsSL -o "$tmpdir/$asset" "$REPO/releases/download/$tag/$asset"
curl -fsSL -o "$tmpdir/checksums" "$REPO/releases/download/$tag/checksums"
(
  cd "$tmpdir"
  actual=$(sha256sum "$asset" | cut -d ' ' -f 1)
  checksum_line=$(grep "^${asset} " checksums)
  printf '%s\n' "$checksum_line" | tr ' ' '\n' | grep -Fqx "$actual" || {
    echo "SHA-256 verification failed for $asset" >&2
    exit 1
  }
  echo "$asset: SHA-256 OK"
)
install -m 0755 "$tmpdir/$asset" "$INSTALL_PATH"
"$INSTALL_PATH" --version
