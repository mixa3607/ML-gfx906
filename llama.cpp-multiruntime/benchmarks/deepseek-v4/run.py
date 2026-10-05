#!/usr/bin/env python3
"""Run a saved llama-server command and reproducible uncached HTTP requests."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time
import urllib.error
import urllib.request


def request(endpoint, payload=None, timeout=1800):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:18080" + endpoint, data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def snapshot():
    result = {}
    for command in [
        ["nvidia-smi", "--query-gpu=index,name,memory.used,utilization.gpu,power.draw,temperature.gpu", "--format=csv"],
        ["ps", "-eo", "pid,comm,pcpu,rss"],
    ]:
        proc = subprocess.run(command, capture_output=True, text=True)
        result[command[0]] = proc.stdout
    result["amd"] = {}
    for card in Path("/sys/class/drm").glob("card[0-9]*/device"):
        values = {}
        for name in ("vendor", "numa_node", "mem_info_vram_used", "mem_info_vram_total", "gpu_busy_percent"):
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
    parser.add_argument("--lengths", default="512,2048")
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--generate", type=int, default=128)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    command = json.loads(args.command.read_text())
    (args.output / "command.json").write_text(json.dumps(command, indent=2))
    (args.output / "before.json").write_text(json.dumps(snapshot(), indent=2))
    rows = []
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
            (args.output / "props.json").write_text(json.dumps(request("/props"), indent=2))
            (args.output / "loaded.json").write_text(json.dumps(snapshot(), indent=2))
            text = args.prompt_file.read_text() if args.prompt_file else "\n".join(
                f"Record {i}: a Kubernetes worker processes requests using CPU memory, GPU memory, and PCIe transfers. "
                "Compare latency, throughput, scheduling, and data locality; explain the tradeoffs with examples."
                for i in range(600)
            )
            tokens = request("/tokenize", {"content": text, "add_special": True})["tokens"]
            lengths = [int(n) for n in args.lengths.split(",")]
            if len(tokens) < max(lengths):
                max_length = len(tokens) - 1
                print(f"clamping lengths {lengths} to available {max_length} tokens", flush=True)
                lengths = [min(n, max_length) for n in lengths]
            (args.output / "tokens.json").write_text(json.dumps(tokens[:max(lengths)]))

            def complete(length, count):
                payload = {
                    "prompt": tokens[:length], "n_predict": count,
                    "temperature": 0, "seed": 42, "ignore_eos": True,
                    "cache_prompt": False, "stream": False, "id_slot": 0,
                }
                before = time.monotonic()
                response = request("/completion", payload)
                elapsed = time.monotonic() - before
                if response.get("tokens_predicted") != count:
                    raise RuntimeError(f"Unexpected generation count: {response}")
                if response["timings"]["prompt_n"] != length:
                    raise RuntimeError(f"Prompt was not fully evaluated: {response['timings']}")
                return response, elapsed

            warmup, _ = complete(128, 16)
            (args.output / "warmup.json").write_text(json.dumps(warmup, indent=2))
            for length in lengths:
                for repeat in range(args.repetitions):
                    response, elapsed = complete(length, args.generate)
                    (args.output / f"response-{length}-{repeat}.json").write_text(json.dumps(response, indent=2))
                    row = {
                        "prompt": length, "generate": args.generate, "repeat": repeat,
                        "wall_seconds": elapsed, "timings": response["timings"],
                        "content_sha256": hashlib.sha256(response["content"].encode()).hexdigest(),
                    }
                    rows.append(row)
                    with (args.output / "results.jsonl").open("a") as output:
                        output.write(json.dumps(row) + "\n")
                    print(json.dumps(row), flush=True)
            summary = []
            for length in lengths:
                samples = [row for row in rows if row["prompt"] == length]
                summary.append({
                    "prompt": length, "generate": args.generate,
                    "pp_tps_median": statistics.median(row["timings"]["prompt_per_second"] for row in samples),
                    "tg_tps_median": statistics.median(row["timings"]["predicted_per_second"] for row in samples),
                    "tg_tps_min": min(row["timings"]["predicted_per_second"] for row in samples),
                    "tg_tps_max": max(row["timings"]["predicted_per_second"] for row in samples),
                })
            (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
            print(json.dumps(summary, indent=2), flush=True)
        finally:
            (args.output / "after.json").write_text(json.dumps(snapshot(), indent=2))
            server.terminate()
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
