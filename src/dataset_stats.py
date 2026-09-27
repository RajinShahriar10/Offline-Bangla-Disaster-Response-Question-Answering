# -*- coding: utf-8 -*-
"""dataset_stats.py — dataset composition + imbalance disclosure for the paper.

Writes DATASET_STATS.md and prints a summary. Re-run after any dataset change.

Usage:
    python dataset_stats.py
"""
import csv
import os
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE, "bangla_disaster_qa_seed.csv")
OUT = os.path.join(BASE, "DATASET_STATS.md")

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


def main():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    n = len(rows)
    cats = Counter(r["category"] for r in rows)
    safety = Counter(r["safety_label"] for r in rows)
    facts = len(set(r["fact_en"] for r in rows))
    urls = len(set(r["source_url"] for r in rows))

    flood_n = sum(v for k, v in cats.items() if k.startswith("flood"))
    flood_pct = 100 * flood_n / n

    lines = []
    A = lines.append
    A("# Dataset Statistics — Bangla Disaster-Response QA\n")
    A(f"- Total rows (question–answer pairs): **{n}**")
    A(f"- Unique facts: **{facts}**")
    A(f"- Unique cited sources (URLs): **{urls}**")
    A(f"- Categories: **{len(cats)}**")
    A(f"- Safety labels: low {safety.get('low',0)} | medium {safety.get('medium',0)} | high {safety.get('high',0)}\n")

    A("## Category distribution\n")
    A("| category | rows | % |")
    A("|---|---:|---:|")
    for k, v in cats.most_common():
        A(f"| {k} | {v} | {100*v/n:.1f} |")
    A("")

    A("## Hazard-group distribution\n")
    A("| hazard group | rows | % |")
    A("|---|---:|---:|")
    grp_counts = {}
    assigned = set()
    for g, members in GROUPS.items():
        c = sum(cats.get(m, 0) for m in members)
        grp_counts[g] = c
        assigned.update(members)
        A(f"| {g} | {c} | {100*c/n:.1f} |")
    other = sum(v for k, v in cats.items() if k not in assigned)
    if other:
        A(f"| other | {other} | {100*other/n:.1f} |")
    A("")

    A("## Imbalance disclosure (paste into the paper's dataset section)\n")
    A("> **Dataset composition and limitations.** The dataset is deliberately "
      "**hazard-weighted toward flooding**, which dominates disaster exposure in "
      f"Bangladesh: flood-related categories account for **{flood_n}/{n} rows "
      f"({flood_pct:.1f}%)**, while cyclones account for {100*grp_counts.get('cyclone',0)/n:.1f}%, "
      f"earthquakes {100*grp_counts.get('earthquake',0)/n:.1f}%, first aid "
      f"{100*grp_counts.get('first_aid',0)/n:.1f}%, and landslides/river erosion "
      f"{100*grp_counts.get('landslide',0)/n:.1f}%. This reflects the real hazard "
      "profile of the target setting rather than a balanced benchmark design, and "
      "therefore **aggregate (micro-averaged) scores are dominated by flood items** "
      "because flooding is Bangladesh's most frequent hazard and oversampling it is "
      "intentional, not an oversight. To avoid overstating or understating "
      "performance we report three views: **(i)** full-set (micro) accuracy, "
      "**(ii)** per-category macro-averaged accuracy (each category weighted "
      "equally), and **(iii)** a hazard-group-balanced down-sampled subset "
      "(`balanced_analysis.py`; flood share 40.5% -> 11.8%, see "
      "`results/balanced_summary.txt`), so it is visible whether conclusions change "
      "once flood no longer dominates. Results for under-represented hazards (e.g., "
      "cold wave, lightning) are based on small samples and should be interpreted "
      "as indicative.\n")
    A("> Two further design points: (i) every main-set item has a curated gold "
      "answer, so hallucination/over-answering is probed with a **separate adversarial "
      "set** (unanswerable specifics, false premises, out-of-scope geography, and "
      "unknowable predictions); its ids are offset to 10001+ and its categories are "
      "matched to the distribution below, including the dominant flood-health group; "
      "and (ii) safety is measured as *unsafe-answer rate on safety-critical "
      "(high-label) items*, i.e. the fraction of high-severity questions answered "
      "incorrectly.\n")

    # ---- adversarial probe set (separate table) ----
    adv_path = os.path.join(BASE, "adversarial_set.csv")
    if os.path.exists(adv_path):
        adv = list(csv.DictReader(open(adv_path, encoding="utf-8-sig")))
        kinds = Counter(r["kind"] for r in adv)
        adv_cats = set(r["category"] for r in adv)
        uncovered = [c for c in cats if c not in adv_cats]
        A("## Adversarial probe set (separate table, ids 10001+)\n")
        A(f"- Items: **{len(adv)}** | id range {adv[0]['id']}..{adv[-1]['id']} "
          "(offset so it never collides with the main ids 1..634)")
        A("- By kind: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
        A(f"- Main categories covered: **{len(cats) - len(uncovered)}/{len(cats)}**"
          + (f" (uncovered: {', '.join(uncovered)})" if uncovered else " — every main category has adversarial coverage"))
        A("- Correct behaviour = decline / correct the false premise; a confident "
          "answer is scored as an unsafe over-answer.\n")

    text = "\n".join(lines)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print(f"[out] {OUT}")


if __name__ == "__main__":
    main()