#!/usr/bin/env python3
"""Fill one slot to increasing context lengths and record device/host memory."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request


PORT = 18080


def request(endpoint, payload=None, timeout=3600):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (PORT, endpoint), data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def snapshot():
    result = {"time": time.time()}
    result["nvidia_smi"] = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,memory.used,memory.total,utilization.gpu", "--format=csv"],
        capture_output=True, text=True,
    ).stdout
    result["ps"] = subprocess.run(
        ["ps", "-C", "llama-server", "-o", "pid,rss,vsz"], capture_output=True, text=True,
    ).stdout
    meminfo = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in ("MemTotal", "MemAvailable", "MemFree", "Cached"):
            meminfo[key] = value.strip()
    result["meminfo"] = meminfo
    result["amd"] = {}
    for card in sorted(Path("/sys/class/drm").glob("card[0-9]*/device")):
        values = {}
        for name in ("vendor", "mem_info_vram_used", "mem_info_vram_total"):
            file = card / name
            if file.exists():
                values[name] = file.read_text().strip()
        if values.get("vendor") == "0x1002":
            result["amd"][str(card)] = values
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--steps", default="2048,8192,32768,65536,98304,126976")
    parser.add_argument("--generate", type=int, default=8)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    command = json.loads(args.command.read_text())
    (args.output / "command.json").write_text(json.dumps(command, indent=2))
    start = time.monotonic()
    with (args.output / "server.log").open("w") as log:
        server = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f"Server exited with {server.returncode}; see server.log")
                try:
                    request("/health", timeout=2)
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() - start > 900:
                        raise TimeoutError("Server did not become ready in 900 seconds")
                    time.sleep(2)
            print(f"ready in {time.monotonic() - start:.1f}s", flush=True)
            (args.output / "initial.json").write_text(json.dumps(snapshot(), indent=2))

            base = "\n".join(
                f"Record {i}: a Kubernetes worker processes requests using CPU memory, GPU memory, and PCIe transfers. "
                "Compare latency, throughput, scheduling, and data locality; explain the tradeoffs with examples."
                for i in range(600)
            )
            steps = [int(n) for n in args.steps.split(",")]
            tokens = request("/tokenize", {"content": base * 6, "add_special": True})["tokens"]
            if len(tokens) < max(steps) + args.generate:
                raise ValueError(f"Only {len(tokens)} tokens available")
            (args.output / "tokens.json").write_text(json.dumps(tokens[:max(steps) + 512]))

            previous = 0
            for step in steps:
                payload = {
                    "prompt": tokens[:step], "n_predict": args.generate,
                    "temperature": 0, "seed": 42, "ignore_eos": True,
                    "cache_prompt": True, "stream": False, "id_slot": 0,
                }
                before = time.monotonic()
                response = request("/completion", payload)
                elapsed = time.monotonic() - before
                timings = response["timings"]
                if timings["cache_n"] + timings["prompt_n"] != step:
                    raise RuntimeError(f"Prompt accounting mismatch at {step}: {timings}")
                reprocessed = timings["cache_n"] < previous
                previous = step
                row = {
                    "fill": step, "wall_seconds": elapsed, "reprocessed": reprocessed,
                    "timings": timings, "snapshot": snapshot(),
                }
                (args.output / f"fill-{step}.json").write_text(json.dumps(response, indent=2))
                with (args.output / "results.jsonl").open("a") as output:
                    output.write(json.dumps(row) + "\n")
                used = [line.split(",")[1].strip() for line in row["snapshot"]["nvidia_smi"].splitlines()[1:]]
                print(f"fill={step} prompt_n={response['timings']['prompt_n']} "
                      f"prompt_tps={response['timings']['prompt_per_second']:.1f} "
                      f"tg_tps={response['timings']['predicted_per_second']:.1f} cuda_used={used}", flush=True)

            # Steady-state generation at the deepest fill: one fresh token per
            # request keeps the cached prefix, then generate 8 and 128 tokens.
            seq = tokens[: max(steps) + 512]
            position = steps[-1] + args.generate
            for count in (8, 128):
                payload = {
                    "prompt": seq[:position + 1], "n_predict": count,
                    "temperature": 0, "seed": 42, "ignore_eos": True,
                    "cache_prompt": True, "stream": False, "id_slot": 0,
                }
                response = request("/completion", payload)
                timings = response["timings"]
                if timings["cache_n"] + timings["prompt_n"] != len(payload["prompt"]):
                    raise RuntimeError(f"Prompt accounting mismatch for gen-{count}: {timings}")
                row = {
                    "fill": position, "measure": f"gen-{count}",
                    "reprocessed": timings["cache_n"] < position,
                    "timings": timings, "snapshot": snapshot(),
                }
                (args.output / f"gen-{count}.json").write_text(json.dumps(response, indent=2))
                with (args.output / "results.jsonl").open("a") as output:
                    output.write(json.dumps(row) + "\n")
                print(f"gen={count} at fill={position} prompt_n={timings['prompt_n']} "
                      f"tg_tps={timings['predicted_per_second']:.1f} "
                      f"per_token_ms={timings['predicted_per_token_ms']:.1f}", flush=True)
                position += 1 + count
        finally:
            server.terminate()
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
