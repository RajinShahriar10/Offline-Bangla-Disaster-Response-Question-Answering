# -*- coding: utf-8 -*-
"""generate_figures.py — produce the paper figures from current result CSVs.

Reads:
  - results/scored_full_<model>.csv      -> CE scores, correctness, danger
  - results/balanced_subset_group.csv    -> balanced-subset ids (group, cap 30)
  - results/full_<model>.csv             -> latency / steady-state tokens/sec
  - results/adv_<model>.csv              -> safe (over-answer) rate
  - results/footprint.txt                -> disk + peak RAM

Outputs results/figures/*.png (300 dpi, IEEE-friendly styling).
"""
import csv
import glob
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)
from safety_lexicon import is_safe

RES = os.path.join(PROJ, "results")
OUT = os.path.join(RES, "figures")
os.makedirs(OUT, exist_ok=True)

MODELS = [
    ("gemma3-1b", 815),
    ("gemma3-4b", 3.3),
    ("qwen3-1.7b", 1.4),
    ("qwen3-4b-instruct-2507-q4_K_M", 2.5),
    ("titulm-v1.1-1b", 807),
    ("titulm-v1.1-3b", 2.0),
]
ORDER = ["gemma3-1b", "gemma3-4b", "qwen3-1.7b",
         "qwen3-4b-instruct-2507-q4_K_M", "titulm-v1.1-1b", "titulm-v1.1-3b"]
SHORT = {
    "gemma3-1b": "Gemma3-1B",
    "gemma3-4b": "Gemma3-4B",
    "qwen3-1.7b": "Qwen3-1.7B",
    "qwen3-4b-instruct-2507-q4_K_M": "Qwen3-4B",
    "titulm-v1.1-1b": "TituLM-1B",
    "titulm-v1.1-3b": "TituLM-3B",
}
STY = dict(fontsize=8)
TICKS = dict(labelsize=7.5)


def load_scored(model):
    p = os.path.join(RES, f"scored_full_{model}.csv")
    if not os.path.exists(p):
        return None
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    return rows


def load_full(model):
    p = os.path.join(RES, f"full_{model}.csv")
    if not os.path.exists(p):
        return None
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def load_adv(model):
    p = os.path.join(RES, f"adv_{model}.csv")
    if not os.path.exists(p):
        return None
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def stat(rows, key, pred=lambda r: True):
    v = [float(r[key]) for r in rows if pred(r) and str(r[key]).strip() != ""]
    return float(np.mean(v)) if v else float("nan")


def load_adv_review():
    """results/adv_review.csv: recomputed (current-lexicon) safe + human overrides."""
    p = os.path.join(RES, "adv_review.csv")
    if not os.path.exists(p):
        return {}
    out = {}
    for r in csv.DictReader(open(p, encoding="utf-8-sig")):
        hum = str(r.get("human_safe(1/0)", "") or "").strip()
        final = int(hum) if hum in ("0", "1") else int(float(r["safe"]))
        out[(r["model"], r["id"].strip())] = final
    return out


def load_footprint():
    """results/footprint.txt -> {model: (ram_mb, disk_gb_or_mb_str)}."""
    p = os.path.join(RES, "footprint.txt")
    if not os.path.exists(p):
        return {}
    out = {}
    pat = re.compile(r"^(\S+)\s+(\S+)\s+(\d+)\s+MB\s+")
    for ln in open(p, encoding="utf-8"):
        m = pat.match(ln)
        if m:
            out[m.group(1)] = (int(m.group(3)),
                               float(m.group(2)) if not m.group(2).endswith("B") else m.group(2))
    return out


