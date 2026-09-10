# Batch financial-statement processing

The earlier pipeline downloaded PDFs and found financial keywords, but did not
structure statement rows. `structure_financials.py` now scans all existing
hash-checked extraction archives on every pipeline run and caches results by the
source hash and parser-code hash. It does not require downloading these PDFs again.

It recognizes consolidated annual, half-year and quarterly statement headings,
stops at parent-only statements, checks yuan units, and retains both printed
columns plus page and line anchors. It extracts 16 feature inputs and five
accounting controls. Blank values are not zeros, missing comparative columns
cannot borrow numbers from another row, and two statement versions in one report
are sent to review. Comparative dates are not inferred from the current date:
in particular, a January 1 balance is not silently relabelled December 31.

Four accounting checks run separately on each column: assets = liabilities +
equity; pretax profit minus income tax = consolidated net profit; parent profit
plus minority profit = consolidated net profit; and operating inflows minus
outflows = operating cash flow. The absolute residual tolerance is two yuan.
These are consistency checks, not independent validation of all input amounts.

Outputs under `data/automation/structured/` contain one compressed statement
packet per document, `status.json` with counts, and `exceptions.json` with
document-specific parsing failures. A machine pass still needs period/header,
disclosure-version, cross-report comparability and completeness review. These
candidate rows do not enter the verified-facts table and cannot trigger training.
Historical membership/industry, ST event coverage, audit classification, MD&A
selection and 12-month labels remain separate sample requirements.

The extraction schedule changes from 500 documents per hour to at most 1,000 per
half-hour, with the same four processes and 25-minute time bound. This is a
fourfold increase in scheduled document capacity, not a promise of fourfold
verified-sample throughput. GitHub scheduling delays, source availability,
timeouts and review exceptions can reduce actual throughput.

Collection also prioritizes disclosures needed by the registered origins:
five annual inputs plus beginning balances, quarterly inputs, and reports in
the twelve-month follow-up window. Older ancillary quarters are retained at a
lower priority; unknown report titles remain queued for period review. No firm,
sample or document is deleted by this ordering, and report versions are retained.

Tests compare parsed values and page anchors with existing visually reviewed
evidence and exercise parent-scope contamination, missing values, wrong units,
accounting failures, ambiguous versions and future-period rejection. Final sample
counts and manuscript performance claims are unchanged until sample freeze and
actual experiments.
