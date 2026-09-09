# Data Directory

- `raw/records.json`: companies, disclosures, financial observations, events, and audit opinions.
- `derived/distress.sqlite`: database with source references and sample eligibility.
- `derived/financials.csv`: financial observations with units, disclosure dates, and source URLs.
- `derived/samples.csv`: company-year records, forecast windows, baseline status, and outcomes.

Run `python analysis/build_database.py` to regenerate these outputs in `derived/rebuilt/`. The JSON file is the input; SQLite and CSV files are generated views.

In the CSV files, blank values mean unknown or unavailable. For `outcome`, `1` denotes incident distress and `0` requires complete non-distress follow-up. `analytical_eligible=1` identifies records ready for analysis. Excluded and pending records have blank outcomes.
