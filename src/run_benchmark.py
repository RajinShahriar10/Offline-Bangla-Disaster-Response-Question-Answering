# -*- coding: utf-8 -*-
"""run_benchmark.py — resumable full benchmark: every model x every dataset row.

Writes one CSV per model under results/ and a .log. Re-running skips rows whose
id already has a successful output, so the long CPU run can be interrupted and
resumed.

Usage:
    python run_benchmark.py --model qwen2.5:3b --model phi3:mini --model gemma2:2b
"""
import argparse
import csv
import datetime
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from eval_llm import BANGLA_PROMPT_TMPL, load_rows, ollama_generate, model_slug  # noqa: E402

OUT_DIR = os.path.join(BASE, "results")


def already_done(path):
    done = set()
    if not os.path.exists(path):
        return done
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if str(r.get("ok", "")).strip().lower() in ("1", "true"):
                done.add(str(r["id"]))
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--num-predict", type=int, default=128)
    args = ap.parse_args()

    rows = load_rows()
    os.makedirs(OUT_DIR, exist_ok=True)

    for model in args.model:
        slug = model_slug(model)
        out_path = os.path.join(OUT_DIR, f"full_{slug}.csv")
        log_path = os.path.join(OUT_DIR, f"full_{slug}.log")
        done = already_done(out_path)
        new_file = not os.path.exists(out_path)

        f = open(out_path, "a", encoding="utf-8-sig", newline="")
        w = csv.writer(f)
        if new_file:
            w.writerow(["id", "model", "category", "safety_label",
                        "question_bn", "gold_bn", "output_bn", "ok",
                        "wall_ms", "total_duration_ms", "load_duration_ms",
                        "eval_duration_ms", "eval_count", "prompt_eval_count"])
            f.flush()

        remaining = [r for r in rows if str(r["id"]) not in done]
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(f"\n=== {datetime.datetime.now()} model={model} "
                      f"todo={len(remaining)} already={len(done)} ===\n")
            log.flush()
            print(f"[{model}] resuming: {len(done)} done, {len(remaining)} to go", flush=True)
            for i, row in enumerate(remaining, 1):
                t0 = time.perf_counter()
                try:
                    res = ollama_generate(model, BANGLA_PROMPT_TMPL.format(question=row["question_bn"]),
                                          num_predict=args.num_predict)
                    res["ok"] = True
                except Exception as e:
                    res = {"ok": False, "text": f"ERROR: {e}", "wall_ms": (time.perf_counter()-t0)*1000,
                           "total_duration_ms": 0, "load_duration_ms": 0,
                           "eval_duration_ms": 0, "eval_count": 0, "prompt_eval_count": 0}
                w.writerow([row["id"], model, row["category"], row["safety_label"],
                            row["question_bn"], row["answer_bn"], res.get("text", ""),
                            res["ok"], round(res["wall_ms"], 1),
                            round(res["total_duration_ms"], 1), round(res["load_duration_ms"], 1),
                            round(res["eval_duration_ms"], 1), res["eval_count"], res["prompt_eval_count"]])
                f.flush()
                tok_s = (res["eval_count"] / (res["eval_duration_ms"]/1000.0)) if res["eval_duration_ms"] else 0
                msg = f"  [{i}/{len(remaining)}] id={row['id']} ok={res['ok']} {res['eval_duration_ms']:.0f}ms tok/s={tok_s:.1f}"
                print(msg, flush=True)
                log.write(msg + "\n")
                log.flush()
        f.close()
        print(f"[{model}] COMPLETE -> {out_path}", flush=True)


if __name__ == "__main__":
    sys.exit(main())