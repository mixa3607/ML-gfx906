"""Launch a bounded tuning Job using the existing GPU smoke-test pod layout."""
import argparse
import json
from pathlib import Path
import subprocess

import yaml


def kubectl(*args, value=None):
    return subprocess.check_output(["kubectl", "-n", "apps-ml", *args],
                                   input=json.dumps(value).encode() if value is not None else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configs", help='JSON array, e.g. [{"cpu":48,"chunk":2048,"reserve":512}]')
    parser.add_argument("--prefix", default="maya-ds41-ru-tune-")
    parser.add_argument("--image", default=("registry.arkprojects.space/apps/maya-gfx906:v1.1.21-rocm-10.1@"
                        "sha256:56060bf3f2408f13d94a7cb6aa5a3a327004016740304bb9d06036dabdc8ec73"))
    parser.add_argument("--rounds", type=int, default=1, help="Measured corpus passes per loaded engine")
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    root = Path(__file__).resolve().parents[1]
    script = Path(__file__).with_name("ds41-tune.py")
    job = yaml.safe_load((root / "test-job.yaml").read_text())
    job["metadata"]["generateName"] = args.prefix
    job["spec"].update(activeDeadlineSeconds=10800, ttlSecondsAfterFinished=86400)
    spec = job["spec"]["template"]["spec"]
    spec["nodeSelector"] = {"kubernetes.io/hostname": "kube-worker6.arkprojects.lan"}
    c = spec["containers"][0]
    c["name"] = "bench"
    c["image"] = args.image
    # No CPU quota; retain only a total RAM cap to respect the user's 192 GB budget.
    c["resources"] = {"requests": {"cpu": "1", "memory": "8Gi"}, "limits": {"memory": "192G"}}
    c["env"] = [
        {"name": "POD_NAME", "valueFrom": {"fieldRef": {"fieldPath": "metadata.name"}}},
        {"name": "MAYA_BENCH_OUT", "value": "/results/$(POD_NAME)"},
        {"name": "MAYA_BENCH_MODEL", "value": "/hf/hub/models--unsloth--DeepSeek-V4.1-Flash-1017-GGUF/"
         "snapshots/60ad3651641b5c97679c807e064ab1d7a3ca1455/UD-Q8_K_XL"},
        {"name": "HIP_VISIBLE_DEVICES", "value": "0,1,2,3"},
        {"name": "HSA_XNACK", "value": "0"},
        {"name": "DS4_ENGRAM_CACHE_MB", "value": "256"},
        {"name": "STRATA_DS4_RAM_TIER", "value": "0"},
        {"name": "STRATA_DS4_DISK_SKIP_W", "value": "0"},
        {"name": "STRATA_DS4_PROMPT_SKIP", "value": "0"},
        {"name": "MAYA_TUNE_ROUNDS", "value": str(args.rounds)},
    ]
    if args.configs:
        configs = json.loads(args.configs)
        assert isinstance(configs, list) and configs
        c["env"].append({"name": "MAYA_TUNE_CONFIGS", "value": json.dumps(configs)})
    c["command"] = ["python", "/bench/ds41-tune.py"]
    cm = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"generateName": args.prefix,
          "namespace": "apps-ml"}, "data": {script.name: script.read_text()}}
    cm_name = json.loads(kubectl("create", "-f", "-", "-o", "json", value=cm))["metadata"]["name"]
    c["volumeMounts"] += [{"name": "hf", "mountPath": "/hf", "readOnly": True},
                          {"name": "results", "mountPath": "/results"},
                          {"name": "bench", "mountPath": "/bench", "readOnly": True}]
    spec["volumes"] += [{"name": "hf", "hostPath": {"path": "/srv/ml/shared-hf-cache", "type": "Directory"}},
                        {"name": "results", "hostPath": {"path": "/srv/ml/maya-gfx906-tests", "type": "DirectoryOrCreate"}},
                        {"name": "bench", "configMap": {"name": cm_name}}]
    created = json.loads(kubectl("create", "-f", "-", "-o", "json", value=job))
    name = created["metadata"]["name"]
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    (logs / (name + "-spec.json")).write_text(json.dumps(created, indent=2))
    Path("/tmp/opencode/maya-ds41-tune-job").write_text(name)
    kubectl("patch", "configmap", cm_name, "--type=merge", "-p", json.dumps({"metadata": {
        "ownerReferences": [{"apiVersion": "batch/v1", "kind": "Job", "name": name,
                             "uid": created["metadata"]["uid"]}]}}))
    print("JOB", name, flush=True)
    selector = "batch.kubernetes.io/job-name=" + name
    kubectl("wait", "--for=create", "pod", "-l", selector, "--timeout=60s")
    kubectl("wait", "--for=jsonpath={.status.containerStatuses[0].containerID}",
            "pod", "-l", selector, "--timeout=10m")
    with (logs / (name + ".log")).open("wb") as log:
        proc = subprocess.Popen(["kubectl", "-n", "apps-ml", "logs", "-f", "job/" + name],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in proc.stdout:
            log.write(line)
            log.flush()
            print(line.decode(), end="", flush=True)
        if proc.wait():
            raise RuntimeError("kubectl logs failed")
    kubectl("wait", "--for=jsonpath={.status.containerStatuses[0].state.terminated.reason}",
            "pod", "-l", selector, "--timeout=90s")
    pods = json.loads(kubectl("get", "pods", "-l", selector, "-o", "json"))
    state = pods["items"][0]["status"]["containerStatuses"][0]["state"]
    print(json.dumps(state), flush=True)
    if state["terminated"]["exitCode"] != 0:
        raise SystemExit(state["terminated"]["exitCode"])


if __name__ == "__main__":
    main()
