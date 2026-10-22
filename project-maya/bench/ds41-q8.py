"""Bounded, local-only API smoke/bench using an existing DeepSeek GGUF set."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


MODEL = Path(os.environ["MAYA_BENCH_MODEL"])
OUT = Path(os.environ.get("MAYA_BENCH_OUT", "/results"))
ROOT = Path("/opt/maya")
BASE = "http://127.0.0.1:8080"


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def api(path, body=None, timeout=600):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pack = OUT / "pack"
    started = time.monotonic()
    with (OUT / "pack.log").open("w") as log:
        subprocess.run([sys.executable, "tools/ds4/pack_gguf.py", "--model", str(MODEL),
                        "--out", str(pack)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    print((OUT / "pack.log").read_text(), flush=True)
    config = {
        "exe": str(ROOT / "build-hip/maya-ds4"), "cwd": str(ROOT), "backend": "hip",
        "args": ["--pack", str(pack), "--gpus", "0,1,2,3", "--max-context", "2048",
                 "--reserve-mib", "4096", "--cpu-threads", "16", "--tp", "1",
                 "--threads", "off", "--prefill-chunk", "0", "--dspark", "none",
                 "--vision", "off", "--mmap-experts", "on", "--expert-profile", "none"],
        "tokenizer": str(pack / "tokenizer"), "log": str(OUT / "engine.log"),
        "model_name": "DeepSeek-V4.1-Flash-1017-UD-Q8_K_XL", "reasoning_effort": "none",
    }
    save("config.json", config)
    summary = {"config": config, "requests": [], "pack_seconds": time.monotonic() - started}
    with (OUT / "server.log").open("w") as log:
        server = subprocess.Popen([sys.executable, "serve/server.py", "--engine", "strata",
                                   "--config", str(OUT / "config.json"), "--host", "127.0.0.1",
                                   "--port", "8080"], cwd=ROOT, stdout=log,
                                  stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 1200
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f"server exited during startup: {server.returncode}")
                try:
                    health = api("/health", timeout=2)
                    break
                except (OSError, urllib.error.URLError):
                    if time.monotonic() > deadline:
                        raise TimeoutError("model startup exceeded 1200 seconds")
                    time.sleep(2)
            summary["startup_seconds"] = time.monotonic() - started
            save("health.json", health)
            save("models.json", api("/v1/models"))
            print(f"MODEL READY after {summary['startup_seconds']:.2f}s", flush=True)
            long_prompt = ("A benchmark checks correctness before optimizing performance. " * 24
                           + "Summarize the preceding text in one short sentence.")
            decode_prompt = "List the integers from 1 to 100, separated by commas, without any explanation."
            cases = [
                ("warmup", "Say hello.", 8),
                ("arithmetic", "What is 2 + 2? Reply with only the integer.", 32),
                ("geography", "What is the capital of France? Reply with only the city name.", 32),
                ("prefill", long_prompt, 32),
                ("prefill_repeat", long_prompt, 32),
                ("decode128", decode_prompt, 128),
                ("decode128_repeat", decode_prompt, 128),
            ]
            for name, prompt, count in cases:
                body = {"model": config["model_name"], "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": count, "temperature": 0, "seed": 1, "reasoning_effort": "none",
                        "stream": False}
                save(name + "-request.json", body)
                t0 = time.monotonic()
                result = api("/v1/chat/completions", body)
                elapsed = time.monotonic() - t0
                save(name + "-response.json", result)
                if "error" in result or not result.get("choices"):
                    raise RuntimeError(f"{name}: invalid completion: {result}")
                row = {"case": name, "wall_seconds": elapsed, "usage": result.get("usage"),
                       "timings": result.get("timings"), "message": result["choices"][0]["message"],
                       "finish_reason": result["choices"][0].get("finish_reason")}
                summary["requests"].append(row)
                save("summary.json", summary)
                save(name + "-metrics.json", api("/metrics"))
                print(json.dumps(row, ensure_ascii=False), flush=True)
            summary["completed"] = True
            save("summary.json", summary)
        except Exception as error:
            summary["error"] = repr(error)
            save("summary.json", summary)
            for name in ("server.log", "engine.log"):
                if (OUT / name).exists():
                    print(f"--- {name} ---\n" + (OUT / name).read_text()[-20000:], flush=True)
            raise
        finally:
            if server.poll() is None:
                os.killpg(server.pid, signal.SIGTERM)
                try:
                    server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(server.pid, signal.SIGKILL)
                    server.wait()


if __name__ == "__main__":
    main()
