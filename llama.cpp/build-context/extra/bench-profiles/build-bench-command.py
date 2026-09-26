#!/usr/bin/env python3
"""Render a llama-bench shell command from YAML or JSON benchmark profiles."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml


VERSION = "0.1.0"
INPUT_SUFFIXES = frozenset({".json", ".yaml", ".yml"})
PROFILE_KEYS = frozenset({"command", "env", "args"})
FLAG_ONLY_OPTIONS = frozenset(
    {"offline", "verbose", "progress", "no-warmup", "list-devices", "help"}
)
ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
OPTION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*\Z")
COMMAND_PLACEHOLDER = re.compile(r"(?<!\$)\{(env|args|profile)\}")


class BenchmarkError(ValueError):
    """A benchmark profile cannot be rendered as a llama-bench command."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a llama-bench command from YAML/JSON benchmark profiles."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="directory searched recursively for .yaml, .yml, and .json files",
    )
    parser.add_argument("--bench", required=True, help="name of the benchmark profile")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="destination command file, or '-' to write to standard output",
    )
    return parser.parse_args()


def load_documents(path: Path) -> list[Mapping[str, Any]]:
    try:
        with path.open(encoding="utf-8") as source:
            documents = list(yaml.safe_load_all(source))
    except yaml.YAMLError as error:
        raise BenchmarkError(f"{path}: cannot parse input: {error}") from error

    result: list[Mapping[str, Any]] = []
    for index, document in enumerate(documents, start=1):
        if document is None:
            continue
        if not isinstance(document, Mapping):
            raise BenchmarkError(
                f"{path}: document {index} root must map benchmark names to profiles"
            )
        result.append(document)
    return result


def validate_profile(name: str, profile: Any, *, source: Path) -> Mapping[str, Any]:
    if not isinstance(profile, Mapping):
        raise BenchmarkError(f"{source}: benchmark '{name}' must be a mapping")
    unknown_keys = set(profile) - PROFILE_KEYS
    if unknown_keys:
        rendered = ", ".join(sorted(map(str, unknown_keys)))
        raise BenchmarkError(f"{source}: benchmark '{name}' has unknown keys: {rendered}")
    for key in ("env", "args"):
        if profile.get(key) is not None and not isinstance(profile[key], Mapping):
            raise BenchmarkError(f"{source}: benchmark '{name}'.{key} must be a mapping or null")
    if profile.get("command") is not None and not isinstance(profile["command"], str):
        raise BenchmarkError(f"{source}: benchmark '{name}'.command must be a string or null")
    return profile


def collect_profiles(source_dir: Path) -> dict[str, Mapping[str, Any]]:
    if not source_dir.is_dir():
        raise BenchmarkError(f"source directory does not exist or is not a directory: {source_dir}")

    files = sorted(
        (path for path in source_dir.rglob("*") if path.is_file() and path.suffix.lower() in INPUT_SUFFIXES),
        key=lambda path: path.relative_to(source_dir).as_posix(),
    )
    profiles: dict[str, Mapping[str, Any]] = {}
    for path in files:
        for document in load_documents(path):
            for name, profile in document.items():
                if not isinstance(name, str):
                    raise BenchmarkError(f"{path}: benchmark names must be strings")
                if name in profiles:
                    raise BenchmarkError(f"{path}: duplicate benchmark name: '{name}'")
                profiles[name] = validate_profile(name, profile, source=path)
    return profiles


def merge_settings(
    global_profile: Mapping[str, Any], selected_profile: Mapping[str, Any]
) -> dict[str, Any]:
    """Merge mappings recursively; null deletes a key, lists and scalars replace it."""
    merged: dict[str, Any] = {}
    for settings in (global_profile, selected_profile):
        for key, value in settings.items():
            if value is None:
                merged.pop(key, None)
            elif isinstance(value, Mapping):
                previous = merged.get(key, {})
                merged[key] = merge_settings(previous if isinstance(previous, Mapping) else {}, value)
            else:
                merged[key] = value
    return merged


