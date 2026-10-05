#!/usr/bin/env python3
"""Check profile YAML -> presets.ini -> router -> autoload -> inference."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


def request(base, endpoint, payload=None, timeout=3600):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base + endpoint, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def snapshot():
    result = {"time": time.time()}
    result["nvidia_smi"] = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,memory.used,memory.total,utilization.gpu", "--format=csv"],
        capture_output=True, text=True,
    ).stdout
    result["ps"] = subprocess.run(
        ["ps", "-eo", "pid,rss", "--sort=-rss"], capture_output=True, text=True,
    ).stdout.splitlines()[:4]
    meminfo = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in ("MemTotal", "MemAvailable"):
            meminfo[key] = value.strip()
    result["meminfo"] = meminfo
    result["amd"] = {}
    for card in sorted(Path("/sys/class/drm").glob("card[0-9]*/device")):
        vendor = card / "vendor"
        if vendor.exists() and vendor.read_text().strip() == "0x1002":
            result["amd"][card.parent.name] = {
                "used": int((card / "mem_info_vram_used").read_text().strip()),
                "total": int((card / "mem_info_vram_total").read_text().strip()),
            }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ctx", type=int, default=196608)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--server", default="/app/llama-server")
    parser.add_argument("--builder", default="/app/server-profiles/build-presets-ini.py")
    parser.add_argument("--generate", type=int, default=64)
    args = parser.parse_args()

    base = f"http://127.0.0.1:{args.port}"
    args.output.mkdir(parents=True, exist_ok=False)
    profiles_dir = args.output / "profiles"
    profiles_dir.mkdir()

    profile = args.profile.read_text()
    patched, count = re.subn(r"(ctx-size:\s*)\d+", rf"\g<1>{args.ctx}", profile)
    if count != 1:
        raise RuntimeError(f"expected exactly one ctx-size line, patched {count}")
    (profiles_dir / args.profile.name).write_text(patched)

    subprocess.run(
        ["python3", args.builder, "--source-dir", str(profiles_dir), "--output", str(args.output / "presets.ini")],
        check=True, capture_output=True, text=True,
    )
    presets = (args.output / "presets.ini").read_text()
    name = next(line for line in presets.splitlines() if line.startswith("[") and line != "[*]").strip("[]")
    print(f"preset: {name}")

    env = os.environ.copy()
    env["LLAMA_ARG_MODELS_PRESET"] = str(args.output / "presets.ini")
    start = time.monotonic()
    with (args.output / "server.log").open("w") as log:
        server = subprocess.Popen(
            [args.server, "--host", "127.0.0.1", "--port", str(args.port)],
            stdout=log, stderr=subprocess.STDOUT, env=env,
        )
        try:
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f"router exited with {server.returncode}; see server.log")
                try:
                    request(base, "/health", timeout=2)
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() - start > 900:
                        raise TimeoutError("router did not become ready in 900 seconds")
                    time.sleep(2)
            print(f"router ready in {time.monotonic() - start:.1f}s", flush=True)
            (args.output / "router.json").write_text(json.dumps(request(base, "/props"), indent=2))

            models = request(base, "/models?reload=1")
            (args.output / "models-before.json").write_text(json.dumps(models, indent=2))
            entry = next(m for m in models["data"] if m["id"] == name)
            print("before load:", entry["status"]["value"])

            # First request triggers autoload and waits for the model.
            load_start = time.monotonic()
            props = request(base, f"/props?model={urllib.parse.quote(name)}", timeout=1200)
            load_seconds = time.monotonic() - load_start
            (args.output / "props.json").write_text(json.dumps(props, indent=2))
            models = request(base, "/models")
            (args.output / "models-loaded.json").write_text(json.dumps(models, indent=2))
            entry = next(m for m in models["data"] if m["id"] == name)
            print(f"loaded in {load_seconds:.1f}s: {entry['status']['value']}")
            print("args:", " ".join(entry["status"].get("args", [])))
            (args.output / "loaded.json").write_text(json.dumps(snapshot(), indent=2))

            text = "\n".join(
                f"Record {i}: a Kubernetes worker processes requests using CPU memory, GPU memory, and PCIe transfers. "
                "Compare latency, throughput, scheduling, and data locality; explain the tradeoffs with examples."
                for i in range(600)
            )
            results = {}
            for label, prompt, count in [("short", "Write a short paragraph about GPU memory management.", args.generate),
                                         ("long", text, args.generate)]:
                before = time.monotonic()
                response = request(base, "/v1/completions", {
                    "model": name, "prompt": prompt, "max_tokens": count,
                    "temperature": 0, "seed": 42,
                })
                elapsed = time.monotonic() - before
                results[label] = {"wall_seconds": elapsed, "usage": response.get("usage"),
                                  "text": response["choices"][0]["text"][:200]}
                print(f"{label}: {elapsed:.1f}s, usage={response.get('usage')}", flush=True)
            (args.output / "completions.json").write_text(json.dumps(results, indent=2))
            (args.output / "after.json").write_text(json.dumps(snapshot(), indent=2))
        finally:
            server.terminate()
            try:
                server.wait(timeout=60)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
