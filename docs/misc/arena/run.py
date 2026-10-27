#!/usr/bin/env python3
"""Collect, independently judge, and export Neuro-Arena answers."""

import argparse
from http.client import HTTPException
import math
from pathlib import Path
import signal
import sys

from commands import examine, export, validate
from common import BENCH


def positive_timeout(value):
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number")
    return timeout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    examine_parser = commands.add_parser("examine", help="collect or resume model answers")
    examine_parser.add_argument("--bench", type=Path, default=BENCH, help="source HTML")
    validate_parser = commands.add_parser("validate", help="judge answers into a separate resumable file")
    export_parser = commands.add_parser("export", help="export HTML history JSON or a Markdown report")
    export_parser.add_argument("--format", choices=("json", "markdown"), default="json",
                               help="output format (default: json)")
    export_parser.add_argument("--output", type=Path,
                               help="default: <answers name>.import.json or <answers name>.md")
    for command in (examine_parser, validate_parser, export_parser):
        command.add_argument("--answers", type=Path, required=True, help="exam answers JSON path")
    for command in (examine_parser, validate_parser):
        command.add_argument("--model", type=Path, required=True, help="model YAML config")
        command.add_argument("--timeout", type=positive_timeout, default=3600,
                             help="per-request socket timeout in seconds (default: 3600)")
    validate_parser.add_argument("--validation", type=Path, required=True, help="judgements JSON path")
    export_parser.add_argument("--validation", type=Path, help="optional judgements JSON path")
    examine_parser.set_defaults(handler=examine.run)
    validate_parser.set_defaults(handler=validate.run)
    export_parser.set_defaults(handler=export.run)
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except KeyboardInterrupt:
        print("Interrupted. Saved progress is safe; rerun the same command to resume.",
              file=sys.stderr)
        return 130
    except (OSError, HTTPException, ValueError, TypeError, KeyError) as error:
        print(f"Error: {error}\nSaved progress is safe; rerun the same command to resume.", file=sys.stderr)
        return 1
    return 0


def interrupted(signum, frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(main())
