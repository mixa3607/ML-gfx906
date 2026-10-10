#!/usr/bin/env python3
"""Apply a server profile's child-wrapper configuration before exec."""

from __future__ import annotations

import importlib.util
import os
import re
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def load_profiles_module():
    path = Path(__file__).with_name("build-presets-ini.py").resolve()
    spec = importlib.util.spec_from_file_location("server_profiles", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def log(message: str) -> None:
    print(f"child-wrapper: {message}", file=sys.stderr, flush=True)


def find_alias(args: list[str]) -> str | None:
    alias = None
    for index, arg in enumerate(args):
        if arg in ("--alias", "-a") and index + 1 < len(args):
            alias = args[index + 1]
        elif arg.startswith("--alias="):
            alias = arg.split("=", 1)[1]
    return alias


def wrapper_options(sections, alias: str) -> dict[str, Any]:
    profiles = dict(sections)
    result: dict[str, Any] = {"env": {}}
    for name in ("*", alias) if alias != "*" else ("*",):
        config = profiles.get(name, {}).get("child-wrapper", {})
        if not isinstance(config, Mapping):
            raise ValueError(f"[{name}].child-wrapper must be a mapping")
        env = config.get("env", {})
        if not isinstance(env, Mapping):
            raise ValueError(f"[{name}].child-wrapper.env must be a mapping")
        result["env"].update(env)
        if "command" in config:
            result["command"] = config["command"]
    return result


def prepare_launch(binary: str, args: list[str], config: Mapping[str, Any]):
    env = dict(os.environ)
    for key, value in config.get("env", {}).items():
        if value is None:
            env.pop(key, None)
            log(f"unset {key}")
        else:
            env[key] = str(value)
            log(f"set {key}={env[key]}")
    env.pop("M36_LLAMA_CHILD_WRAPPER", None)
    log("unset M36_LLAMA_CHILD_WRAPPER")

    command = config.get("command")
    if command is None or not command.strip():
        return [binary, *args], env
    replacements = {"exe": shlex.quote(binary), "args": shlex.join(args)}
    rendered = re.sub(r"\{(exe|args)\}", lambda match: replacements[match[1]], command)
    return ["/bin/bash", "-c", "exec " + rendered], env


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: profiles-wrapper.py EXECUTABLE [ARG ...]", file=sys.stderr)
        return 2
    binary, args = sys.argv[1], sys.argv[2:]
    try:
        alias = find_alias(args)
        config = {}
        if alias is not None:
            profiles = load_profiles_module()
            source_dir = Path(
                os.environ.get("M36_LLAMA_MODELS_PRESETS_DIR")
                or "./server-profiles"
            )
            config = wrapper_options(profiles.collect_sections(source_dir), alias)
            log(f"profile {alias!r} from {str(source_dir)!r}")
        argv, env = prepare_launch(binary, args, config)
        log(f"exec {shlex.join(argv)}")
        os.execvpe(argv[0], argv, env)
    except (OSError, ValueError) as error:
        log(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
