"""Russian multi-topic tuning; one persistent engine per launch configuration."""
import json
import os
from pathlib import Path
import queue
import shutil
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


TOPICS = {
    "climate": (
        "Климат и городская инфраструктура",
        ["Городские деревья затеняют тротуары и уменьшают нагрев поверхности летом.",
         "При проектировании водоотведения учитывают площадь водосбора и интенсивность осадков.",
         "Датчики температуры устанавливают вдали от прямого солнечного света и вентиляционных выбросов.",
         "Проницаемые покрытия помогают задерживать ливневый сток, но требуют обслуживания.",
         "Для сравнения районов нужны одинаковые интервалы наблюдений и проверка пропусков данных.",
         "Приоритет озеленения зависит от плотности населения, доступности воды и состояния почвы."],
        "Предложи на русском языке подробный план адаптации городского района к жаре и сильным дождям. "
        "Раздели меры на инженерные, организационные и измерительные; объясни ограничения и порядок проверки результатов."),
    "databases": (
        "Базы данных и надёжность сервиса",
        ["Сервис обрабатывает заказы через очередь, а результат сохраняет в транзакционной базе данных.",
         "Повторная доставка сообщения возможна после сбоя подтверждения; обработчики должны быть идемпотентными.",
         "Индекс ускоряет часть запросов, но увеличивает стоимость записи и расход дискового пространства.",
         "Резервную копию проверяют восстановлением на отдельном экземпляре, а не только фактом создания архива.",
         "Репликация не заменяет резервное копирование, поскольку ошибочное удаление может попасть на реплики.",
         "Увеличение числа соединений без измерений может усилить конкуренцию за блокировки."],
        "Напиши на русском подробный план повышения надёжности сервиса заказов. "
        "Объясни транзакции, идемпотентность, восстановление и метрики; не подменяй гарантии обещаниями."),
    "history": (
        "История торговли и работа с источниками",
        ["Историки сопоставляют таможенные записи, письма купцов, карты и археологические находки.",
         "Объём сохранившихся документов зависит от работы архивов и не равен объёму всей торговли.",
         "Речные маршруты снижали стоимость перевозки тяжёлых грузов, но зависели от сезона и состояния пристаней.",
         "В разных городах использовали разные меры веса и денежные единицы; прямое сравнение цен требует пересчёта.",
         "Изменение торгового пути может иметь несколько причин: безопасность, пошлины, спрос и транспортные технологии.",
         "Поздняя копия документа и оригинал имеют разную историю происхождения и требуют отдельной проверки."],
        "Объясни по-русски, как исследовать изменение региональных торговых путей по разнородным источникам. "
        "Дай развёрнутый пошаговый метод, способы проверки гипотез и ограничения выводов."),
    "biology": (
        "Экология и планирование полевого исследования",
        ["Численность насекомых на участке зависит от сезона, погоды, растительности и способа учёта.",
         "Контрольные и исследуемые участки подбирают по сходным характеристикам до начала вмешательства.",
         "Наблюдения повторяют в одинаковое время суток и фиксируют условия отбора проб.",
         "Отсутствие вида в одной пробе не доказывает его отсутствие на всей территории.",
         "Несколько измерений на одном участке не всегда являются независимыми повторностями.",
         "Нужны предварительный план анализа, описание неопределённости и сохранение исходных наблюдений."],
        "Составь на русском языке подробный план исследования влияния озеленения на насекомых-опылителей. "
        "Опиши контроль, повторности, измерения, смешивающие факторы и честную интерпретацию результатов."),
}


def make_cases(pack):
    tok = Tokenizer.from_dir(pack / "tokenizer")
    template = ChatTemplate(pack / "tokenizer/chat_template.jinja")

    def encode(text):
        return tok.encode(template.render([{"role": "user", "content": text}],
                                         enable_thinking=False, reasoning_effort="none"), parse_special=True)

    cases = []
    for topic, size in [("biology", 2048), ("climate", 2048), ("databases", 2048),
                        ("history", 8192), ("biology", 2048)]:
        title, facts, task = TOPICS[topic]
        # Vary vocabulary and paragraph order, rather than repeat one benchmark sentence.
        records = [f"Наблюдение {i + 1}. " + " ".join(facts[(i + j) % len(facts)] for j in range(3))
                   for i in range(400)]
        full = encode(title + "\n\n" + "\n".join(records) + "\n\n" + task)
        assert len(full) > size
        ids = full[:size - 128] + full[-128:]
        name = f"{topic}-{size}"
        if not cases:
            name = "warmup-biology-2048"
        cases.append({"name": name, "ids": ids, "tg": 64 if not cases else 256,
                      "warmup": not cases})
    checks = [{"name": "check-arithmetic", "ids": encode("Сколько будет 2 + 2? Ответь только числом."),
               "tg": 16, "expected": "4"},
              {"name": "check-geography", "ids": encode("Назови столицу России. Ответь только названием города."),
               "tg": 16, "expected": "Москва"}]
    for case in cases + checks:
        directory = OUT / "inputs" / case["name"]
        directory.mkdir(parents=True, exist_ok=True)
        save(directory / "ids.json", case["ids"])
        (directory / "text.txt").write_text(tok.decode(case["ids"]))
    return tok, cases, checks