def scalar_to_text(value: Any, *, path: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        # llama-bench value-taking boolean options are documented as 0|1.
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    raise BenchmarkError(f"{path}: expected a scalar value, got {type(value).__name__}")


def is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def matrix_to_text(value: Any, *, path: str, nested_separator: str = ";") -> str:
    """Render comma-separated matrix candidates and nested candidate values."""
    if not is_sequence(value):
        return scalar_to_text(value, path=path)

    candidates: list[str] = []
    for index, candidate in enumerate(value):
        candidate_path = f"{path}[{index}]"
        if is_sequence(candidate):
            candidates.append(
                nested_separator.join(
                    scalar_to_text(item, path=f"{candidate_path}[{item_index}]")
                    for item_index, item in enumerate(candidate)
                )
            )
        else:
            candidates.append(scalar_to_text(candidate, path=candidate_path))
    return ",".join(candidates)


def override_tensor_to_text(value: Any, *, path: str) -> str:
    """Render matrix alternatives for llama-bench --override-tensor."""
    if isinstance(value, str):
        return value
    if not is_sequence(value):
        raise BenchmarkError(f"{path}: override-tensor must be a string or a list of variants")

    variants: list[str] = []
    for variant_index, variant in enumerate(value):
        variant_path = f"{path}[{variant_index}]"
        if not is_sequence(variant):
            raise BenchmarkError(f"{variant_path}: each override-tensor variant must be a list")

        overrides: list[str] = []
        for override_index, override in enumerate(variant):
            override_path = f"{variant_path}[{override_index}]"
            if not isinstance(override, Mapping):
                raise BenchmarkError(f"{override_path}: expected a mapping with tensors and target")
            if set(override) != {"tensors", "target"}:
                raise BenchmarkError(f"{override_path}: expected exactly 'tensors' and 'target'")

            tensors = override["tensors"]
            if not is_sequence(tensors):
                raise BenchmarkError(f"{override_path}.tensors: must be a list")
            patterns = "|".join(
                scalar_to_text(tensor, path=f"{override_path}.tensors[{tensor_index}]")
                for tensor_index, tensor in enumerate(tensors)
            )
            target = scalar_to_text(override["target"], path=f"{override_path}.target")
            overrides.append(f"({patterns})={target}")
        variants.append(";".join(overrides))
    return ",".join(variants)


def render_environment(environment: Mapping[str, Any]) -> list[str]:
    rendered: list[str] = []
    for name, value in environment.items():
        if not isinstance(name, str) or not ENVIRONMENT_NAME.fullmatch(name):
            raise BenchmarkError(f"env: invalid environment variable name: {name!r}")
        if value is None:
            continue
        rendered.append(f"{name}={shlex.quote(scalar_to_text(value, path=f'env.{name}'))}")
    return rendered


def render_arguments(arguments: Mapping[str, Any]) -> list[str]:
    rendered: list[str] = []
    for name, value in arguments.items():
        if not isinstance(name, str) or not OPTION_NAME.fullmatch(name):
            raise BenchmarkError(f"args: invalid llama-bench option name: {name!r}")
        if value is None:
            continue

        if name in FLAG_ONLY_OPTIONS:
            if not isinstance(value, bool):
                raise BenchmarkError(f"args.{name}: flag-only options must be booleans or null")
            if value:
                rendered.append(f"--{name}")
            continue

        if name == "device":
            text = matrix_to_text(value, path=f"args.{name}", nested_separator="/")
        elif name == "override-tensor":
            text = override_tensor_to_text(value, path=f"args.{name}")
        else:
            text = matrix_to_text(value, path=f"args.{name}")
        rendered.extend((f"--{name}", shlex.quote(text)))
    return rendered


def build_command(profiles: Mapping[str, Mapping[str, Any]], bench: str) -> str:
    if bench == "*" or bench not in profiles:
        available = ", ".join(sorted(name for name in profiles if name != "*")) or "(none)"
        raise BenchmarkError(f"unknown benchmark '{bench}'; available: {available}")
    settings = merge_settings(profiles.get("*", {}), profiles[bench])
    command = settings.get("command")
    if not isinstance(command, str) or not command.strip():
        raise BenchmarkError(f"benchmark '{bench}' must define or inherit a non-empty 'command'")
    replacements = {
        "env": " ".join(render_environment(settings.get("env", {}))),
        "args": " ".join(render_arguments(settings.get("args", {}))),
        "profile": shlex.quote(bench),
    }
    # One pass: values may contain marker text, and shell braces are not formatting syntax.
    rendered = COMMAND_PLACEHOLDER.sub(lambda match: replacements[match[1]], command)
    return rendered if rendered.endswith("\n") else rendered + "\n"


def write_output(path: Path, content: str) -> None:
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
        command = build_command(collect_profiles(args.source_dir), args.bench)
        if args.output == Path("-"):
            print(command, end="")
        else:
            write_output(args.output, command)
    except (OSError, BenchmarkError) as error:
        raise SystemExit(f"error: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
