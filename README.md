# Offline Bangla Disaster-Response QA with Compact Open-Source LLMs

Artefacts for the ICCIT paper *"Offline Bangla Disaster-Response Question
Answering with Compact Open-Source LLMs: A CPU-Only Evaluation of Accuracy,
Safety, and Efficiency Trade-offs."*

This repository releases the benchmark, the adversarial answerability probe, the
human annotation record, the evaluation pipeline, and the exact per-model
outputs behind every number in the paper.

**Headline result (negative, and reproducible).** At a strict human-calibrated
threshold, the best of six compact open-weight models answers only **25.7%** of
634 Bangla disaster questions correctly, and **all six** answer the majority of
64 adversarial traps with a confident fabrication (62.5-93.8% over-answering).
A deterministic refuse-by-default wrapper cuts over-answering to 0.0-6.2% at the
cost of availability, but is explicitly not sufficient on its own.

---

## What is here

```
data/      benchmark (634 items), adversarial probe (64 items), licensing notes
src/       the evaluation pipeline (20 scripts)
results/   per-model generations, cross-encoder scores, human labels, summary tables
paper/     ICCIT2026.tex and refs.bib
docs/      methodology notes, dataset statistics, source-URL audit
```

## The data

### `data/bangla_disaster_qa.csv` — 634 items

| Column | Meaning |
|---|---|
| `id` | sequential item id |
| `category` | one of 24 hazard/response categories |
| `question_bn`, `question_en` | the question (Bangla is the evaluated form) |
| `answer_bn`, `answer_en` | single gold answer |
| `safety_label` | `low` 236 / `medium` 247 / `high` 151 — how dangerous a wrong answer would be |
| `source_name`, `source_url` | the official or news source the fact was drawn from |

Distribution is deliberately flood-heavy (257 rows, 40.5%) to mirror Bangladesh's
hazard profile, which is why the paper reports micro, macro, and two
hazard-balanced views rather than a single accuracy figure: a group-balanced
subset (cap 30 -> 254 rows, 11.8% flood) and a category-balanced subset
(cap 16 -> 331 rows, 24.2% flood). See `results/balanced_summary.txt` and
`results/balanced_summary_category.txt`.

### `data/adversarial_set.csv` — 64 items

Four trap types where declining is the correct behaviour: 20 unanswerable
specifics, 20 false premises, 9 out-of-scope requests, 15 unknowable
predictions. No gold answer; scoring uses the human-validated safe/over-answer
label.

### Human labels

- `results/review_full_*.csv` — **2,058** accuracy judgements (labelled rows only)
- `results/adv_review.csv` — **384** adversarial safety judgements
- `results/iaa_result.txt` — inter-annotator agreement, n=32 (16 accuracy + 16
  safety items double-annotated): 27/32 = 84.4% raw agreement, Cohen's kappa
  0.774 combined

Both annotators' verdicts are recorded against item ids only; no annotator
identities are included. See `data/LICENSING.md` for what is withheld and why.

## Reproducing

### Requirements