def sample(stop, path):
    relative = next(line[3:] for line in Path("/proc/self/cgroup").read_text().splitlines()
                    if line.startswith("0::"))
    cgroup = Path("/sys/fs/cgroup") / relative.lstrip("/")
    with path.open("w") as log:
        while not stop.is_set():
            row = {"time": time.time()}
            for name in ("memory.current", "memory.peak", "memory.max", "memory.events", "cpu.stat", "cpu.max", "io.stat"):
                file = cgroup / name
                if file.exists():
                    row[name] = file.read_text().strip()
            row["gpus"] = {}
            for device in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
                base = device / "device"
                if (base / "mem_info_vram_used").exists():
                    row["gpus"][device.name] = {
                        key: (base / key).read_text().strip()
                        for key in ("mem_info_vram_used", "gpu_busy_percent")}
            log.write(json.dumps(row) + "\n")
            log.flush()
            stop.wait(2)


class Engine:
    def __init__(self, directory, config, pack):
        self.directory = directory
        directory.mkdir()
        self.config = config
        self.lines = queue.Queue()
        self.stderr = (directory / "engine.log").open("w")
        self.protocol = (directory / "protocol.log").open("w")
        # Start each configuration with the same generic profile, then keep all updates within that run.
        profile = directory / "expert-profile.bin"
        shutil.copyfile(ROOT / "data/expert-profile-ds4.bin", profile)
        args = [config.get("binary", str(ROOT / "build-hip/maya-ds4")), "--serve", "--pack", str(pack),
                "--gpus", "0,1,2,3", "--max-context", "8704", "--reserve-mib", str(config["reserve"]),
                "--cpu-threads", str(config["cpu"]), "--tp", str(config.get("tp", 1)),
                "--threads", config.get("threads", "on"), "--prefill-chunk", str(config["chunk"]), "--dspark", "none",
                "--vision", "off", "--mmap-experts", config.get("mmap", "on"),
                 "--expert-profile", str(profile), "--eos", "-1"]
        args += config.get("extra_args", [])
        save(directory / "command.json", args)
        started = time.monotonic()
        env = dict(os.environ, OMP_NUM_THREADS=str(config["cpu"]))
        env.update(config.get("env", {}))
        self.proc = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.stderr, text=True, bufsize=1, env=env, start_new_session=True)
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()
        self.stop_sample = threading.Event()
        self.sampler = threading.Thread(target=sample, args=(self.stop_sample, directory / "resources.jsonl"), daemon=True)
        self.sampler.start()
        try:
            self.info = []
            while True:
                line = self.receive(started + 1200)
                self.info.append(line)
                if line.startswith("READY "):
                    break
            self.load_seconds = time.monotonic() - started
            print(f"{directory.name}: READY after {self.load_seconds:.2f}s", flush=True)
        except BaseException:
            self.close()
            raise

    def read(self):
        for line in self.proc.stdout:
            self.protocol.write(line)
            self.protocol.flush()
            self.lines.put(line.strip())
        self.lines.put(None)

    def receive(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("engine deadline exceeded")
        try:
            line = self.lines.get(timeout=remaining)
        except queue.Empty:
            raise TimeoutError("engine deadline exceeded") from None
        if line is None:
            raise RuntimeError(f"engine exited: {self.proc.poll()}")
        if line.startswith("ERR"):
            raise RuntimeError(line)
        return line

    def request(self, case, tok):
        started = time.monotonic()
        ids, tg = case["ids"], case["tg"]
        self.proc.stdin.write(f"GEN {tg} temperature=0 " + ",".join(map(str, ids)) + "\n")
        self.proc.stdin.flush()
        output, stat, first_token = [], "", None
        last_progress = None
        while True:
            line = self.receive(started + 1800)
            if line.startswith("T "):
                output.append(int(line.split()[1]))
                if first_token is None:
                    first_token = time.monotonic() - started
            elif line.startswith("STAT "):
                stat = line
            elif line.startswith("PP "):
                progress = int(line.split()[1])
                if progress != last_progress:
                    print(f"{self.directory.name}/{case['name']}: {line}", flush=True)
                    last_progress = progress
            elif line.startswith("DONE "):
                done = line.split()
                break
        wall = time.monotonic() - started
        generated, prompt, cached = int(done[1]), int(done[2]), int(done[8])
        pp_ms, tg_ms = float(done[3]), float(done[4])
        assert len(output) == generated == tg and prompt == len(ids), done
        assert done[5] == "length" and int(done[6]) == int(done[7]) == 0, done
        text = tok.decode(output)
        result = {"case": case["name"], "prompt_tokens": prompt, "cached_tokens": cached,
                  "output_tokens": generated, "prompt_ms": pp_ms, "decode_ms": tg_ms,
                  "prefill_tok_s": (prompt - cached) * 1000 / pp_ms if pp_ms else None,
                  "decode_tok_s": generated * 1000 / tg_ms, "wall_seconds": wall,
                  "first_token_seconds": first_token, "last_stat": stat,
                  "warmup": case.get("warmup", False), "output_preview": text[:400]}
        if "round" in case:
            result.update(round=case["round"], base_case=case["base_case"])
        if "expected" in case:
            # Only the answer before EOS matters; throughput requests intentionally ignore EOS stopping.
            answer = text.split("<｜end▁of▁sentence｜>")[0].strip()
            result["expected"] = case["expected"]
            result["check_pass"] = answer == case["expected"]
        directory = self.directory / case["name"]
        directory.mkdir()
        save(directory / "output-ids.json", output)
        (directory / "output.txt").write_text(text)
        save(directory / "result.json", result)
        print(json.dumps({"variant": self.directory.name, **result}, ensure_ascii=False), flush=True)
        return result

    def close(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.write("QUIT\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=20)
            except (OSError, subprocess.TimeoutExpired):
                os.killpg(self.proc.pid, signal.SIGTERM)
                try:
                    self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                    self.proc.wait()
        self.reader.join(timeout=5)
        self.stop_sample.set()
        self.sampler.join(timeout=5)
        self.stderr.close()
        self.protocol.close()


def run(config, pack, tok, cases, checks):
    name = f"cpu{config['cpu']}-chunk{config['chunk']}-reserve{config['reserve']}-tp{config.get('tp', 1)}"
    if config.get("label"):
        name += "-" + config["label"]
    directory = OUT / name
    result = {"name": name, "config": config, "requests": []}
    engine = None
    try:
        engine = Engine(directory, config, pack)
        result["load_seconds"] = engine.load_seconds
        result["info"] = engine.info
        rounds = int(os.environ.get("MAYA_TUNE_ROUNDS", "1"))
        assert rounds > 0
        requests = [c for c in cases if c.get("warmup")]
        for iteration in range(1, rounds + 1):
            for case in cases:
                if not case.get("warmup"):
                    requests.append({**case, "name": f"r{iteration}-{case['name']}" if rounds > 1 else case["name"],
                                     "round": iteration, "base_case": case["name"]})
        requests += checks
        result["measured_rounds"] = rounds
        for case in requests:
            result["requests"].append(engine.request(case, tok))
            save(directory / "summary.json", result)
        measured = [r for r in result["requests"] if not r["warmup"] and "check_pass" not in r]
        result["measured_wall_seconds"] = sum(r["wall_seconds"] for r in measured)
        result["decode_tok_s"] = sum(r["output_tokens"] for r in measured) / sum(r["decode_ms"] for r in measured) * 1000
        result["prefill_tok_s"] = sum(r["prompt_tokens"] - r["cached_tokens"] for r in measured) / sum(r["prompt_ms"] for r in measured) * 1000
        result["checks_pass"] = all(r["check_pass"] for r in result["requests"] if "check_pass" in r)
        result["completed"] = True
    except Exception as error:
        result["error"] = repr(error)
        if (directory / "engine.log").exists():
            print((directory / "engine.log").read_text()[-12000:], flush=True)
        print(f"{name}: FAILED {error!r}", flush=True)
    finally:
        if engine is not None:
            engine.close()
        directory.mkdir(exist_ok=True)
        save(directory / "summary.json", result)
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pack = OUT / "pack"
    with (OUT / "pack.log").open("w") as log:
        subprocess.run([sys.executable, "tools/ds4/pack_gguf.py", "--model", str(MODEL),
                        "--out", str(pack)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    tok, cases, checks = make_cases(pack)
    candidates = json.loads(os.environ.get("MAYA_TUNE_CONFIGS", '[{"cpu":48,"chunk":2048,"reserve":512},{"cpu":56,"chunk":2048,"reserve":512}]'))
    summary = {"variants": [], "method": "persistent engine across Russian topics; identical corpus/order; EOS disabled; no speculation"}
    index = 0
    while index < len(candidates):
        config = candidates[index]
        summary["variants"].append(run(config, pack, tok, cases, checks))
        save(OUT / "summary.json", summary)
        time.sleep(3)
        index += 1
        if index == 2 and os.environ.get("MAYA_TUNE_CONFIGS") is None:
            good = [r for r in summary["variants"] if r.get("completed") and r.get("checks_pass")]
            if good:
                best = min(good, key=lambda r: r["measured_wall_seconds"])
                candidates.append({**best["config"], "chunk": 8192})
    good = [r for r in summary["variants"] if r.get("completed") and r.get("checks_pass")]
    summary["completed"] = len(good) == len(candidates)
    if good:
        summary["fastest_measured"] = min(good, key=lambda r: r["measured_wall_seconds"])["name"]
    save(OUT / "summary.json", summary)
    if not summary["completed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
