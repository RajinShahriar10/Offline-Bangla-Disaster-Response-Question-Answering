# -*- coding: utf-8 -*-
"""score.py — hybrid accuracy scoring for eval_llm.py outputs.

Primary automatic metric is a multilingual CROSS-ENCODER relevance score
(gold_answer, model_output). Unlike raw embedding cosine (which scored
hallucinated Bangla answers ~0.93), the cross-encoder gives clear separation:
on-topic ~ +0.85, off-topic/hallucinated ~ -1..-2.5, random-wrong-gold ~ -3.

Per row:
  - exact    : 1.0 if normalized output == gold
  - f1       : token-overlap F1
  - ce       : cross-encoder logit relevance(gold, output)
  - correct  : ce >= --ce-thresh (provisional; CALIBRATE on the review set)

Outputs (results/):
  - scored_<file>.csv
  - review_<file>.csv   : manual-labeling set (safety-critical + uncertain band)
  - summary_<file>.txt  : aggregate tables for the paper

Model weights are cached under <repo>/.cache (override with FASTEMBED_CACHE_PATH).
"""
import argparse
import csv
import datetime
import os
import random
import re
import sys
import unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(BASE), "results")
os.environ.setdefault("FASTEMBED_CACHE_PATH",
                      os.path.join(os.path.dirname(os.path.dirname(BASE)), ".cache", "fastembed"))
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

CE_MODEL = "jinaai/jina-reranker-v2-base-multilingual"
_ce = None


def get_cross_encoder():
    global _ce
    if _ce is not None:
        return _ce
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        _ce = TextCrossEncoder(model_name=CE_MODEL)
        return _ce
    except Exception as e:
        print(f"[warn] cross-encoder unavailable: {e}")
        return None


def _norm(s):
    s = unicodedata.normalize("NFC", s.lower())
    s = re.sub(r"[^\w\u0980-\u09FF]+", " ", s, flags=re.UNICODE)
    return " ".join(s.split())


def tokenize(s):
    return _norm(s).split()


