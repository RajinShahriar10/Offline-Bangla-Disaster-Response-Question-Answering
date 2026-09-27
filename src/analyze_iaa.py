# -*- coding: utf-8 -*-
"""analyze_iaa.py — inter-annotator agreement: A (results/*.csv/.xlsx) vs B (iaa_sheet.xlsx).

Reads:
  - A accuracy labels  from results/review_full_*.csv        (human_correct (Y/N))
  - A safety labels    from results/adv_review.xlsx/csv      (human_safe(1/0))
  - B labels           from results/iaa_sheet.xlsx           (Accuracy + Safety tabs)

Reports agreement % and Cohen's kappa per dimension and combined, plus the
disagreement rows, to stdout and results/iaa_result.txt.

Usage: python analyze_iaa.py
"""
import csv
import glob
import os

try:
    import openpyxl
except ImportError:
    raise SystemExit("openpyxl required")


BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(BASE, "results")
NORM = lambda v: str("" if v is None else v).strip().upper()


def kappa(a, b):
    n = len(a)
    p0 = sum(x == y for x, y in zip(a, b)) / n
    pa = {v: sum(x == v for x in a) / n for v in set(a + b)}
    pb = {v: sum(x == v for x in b) / n for v in set(a + b)}
    pe = sum(pa.get(v, 0) * pb.get(v, 0) for v in set(a + b))
    return (p0, (p0 - pe) / (1 - pe)) if pe < 1 else (p0, None)


def load_a_accuracy():
    A = {}
    for p in glob.glob(os.path.join(RES, "review_full_*.csv")):
        for r in csv.DictReader(open(p, encoding="utf-8-sig", newline="")):
            v = NORM(r["human_correct (Y/N)"])
            if v in ("Y", "N"):
                A[(r["model"].replace(":", "-").strip(), str(r["id"]).strip())] = v
    return A


def load_a_safety():
    A = {}
    for ext in (".xlsx", ".csv"):
        p = os.path.join(RES, "adv_review" + ext)
        if not os.path.exists(p):
            continue
        if ext == ".xlsx":
            wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
            ws = wb[wb.sheetnames[0]]
            hdr = list(ws.iter_rows(min_row=1, max_row=1, values_only=True))[0]
            rows = list(ws.iter_rows(min_row=2, values_only=True))
            for d in (dict(zip(hdr, r)) for r in rows):
                v = NORM(d.get("human_safe(1/0)"))
                if v in ("1", "0"):
                    A[(str(d["model"]).strip(), str(d["id"]).strip())] = v
        else:
            for r in csv.DictReader(open(p, encoding="utf-8-sig", newline="")):
                v = NORM(r.get("human_safe(1/0)"))
                if v in ("1", "0"):
                    A[(r["model"].strip(), str(r["id"]).strip())] = v
        break
    return A


def load_b():
    wb = openpyxl.load_workbook(os.path.join(RES, "iaa_sheet.xlsx"),
                                data_only=True, read_only=True)
    acc, saf = {}, {}
    ws = wb["Accuracy (Y or N)"]
    for r in ws.iter_rows(min_row=2, values_only=True):
        v = NORM(r[-1])
        if v in ("Y", "N"):
            acc[(str(r[0]).strip(), str(r[1]).strip())] = v
    ws = wb["Safety (1 or 0)"]
    for r in ws.iter_rows(min_row=2, values_only=True):
        v = NORM(r[-1])
        if v in ("1", "0"):
            saf[(str(r[0]).strip(), str(r[1]).strip())] = v
    return acc, saf


def main():
    A_acc, A_saf = load_a_accuracy(), load_a_safety()
    A = dict(A_acc)
    A.update(A_saf)
    B_acc, B_saf = load_b()

    lines = []
    A_ = lines.append
    A_("=" * 72)
    A_("INTER-ANNOTATOR AGREEMENT — annotator A (first) vs annotator B (second)")
    A_("=" * 72)
    full = []
    for title, bs, asrc in (("ACCURACY (Y/N)", B_acc, A_acc),
                            ("SAFETY (1/0)", B_saf, A_saf)):
        keys = [k for k in bs if k in asrc]
        if not keys:
            A_(f"{title}: no overlapping A labels yet")
            continue
        aa = [asrc[k] for k in keys]
        bb = [bs[k] for k in keys]
        ag = sum(x == y for x, y in zip(aa, bb))
        p0, k = kappa(aa, bb)
        A_(f"{title}  n={len(keys)}  agreement={ag}/{len(keys)}"
           f" ({100*ag/len(keys):.1f}%)  Cohen's kappa={k:.3f}")
        full += keys
        for k in keys:
            if asrc[k] != bs[k]:
                A_(f"  DISAGREE  model={k[0]}  id={k[1]}  A={asrc[k]}  B={bs[k]}")
    if full:
        aa = [A[k] for k in full]
        bb = []
        for k in full:
            bb.append(B_acc[k] if k in B_acc else B_saf[k])
        ag = sum(x == y for x, y in zip(aa, bb))
        p0, k = kappa(aa, bb)
        A_("")
        A_(f"COMBINED  n={len(full)}  agreement={ag}/{len(full)}"
           f" ({100*ag/len(full):.1f}%)  Cohen's kappa={k:.3f}")

    text = "\n".join(lines)
    print(text)
    out = os.path.join(RES, "iaa_result.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"[out] {out}")


if __name__ == "__main__":
    main()