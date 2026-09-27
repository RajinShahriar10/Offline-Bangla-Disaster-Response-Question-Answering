# -*- coding: utf-8 -*-
"""verify_outputs.py — post-rerun audit of generation outputs.

Checks each results/full_*.csv (and results/adv_*.csv) for:
  - row count vs expected (634 for main set)
  - completeness / duplicates / failed rows
  - eval_count distribution and whether outputs PIN at the generation cap
    (128 or 512). Pinning means the response was truncated by num_predict
    rather than ending on its own EOS — the exact bug fixed by the 512 rerun.

Usage:
    python verify_outputs.py
"""
import csv
import glob
import os
import statistics

BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(BASE, "results")
EXPECTED_MAIN = 634
NOTABLE_CAPS = [128, 512]


def audit(path, expected):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    ok = [r for r in rows if str(r.get("ok", "")).strip().lower() in ("1", "true")]
    ids = [str(r["id"]) for r in ok]
    ecs = []
    for r in ok:
        try:
            ecs.append(int(float(r["eval_count"])))
        except (ValueError, KeyError, TypeError):
            pass
    lines = []
    A = lines.append
    A(f"  rows={len(rows)}  ok={len(ok)}  unique_ids={len(set(ids))}  "
      f"dup_ids={len(ids)-len(set(ids))}  missing_vs_expected={expected - len(set(ids))}")
    if ecs:
        counts = {c: ecs.count(c) for c in NOTABLE_CAPS}
        pin = max(counts.values()) / len(ecs)
        A(f"  eval_count: n={len(ecs)} min={min(ecs)} max={max(ecs)} mean={statistics.mean(ecs):.0f} "
          f"std={statistics.pstdev(ecs):.1f}")
        A(f"  CAP PINNING: rows at exactly 128 = {counts[128]} ({100*counts[128]/len(ecs):.1f}%) | "
          f"rows at exactly 512 = {counts[512]} ({100*counts[512]/len(ecs):.1f}%)")
        A(f"  max-fraction at a single cap = {100*pin:.1f}% "
          f"{'<-- VERIFY (hard pin possible, esp. base models that never emit EOS)' if pin > 0.5 else ''}")
    return lines, len(ids) - len(set(ids)), ecs


def main():
    files = sorted(glob.glob(os.path.join(RES, "full_*.csv")))
    adv_files = sorted(glob.glob(os.path.join(RES, "adv_*.csv")))
    adv_files = [p for p in adv_files if os.path.basename(p) not in ("adv_review.csv",)]

    lines = []
    A = lines.append
    A("=" * 100)
    A("OUTPUT AUDIT — completeness + eval_count / cap-pinning check")
    A("=" * 100)
    A("Main benchmark set (expected 634 rows, ok, unique, no dups):")
    total_bad = 0
    for p in files:
        tag = os.path.basename(p)[len("full_"):-4]
        A(f"[{tag}]")
        ls, dups, ecs = audit(p, EXPECTED_MAIN)
        for l in ls:
            A("  " + l)
        total_bad += dups
    A("")
    A("Adversarial set (64 items per model, 2 passes already archived):")
    for p in adv_files:
        tag = os.path.basename(p)[len("adv_"):-4]
        A(f"[{tag}]")
        ls, dups, ecs = audit(p, 64)
        for l in ls:
            A("  " + l)
    A("")
    A("READ THIS: a single cap 'pin' >50% with std low means the response budget is")
    A("being exhausted every time. For instruct models this is a bug. For base models")
    A("(TituLM v1.x) that never emit EOS it is expected behaviour and was validated not")
    A("to distort the CE accuracy metric (30-row pilot: ACC unchanged at 0.233).")
    text = "\n".join(lines)
    out = os.path.join(RES, "output_audit.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print(f"[out] {out}")


if __name__ == "__main__":
    main()