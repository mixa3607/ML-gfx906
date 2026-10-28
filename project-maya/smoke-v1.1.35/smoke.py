#!/usr/bin/env python3
"""Serial functional requests only; no throughput benchmark or speed calibration."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


def request(path, payload=None, timeout=600):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8080" + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def image_url(blank=False):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (448, 224), "white")
    if not blank:
        draw = ImageDraw.Draw(image)
        draw.rectangle((32, 56, 184, 168), fill="red")
        draw.ellipse((264, 56, 376, 168), fill="blue")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def run_model(name, source, results):
    out = results / name
    out.mkdir(parents=True, exist_ok=True)
    cfg = Path("/data/config") / (name + ".json")
    env = dict(os.environ, MAYA_CONFIG=str(cfg), MAYA_CONFIG_TEMPLATE=str(source / name / "maya-config.json"))
    record = {"model": name, "requests": [], "ready": False}
    process = None
    try:
        with (out / "prepare.log").open("w") as log:
            subprocess.run(["bash", str(source / name / "prepare.sh")], env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=1800)
            # A second preparation must reuse the pack without touching cached weights.
            subprocess.run(["bash", str(source / name / "prepare.sh")], env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=120)
        sys.path.insert(0, "/opt/maya")
        import maya

        prepared = json.loads(cfg.read_text())
        if maya.needs_prefill_calibration(prepared) or maya.needs_speed_calibration(prepared):
            raise RuntimeError("config would trigger an automatic launcher calibration; refusing GPU launch")
        record["automatic_calibration_blocked"] = True
        with (out / "server.log").open("w") as log:
            process = subprocess.Popen(
                ["python", "maya.py", "--backend", "hip", "--config", str(cfg), "--plain",
                 "--host", "127.0.0.1", "--port", "8080"],
                cwd="/opt/maya", env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
            deadline = time.monotonic() + 1800
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("server exited before readiness: " + str(process.returncode))
                try:
                    record["health"] = request("/health", timeout=5)
                    record["models"] = request("/v1/models", timeout=5)
                    record["ready"] = True
                    break
                except (OSError, ValueError, urllib.error.URLError):
                    time.sleep(5)
            else:
                raise TimeoutError("server did not become ready")

            model = json.loads(cfg.read_text())["model_name"]

            def chat(label, messages, expected=None):
                item = {"case": label, "messages": messages}
                # Store image inputs by description, not duplicated base64 payloads.
                if label.startswith("image-"):
                    item["messages"] = "white image" if label == "image-blank" else "red rectangle left, blue circle right"
                try:
                    response = request("/v1/chat/completions", {
                        "model": model, "messages": messages, "max_tokens": 384,
                        "temperature": 0, "seed": 1, "reasoning_effort": "none", "stream": False,
                    })
                    item["response"] = response
                    message = response["choices"][0]["message"]
                    content = message.get("content") or ""
                    item["nonempty"] = bool(content.strip())
                    if expected:
                        item["expected"] = expected
                        item["contains_expected"] = all(word.lower() in content.lower() for word in expected)
                    print(name, label, json.dumps(message, ensure_ascii=False), flush=True)
                    return message
                except Exception as error:
                    item["error"] = str(error)
                    print(name, label, "ERROR", str(error), flush=True)
                    return None
                finally:
                    record["requests"].append(item)
                    (out / "results.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")

            chat("arithmetic", [{"role": "user", "content": "Вычисли 17 * 23. Ответь только числом."}], ["391"])
            chat("russian", [{"role": "user", "content": "Двумя короткими предложениями по-русски объясни, почему зимой замерзает вода."}])
            chat("python", [{"role": "user", "content": "Напиши функцию Python square_even(xs), которая возвращает квадраты только чётных чисел из xs, сохраняя порядок. Только код."}], ["def square_even"])
            first = {"role": "user", "content": "Запомни: условное имя моего проекта — Листопад, его код — 48271. Ответь коротко, что запомнил."}
            answer = chat("conversation-start", [first])
            if answer:
                chat("conversation-followup", [first, {"role": "assistant", "content": answer.get("content") or ""},
                     {"role": "user", "content": "Какое имя и код у моего проекта?"}], ["Листопад", "48271"])
            if name != "cyber-frost":
                for blank in (False, True):
                    chat("image-blank" if blank else "image-shapes", [{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": image_url(blank)}},
                        {"type": "text", "text": "Describe this image briefly. State the colors and shapes if any are visible."},
                    ]}])
    except Exception as error:
        record["error"] = str(error)
        print(name, "FAILED", str(error), flush=True)
    finally:
        if process is not None:
            try:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=30)
            record["server_exit"] = process.returncode
            # Also reap a child engine left behind by an early wrapper exit.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            time.sleep(10)
        engine_log = Path("/data") / name / "engine.log"
        if engine_log.exists():
            (out / "engine.log").write_bytes(engine_log.read_bytes())
        (out / "results.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", choices=("glm-s24", "minimax-xs", "cyber-frost"))
    parser.add_argument("--source", type=Path, default=Path("/work"))
    parser.add_argument("--results", type=Path, default=Path("/data/results"))
    args = parser.parse_args()
    args.results.mkdir(parents=True, exist_ok=True)
    records = [run_model(model, args.source, args.results) for model in args.models]
    failed = any(not record["ready"] or record.get("error") or
                 any(item.get("error") or not item.get("nonempty") or item.get("contains_expected") is False
                     for item in record["requests"]) for record in records)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
