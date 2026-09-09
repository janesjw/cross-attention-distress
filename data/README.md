# Data Directory

- `raw/market_records.json`: exchange listings and historical name changes.
- `raw/market_sources.zip`: original exchange downloads and source hashes.
- `raw/disclosure_firms.json`: issuer IDs for periodic-report collection.
- `raw/records.json`: companies, disclosures, financial observations, events, and audit opinions.
- `derived/distress.sqlite`: database with source references and sample eligibility.
- `derived/financials.csv`: financial observations with units, disclosure dates, and source URLs.
- `derived/samples.csv`: company-year records, forecast windows, baseline status, and outcomes.

Run `python analysis/build_database.py` to regenerate these outputs in `derived/rebuilt/`. The JSON files are the inputs; SQLite and CSV files are generated views.

In the CSV files, blank values mean unknown or unavailable. For `outcome`, `1` denotes incident distress and `0` requires complete non-distress follow-up. `analytical_eligible=1` identifies records ready for analysis. Excluded and pending records have blank outcomes.

`candidate_register` contains listing-date candidates and name-based ST screening evidence. It does not identify training-ready observations. Current industry classifications are retained as snapshots, not historical classifications.
CDRs are retained in the source register and excluded from the A-share candidate frame.

`derived/cohort_screening.csv` and `derived/cohort_screening.sqlite` contain the fixed cohort with industry, baseline ST and completeness statuses. `derived/historical_industry.json` preserves pre-origin classification sources and page references. An excluded record is not a future positive label. Pending records remain in the register and are not eligible for analysis.