def token_f1(out, gold):
    a, b = tokenize(out), tokenize(gold)
    if not a or not b:
        return 1.0 if (not a and not b) else 0.0
    ca, cb = {}, {}
    for t in a:
        ca[t] = ca.get(t, 0) + 1
    for t in b:
        cb[t] = cb.get(t, 0) + 1
    inter = sum(min(ca.get(t, 0), cb.get(t, 0)) for t in cb)
    p, r = inter / len(a), inter / len(b)
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", required=True, help="eval CSV from eval_llm.py")
    ap.add_argument("--ce-thresh", type=float, default=0.0,
                    help="cross-encoder threshold for 'correct' (provisional; calibrate on review set)")
    ap.add_argument("--truncate-selfqa", action="store_true",
                    help="titulm base models: slice output at the first self-authored "
                         "'proshno:' marker so the cross-encoder sees only the primary "
                         "answer, not the 512-token QA loop that follows (base models "
                         "never emit EOS; structured prompts do not anchor them)")
    ap.add_argument("--f1-thresh", type=float, default=0.45)
    ap.add_argument("--uncertain-band", type=float, default=1.0,
                    help="export rows with |ce| within this band for manual review")
    ap.add_argument("--calib-n", type=int, default=60,
                    help="extra random rows to export for threshold calibration")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    rows = []
    with open(args.eval, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if str(r.get("ok", "")).strip().lower() in ("", "0", "false"):
                continue
            rows.append(r)

    print(f"[data] {len(rows)} evaluated rows from {os.path.basename(args.eval)}")

    ce = get_cross_encoder()
    have_ce = ce is not None
    print(f"[model] cross-encoder: {'ON (' + CE_MODEL + ')' if have_ce else 'OFF'}")

    selfqa = re.compile(r"\n[ \t]*\u09aa\u09cd\u09b0\u09b6\u09cd\u09a8[ \t]*[:\u0983]")
    out_bn = []
    for r in rows:
        o = r["output_bn"]
        if args.truncate_selfqa:
            m = selfqa.search(o)
            if m and len(o[:m.start()].strip()) >= 15:
                o = o[:m.start()].rstrip()
        out_bn.append(o)

    norm_out = [_norm(o) for o in out_bn]
    norm_gold = [_norm(r["gold_bn"]) for r in rows]
    exacts = [1.0 if o == g else 0.0 for o, g in zip(norm_out, norm_gold)]
    f1s = [token_f1(o, g) for o, g in zip(norm_out, norm_gold)]

    if have_ce:
        ces = []
        for i, r in enumerate(rows):
            try:
                s = list(ce.rerank(r["gold_bn"], [out_bn[i]]))[0]
            except Exception:
                s = float("-inf")
            ces.append(s)
            if (i + 1) % 50 == 0:
                print(f"  [ce] {i+1}/{len(rows)}", flush=True)
    else:
        ces = [None] * len(rows)

    if have_ce:
        corrects = [1.0 if (c is not None and c >= args.ce_thresh) else 0.0 for c in ces]
    else:
        corrects = [1.0 if f >= args.f1_thresh else 0.0 for f in f1s]

    danger_flags = [1 if (r["safety_label"] == "high" and corrects[i] == 0.0) else 0
                    for i, r in enumerate(rows)]

    tag = os.path.splitext(os.path.basename(args.eval))[0]

    scored_path = os.path.join(OUT_DIR, f"scored_{tag}.csv")
    with open(scored_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "model", "category", "safety_label", "exact", "f1",
                    "ce", "correct", "danger", "question_bn", "gold_bn", "output_bn"])
        for i, r in enumerate(rows):
            w.writerow([r["id"], r["model"], r["category"], r["safety_label"],
                        round(exacts[i], 4), round(f1s[i], 4),
                        round(ces[i], 4) if ces[i] is not None else "",
                        corrects[i], danger_flags[i],
                        r["question_bn"], r["gold_bn"], out_bn[i]])
    print(f"[out] scored -> {scored_path}")

    # ---- review set: danger + uncertain band + random calibration sample ----
    review_idx = set()
    for i in range(len(rows)):
        if danger_flags[i]:
            review_idx.add(i)
        if have_ce and ces[i] is not None and abs(ces[i] - args.ce_thresh) <= args.uncertain_band:
            review_idx.add(i)
    pool = [i for i in range(len(rows)) if i not in review_idx]
    random.seed(0)
    review_idx.update(random.sample(pool, min(args.calib_n, len(pool))))
    review_idx = sorted(review_idx)

    # Preserve any human labels already entered in a previous review file for the
    # same model+id, so regenerating (post-512 rerun) does not wipe manual work.
    old_review = os.path.join(OUT_DIR, f"review_{tag}.csv")
    saved = {}
    if os.path.exists(old_review):
        with open(old_review, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                v = (r.get("human_correct (Y/N)") or r.get("human_correct") or "").strip()
                if v.lower() in ("y", "n", "1", "0", "yes", "no", "true", "false"):
                    saved[str(r["id"])] = v

    review_path = os.path.join(OUT_DIR, f"review_{tag}.csv")
    with open(review_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "model", "category", "safety_label", "f1", "ce",
                    "question_bn", "gold_bn", "output_bn",
                    "human_correct (Y/N)", "notes"])
        for i in review_idx:
            lab = saved.get(str(rows[i]["id"]), "")
            w.writerow([rows[i]["id"], rows[i]["model"], rows[i]["category"],
                        rows[i]["safety_label"], round(f1s[i], 4),
                        round(ces[i], 4) if ces[i] is not None else "",
                        rows[i]["question_bn"], rows[i]["gold_bn"], out_bn[i],
                        lab, ""])
    print(f"[out] review -> {review_path} ({len(review_idx)} rows to label)")

    # ---- summary ----
    def acc(vals):
        return sum(vals) / len(vals) if vals else 0.0

    lines = []
    lines.append(f"MODEL: {rows[0]['model'] if rows else '?'}")
    lines.append(f"ROWS: {len(rows)}")
    lines.append(f"CE_THRESHOLD: {args.ce_thresh} (provisional - calibrate on review set)")
    lines.append(f"ACC (correct rate): {acc(corrects):.4f}")
    lines.append(f"EXACT rate: {acc(exacts):.4f}")
    lines.append(f"F1 mean: {acc(f1s):.4f}")
    if have_ce:
        lines.append(f"CE mean: {acc(ces):.4f}")
        lines.append(f"CE median: {sorted(ces)[len(ces)//2]:.4f}")
    lines.append("")
    lines.append("BY SAFETY LABEL (acc, n):")
    from collections import defaultdict
    g1 = defaultdict(list)
    for i, r in enumerate(rows):
        g1[r["safety_label"]].append(corrects[i])
    for k in sorted(g1):
        lines.append(f"  {k}: {acc(g1[k]):.4f}  (n={len(g1[k])})")
    lines.append("")
    lines.append("BY CATEGORY (acc, n):")
    g2 = defaultdict(list)
    for i, r in enumerate(rows):
        g2[r["category"]].append(corrects[i])
    for k in sorted(g2):
        lines.append(f"  {k}: {acc(g2[k]):.4f}  (n={len(g2[k])})")
    lines.append("")
    lines.append(f"DANGER rows (high-safety & wrong): {sum(danger_flags)}")
    summary_path = os.path.join(OUT_DIR, f"summary_{tag}.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[out] summary -> {summary_path}")
    print("\n".join(lines[:7]))


if __name__ == "__main__":
    sys.exit(main())