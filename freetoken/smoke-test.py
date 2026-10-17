import argparse
import concurrent.futures
import json
import time
import urllib.request


parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:1919")
parser.add_argument("--benchmark", action="store_true")
args = parser.parse_args()


def get(path):
    with urllib.request.urlopen(args.url + path, timeout=30) as response:
        return json.load(response)


def complete(prompt, stream=False, max_tokens=64):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": stream,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if stream:
        body["stream_options"] = {"include_usage": True}
    request = urllib.request.Request(
        args.url + "/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    first_token = None
    text = ""
    usage = None
    with urllib.request.urlopen(request, timeout=300) as response:
        if stream:
            for line in response:
                if not line.startswith(b"data: "):
                    continue
                payload = line[6:].strip()
                if payload == b"[DONE]":
                    break
                chunk = json.loads(payload)
                usage = chunk.get("usage") or usage
                for choice in chunk.get("choices", []):
                    content = choice.get("delta", {}).get("content") or ""
                    if content and first_token is None:
                        first_token = time.perf_counter() - start
                    text += content
        else:
            payload = json.load(response)
            text = payload["choices"][0]["message"].get("content") or ""
            usage = payload.get("usage")
    elapsed = time.perf_counter() - start
    assert text.strip(), payload
    result = {
        "prompt": prompt,
        "stream": stream,
        "text": text,
        "seconds": round(elapsed, 3),
        "ttft_seconds": round(first_token, 3) if first_token is not None else None,
        "usage": usage,
    }
    if usage and usage.get("completion_tokens"):
        result["end_to_end_tokens_per_second"] = round(usage["completion_tokens"] / elapsed, 2)
        if first_token is not None and usage["completion_tokens"] > 1:
            result["decode_tokens_per_second"] = round((usage["completion_tokens"] - 1) / (elapsed - first_token), 2)
    return result


health = get("/health")
models = get("/v1/models")
model = models["data"][0]["id"]
results = [complete("What is 2+2?")]
assert "4" in results[0]["text"], results[0]
results.append(complete("What is the capital of France? Answer with only the city name.", stream=True))
assert "paris" in results[-1]["text"].lower(), results[-1]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results.extend(pool.map(complete, ["Count from 1 to 5.", "Say hello in Russian.", "Name three colors.", "What is 3 + 5?"]))
if args.benchmark:
    for _ in range(2):
        results.append(complete("Write a detailed explanation of how computers work.", stream=True, max_tokens=128))
print(json.dumps({"health": health, "models": models, "results": results}, ensure_ascii=False, indent=2))
