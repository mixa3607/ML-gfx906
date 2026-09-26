#!/usr/bin/env python3
"""Build a llama.cpp model-presets INI file from YAML and JSON profiles.

Each input document is a mapping of preset name to its options.  The special
``enabled`` option decides whether its containing preset is emitted and is not
written into the INI file itself.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml


VERSION = "0.1.0"
INPUT_SUFFIXES = frozenset({".json", ".yaml", ".yml"})


class PresetError(ValueError):
    """An input profile cannot be represented safely as a presets INI file."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine YAML/JSON llama.cpp profiles into a presets.ini file."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="directory searched recursively for .yaml, .yml, and .json files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="destination INI file, or '-' to write to standard output",
    )
    return parser.parse_args()


def load_documents(paths: Sequence[Path]) -> list[tuple[Path, Mapping[str, Any]]]:
    if not paths:
        raise PresetError("no YAML or JSON profile files found")

    result: list[tuple[Path, Mapping[str, Any]]] = []
    for path in paths:
        try:
            with path.open(encoding="utf-8") as source:
                documents = list(yaml.safe_load_all(source))
        except yaml.YAMLError as error:
            raise PresetError(f"{path}: cannot parse input: {error}") from error

        for index, document in enumerate(documents, start=1):
            if document is None:
                result.append((path, {}))
                continue
            if not isinstance(document, Mapping):
                raise PresetError(
                    f"{path}: document {index} root must be a mapping of preset names"
                )
            result.append((path, document))
    return result


def scalar_to_text(value: Any, *, path: str) -> str:
    """Render INI scalars while keeping strings (including Helm templates) untouched."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return ""
    raise PresetError(f"{path}: expected a scalar value, got {type(value).__name__}")


def sequence_to_text(value: Sequence[Any], *, path: str) -> str:
    if isinstance(value, (str, bytes, bytearray)):
        raise PresetError(f"{path}: internal error: strings are not sequences here")
    return ",".join(
        scalar_to_text(item, path=f"{path}[{index}]") for index, item in enumerate(value)
    )


def override_tensor_to_text(value: Any, *, path: str) -> str:
    if isinstance(value, str):
        return value

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PresetError(f"{path}: override-tensor must be a list")

    rendered_groups: list[str] = []
    for index, group in enumerate(value):
        group_path = f"{path}[{index}]"
        if not isinstance(group, Mapping):
            raise PresetError(f"{group_path}: expected a mapping with tensors and target")
        if set(group) != {"tensors", "target"}:
            raise PresetError(f"{group_path}: expected exactly 'tensors' and 'target'")

        tensors = group["tensors"]
        if not isinstance(tensors, Sequence) or isinstance(tensors, (str, bytes, bytearray)):
            raise PresetError(f"{group_path}.tensors: must be a list")
        tensor_patterns = "|".join(
            scalar_to_text(tensor, path=f"{group_path}.tensors[{tensor_index}]")
            for tensor_index, tensor in enumerate(tensors)
        )
        target = scalar_to_text(group["target"], path=f"{group_path}.target")
        rendered_groups.append(f"({tensor_patterns})={target}")
    return ",".join(rendered_groups)


def override_kwargs_to_text(value: Any, *, path: str) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, Mapping):
        raise PresetError(f"{path}: chat-template-kwargs must be a mapping or a string")
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise PresetError(f"{path}: cannot serialize chat-template-kwargs as JSON: {error}") from error


def flatten_options(options: Mapping[str, Any], *, path: str, prefix: str = "") -> list[tuple[str, str]]:
    """Flatten nested maps into dash-separated INI keys."""
    result: list[tuple[str, str]] = []
    for raw_key, value in options.items():
        if not isinstance(raw_key, str):
            raise PresetError(f"{path}: option names must be strings")
        key = f"{prefix}-{raw_key}" if prefix else raw_key
        value_path = f"{path}.{raw_key}"

        if key == "override-tensor":
            result.append((key, override_tensor_to_text(value, path=value_path)))
        elif key == "chat-template-kwargs":
            result.append((key, override_kwargs_to_text(value, path=value_path)))
        elif isinstance(value, Mapping):
            result.extend(flatten_options(value, path=value_path, prefix=key))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            result.append((key, sequence_to_text(value, path=value_path)))
        else:
            result.append((key, scalar_to_text(value, path=value_path)))
    return result


def collect_sections(source_dir: Path) -> list[tuple[str, Mapping[str, Any]]]:
    if not source_dir.is_dir():
        raise PresetError(f"source directory does not exist or is not a directory: {source_dir}")

    files = sorted(
        (path for path in source_dir.rglob("*") if path.is_file() and path.suffix.lower() in INPUT_SUFFIXES),
        key=lambda path: path.relative_to(source_dir).as_posix(),
    )
    sections: list[tuple[str, Mapping[str, Any]]] = []
    seen_names: set[str] = set()

    for path, document in load_documents(files):
        for name, options in document.items():
            if not isinstance(name, str):
                raise PresetError(f"{path}: preset names must be strings")
            if not isinstance(options, Mapping):
                raise PresetError(f"{path}: preset '{name}' must contain a mapping of options")

            enabled = options.get("enabled", True)
            if not isinstance(enabled, bool):
                raise PresetError(f"{path}: preset '{name}'.enabled must be a boolean")
            if not enabled:
                continue
            if name in seen_names:
                raise PresetError(f"{path}: duplicate enabled preset name: '{name}'")
            seen_names.add(name)
            sections.append((name, {key: value for key, value in options.items() if key != "enabled"}))

    # llama.cpp accepts [*] anywhere, but emitting it first makes the generated
    # file easier to read and preserves the conventional presets.ini layout.
    return sorted(sections, key=lambda section: (section[0] != "*", section[0]))


def render_ini(sections: list[tuple[str, Mapping[str, Any]]]) -> str:
    rendered = [
        f"# Generated by build-presets-ini.py {VERSION}.",
        "# This file will be overwritten by build-presets-ini.py on the next successful generation.",
        "# Edit the source YAML/JSON profiles instead of this file.",
        "",
        "version = 1",
    ]
    for name, options in sections:
        rendered.append("")
        rendered.append(f"[{name}]")
        for key, value in flatten_options(options, path=f"[{name}]"):
            rendered.append(f"{key} = {value}")
    return "\n".join(rendered) + "\n"


def write_output(path: Path, content: str) -> None:
    if path == Path("-"):
        print(content, end="")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)

def main() -> int:
    args = parse_args()
    try:
        content = render_ini(collect_sections(args.source_dir))
        write_output(args.output, content)
    except (OSError, PresetError) as error:
        raise SystemExit(f"error: {error}") from error
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
