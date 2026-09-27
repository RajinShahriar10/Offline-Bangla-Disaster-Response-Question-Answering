# -*- coding: utf-8 -*-
"""eval_llm.py — run compact open-source LLMs (via Ollama) over bangla_disaster_qa_seed.csv
and record outputs + latency metrics for the Efficiency-Accuracy-Safety study.

Usage:
    python eval_llm.py --model qwen2.5:3b --limit 20
    python eval_llm.py --model qwen2.5:3b --model phi3:mini --model gemma2:2b
    python eval_llm.py --model qwen2.5:3b --rowid 5 --rowid 12   # specific rows
"""
import argparse
import csv
import datetime
import io
import json
import os
import sys
import time
import urllib.request

HOST = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
BASE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE, "bangla_disaster_qa_seed.csv")
OUT_DIR = os.path.join(BASE, "results")

BANGLA_PROMPT_TMPL = (
    "আপনি বাংলাদেশের দুর্যোগ ব্যবস্থাপনার একজন বিশেষজ্ঞ সহায়ক। "
    "নিচের প্রশ্নের সংক্ষিপ্ত, সঠিক ও নিরাপদ উত্তর দিন। "
    "শুধু প্রয়োজনীয় উত্তরটিই লিখুন, অতিরিক্ত কোনো ব্যাখ্যা নয়।\n\n"
    "প্রশ্ন: {question}\n\nউত্তর:"
)


def model_slug(model):
    """Filesystem-safe slug for a model tag (handles hf.co/.../repo:quant)."""
    return model.replace(":", "-").replace("/", "_")


def ollama_generate(model, prompt, num_predict=128, temperature=0.0, think=None):
    """Return (text, total_ms, eval_ms, eval_count, load_ms).

    `think`: for thinking-capable models (Qwen3) disable the reasoning block so
    answers stay short and latency is comparable. Auto-disabled for qwen3.
    """
    if think is None:
        think = False if model.split(":")[0].lower().startswith("qwen3") else None
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": num_predict, "temperature": temperature},
    }
    if think is not None:
        payload["think"] = think
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://{HOST}/api/generate", data=data,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        raw = resp.read()
    wall = (time.perf_counter() - t0) * 1000.0
    out = json.loads(raw.decode("utf-8"))
    text = (out.get("response") or "").strip()
    return {
        "text": text,
        "wall_ms": wall,
        "total_duration_ms": out.get("total_duration", 0) / 1e6,
        "load_duration_ms": out.get("load_duration", 0) / 1e6,
        "eval_duration_ms": out.get("eval_duration", 0) / 1e6,
        "eval_count": out.get("eval_count", 0),
        "prompt_eval_count": out.get("prompt_eval_count", 0),
    }


def load_rows():
    rows = []
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", required=True,
                    help="Ollama model tag; repeat for multiple models")
    ap.add_argument("--limit", type=int, default=None, help="limit rows (first N)")
    ap.add_argument("--rowid", action="append", type=int, default=None,
                    help="specific row id(s); repeatable")
    ap.add_argument("--seed", type=int, default=0, help="random sample seed")
    args = ap.parse_args()

    rows = load_rows()
    if args.rowid:
        ids = set(args.rowid)
        rows = [r for r in rows if int(r["id"]) in ids]
    elif args.limit is not None:
        import random
        random.seed(args.seed)
        rows = random.sample(rows, min(args.limit, len(rows)))

    print(f"[data] {len(rows)} question rows to evaluate across {len(args.model)} model(s)")

    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    base_model = "base"
    for model in args.model:
        slug = model_slug(model)
        out_path = os.path.join(OUT_DIR, f"eval_{slug}_{stamp}.csv")
        meta = []
        rows_out = []

        for i, row in enumerate(rows, 1):
            q = row["question_bn"]
            gold = row["answer_bn"]
            try:
                res = ollama_generate(model, BANGLA_PROMPT_TMPL.format(question=q))
                res["ok"] = True
            except Exception as e:
                res = {"ok": False, "error": str(e)}
                print(f"  [{i}/{len(rows)}] {row['id']}: ERROR {e}", flush=True)
            res["model"] = model
            res["id"] = row["id"]
            res["category"] = row["category"]
            res["safety_label"] = row["safety_label"]
            res["fact_bn"] = row["fact_bn"]
            res["question_bn"] = q
            res["gold_bn"] = gold
            meta.append(res)

            if res["ok"]:
                tok_s = res["eval_count"] / (res["eval_duration_ms"] / 1000.0) if res["eval_duration_ms"] > 0 else 0.0
                print(f"  [{i}/{len(rows)}] id={row['id']} aprx={res['eval_duration_ms']:.0f}ms tok/s={tok_s:.1f}", flush=True)
            rows_out.append(res)

        with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "id", "model", "category", "safety_label",
                "question_bn", "gold_bn", "fact_bn", "output_bn", "ok",
                "wall_ms", "total_duration_ms", "load_duration_ms",
                "eval_duration_ms", "eval_count", "prompt_eval_count",
            ])
            for m in meta:
                w.writerow([
                    m["id"], m["model"], m["category"], m["safety_label"],
                    m["question_bn"], m["gold_bn"], m["fact_bn"], m.get("text", ""),
                    m.get("ok", False),
                    round(m.get("wall_ms", 0), 1), round(m.get("total_duration_ms", 0), 1),
                    round(m.get("load_duration_ms", 0), 1), round(m.get("eval_duration_ms", 0), 1),
                    m.get("eval_count", 0), m.get("prompt_eval_count", 0),
                ])
        n_ok = sum(1 for m in meta if m.get("ok"))
        print(f"[done] {model}: {n_ok}/{len(meta)} ok -> {out_path}")


if __name__ == "__main__":
    sys.exit(main())