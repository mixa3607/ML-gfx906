"""Exact-length DS4 benchmark: fresh engine per prompt, 256 outputs, EOS ignored."""
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time


ROOT = Path("/opt/maya")
OUT = Path(os.environ.get("MAYA_BENCH_OUT", "/results"))
MODEL = Path(os.environ["MAYA_BENCH_MODEL"])
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from serve.frontend import ChatTemplate
from strata_tokenizer import Tokenizer


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def prompts(pack):
    tok = Tokenizer.from_dir(pack / "tokenizer")
    template = ChatTemplate(pack / "tokenizer/chat_template.jinja")
    text = "\n".join(
        f"Experiment {i}: The team measured latency, throughput, memory use and numerical accuracy. "
        "Input sequences were processed on four accelerators, with remaining expert weights read from local storage. "
        "Results were recorded before changing any parameters, and every measurement used the same model."
        for i in range(1000))
    rendered = template.render([{"role": "user", "content": text +
                                "\nSummarize the experimental procedure in detail."}], enable_thinking=False,
                               reasoning_effort="none")
    ids = tok.encode(rendered, parse_special=True)
    assert len(ids) > 8192
    cases = [(0, [tok.special_ids["bos"]])]
    for count in (2048, 8192):
        # Keep the generation header and final instruction, truncate the middle.
        exact = ids[:count - 64] + ids[-64:]
        assert len(exact) == count
        cases.append((count, exact))
    return tok, cases


def benchmark(context, ids, tok, pack):
    case = OUT / f"ctx-{context}"
    case.mkdir()
    save(case / "input-ids.json", ids)
    (case / "input.txt").write_text(tok.decode(ids))
    args = [str(ROOT / "build-hip/maya-ds4"), "--serve", "--pack", str(pack),
            "--gpus", "0,1,2,3", "--max-context", "8704", "--reserve-mib", "4096",
            "--cpu-threads", "16", "--tp", "1", "--threads", "off", "--prefill-chunk", "0",
            "--dspark", "none", "--vision", "off", "--mmap-experts", "on",
            "--expert-profile", "none", "--eos", "-1"]
    save(case / "command.json", args)
    started = time.monotonic()
    with (case / "engine.log").open("w") as stderr, (case / "protocol.log").open("w") as protocol:
        proc = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=stderr, text=True, bufsize=1, start_new_session=True)
        lines = queue.Queue()

        def read():
            for line in proc.stdout:
                protocol.write(line)
                protocol.flush()
                lines.put(line.strip())
            lines.put(None)

        reader = threading.Thread(target=read, daemon=True)
        reader.start()

        def receive(deadline):
            while True:
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError(f"ctx {context}: engine deadline exceeded")
                try:
                    line = lines.get(timeout=min(left, 10))
                except queue.Empty:
                    continue
                if line is None:
                    raise RuntimeError(f"ctx {context}: engine exited {proc.poll()}")
                if line.startswith("ERR"):
                    raise RuntimeError(line)
                return line

        try:
            deadline = started + 900
            info = []
            while True:
                line = receive(deadline)
                info.append(line)
                if line.startswith("READY "):
                    break
            load_seconds = time.monotonic() - started
            print(f"ctx={context}: engine ready in {load_seconds:.2f}s, actual prompt={len(ids)}", flush=True)
            t0 = time.monotonic()
            proc.stdin.write("GEN 256 temperature=0 " + ",".join(map(str, ids)) + "\n")
            proc.stdin.flush()
            output = []
            first_token = None
            stat = ""
            deadline = t0 + 1800
            while True:
                line = receive(deadline)
                if line.startswith("T "):
                    output.append(int(line.split()[1]))
                    if first_token is None:
                        first_token = time.monotonic() - t0
                elif line.startswith("PP "):
                    fields = line.split()
                    if int(fields[1]) % 1024 == 0 or int(fields[1]) == len(ids):
                        print(f"ctx={context}: {line}", flush=True)
                elif line.startswith("STAT "):
                    stat = line
                elif line.startswith("DONE "):
                    done = line.split()
                    break
            wall = time.monotonic() - t0
            generated, prompt = int(done[1]), int(done[2])
            prompt_ms, decode_ms = float(done[3]), float(done[4])
            reused = int(done[8])
            assert len(output) == generated == 256, (generated, len(output))
            assert prompt == len(ids) and reused == 0, (prompt, reused)
            assert done[5] == "length" and int(done[7]) == 0, done
            save(case / "output-ids.json", output)
            (case / "output.txt").write_text(tok.decode(output))
            result = {"requested_context": context, "actual_prompt_tokens": prompt,
                      "cached_tokens": reused, "generated_tokens": generated,
                      "prompt_ms": prompt_ms, "decode_ms": decode_ms,
                      "prefill_tok_s": prompt * 1000 / prompt_ms if prompt_ms else None,
                      "decode_tok_s": generated * 1000 / decode_ms,
                      "decode_forward_steps_s": (generated - 1) * 1000 / decode_ms,
                      "wall_seconds": wall, "first_token_seconds": first_token,
                      "load_seconds": load_seconds, "last_stat": stat, "info": info,
                      "output_preview": tok.decode(output)[:300]}
            save(case / "result.json", result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return result
        finally:
            if proc.poll() is None:
                try:
                    proc.stdin.write("QUIT\n")
                    proc.stdin.flush()
                    proc.wait(timeout=20)
                except (OSError, subprocess.TimeoutExpired):
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
            reader.join(timeout=5)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pack = OUT / "pack"
    with (OUT / "pack.log").open("w") as log:
        subprocess.run([sys.executable, "tools/ds4/pack_gguf.py", "--model", str(MODEL),
                        "--out", str(pack)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    tok, cases = prompts(pack)
    summary = {"results": [], "method": "fresh process per context; no KV reuse; EOS disabled; greedy"}
    try:
        for context, ids in cases:
            summary["results"].append(benchmark(context, ids, tok, pack))
            save(OUT / "summary.json", summary)
            time.sleep(3)  # Let HIP release the previous process's allocations.
        summary["completed"] = True
    except Exception as error:
        summary["error"] = repr(error)
        raise
    finally:
        save(OUT / "summary.json", summary)


if __name__ == "__main__":
    main()
