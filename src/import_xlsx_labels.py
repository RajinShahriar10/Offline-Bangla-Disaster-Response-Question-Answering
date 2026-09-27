# -*- coding: utf-8 -*-
"""import_xlsx_labels.py — merge human labels back into the review CSVs.

Reads the 'Label it' sheet of each fill-in workbook and writes the labels into
results/review_full_<slug>.csv ('human_correct (Y/N)' column), keyed by id.
The label column is detected by name because annotators may have renamed it
(e.g. 'correct (Y/N)' instead of 'human_correct (Y/N)'). Existing labels in the
CSV are preserved/overwritten by id from the workbook.

The adversarial workbook (adv_review.xlsx) is intentionally NOT merged here:
score_adversarial.py loads its labels live via load_human().

Usage:
    python import_xlsx_labels.py
"""
import csv
import os

try:
    import openpyxl
except ImportError:
    raise SystemExit("openpyxl required:  python -m pip install openpyxl")

BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(BASE, "results")

# (workbook file in results/, csv slug). Renames by annotator: dots -> _
PAIRS = [
    ("review_full_qwen3-1_7b.xlsx", "qwen3-1.7b"),
    ("review_full_qwen3-4b-instruct-2507-q4_K_M.xlsx", "qwen3-4b-instruct-2507-q4_K_M"),
    ("review_full_titulm-v1_1-3b.xlsx", "titulm-v1.1-3b"),
    ("review_full_titulm-v1.1-1b.xlsx", "titulm-v1.1-1b"),
]

LABEL_COLS = ("human_correct (Y/N)", "correct (Y/N)", "human_correct", "correct")


def norm(v):
    s = str(v if v is not None else "").strip().upper()
    if s in ("Y", "YES", "1", "TRUE"):    return "Y"
    if s in ("N", "NO", "0", "FALSE"):    return "N"
    return ""


def main():
    for xlsx, slug in PAIRS:
        wb = openpyxl.load_workbook(os.path.join(RES, xlsx), data_only=True)
        ws = wb["Label it"]
        hdr = [c.value for c in ws[1]]
        col = {h: i for i, h in enumerate(hdr)}
        label_col = next((h for h in LABEL_COLS if h in col), None)
        if label_col is None:
            print(f"{xlsx}: NO label column found (have {hdr}) — SKIPPED")
            continue
        labs = {}
        id_i, lab_i = col.get("id"), col[label_col]
        for r in ws.iter_rows(min_row=2, values_only=True):
            if r[id_i] is None:
                continue
            v = norm(r[lab_i])
            if v:
                labs[str(r[id_i]).strip()] = v
        print(f"{xlsx}: label col='{label_col}'  filled={len(labs)} rows")

        csv_path = os.path.join(RES, f"review_full_{slug}.csv")
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        fld = rows[0].keys() if rows else []
        merged = 0
        for r in rows:
            key = str(r["id"]).strip()
            if key in labs:
                r["human_correct (Y/N)"] = labs[key]
                merged += 1
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fld)
            w.writeheader()
            w.writerows(rows)
        missing = set(labs) - {str(r["id"]).strip() for r in rows}
        if missing:
            print(f"   WARNING ids in workbook not in CSV: {sorted(missing)}")
        print(f"   -> review_full_{slug}.csv: {merged}/{len(rows)} labelled")


if __name__ == "__main__":
    main()