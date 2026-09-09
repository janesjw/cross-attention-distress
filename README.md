# A Cross-Attention Multimodal Fusion Network for Corporate Financial Distress Early Warning

This repository contains data and Python code for corporate financial distress prediction using annual financial indicators, quarterly changes, and annual-report text. The model combines a Transformer, an LSTM, and Chinese FinBERT through cross-attention and sample-specific fusion weights.

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

The build command creates a fresh copy in `data/derived/rebuilt/`, preserving the included snapshot. Verification checks file hashes, database consistency, CSV outputs, and 35 tests. These commands run offline after dependency installation. `requirements-lock.txt` records the tested environment; model weights and source PDFs are downloaded separately.

## Data and prediction setup

The current snapshot contains two companies, 26 disclosures, 142 financial observations, and four company-year records. Two records are excluded at baseline; two remain pending. Full-sample estimation is pending.

Predictions are dated May 1, using information disclosed through April 30, with a 12-month follow-up. Records already meeting a distress condition are excluded. Inputs comprise 90 annual values, 32 quarterly values, and report text. Missingness is assessed before imputation: more than 27 missing annual values or nine missing quarterly values excludes a record after source collection is complete.

## Reuse

Source data and pretrained models remain subject to their providers' terms. A code license has not yet been selected.
