#!/usr/bin/env python3
"""Replace the stock draft settings with a DSpark draft configuration."""
import argparse
import json
from pathlib import Path

root = Path(__file__).resolve().parent

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("draft", help="path to the dflash draft GGUF")
parser.add_argument("--device", default="none", help="--spec-draft-device value")
parser.add_argument("--n-max", type=int, default=4, help="--spec-draft-n-max")
parser.add_argument("--split", help="override --tensor-split")
parser.add_argument("--name", default="dense-cuda-redistributed-plus-dspark", help="output file stem")
args = parser.parse_args()

command = json.loads((root / "dense-cuda-redistributed-plus.json").read_text())

drop = {"--spec-type", "--device-draft", "--spec-draft-n-max", "--n-gpu-layers-draft"}
cleaned = []
index = 0
while index < len(command):
    if command[index] in drop:
        index += 2
        continue
    cleaned.append(command[index])
    index += 1

cleaned += [
    "--spec-type", "draft-dspark",
    "--spec-draft-model", args.draft,
    "--spec-draft-device", args.device,
    "--spec-draft-ngl", "0",
    "--spec-draft-n-max", str(args.n_max),
]
if args.split:
    cleaned[cleaned.index("--tensor-split") + 1] = args.split

(root / f"{args.name}.json").write_text(json.dumps(cleaned, indent=2) + "\n")
print(f"written {args.name}.json")