def main():
    scored_ids = {}
    try:
        with open(os.path.join(RES, "balanced_subset_group.csv"), encoding="utf-8-sig") as f:
            scored_ids = {r["id"] for r in csv.DictReader(f)}
    except Exception:
        pass

    adv_final = load_adv_review()
    fp = load_footprint()

    data = {}
    for name, disk in MODELS:
        s = load_scored(name)
        f = load_full(name)
        a = load_adv(name)
        ok = [r for r in f if str(r["ok"]).lower() in ("1", "true")] if f else []
        tps = [float(r["eval_count"]) / (float(r["eval_duration_ms"]) / 1000.0)
               for r in ok if float(r["eval_duration_ms"]) > 0]
        over_safe = [adv_final[(name, str(r["id"]).strip())]
                     if (name, str(r["id"]).strip()) in adv_final
                     else int(is_safe(r["kind"], r["output_bn"]))
                     for r in a]
        bal = np.mean([float(r["correct"]) for r in s if r["id"] in scored_ids]) if s and scored_ids else float("nan")
        data[name] = {
            "acc": stat(s, "correct") if s else float("nan"),
            "balacc": bal,
            "ce": [float(r["ce"]) for r in s] if s else [],
            "danger": stat(s, "danger") if s else float("nan"),
            "lat_mean_s": stat(f, "wall_ms") / 1000.0 if f else float("nan"),
            "toks": float(np.mean(tps)) if tps else float("nan"),
            "over": 1.0 - float(np.mean(over_safe)) if over_safe else float("nan"),
            "disk_gb": disk,
            "ram_mb": fp.get(name, (0,))[0] if name in fp else (0.0),
        }

    # ---------- Fig 1: CE box plots with deployed threshold ----------
    fig, ax = plt.subplots(figsize=(3.42, 2.4), dpi=300)
    order = [m for m in ORDER if data[m]["ce"]]
    labels = [SHORT[m] for m in order]
    bp = ax.boxplot([data[m]["ce"] for m in order], tick_labels=labels,
                    patch_artist=True, widths=0.6, showfliers=False)
    for b in bp["boxes"]:
        b.set_facecolor("#CBD5E0")
    ax.axhline(0.0, color="#C0392B", lw=1.0, ls="--")
    ax.text(0.99, 0.02, "deployed CE threshold t=0.0", transform=ax.transAxes,
            color="#C0392B", ha="right", va="bottom", fontsize=6.5,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1.0))
    ax.set_ylabel("Semantic-relevance score (CE)", fontsize=8)
    ax.tick_params(axis="x", labelsize=6.5, rotation=18)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_ylim(-2.5, 4.0)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig1_ce_scores.png"))
    plt.close(fig)

    # ---------- Fig 2: accuracy bars (micro + balanced) ----------
    fig, ax = plt.subplots(figsize=(3.62, 2.4), dpi=300)
    x = np.arange(len(order))
    w = 0.34
    accs = [data[m]["acc"] for m in order]
    bals = [data[m]["balacc"] for m in order]
    b1 = ax.bar(x - w / 2, accs, w, label="Micro ACC (n=634)", color="#2E86C1")
    b2 = ax.bar(x + w / 2, bals, w, label="Balanced ACC (subset)", color="#E67E22")
    for b in b1 + b2:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.009,
                f"{b.get_height():.2f}", ha="center", va="bottom", fontsize=5.4)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=6.5, rotation=18, ha="right")
    ax.set_ylabel("Correct-answer rate", fontsize=8)
    ax.set_ylim(0, 0.55)
    ax.legend(fontsize=6.5, frameon=False, loc="upper right",
              bbox_to_anchor=(1.0, 1.0))
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig2_accuracy.png"))
    plt.close(fig)

    # ---------- Fig 3: efficiency-accuracy-safety trade-off scatter ----------
    fig, ax = plt.subplots(figsize=(3.42, 2.7), dpi=300)
    # label offsets (points) spread out clusters; the three top models sit at
    # ~(6.6-8.3 tok/s, 0.23-0.26 acc) so their annotations are staggered
    OFF = {
        "gemma3-1b": (6, 6),
        "gemma3-4b": (52, 16),
        "qwen3-1.7b": (6, 12),
        "qwen3-4b-instruct-2507-q4_K_M": (8, 22),
        "titulm-v1.1-1b": (8, -18),
        "titulm-v1.1-3b": (52, -14),
    }
    for name in order:
        d = data[name]
        if np.isnan(d["acc"]) or np.isnan(d["toks"]):
            continue
        ram = d["ram_mb"]
        safe = 1.0 - d["over"]
        size = 18 + 42 * (ram / 3600.0)
        col = (0.13 + (1 - safe) * 0.85, 0.55 * safe + 0.1, 0.85 * (1 - safe) + 0.12)
        ax.scatter(d["toks"], d["acc"], s=size, c=[col], alpha=0.9,
                   edgecolors="k", linewidths=0.5)
        ax.annotate(SHORT[name], (d["toks"], d["acc"]),
                    fontsize=6.5, xytext=OFF[name], textcoords="offset points",
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=0.6))
    ax.set_xlabel("Throughput (tok/s, CPU, 512-budget)", fontsize=8)
    ax.set_ylabel("Micro accuracy (CE@0.0)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.3)
    ax.set_xlim(4.5, 25.5)
    ax.set_ylim(0.10, 0.32)
    h = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#7FB3D5",
                    markersize=4, label="917-1100 MB"),
         plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#5DADE2",
                    markersize=7, label="1.9 GB"),
         plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#2E86C1",
                    markersize=10, label="2.4-3.6 GB")]
    ax.legend(handles=h, fontsize=6, frameon=False, title="Peak RAM",
              title_fontsize=6.5, loc="lower right")
    ax.text(0.02, 0.98, "lighter bubble = safer (lower over-answer rate)",
            transform=ax.transAxes, ha="left", va="top", fontsize=6, alpha=0.85)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig3_tradeoff.png"))
    plt.close(fig)

    for f in sorted(os.listdir(OUT)):
        print("[out]", os.path.join(OUT, f))


if __name__ == "__main__":
    main()