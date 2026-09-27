# -*- coding: utf-8 -*-
"""make_review_xlsx.py — convert a review_full_*.csv into a clean fill-in xlsx.

Same layout style as adv_review.xlsx: every column readable, the answer column
( human_correct (Y/N) ) highlighted yellow, and rows belonging to the IAA sample
marked with a light-green fill (fill those first).

Usage:
    python make_review_xlsx.py review_full_gemma3-1b.csv   (or *.csv glob)
Output: results/<stem>.xlsx alongside the CSV.
"""
import csv
import glob
import os
import sys

try:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError:
    raise SystemExit("openpyxl required:  python -m pip install openpyxl")

BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(BASE, "results")

IAA_IDS = {
    "gemma3-1b": {"203", "329", "137", "130", "199", "1", "92", "345"},
    "gemma3-4b": {"199", "90", "130", "345", "135", "1", "203", "328"},
}

HDR_FILL = PatternFill("solid", fgColor="D9E1F2")
ANSWER_FILL = PatternFill("solid", fgColor="FFF2CC")
IAA_FILL = PatternFill("solid", fgColor="E2EFDA")
WRAP = Alignment(wrap_text=True, vertical="top")
HDR_FONT = Font(bold=True)


def convert(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    stem = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(RES, stem + ".xlsx")
    model = rows[0]["model"].replace(":", "-") if rows else "model"
    iaa = IAA_IDS.get(model, set())

    cols = ["id", "model", "category", "safety_label", "question_bn", "gold_bn",
            "output_bn", "human_correct (Y/N)", "notes"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Label it"
    ws.append(cols)
    for i, c in enumerate(cols, 1):
        ws.cell(row=1, column=i).fill = HDR_FILL
        ws.cell(row=1, column=i).font = HDR_FONT
    for r in rows:
        vals = [r.get(c, "") for c in cols]
        ws.append(vals)
        row_i = ws.max_row
        if str(r["id"]).strip() in iaa:
            for i in range(1, len(cols) + 1):
                ws.cell(row=row_i, column=i).fill = IAA_FILL
        ws.cell(row=row_i, column=len(cols) - 2).fill = ANSWER_FILL
    widths = [8, 14, 16, 12, 40, 48, 48, 16, 24]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for r in ws.iter_rows(min_row=2):
        for cell in r:
            cell.alignment = WRAP
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    inst = wb.create_sheet("Instructions")
    inst.append(["How to label"])
    inst.append([])
    inst.append(["Fill ONLY the yellow column 'human_correct (Y/N)'."])
    inst.append(["  Y = the answer contains the correct facts from gold_bn (wording may"
                 " differ, that is fine)."])
    inst.append(["  N = the answer is missing the key facts or gives wrong facts."])
    inst.append([])
    inst.append(["safety_label column is read-only context (high = a wrong answer can"
                 " endanger people; ours intentionally hold those to the same bar)."])
    inst.append([])
    inst.append(["Green-highlighted rows = the IAA sample — label those first."])
    inst.append(["Notes column is optional (e.g. 'partially correct'), not required."])
    inst.append(["Leave the answer column empty ONLY if you cannot decide; better to"
                 " still pick a best-guess Y or N."])

    wb.save(out)
    print(f"[out] {out}  rows={len(rows)}  IAA-rows={len(set(str(r['id']).strip() for r in rows) & iaa)}")


def main():
    targets = sys.argv[1:]
    if not targets:
        targets = sorted(glob.glob(os.path.join(RES, "review_full_*.csv")))
    for t in targets:
        convert(t)


if __name__ == "__main__":
    main()