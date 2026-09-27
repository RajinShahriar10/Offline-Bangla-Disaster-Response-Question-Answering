# wrapper_claims_check.py
# Verifies every numeric claim in the spliced wrapper paragraph against the
# artifact the paper cites (results/wrapper_table.txt) — no model inference,
# pure CSV arithmetic on the released human-validated adversarial labels.
import io, re, sys

tbl = io.open(r"results\wrapper_table.txt", encoding="utf-8").read()
lines = [l.strip() for l in tbl.splitlines() if l.strip()]
# example real line:
# "titulm-v1.1-3b","64","0.94","0.97","0.94","0.02","0.17","0.17",""
#  model, n, rawOver, lexAgree, refuseShare, residAll, residDeliv, safeBlocked, ...
def line2row(l):
    # crude csv split on commas only (plain numbers here, no commas in fields)
    import csv, io as _io
    return next(csv.reader(_io.StringIO(l)))

rows = []
for l in lines[2:]:          # skip the 2 header/meta lines
    if l.startswith("model") or l.startswith('"') is False:
        try:
            r = line2row(l)
            if len(r) >= 8 and r[0].strip('"'):
                rows.append(r)
        except Exception:
            pass

print("parsed wrapper rows:", len(rows), "| models:", ", ".join(sorted({r[0] for r in rows})))
print()

def pct(x):
    return float(x.strip('%"'))/100.0

residAll   = [pct(r[5]) for r in rows]   # residual over-answer share of ALL adv rows
residDeliv = [pct(r[6]) for r in rows]   # residual among the rows the wrapper *delivers*
safeBlock  = [pct(r[7]) for r in rows]   # share of human-safe rows wrongly withheld
rawOver    = [pct(r[2]) for r in rows]

print("CLAIM 1: residual across ALL adversarial rows = 0.0--6.2%% -> computed [%g, %g]" % (min(residAll), max(residAll)))
print("    paper says 0.0--6.2 :", (min(residAll) >= 0.0 and max(residAll) <= 0.062))
print()
print("CLAIM 2: at most 4.7%% even among the rows it delivers -> computed [%g, %g]" % (min(residDeliv), max(residDeliv)))
print("    paper says at most 4.7%% :", max(residDeliv) <= 0.047)
print()
print("CLAIM 3: wrongly withholds 0--25%% of human-safe rows -> computed [%g, %g]" % (min(safeBlock), max(safeBlock)))
print("    paper says 0--25%% :", (min(safeBlock) >= 0.0 and max(safeBlock) <= 0.25))
print()
print("CONTEXT: raw over-answer 62.5--93.8%% -> computed [%g, %g]; wrapper pulls to residual above" % (min(rawOver), max(rawOver)))
print()
for r, c1, c2, c3 in zip(rows, residAll, residDeliv, safeBlock):
    print("  %-28s residAll=%.1f%% residDeliv=%.1f%% safeBlock=%.1f%%" % (r[0][1:-1], 100*c1, 100*c2, 100*c3))
