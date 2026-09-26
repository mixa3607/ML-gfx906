#!/usr/bin/env python3
"""Format one llama-bench JSONL file using configurable report columns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


VERSION = "0.1.0"
BYTE_UNITS = {unit: 1024 ** index for index, unit in enumerate(("B", "KiB", "MiB", "GiB", "TiB"))}
FORMATS = {"raw", "hf-path", "bytes", "count", "map"}
COLUMN_KEYS = {"field", "name", "enabled", "format", "unit", "precision", "separator", "map"}


class ResultError(ValueError):
    """A report configuration or input record is invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="one llama-bench JSONL file")
    parser.add_argument(
        "--config", type=Path,
        default=Path(__file__).with_name("result-format.yaml"),
        help="column configuration (default: result-format.yaml next to this script)",
    )
    parser.add_argument("--format", choices=("yaml", "json", "md-table"), required=True)
    parser.add_argument("--no-header", action="store_true", help="omit the header and separator for md-table output")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser.parse_args()


def load_columns(path: Path) -> dict[str, dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        config = yaml.safe_load(source)
    if not isinstance(config, dict) or config.get("version") != 1:
        raise ResultError(f"{path}: expected a mapping with version: 1")
    columns = config.get("columns")
    if not isinstance(columns, dict) or not columns:
        raise ResultError(f"{path}: columns must be a non-empty mapping")
    selected = {}
    for key, options in columns.items():
        if not isinstance(key, str) or not isinstance(options, dict):
            raise ResultError(f"{path}: each column must have a string ID and an option mapping")
        unknown = set(options) - COLUMN_KEYS
        if unknown:
            raise ResultError(f"column {key}: unknown options: {', '.join(map(str, unknown))}")
        if not isinstance(options.get("enabled", True), bool):
            raise ResultError(f"column {key}: enabled must be a boolean")
        if not options.get("enabled", True):
            continue
        for option, default in (("field", key), ("name", key), ("format", "raw")):
            if not isinstance(options.get(option, default), str):
                raise ResultError(f"column {key}: {option} must be a string")
        kind = options.get("format", "raw")
        if kind not in FORMATS:
            raise ResultError(f"column {key}: unknown format: {kind}")
        precision = options.get("precision", 2)
        if type(precision) is not int or precision < 0:
            raise ResultError(f"column {key}: precision must be a non-negative integer")
        if kind == "bytes" and (
            not isinstance(options.get("unit", "GiB"), str) or options.get("unit", "GiB") not in BYTE_UNITS
        ):
            raise ResultError(f"column {key}: unsupported byte unit")
        if kind == "count" and (
            not isinstance(options.get("separator", "/"), str) or not options.get("separator", "/")
        ):
            raise ResultError(f"column {key}: separator must be a non-empty string")
        if kind == "map" and not isinstance(options.get("map"), dict):
            raise ResultError(f"column {key}: format map requires a map mapping")
        selected[key] = options
    if not selected:
        raise ResultError(f"{path}: no enabled columns")
    return selected


def hf_path(value: str) -> str:
    parts = Path(value).parts
    for index, part in enumerate(parts):
        if part.startswith("models--") and len(parts) > index + 3 and parts[index + 1] == "snapshots":
            repo = part.removeprefix("models--").replace("--", "/")
            return "/".join((repo, *parts[index + 3:]))
    return Path(value).name


def format_value(value: Any, options: dict[str, Any]) -> Any:
    if value is None:
        return None
    kind = options.get("format", "raw")
    if kind == "map":
        if isinstance(value, (dict, list)):
            raise ResultError("map requires a scalar input")
        value = options["map"].get(value, value)
    elif kind == "bytes":
        if type(value) not in (int, float):
            raise ResultError("bytes requires a numeric input")
        unit = options.get("unit", "GiB")
        return f"{value / BYTE_UNITS[unit]:.{options.get('precision', 2)}f} {unit}"
    elif kind in ("hf-path", "count"):
        if not isinstance(value, str):
            raise ResultError(f"{kind} requires a string input")
        if kind == "hf-path":
            return hf_path(value)
        if value.strip() == "auto":
            return None
        if value.strip() in ("", "none"):
            return 0
        return sum(bool(part.strip()) for part in value.split(options.get("separator", "/")))
    if "precision" in options and type(value) in (int, float):
        value = round(value, options["precision"])
    return value


def read_results(path: Path, columns: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ResultError(f"{path}:{line_number}: invalid JSON: {error.msg}") from error
            if not isinstance(record, dict):
                raise ResultError(f"{path}:{line_number}: expected a JSON object")
            row = {}
            for key, options in columns.items():
                try:
                    row[key] = format_value(record.get(options.get("field", key)), options)
                except ResultError as error:
                    raise ResultError(f"{path}:{line_number}: column {key}: {error}") from error
            rows.append(row)
    return rows


def markdown_cell(value: Any, options: dict[str, Any]) -> str:
    if value is None:
        text = "—"
    elif "precision" in options and type(value) in (int, float):
        text = f"{value:.{options['precision']}f}"
    elif isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    # Escape data before introducing the HTML line breaks used inside table cells.
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for character in ("\\", "`", "*", "_", "[", "]", "|"):
        text = text.replace(character, "\\" + character)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def render(
    rows: list[dict[str, Any]], columns: dict[str, dict[str, Any]], output_format: str,
    *, no_header: bool = False,
) -> str:
    if output_format == "json":
        return json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output_format == "yaml":
        return yaml.safe_dump(rows, allow_unicode=True, sort_keys=False)
    lines = [] if no_header else [
        "| " + " | ".join(markdown_cell(options.get("name", key), {}) for key, options in columns.items()) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(markdown_cell(row[key], options) for key, options in columns.items()) + " |")
    return "\n".join(lines) + "\n" if lines else ""


def main() -> int:
    args = parse_args()
    try:
        columns = load_columns(args.config)
        output = render(read_results(args.input, columns), columns, args.format, no_header=args.no_header)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise SystemExit(f"error: {error}") from error
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
