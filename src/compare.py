# -*- coding: utf-8 -*-
"""compare.py — build the paper's cross-model Efficiency / Accuracy / Safety table.

Reads results/scored_full_<model>.csv (produced by score.py over full_<model>.csv)
and results/full_<model>.csv (for latency), then prints + writes a combined table.

Usage:
    python compare.py
"""
import csv
import glob
import os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(BASE, "results")


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def pct(vals, q=50):
    if not vals:
        return 0.0
    s = sorted(vals)
    return s[min(len(s) - 1, int(len(s) * q / 100))]


def main():
    # efficiency from full_*.csv
    eff = {}
    for path in glob.glob(os.path.join(RES, "full_*.csv")):
        model = os.path.basename(path)[5:-4]
        rows = read_csv(path)
        ok = [r for r in rows if str(r.get("ok", "")).lower() in ("1", "true")]
        if not ok:
            continue
        lat = [float(r["wall_ms"]) for r in ok if r["wall_ms"]]
        eval_ms = [float(r["eval_duration_ms"]) for r in ok if r["eval_duration_ms"]]
        tps = [float(r["eval_count"]) / (float(r["eval_duration_ms"]) / 1000.0)
               for r in ok if r["eval_duration_ms"] and float(r["eval_duration_ms"]) > 0]
        load_rows = 1 if lat else 0
        eff[model] = {
            "n": len(ok),
            "lat_wall_p95_s": pct(lat, 95) / 1000.0 if lat else float("nan"),
            "lat_eval_mean_s": mean(eval_ms) / 1000.0,
            "lat_eval_p95_s": pct(eval_ms, 95) / 1000.0,
            "tok_s": mean(tps),
            "eval_ms_mean": mean(eval_ms),
        }

    # accuracy/safety from scored_full_*.csv
    acc = {}
    for path in glob.glob(os.path.join(RES, "scored_full_*.csv")):
        model = os.path.basename(path)[12:-4]
        rows = read_csv(path)
        if not rows:
            continue
        corrects = [float(r["correct"]) for r in rows]
        ces = [float(r["ce"]) for r in rows if r.get("ce", "") != ""]
        danger = sum(int(r["danger"]) for r in rows)
        high = [r for r in rows if r["safety_label"] == "high"]
        high_danger = sum(int(r["danger"]) for r in high)
        by_safety = defaultdict(list)
        by_cat = defaultdict(list)
        for r in rows:
            by_safety[r["safety_label"]].append(float(r["correct"]))
            by_cat[r["category"]].append(float(r["correct"]))
        cat_acc = {k: mean(v) for k, v in by_cat.items()}
        acc[model] = {
            "n": len(rows),
            "acc": mean(corrects),
            "macro_acc": mean(list(cat_acc.values())),
            "ce_mean": mean(ces),
            "danger": danger,
            "danger_rate": danger / len(rows),
            "high_n": len(high),
            "high_acc": mean([float(r["correct"]) for r in high]),
            "high_danger_rate": high_danger / len(high) if high else 0.0,
            "by_safety": {k: mean(v) for k, v in by_safety.items()},
            "by_cat": cat_acc,
        }

    models = sorted(set(eff) | set(acc))
    lines = []
    lines.append("=" * 100)
    lines.append("COMPACT LLM BENCHMARK — Bangla Disaster-Response QA (dataset n=634)")
    lines.append("=" * 100)
    hdr = f"{'model':<14}{'n':>5}{'acc':>8}{'macroAcc':>10}{'CEmean':>9}{'danger':>8}{'highAcc':>9}{'highDngr':>10}{'latEval':>9}{'latP95':>8}{'tok/s':>7}"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for m in models:
        e = eff.get(m, {})
        a = acc.get(m, {})
        lines.append(
            f"{m:<14}"
            f"{a.get('n', e.get('n', 0)):>5}"
            f"{a.get('acc', float('nan')):>8.3f}"
            f"{a.get('macro_acc', float('nan')):>10.3f}"
            f"{a.get('ce_mean', float('nan')):>9.3f}"
            f"{a.get('danger', 0):>8}"
            f"{a.get('high_acc', float('nan')):>9.3f}"
            f"{a.get('high_danger_rate', 0):>10.3f}"
            f"{e.get('lat_eval_mean_s', float('nan')):>9.2f}"
            f"{e.get('lat_eval_p95_s', float('nan')):>8.2f}"
            f"{e.get('tok_s', float('nan')):>7.2f}"
        )
    lines.append("")
    lines.append("ACCURACY BY SAFETY LABEL (correct rate):")
    labels = ["low", "medium", "high"]
    lines.append("  " + f"{'model':<14}" + "".join(f"{l:>10}" for l in labels))
    for m in models:
        bs = acc.get(m, {}).get("by_safety", {})
        lines.append("  " + f"{m:<14}" + "".join(f"{bs.get(l, float('nan')):>10.3f}" for l in labels))
    lines.append("")
    lines.append("Note: 'correct' uses cross-encoder gold-vs-output relevance (provisional")
    lines.append("threshold 0.0; calibrate against results/review_full_*.csv human labels).")
    lines.append("Danger = high-safety question answered incorrectly.")
    lines.append("acc = micro-averaged (row-weighted); macroAcc = mean over categories")
    lines.append("(mitigates the flood-heavy 40.5% skew; see DATASET_STATS.md).")
    lines.append("latEval = mean inference wall-time from eval_duration_ms (steady-state,")
    lines.append("excludes model cold-load on the first request; wall_ms P95 is inflated")
    lines.append("to ~1.4-3.3x by the ~40-140s cold start). tok/s = steady-state decode.")

    all_cats = sorted({c for a in acc.values() for c in a.get("by_cat", {})})
    if all_cats:
        lines.append("")
        lines.append("PER-CATEGORY ACCURACY (correct rate):")
        lines.append("  " + f"{'category':<20}" + "".join(f"{m[:12]:>13}" for m in models))
        for c in all_cats:
            lines.append("  " + f"{c:<20}" + "".join(
                f"{acc.get(m, {}).get('by_cat', {}).get(c, float('nan')):>13.3f}" for m in models))

    text = "\n".join(lines)
    out = os.path.join(RES, "comparison_table.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print(f"\n[out] {out}")


if __name__ == "__main__":
    main()