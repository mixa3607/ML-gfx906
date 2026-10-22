#!/usr/bin/env python3
"""Resolve the merged source asset, not the unmerged Git tag, of an Unsloth mix release."""

import argparse
import json
import re
import urllib.request


def resolve_source(release, tag):
    if release.get("tag_name") != tag or release.get("draft"):
        raise ValueError(f"Not a published release: {tag}")
    name = f"llama.cpp-source-{tag}.tar.gz"
    asset, = [asset for asset in release["assets"] if asset["name"] == name]
    url = f"https://github.com/unslothai/llama.cpp/releases/download/{tag}/{name}"
    if asset["browser_download_url"] != url:
        raise ValueError(f"Unexpected source URL: {asset['browser_download_url']}")
    digest = asset.get("digest") or ""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError(f"Missing SHA256 for {name}")
    return url, digest.removeprefix("sha256:")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    args = parser.parse_args()
    if not re.fullmatch(r"b[0-9]+-mix-[0-9a-f]+", args.tag):
        parser.error("Expected an Unsloth bNNNNN-mix-HASH release tag")
    request = urllib.request.Request(
        f"https://api.github.com/repos/unslothai/llama.cpp/releases/tags/{args.tag}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "ML-gfx906"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        print(*resolve_source(json.load(response), args.tag))


if __name__ == "__main__":
    main()
