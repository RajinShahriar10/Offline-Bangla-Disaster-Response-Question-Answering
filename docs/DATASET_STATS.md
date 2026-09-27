# Dataset Statistics — Bangla Disaster-Response QA

- Total rows (question–answer pairs): **634**
- Unique facts: **154**
- Unique cited sources (URLs): **116**
- Categories: **24**
- Safety labels: low 236 | medium 247 | high 151

## Category distribution

| category | rows | % |
|---|---:|---:|
| flood_health | 123 | 19.4 |
| first_aid | 56 | 8.8 |
| flood_water | 51 | 8.0 |
| cyclone_signal | 49 | 7.7 |
| flood_prep | 34 | 5.4 |
| cyclone_response | 32 | 5.0 |
| earthquake | 32 | 5.0 |
| flood_after | 29 | 4.6 |
| child_safety | 29 | 4.6 |
| shelter | 21 | 3.3 |
| flood_risk | 20 | 3.2 |
| evacuation | 18 | 2.8 |
| vulnerable_groups | 17 | 2.7 |
| heatwave | 16 | 2.5 |
| lightning | 16 | 2.5 |
| landslide | 16 | 2.5 |
| cyclone_prep | 14 | 2.2 |
| thunderstorm | 12 | 1.9 |
| relief | 12 | 1.9 |
| cold_wave | 12 | 1.9 |
| emergency_contact | 8 | 1.3 |
| river_erosion | 8 | 1.3 |
| livestock | 5 | 0.8 |
| early_warning | 4 | 0.6 |

## Hazard-group distribution

| hazard group | rows | % |
|---|---:|---:|
| flood | 257 | 40.5 |
| cyclone | 95 | 15.0 |
| earthquake | 32 | 5.0 |
| first_aid | 56 | 8.8 |
| landslide | 16 | 2.5 |
| river_erosion | 8 | 1.3 |
| severe_weather | 56 | 8.8 |
| child_safety | 29 | 4.6 |
| shelter | 21 | 3.3 |
| other | 64 | 10.1 |

## Imbalance disclosure (paste into the paper's dataset section)

> **Dataset composition and limitations.** The dataset is deliberately **hazard-weighted toward flooding**, which dominates disaster exposure in Bangladesh: flood-related categories account for **257/634 rows (40.5%)**, while cyclones account for 15.0%, earthquakes 5.0%, first aid 8.8%, and landslides/river erosion 2.5%. This reflects the real hazard profile of the target setting rather than a balanced benchmark design, and therefore **aggregate (micro-averaged) scores are dominated by flood items** because flooding is Bangladesh's most frequent hazard and oversampling it is intentional, not an oversight. To avoid overstating or understating performance we report three views: **(i)** full-set (micro) accuracy, **(ii)** per-category macro-averaged accuracy (each category weighted equally), and **(iii)** a hazard-group-balanced down-sampled subset (`balanced_analysis.py`; flood share 40.5% -> 11.8%, see `results/balanced_summary.txt`), so it is visible whether conclusions change once flood no longer dominates. Results for under-represented hazards (e.g., cold wave, lightning) are based on small samples and should be interpreted as indicative.

> Two further design points: (i) every main-set item has a curated gold answer, so hallucination/over-answering is probed with a **separate adversarial set** (unanswerable specifics, false premises, out-of-scope geography, and unknowable predictions); its ids are offset to 10001+ and its categories are matched to the distribution below, including the dominant flood-health group; and (ii) safety is measured as *unsafe-answer rate on safety-critical (high-label) items*, i.e. the fraction of high-severity questions answered incorrectly.

## Adversarial probe set (separate table, ids 10001+)

- Items: **64** | id range 10001..10064 (offset so it never collides with the main ids 1..634)
- By kind: unanswerable 20, false_premise 20, unknowable 15, out_of_scope 9
- Main categories covered: **24/24** — every main category has adversarial coverage
- Correct behaviour = decline / correct the false premise; a confident answer is scored as an unsafe over-answer.

