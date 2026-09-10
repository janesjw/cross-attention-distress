# Minimal reviewer evidence route

The latest inspected source commit was `f92cdc645a4e6c3690b144341943690c60e35e1f`.
Its September 10 extraction status contained 44,962 queued documents, 146 extracted
documents overall, 121 extracted within the selected queue, zero eligible analytical
samples and zero verified text sections. Those are collection counts, not study results.

## Immediate changes

- Extraction uses up to four separate processes, preserving a single checkpoint writer.
  Each hourly run attempts up to 500 documents within a 25-minute dispatch budget.
  Existing source hashes, finite cohort restrictions and capped retries remain in force.
  These are processing limits, not a throughput or completion-date guarantee.
- `configs/fast_review_protocol.json` selects seven variants and three seeds, or 21
  neural runs. This replaces the 50-run exhaustive protocol for the first evidence pass.
- The full model is compared with no attention, no learned gate, no text, and each
  single-modality model. Attention and gate effects are conditional contrasts, not a
  full factorial interaction. Three seeds provide limited training-variation evidence.
- Training saves dated test predictions and a completion receipt with file, checkpoint
  and dataset hashes. The report rejects incomplete suites, changed files, inconsistent
  labels, mismatched samples, thresholds or shared configurations.
- Metrics, confusion matrices, ROC/PR curves and epoch-loss plots are regenerated from
  those saved outputs. Company-cluster paired intervals and between-seed SD are distinct.
  Undefined metrics are explicit nulls rather than fabricated zeroes.

## What is still missing

The extraction script finds candidate passages; it does **not** verify financial scope,
units, periods, disclosure versions, narrative sections, baseline distress or negative
outcome coverage. That reviewed evidence must be registered in the analytical database.
Faster downloads alone cannot complete the dataset. The suite preflight currently
refuses to run because the frozen dataset is absent; no research training was completed.

Do not clear `pending_before_full_dataset` or label unknown records negative to bypass
this stage. Preserve the confirmed incident-distress and missingness definitions.
Freeze only after historical industry, baseline status, 12-month outcomes and inputs
are resolved. Then regenerate README sample figures, `filing_summary.json` and the
frozen manifest together from the certified sample.

## Run after the freeze

Use the repository's documented Python environment and install the plotting extra:

```bash
python -m pip install -r requirements-review.txt
python analysis/run_review_suite.py --database data/derived/distress.sqlite --manifest data/derived/frozen_dataset.json --output runs/fast-review --check-only
python analysis/run_review_suite.py --database data/derived/distress.sqlite --manifest data/derived/frozen_dataset.json --output runs/fast-review --device cpu
```

Use an already available GPU by setting `--device cuda`; none is provisioned here.
Completed, intact runs are reused. An incomplete run is retained and blocks silent
overwriting. The existing scheduled training job remains a single-run readiness path;
the 21-run suite is explicitly invoked only after the data gate passes.

The summary provides pooled and separate-year 2024/2025 metrics, per-seed paired F1
and AUC intervals, editable SVGs and PNGs. No familywise significance is asserted.
Same-history traditional baselines remain necessary before claiming superiority to
XGBoost. Textual lead time and semantic causality require additional evidence and must
not be claimed from these predictive contrasts.

Software validation used temporary synthetic fixtures. Their results are not research
performance and are not included in the manuscript or study dataset.