- Python 3.12 (`pip install -r requirements.txt`)
- [Ollama](https://ollama.com) serving the six checkpoints below
- ~8 GB RAM, CPU-only (the reported run: Intel Core i5-10400, 7.8 GB usable, Windows 11)

### Models

All quantised `Q4_K_M`, temperature 0, 512-token decode budget:

```
gemma3:1b    gemma3:4b    qwen3:1.7b
qwen3:4b-instruct-2507-q4_K_M
titulm-v1.1-1b    titulm-v1.1-3b
```

```bash
ollama pull gemma3:1b
ollama pull gemma3:4b
ollama pull qwen3:1.7b
ollama pull qwen3:4b-instruct-2507-q4_K_M
```

TituLM 1B/3B are Bangla base models; adapt them from the Llama-family
checkpoints described in Nahin et al. (Findings of ACL 2025) and run them
through Ollama as `titulm-v1.1-1b` / `titulm-v1.1-3b`.

### Pipeline

Scripts in `src/` assume the current working directory is the repository root
and read `data/`, writing to `results/`.

```bash
# 1. generate answers for the 634-item benchmark (one model at a time)
python src/run_benchmark.py --dataset data/bangla_disaster_qa.csv --model gemma3:1b

# 2. score with the multilingual cross-encoder and build the review set
python src/score.py --input results/full_gemma3-1b.csv

# 3. adversarial probe
python src/eval_adversarial.py --model gemma3:1b
python src/score_adversarial.py

# 4. footprint and speed (peak RAM, cold tTFB, steady tok/s)
python src/measure_footprint.py --model gemma3:1b

# 5. analysis: macro/balanced views, threshold calibration, agreement, tables
python src/balanced_analysis.py
python src/calibrate.py
python src/analyze_iaa.py
python src/dataset_stats.py
python src/generate_figures.py
```

The accuracy metric is a cross-encoder relevance score
(`jinaai/jina-reranker-v2-base-multilingual`, 278M params) thresholded at
`t=0`. That threshold is *not* tuned: it is fixed by two anchors — a
wrong-gold chance condition passes 0/400 pairs, and verbatim gold passes
634/634. Against 2,058 human labels the verdict agrees 59.2-71.7% of the time,
so the reported accuracy is a deliberate **lower bound**.

We deliberately rejected plain embedding cosine: in a pilot it scored fluent
but hallucinated Bangla at ~0.93 and could not separate correct from wrong.

### Annotation

`src/make_review_xlsx.py`, `src/make_adv_review_xlsx.py`, and
`src/make_iaa_sheet.py` generate the labelling workbooks; annotations are
imported back with `src/import_xlsx_labels.py`. Agreement is computed by
`src/analyze_iaa.py` (Cohen's kappa, reported alongside raw agreement per
Artstein & Poesio 2008).

## Mapping claims to files

| Paper claim | Evidence |
|---|---|
| accuracy table, CE@0, danger rate | `results/scored_full_*.csv` (634/model); per-model tables in `results/summary_full_*.txt` |
| latency, tTFB, throughput | `results/full_*.csv` timing columns, `results/footprint.txt` |
| over-answering, `fabOfOver` | `results/adv_*.csv`, `results/adv_review.csv` |
| wrapper effect (62.5–93.8% → 0.0–6.2%) | `results/wrapper_table.txt`, `results/wrapper_summary.txt` |
| macro / hazard-balanced views | `results/balanced_summary.txt` (254-row), `results/balanced_summary_category.txt` (331-row), `results/balanced_subset_*.csv` |
| human agreement 59.2–71.7% | `results/review_full_*.csv` (2,058 rows) |
| IAA 84.4%, kappa 0.774 | `results/iaa_result.txt` |
| dataset composition | `docs/DATASET_STATS.md` |

`src/wrapper_claims_check.py` re-verifies the wrapper figures against the
released CSVs.

**One stale string, flagged on purpose.** `results/summary_full_*.txt` was written
during the pre-calibration stage and prints
`CE_THRESHOLD: 0.0 (provisional - calibrate on review set)`. The "provisional"
note is a leftover, not the final protocol: the reported threshold is `t=0`,
fixed by the two anchors described above and never tuned on the review set. The
accuracy values in those files are the final ones.

## Building the paper

`paper/ICCIT2026.tex` targets the IEEEtran conference class (6 pages).

```bash
cd paper
pdflatex ICCIT2026.tex && bibtex ICCIT2026 && pdflatex ICCIT2026.tex && pdflatex ICCIT2026.tex
```

`paper/refs.bib` contains 20 peer-reviewed references (ACL/NAACL/EMNLP/EACL/
LREC-COLING/COLING/IJCNLP-APACL, AAAI, ICML, MLSys, CoRL, SOSP, IEEE Access,
*Computational Linguistics*). No preprints or workshop papers are cited; model
checkpoints have no bibliographic entry and are identified by exact runtime tag
instead.

## Citation

See `CITATION.cff`. If you use the benchmark or the wrapper, please cite the
paper and reuse the released item ids so results stay comparable.

## Licence

Code: MIT. Data: CC BY 4.0. Third-party source text is deliberately not
redistributed — see `data/LICENSING.md`.

## A note on the safety framing

This work evaluates models on disaster-response questions so that they can be
used *more* safely, not less. The dataset is not operational guidance: it is
author-written QA material for measuring model behaviour, and every answer is
attributed to a citable source. Nothing here should be relied on in an actual
emergency — in Bangladesh, the relevant authorities are the Bangladesh
Meteorological Department and the national emergency services.
