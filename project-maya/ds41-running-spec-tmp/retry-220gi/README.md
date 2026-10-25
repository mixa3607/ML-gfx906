# Approved 220Gi retry

**Completed: A/C measured; C decode +29.7%, full-request wall unchanged.
B was OOM-killed. See [RESULTS.md](RESULTS.md). Both pods are deleted; do not
rerun these GPU commands without approval for a new run.**

Repeat A/B/C once, same frozen cases and model/configuration, with a uniform
220Gi cap. No parameter sweep or automatic retry. Production stays at zero;
HF cache and the production PVC remain read-only. Pod manifest:
`../pod.220gi.yaml`. The first attempt's evidence remains in the parent folder.

The new `../collect.py` runs locally, receiving JSON-framed file updates from
the pod over one unlimited-timeout `kubectl exec -i` connection. Native stderr
is streamed by a separate reader; native stdout protocol is streamed in chunks.
The runner captures timings before exporting each completed request. Collector
fsyncs the artifacts and directories, then ACKs the start/ready/result/final
checkpoint before the runner proceeds. Every 15 seconds a lightweight cgroup
snapshot is exported. The local `run/` directory survives a pod or cgroup OOM.
No competing pipe readers and no GPU retries are used.

Files under `run/` are written incrementally, not reconstructed after failure.
`run/exit.json` records the client exit status and result count. Only six valid
requests and a complete per-mode manifest may be scored. Raw native timings
exclude HTTP; token delivery is bursty with DSpark and is not an ITL measure.

Before GPU work, CPU-only collector tests exercise ACK handling and verify a
saved result survives a simulated remote exit 137. Run those with
`python3 -m unittest discover -s .. -p 'test_*.py'` from this directory.

Run command (from repository root, after preparing/uploading the inputs):

```bash
python3 project-maya/ds41-running-spec-tmp/collect.py \
  --out project-maya/ds41-running-spec-tmp/retry-220gi/run -- \
  kubectl -n apps-ml exec -i maya-ds41-spec-screen-220gi -- \
  env BENCH_STREAM=1 BENCH_MEMORY_GIB=220 python /data/screen/screen.py
```

Use an unlimited external tool timeout. Do not restart that command if the
connection fails; preserve `run/` and inspect the original process instead.

## Continuation after B's OOM

The initial retry completed all six A requests, then B was OOM-killed during
load at 220Gi. All A measurements and B's start/log/heartbeat survived locally.
B's native log reports 11935/11935 CPU experts copied (224.4 GB); the kernel
then records the cgroup OOM while further host/GPU memory was allocated.
There is no B throughput or acceptance result.

The failed pod was deleted (`cleanup-b.txt`). Only the still-unstarted C mode
was continued in a replacement pod using the identical manifest and 220Gi cap;
neither A nor B was repeated. Frozen cases and the original seed SHA-256 were
verified again before C. This is still three total engine starts, not a new
parameter sweep. `pod-start.json` and `pod-c-start.json` record both pod UIDs.

The C collector writes `run-c/`; its CLI uses `--modes C-on-spread` and the
remote runner uses `--mode C-on-spread`. `screen-abc.py` preserves the exact
A/B runner (SHA-256 verified against A's manifest); `screen-c.py` adds only
single-mode selection. `stream.py`, runtime and measurement logic are shared.
All source changes and collector tests precede C's start.

Combined summary command:

```bash
python3 project-maya/ds41-running-spec-tmp/summarize.py \
  project-maya/ds41-running-spec-tmp/retry-220gi/run \
  --additional-root project-maya/ds41-running-spec-tmp/retry-220gi/run-c
```

Replacing the failed pod also changes memory-cgroup/file-cache accounting.
Filesystem caches can survive process starts or be reclaimed after an OOM;
this fixed-order screen must not be described as a controlled cache-state
comparison or a reverse-order repeat.
