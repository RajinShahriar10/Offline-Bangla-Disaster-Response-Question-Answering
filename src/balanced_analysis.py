# -*- coding: utf-8 -*-
"""balanced_analysis.py — flatten the flood dominance two ways, no data deleted.

The full 634-row set is kept as-is. This script ALSO builds a deterministic,
down-sampled evaluation subset with a per-group cap, so you can report a
"balanced" accuracy alongside the full-set (micro) and macro-averaged numbers.

Two grouping modes:
  --by group      cap each HAZARD GROUP (flood, cyclone, earthquake, ...)   [default]
  --by category   cap each of the 24 categories

If results/scored_full_<model>.csv exist, it recomputes accuracy on the balanced
subset for each model (arithmetic only; no re-run, no model inference).

Outputs (results/):
  - balanced_subset_<mode>.csv      : the selected ids
  - balanced_summary.txt            : distribution before/after + balanced accuracy (group mode)
  - balanced_summary_category.txt   : same, for --by category (avoids clobbering group)

Usage:
    python balanced_analysis.py --by group --cap 30
    python balanced_analysis.py --by category --cap 16
"""
import argparse
import csv
import glob
import os
import random
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(BASE, "results")
CSV = os.path.join(BASE, "bangla_disaster_qa_seed.csv")

GROUPS = {
    "flood": ["flood_health", "flood_water", "flood_prep", "flood_after", "flood_risk"],
    "cyclone": ["cyclone_prep", "cyclone_response", "cyclone_signal"],
    "earthquake": ["earthquake"],
    "first_aid": ["first_aid"],
    "landslide": ["landslide"],
    "river_erosion": ["river_erosion"],
    "severe_weather": ["heatwave", "cold_wave", "lightning", "thunderstorm"],
    "child_safety": ["child_safety"],
    "shelter": ["shelter"],
}
CAT2GROUP = {c: g for g, ms in GROUPS.items() for c in ms}


def group_of(cat, by):
    if by == "category":
        return cat
    return CAT2GROUP.get(cat, "other")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--by", choices=["group", "category"], default="group")
    ap.add_argument("--cap", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    n = len(rows)
    flood_n = sum(1 for r in rows if r["category"].startswith("flood"))

    by_key = defaultdict(list)
    for r in rows:
        by_key[group_of(r["category"], args.by)].append(r)

    rng = random.Random(args.seed)
    chosen = []
    for k in sorted(by_key):
        items = by_key[k][:]
        rng.shuffle(items)
        chosen.extend(items[:args.cap])

    chosen.sort(key=lambda r: int(r["id"]))
    bn_flood = sum(1 for r in chosen if r["category"].startswith("flood"))

    lines = []
    A = lines.append
    A("=" * 84)
    A(f"BALANCED SUBSET (by={args.by}, cap={args.cap}) — post-hoc, full set retained")
    A("=" * 84)
    A(f"full set : {n} rows | flood-related {flood_n} ({100*flood_n/n:.1f}%)")
    A(f"balanced : {len(chosen)} rows | flood-related {bn_flood} "
      f"({100*bn_flood/len(chosen):.1f}%)")
    A("")
    A(f"{args.by:<18}{'full n':>8}{'full %':>8}{'bal n':>8}{'bal %':>8}")
    for k in sorted(by_key):
        fn = len(by_key[k])
        cn = sum(1 for r in chosen if group_of(r["category"], args.by) == k)
        A(f"{k:<18}{fn:>8}{100*fn/n:>7.1f}%{cn:>8}{100*cn/len(chosen):>7.1f}%")

    out_sub = os.path.join(RES, f"balanced_subset_{args.by}.csv")
    os.makedirs(RES, exist_ok=True)
    with open(out_sub, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "hazard_group", "safety_label"])
        for r in chosen:
            w.writerow([r["id"], r["category"], group_of(r["category"], args.by),
                        r["safety_label"]])

    ids = set(r["id"] for r in chosen)
    scored = [p for p in glob.glob(os.path.join(RES, "scored_full_*.csv"))]
    if scored:
        A("")
        A("BALANCED ACCURACY (on the subset above):")
        A("  " + f"{'model':<16}{'fullAcc':>10}{'balAcc':>10}{'balN':>7}")
        for p in sorted(scored):
            model = os.path.basename(p)[12:-4]
            sr = list(csv.DictReader(open(p, encoding="utf-8-sig")))
            full = [float(r["correct"]) for r in sr]
            bal = [float(r["correct"]) for r in sr if r["id"] in ids]
            if not bal:
                continue
            A("  " + f"{model:<16}{sum(full)/len(full):>10.3f}{sum(bal)/len(bal):>10.3f}{len(bal):>7}")
    else:
        A("")
        A("(scored_full_*.csv not found yet — run score.py, then re-run for accuracies)")

    text = "\n".join(lines)
    if args.by == "group":
        out = os.path.join(RES, "balanced_summary.txt")
    else:
        out = os.path.join(RES, "balanced_summary_category.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print(f"\n[out] {out}\n[out] {out_sub}")


if __name__ == "__main__":
    main()