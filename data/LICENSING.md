# Licensing and provenance of the released data

## What is released

| File | Rows | Licence |
|---|---|---|
| `data/bangla_disaster_qa.csv` | 634 | CC BY 4.0 |
| `data/adversarial_set.csv` | 64 | CC BY 4.0 |
| `results/review_full_*.csv` | 2,058 (labelled rows only) | CC BY 4.0 |
| `results/adv_review.csv` | 384 | CC BY 4.0 |

## What is withheld, and why

### Verbatim source excerpts (`fact_en`, `fact_bn`)

The working dataset carried two extra columns, `fact_en` and `fact_bn`, holding
near-verbatim excerpts of 154 facts drawn from 116 official and news sources
(for example the Bangladesh Meteorological Department, Directorate General of
Health Services, Fire Service, UNB, The Daily Star, The Business Standard).

These columns are **not** redistributed here. Government and news text is
third-party material whose reuse status varies by jurisdiction, and an audit of
the source URLs (`docs/URL_AUDIT.md`) found that a substantial minority return
HTTP 403 to automated clients. Redistributing the excerpts would import that
ambiguity into this repository for no analytical gain: every downstream
artefact (question, answer, safety label, model output, human judgement) is
derived work that is fully released.

Each row still carries `source_name` and `source_url`, so any third party can
re-fetch the source and re-derive the fact independently. This keeps the
released dataset auditable rather than merely usable.

If you need the excerpt columns for a replication study, request them from the
authors.

### The dataset builder script (`_build_dataset.py`)

Withheld for the same reason: it embeds the 154 verbatim excerpts inline as
Python string literals (~490 KB), so shipping it would defeat the omission
above. `docs/METHODOLOGY_NOTES.md` documents the construction procedure
(fact extraction, de-duplication, id assignment, question/answer authoring, and
the safety-labelling rubric) so the dataset can be rebuilt from scratch.

### `results/wrapper_summary.csv`

Withheld. This file is a 6x-inflated join artefact: it contains 2,304 rows
(each of the 6 models paired with all 384 adversarial rows) rather than the
correct 384 (64 items x 6 models). The wrapper figures quoted in the paper come
from `results/wrapper_table.txt` and `results/wrapper_summary.txt`, which are
computed at n=64 per model and reconcile with the paper's 0.0-6.2% residual
over-answer range. Anyone re-deriving wrapper numbers should start from
`results/adv_*.csv` (the per-model adversarial generations) and
`results/adv_review.csv` (the human labels).

### Annotation workbooks (`results/*.xlsx`)

Withheld in favour of the equivalent CSVs, which carry the same labels and are
far easier to diff and script against. The workbooks are regenerable with
`src/make_review_xlsx.py`, `src/make_adv_review_xlsx.py`, and
`src/make_iaa_sheet.py`. They contain no personal data: columns are limited to
model tag, item id, category, question, gold answer, model output, and the
human judgement.

## Human subjects

The annotation was performed by two annotators on model outputs. No personal
data about the annotators is included: the released files record judgements
against item ids only, with no names, initials, or timestamps identifying who
made which call. See `docs/METHODOLOGY_NOTES.md` for the annotation protocol.
