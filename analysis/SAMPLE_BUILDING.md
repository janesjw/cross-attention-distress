# Evidence-driven sample construction

Run `python analysis/build_samples.py` after reviewed evidence is registered.
The program updates all 5,250 fixed-cohort records from their actual evidence,
preserving unknown labels and writing an explicit eligible/excluded/pending decision.
The existing `cohort_screening` and `sample_readiness_audit` outputs are earlier
snapshots. Use `sample_decisions.csv` and `sample_decisions.json` for the current
adjudication; do not treat the older hard-coded pending columns as current results.

The builder reads historical industry provenance, confirmed baseline ST cover
evidence, reviewed financial facts and audit opinions, annual text sections,
membership evidence, source-completion certificates and follow-up event coverage.
Quarterly and audit conjunctions can be ruled out by a known false component.
Uncollected financial data cannot cause a missingness exclusion. No-event leads
from security-name histories are not silently converted to negative labels.

Every pending record has a task in `sample_completion_tasks.json` specifying
annual years, beginning balances, quarterly cumulative periods, disclosure cutoff,
annual text year and outcome window. This is a work queue, not a frozen manifest.
It does not perform the remaining source review automatically.

The initial execution produced 188 exclusions and 5,062 pending records, with
zero eligible samples. One selected record has known quarterly and audit baseline
components and a verified pre-origin annual text. These remain data-readiness
results, not model-performance results. No training or dataset freeze was performed.

The exporter now recognizes both Chinese and English annual-report titles,
excludes summaries and interim reports, checks the disclosure date, and treats
unresolved simultaneous versions as missing reviewed text. Chinese MD&A sections
receive the same selection priority as their English-named equivalents.

Each scheduled job registers reviewed evidence and rebuilds/preserves sample
decisions before spending time on the next extraction batch. Freeze still requires
completed source review, label ascertainment and the protocol's global gates.
README final sample counts, filing_summary.json and the frozen manifest remain
unchanged until that certified freeze.

The original `financials.csv` and `samples.csv` are seed-recovery views. Current
sample adjudication is in `sample_decisions.csv`; current financial facts are in
the database. Package verification replays the seed, registered reviewed bundles
and sample construction, then compares every database table and decision output.
Newly staged review bundles that have not yet been ingested are not represented
as already registered evidence. Hash and integrity checks remain mandatory.
