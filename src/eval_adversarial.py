# -*- coding: utf-8 -*-
"""eval_adversarial.py — run models over adversarial_set.csv (safety probe).

Resumable: one CSV per model at results/adv_<slug>.csv; re-running skips finished ids.

Usage:
    python eval_adversarial.py --model qwen2.5:3b --model phi3:mini --model gemma2:2b
"""
import argparse
import csv
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from eval_llm import BANGLA_PROMPT_TMPL, ollama_generate, model_slug  # noqa: E402
from safety_lexicon import is_safe  # noqa: E402

ADV_CSV = os.path.join(BASE, "adversarial_set.csv")
OUT_DIR = os.path.join(BASE, "results")


def load_items():
    with open(ADV_CSV, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def done_ids(path):
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if str(r.get("ok", "")).lower() in ("1", "true"):
                    done.add(str(r["id"]))
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--num-predict", type=int, default=512)
    args = ap.parse_args()

    items = load_items()
    os.makedirs(OUT_DIR, exist_ok=True)

    for model in args.model:
        slug = model_slug(model)
        out_path = os.path.join(OUT_DIR, f"adv_{slug}.csv")
        done = done_ids(out_path)
        new_file = not os.path.exists(out_path)
        f = open(out_path, "a", encoding="utf-8-sig", newline="")
        w = csv.writer(f)
        if new_file:
            w.writerow(["id", "kind", "category", "safety_label", "question_bn",
                        "output_bn", "safe_auto", "refused_auto", "has_digits",
                        "ok", "wall_ms", "eval_duration_ms", "eval_count"])
            f.flush()
        todo = [it for it in items if str(it["id"]) not in done]
        print(f"[{model}] {len(done)} done, {len(todo)} to go", flush=True)
        for i, it in enumerate(todo, 1):
            try:
                res = ollama_generate(model, BANGLA_PROMPT_TMPL.format(question=it["question_bn"]),
                                      num_predict=args.num_predict)
                res["ok"] = True
            except Exception as e:
                res = {"ok": False, "text": f"ERROR: {e}", "wall_ms": 0,
                       "eval_duration_ms": 0, "eval_count": 0}
            text = res.get("text", "")
            from safety_lexicon import is_refusal, has_specifics
            safe = is_safe(it["kind"], text)
            w.writerow([it["id"], it["kind"], it["category"], it["safety_label"],
                        it["question_bn"], text, int(safe), int(is_refusal(text)),
                        int(has_specifics(text)), res["ok"],
                        round(res.get("wall_ms", 0), 1),
                        round(res.get("eval_duration_ms", 0), 1), res.get("eval_count", 0)])
            f.flush()
            print(f"  [{i}/{len(todo)}] id={it['id']} {it['kind'][:14]:<14} safe={int(safe)}", flush=True)
        f.close()
        print(f"[{model}] COMPLETE -> {out_path}", flush=True)


if __name__ == "__main__":
    sys.exit(main())