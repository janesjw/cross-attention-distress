# Annual Financial Indicators and Disclosure Text for Predicting ST Risk

The active, user-authorized design uses one pre-origin annual report, 12 financial ratios, annual-report text and a subsequent 12-month ST/*ST endpoint. Five-year histories, quarterly inputs and the composite distress label are retired for this study. There is no fixed final-sample-size quota. See [the simplified study specification](analysis/SIMPLIFIED_STUDY.md) and `configs/active_study.json`.

Collection and input inventory are in progress; the simplified sample is not frozen and empirical results are not yet available. Current readiness is recorded in `data/derived/annual_st/status.json` after the pipeline runs. Candidate observations, parsed values and ST leads are not verified training samples.

The original Transformer/LSTM/FinBERT MMAN implementation and its protocol are preserved for reconstruction and provenance. The reproduction instructions and historical audits below refer to that archived design; its training job is disabled for the active annual-only study.

## Repository contents

- `src/distress/`: data processing, model implementation, training, and evaluation.
- `analysis/`: database build and package verification commands.
- `data/raw/`: financial records and source metadata.
- `data/derived/`: SQLite database and CSV views of financials and sample eligibility.
- `configs/`: prediction rules, model settings, and the text-model version.
- `tests/`: data and model tests.
- `DATA_SOURCES.md`: source locations and data conventions.

## Reproduction

Use Python 3.12 from the repository root:

```bash
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e .
python analysis/build_database.py
python analysis/verify_package.py
```

The build command creates a fresh copy in `data/derived/rebuilt/`, preserving the included snapshot. Verification checks file hashes, database consistency, CSV outputs, and offline tests. These commands run offline after dependency installation. `requirements-lock.txt` records the tested environment; model weights and source PDFs are downloaded separately.

## Data and prediction setup

The exchange register contains 5,550 listings and 7,327 historical name changes. Listing-date screening yields 30,732 candidate company-years. Financial observations currently cover two companies; formal sample selection and estimation remain pending.

Predictions are dated May 1, using information disclosed through April 30, with a 12-month follow-up. Records already meeting a distress condition are excluded. Inputs comprise 90 annual values, 32 quarterly values, and report text. Missingness is assessed before imputation: more than 27 missing annual values or nine missing quarterly values excludes a record after source collection is complete.

## Reuse

Source data and pretrained models remain subject to their providers' terms. A code license has not yet been selected.

