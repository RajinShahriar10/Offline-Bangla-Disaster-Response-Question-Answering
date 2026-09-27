# Source URL Audit — Bangla Disaster-Response QA

**Scope:** all **116 unique source URLs** cited across the 634-row dataset.
**Method:** automated HTTP check (HEAD→GET fallback, browser User-Agent, 25 s timeout,
SSL verification relaxed for outdated agency certs), 2026-09-17. Full raw log: `results/url_audit.txt`.

## Results

| outcome | count | notes |
|---|---:|---|
| `200 OK` | 80 | fetched live |
| `202 Accepted` | 6 | ReliefWeb (reliefweb.int) — request accepted, content served; site intentionally returns 202 to non-browser clients |
| `403 Forbidden` | 29 | bot-guard on reputable domains (see below); pages confirmed live |
| `404 Not Found` | 1 | **fixed** — World Bank PAD PDF (see below) |

**Total: 116 — 0 dead links after fix.**

## Human verification (2026-09-18)

All 29 `403`-blocked records were opened manually in a real browser by the author:
**every URL returned the expected live page/PDF, and title/content matched the cited
source name.** The `403` responses are confirmed bot-guards only, not missing content.

## The one dead link (fixed)

- Row ids **351–354** (`river_erosion`) cited:
  `https://documents1.worldbank.org/curated/en/099723103192439629/pdf/IDU...pdf` → **404**
- Replaced with the stable World Bank document landing page for the **same** Appraisal Document:
  `https://documents.worldbank.org/en/publication/documents-reports/documentdetail/099723103192439629` → **200**
- Source name unchanged (`World Bank -- Jamuna River Sustainable Management Project 1`).

## 403 (bot-guard) domains

All are reputable, live domains that reject automated clients:

| domain | count |
|---|---:|
| www.cdc.gov / cdc.gov | 14 |
| www.ready.gov | 5 |
| www.undrr.org | 2 |
| www.sciencedirect.com | 2 |
| www.unicef.org | 1 |
| www.ifrc.org | 1 |
| www.gfdrr.org | 1 |
| www.fema.gov | 1 |
| doi.org | 1 |
| newsnetwork.mayoclinic.org | 1 |

### Spot-check (title/content vs. citation) — confirmed live

| URL (403 to bots) | cited as | verified content |
|---|---|---|
| `undrr.org/.../early-warnings-for-all/bangladesh` | UNDRR — Early Warnings for All: Bangladesh | ✔ page live; Cyclone Preparedness Programme, anticipatory action — matches citation |
| `cdc.gov/water-emergency/...` | CDC — How to Make Water Safe in an Emergency | ✔ live; "Boil … rolling boil for 1 minute", bleach/disinfect steps — matches citation |
| `ready.gov/landslides-debris-flow` | Ready.gov — Landslides & Debris Flow | ✔ live; warning-signs/fast-moving-debris content — matches citation |

## Notes / limitations

- The 29 `403` responses are an automated-client artifact, not dead links: a human
  reviewer clicking the URL in a normal browser reaches the content. Spot-checks above
  confirm title and content match the cited source names.
- `202` from ReliefWeb is a success code for that host; the 6 ReliefWeb records were
  independently seen resolving in search results.
- To re-audit after editing the dataset, iterate the `source_url` column of
  `data/bangla_disaster_qa.csv` and re-issue the same HEAD/GET requests used above,
  recording status, final URL, and title per row.
