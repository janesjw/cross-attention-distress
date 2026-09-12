# Annual Financial Indicators and Disclosure Text for Predicting ST Risk

## Active study and completed results

The active study is annual-st-sz-v1: one pre-origin annual report, 12 financial ratios, MD&A character TF-IDF/SVD and new ST/*ST in the following 12 months. Predictions are dated May 1 using disclosures available through April 30. Training origins are 2017–2021, validation 2022–2023 and test 2024–2025. Five-year histories, quarterly inputs, FinBERT, gating and composite distress outcomes are retired for this study.

The frozen source-availability sample contains **154 firms and 843 company-years**, with 22 positive outcomes: training 503 (9 positives), validation 124 (2), test 216 (11). All four variants share this sample. Four models across seeds 17, 42 and 2026 have completed; all 12 saved prediction outputs passed the recorded metric audit. No repeat training is required merely to update manuscript wording or figures.

Mean test AP is financial-only 0.3642, text-only 0.0536, concatenation 0.3638 and cross-attention 0.3641. The paired company-cluster 95% AP interval for cross-attention minus concatenation is [-0.0361, 0.0289], and versus financial-only [-0.0868, 0.0538]. These intervals do not establish stable improvement and do not prove equivalence. Validation has only two positive outcomes. ST/*ST measures a regulatory endpoint, not all financial distress.

See [the empirical report](data/derived/annual_st/results/empirical_reanalysis.md), [saved results](data/derived/annual_st/results/results.json), [raw predictions](data/derived/annual_st/results/predictions.csv) and [metric audit](data/derived/annual_st/results/metric_recalculation.json).

## Authoritative data and provenance

- Immutable analysis input: `data/derived/annual_st/frozen_samples.jsonl`.
- Frozen contract and hashes: `data/derived/annual_st/frozen_manifest.json`.
- Eligibility and exclusions: `data/derived/annual_st/sample_inventory.csv`.
- Source selection, label windows and certification: `data/verification/annual_st/`.
- Training implementation: `src/distress/annual_train.py`.
- Filing collection totals and frozen sample totals are separate fields in `data/derived/filing_summary.json`.

The embedded protocol status in the frozen manifest is historical pre-freeze wording. The top-level frozen flag, dataset digest and later completed result files record subsequent stages. Preserve the embedded protocol and evidence hashes; do not overwrite a historical snapshot to make all status strings identical.

The SQLite `sample_register` and `financials.csv` / `samples.csv` support legacy reconstruction and are not the 843-row annual analysis dataset. Annual construction uses the candidate register as a linked source, with separate annual source certification and labels. Seed CSV views are intentionally retained; `analysis/verify_package.py` checks their replay and the current SQLite tables. Do not replace the annual frozen export with legacy eligibility counts.

## Reproduction and checks

Use [the annual workflow](analysis/ANNUAL_WORKFLOW.md) and [study specification](analysis/SIMPLIFIED_STUDY.md) for the active design. Existing result and prediction files support manuscript tables without rerunning training. The annual freeze loader verifies the manifest and dataset hashes. Training is gated by the frozen digest, training-code digest and complete model/seed set.

Legacy package checks use Python 3.12 with the pinned project dependencies:
```bash
python analysis/verify_package.py
```
This verifies registered hashes, SQLite integrity, source normalization, deterministic database/CSV replay and software tests. It does not rerun the 12 annual training experiments. `python analysis/sqlite_closeout.py` provides a read-only summary of existing SQLite files and their candidate linkage to the frozen annual observations, without rebuilding data.

Historical Transformer/LSTM/FinBERT code and the old protocol are preserved for provenance only. Legacy input counts or unresolved composite labels are not current annual-study claims. Synthetic fixtures validate software, not empirical performance.

## Limitations and reuse

The sample is selected by source availability and certification, rather than representative sampling. Most financial input records have rule-based source checks, not manual review. Sparse events and wide intervals constrain inference. A code license has not yet been selected; source material remains subject to its providers' terms.

<!-- ANNUAL_ST_FROZEN_START -->
## Frozen annual ST sample

```json
{
  "sample_version": "annual-st-sz-v1",
  "candidate_firms": 471,
  "candidate_firm_years": 3335,
  "final_firms": 154,
  "final_sample_count": 843,
  "positive": 22,
  "negative": 821,
  "origin_min": "2017-05-01",
  "origin_max": "2025-05-01",
  "splits": {
    "train": {
      "rows": 503,
      "firms": 143,
      "positive": 9,
      "negative": 494,
      "positive_firms": 9,
      "negative_firms": 141
    },
    "validation": {
      "rows": 124,
      "firms": 124,
      "positive": 2,
      "negative": 122,
      "positive_firms": 2,
      "negative_firms": 122
    },
    "test": {
      "rows": 216,
      "firms": 127,
      "positive": 11,
      "negative": 205,
      "positive_firms": 11,
      "negative_firms": 121
    }
  }
}
```

The same summary is recorded in `data/derived/filing_summary.json` and `data/derived/annual_st/frozen_manifest.json`. Source-availability and automatic-validation limitations are recorded in the manifest. Training is complete as documented in the linked result files; the original frozen manifest remains unchanged.
<!-- ANNUAL_ST_FROZEN_END -->
