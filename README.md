# Annual ST risk prediction: multimodal value and early-warning limitations

This compact repository contains the integrated Financial Internet Quarterly working manuscript, versioned model inputs, source audit ledgers, code and verified predictions. The current tracked payload is kept below 10,000,000 bytes. Git history remains intact, so a full clone or GitHub's repository-size statistic can be much larger. No history rewrite is required.

## Current study

Annual-ST-SZ-v2 contains **969 firm-years from 155 firms, with 26 ST/*ST implementation events**. Training: 503 / 9 events (2017–2021); validation: 250 / 6 (2022–2023); test: 216 / 11 (2024–2025). The original 843 observations and all original training/test assignments are unchanged; all 126 industry-resolved 2023 observations are added to validation. See evidence/filing_summary.json and evidence/timing_and_cohort_resolution.md.

Prediction is at May 1, using information available by April 30: twelve annual financial ratios and selected MD&A chunks from the same annual report. Text uses training-fitted character TF-IDF and SVD. The revised analysis is exploratory because original test results had already been inspected. No observations were selected to obtain significance.

Test average precision is 0.2177 for the fixed L2 logistic baseline and, across three neural seeds, 0.3798 financial-only, 0.0579 text-only, 0.3685 concatenation and 0.3547 cross-attention. Paired company-bootstrap intervals do not establish incremental cross-attention value over financial-only or concatenation. The financial neural minus specified logistic AP interval is [0.0136, 0.4066], an unadjusted exploratory comparison. Ranking performance, threshold recall, annual alert budgets and announcement timing are reported separately.

## Paper files

- manuscript/Annual_ST_Manuscript.docx: anonymous complete main text; 13 rendered pages, 33,024 editable characters including references, tables and captions.
- manuscript/Annual_ST_Title_Page.docx: separate supplied author information and declarations; this private repository as a whole is not an anonymous submission package.
- manuscript/Annual_ST_Editable_Tables.docx: six main tables and supplementary Table S1; four pages.
- manuscript/figures/: five separate PNG/SVG figures and seven CSV/PNG/SVG table exports (table_7 is S1).
- manuscript/Reviewer_Response_Ledger.csv and Citation_Audit.csv: original comment, change, location, evidence and status.

Seventeen historical comment items are closed; one citation-locator group remains as an actual Word comment. Four references have verified publisher-abstract support but still need published-page locators or journal acceptance of the explicit electronic paragraph locators. See manuscript/Review_Status.md. No final journal submission has been made.

## Verification and reproduction

Run `python verify.py` using Python 3.12 or newer. This checks every manifested file, exact model inputs, all 26 validation/test metric groups for 13 fits, logistic score-to-sample alignment, and supplementary output counts. It performs no training. GitHub Actions also enforces the current tracked-file size limit, excluding Git history.

To refit, install requirements.txt. Run `PYTHONPATH=src python -m distress.annual_train --root . --output rerun --epochs 100 --bootstrap 2000` for neural models, or `PYTHONPATH=src python fit_logistic.py` for the single fixed logistic model. Training artifacts are intentionally not tracked. Reproduction can vary across hardware and dependency environments; the supplied saved predictions define the reported results. Rerunning analyses may change output files and will require an explicit new manifest/version review.

`python supplement_analysis.py` regenerates annual budgets, validation-event stress checks and notice-conditioned sensitivities from saved scores. `python compare_logistic.py` regenerates paired company-bootstrap comparisons (requires dependencies). `python build_figures.py` regenerates displays with requirements-figures.txt. No rerun is necessary to read or verify this release.

The compact database is gzip-compressed JSONL, not a SQLite database. It preserves exact selected-chunk model inputs, not full raw MD&A documents. Raw historical source packets and v1 evidence remain in earlier commits, including e92becd6ff0f4b2078d29985767cb1f6afced1e2. Original uploaded documents and full local replay artifacts remain in the research workspace. file_manifest.json records current-file SHA-256 values; see evidence/README.md for historical version differences.

## Figure revision — 2026-09-14

All five figures were redrawn with Python/Matplotlib in black/grey academic style. The numerical curves reproduce all 13 saved test AP and ROC AUC values. Main Word remains 13 pages; the original comment is preserved. `build_figures.py` is the current figure source; `build_tables.py` regenerates the unchanged tables separately. Five vector PDFs are included alongside the PNG/SVG files. See manuscript/curve_verification.json, word_update_audit.json and figures/figure_build_audit.json. No training, data or numerical result changed.
