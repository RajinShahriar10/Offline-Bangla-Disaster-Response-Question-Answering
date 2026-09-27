# -*- coding: utf-8 -*-
"""measure_footprint.py — per-model disk+RAM benchmark for the paper (run AFTER the 512 run).

For each model, loads it in Ollama (llama-server hosts the weights), streams a
short Bangla generation while sampling the llama-server process WorkingSet, then
records:
  * disk (from `ollama list`)
  * peak resident RAM delta (model loaded vs baseline, llama-server)
  * throughput (tok/s) + first-token latency  (uses the real benchmark prompt)
Output: results/footprint.txt
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)
import eval_llm as ev

SERVER = "http://127.0.0.1:11434"
MODELS = [
    ("titulm-v1.1-1b", "titulm-v1.1-1b:latest"),
    ("titulm-v1.1-3b", "titulm-v1.1-3b:latest"),
    ("gemma3:1b", "gemma3:1b"),
    ("gemma3:4b", "gemma3:4b"),
    ("qwen3:1.7b", "qwen3:1.7b"),
    ("qwen3:4b-instruct-2507-q4_K_M", "qwen3:4b-instruct-2507-q4_K_M"),
]
PROMPT = ev.BANGLA_PROMPT_TMPL.format(
    question="বন্যা পরিস্থিতিতে নিরাপদ আশ্রয় কোথায় পাব এবং কীভাবে যোগাযোগ করব?")

PS = ("Get-Process | Where-Object { $_.ProcessName -eq 'llama-server' } "
      "| Select-Object Id,WorkingSet64 | ConvertTo-Json")


def ollama_list():
    try:
        out = subprocess.check_output(
            [os.environ.get("OLLAMA", ""), "list"],
            shell=True, text=True, stderr=subprocess.DEVNULL,
        ) if os.environ.get("OLLAMA") else subprocess.check_output(
            ["ollama", "list"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        out = ""
    size_map = {}
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            size_map[parts[0]] = parts[2]
    return size_map


def llama_workingset():
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", PS], text=True).strip()
    except Exception:
        return 0.0
    if not out or out == "null":
        return 0.0
    data = json.loads(out)
    if isinstance(data, dict):
        data = [data]
    return sum(int(p["WorkingSet64"] or 0) for p in data) / 1e6


def ollama_ps_loaded_labels():
    try:
        out = subprocess.check_output(["ollama", "ps"], text=True,
                                      stderr=subprocess.DEVNULL)
    except Exception:
        return []
    return [ln.split()[0] for ln in out.splitlines()[1:] if ln.split()]


def unload_and_wait(name, timeout=90):
    try:
        body = json.dumps({
            "model": name, "prompt": "টেস্ট",
            "stream": False, "options": {"num_predict": 1},
            "keep_alive": 0,
        }).encode()
        req = urllib.request.Request(SERVER + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=120).read()
    except Exception:
        pass
    t0 = time.time()
    while time.time() - t0 < timeout:
        if name not in ollama_ps_loaded_labels():
            return True
        time.sleep(1.5)
    return False


def generate(model, n=96):
    payload = {
        "model": model, "prompt": PROMPT,
        "stream": True, "options": {"num_predict": n, "temperature": 0.0},
        "keep_alive": 0,
    }
    if model.split(":")[0].lower().startswith("qwen3"):
        payload["think"] = False
    body = json.dumps(payload).encode()
    req = urllib.request.Request(SERVER + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    first = None
    tokens = 0
    with urllib.request.urlopen(req, timeout=300) as r:
        for line in r:
            try:
                j = json.loads(line)
            except Exception:
                continue
            if j.get("response"):
                if first is None:
                    first = time.time() - t0
                tokens += 1
    return first, tokens, time.time() - t0


def main():
    size_map = ollama_list()
    lines = []
    A = lines.append
    A("=" * 78)
    A("PER-MODEL FOOTPRINT & THROUGHPUT (CPU, %s)" % time.strftime("%Y-%m-%d %H:%M"))
    A("=" * 78)
    A("%-30s %8s %10s %10s %9s %9s" % ("model", "disk", "peakRAM", "tok/s", "tTFB_s", "t_gen_s"))

    def watch(evt, peak):
        while not evt.is_set():
            try:
                cur = llama_workingset()
                if cur > peak[0]:
                    peak[0] = cur
            except Exception:
                pass
            time.sleep(0.3)

    for label, name in MODELS:
        try:
            if size_map.get(name):
                disk = size_map[name]
            else:
                truth = ollama_list()
                disk = truth.get(label) or truth.get(name) or "?"
        except Exception:
            disk = "?"
        try:
            unload_and_wait(name)
        except Exception:
            pass
        try:
            baseline = llama_workingset()
        except Exception:
            baseline = 0.0
        evt = threading.Event()
        peak = [0.0]
        th = threading.Thread(target=watch, args=(evt, peak), daemon=True)
        th.start()
        try:
            tfb, tok, t = generate(name)
        except Exception as e:
            evt.set()
            A("%-30s %8s  ERROR %s" % (label, disk, str(e)[:40]))
            continue
        evt.set()
        th.join(timeout=3)
        delta = max(peak[0] - baseline, 0.0)
        A("%-30s %8s %7d MB %8.1f %9.2f %9.1f" % (
            label, disk, round(delta), tok / t if t > 0 else 0, tfb or 0, t))
    A("")
    A("disk % = ollama list size (quantized file). peakRAM = llama-server WorkingSet")
    A("delta, model unloaded-then-loaded per model (sampled during streaming).")
    A("tTFB = time-to-first-token (streaming). tok/s = tokens / total wall time.")
    text = "\n".join(lines)
    out = os.path.join(PROJ, "results", "footprint.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()