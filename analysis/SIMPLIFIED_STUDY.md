# Active annual-only ST study

The user authorized simplifying the research design and removing the approximate
5,000-observation target. `configs/active_study.json` now selects
`annual_st_v1`. The original protocol, cohort, database and experiments remain
available for provenance; their feature/label definitions are not the active design.

## Scope and stopping rule

The reduced collection frame contains all 471 Shenzhen firms already included
in the original selection, retaining their 3,335 registered company-year origins
from 2017 to 2025. These are candidates, not a locked sample. Restriction to
Shenzhen is motivated by existing exchange name-history coverage, not selection
for a model result. The frame includes delisted records but does not establish
representative coverage of all historical listings. Conflicting listing records,
historical nonfinancial status and ST history still require review.

There is no target of exactly 5,000, 3,335, or any other final sample count.
Complete the reduced frame and apply the prespecified eligibility rules. Do not
drop or replace companies to obtain significant model differences. The current
name-history leads include 32 potential new ST observations in the training
period, 15 in validation and 24 in testing, among name-history baseline-clear
records. These are not verified labels and precede final eligibility checks.
They motivate retaining event information rather than arbitrarily drawing a
few hundred mostly negative observations. Precision and stability must be
assessed from actual outcomes, firm counts and confidence intervals.

## Annual inputs and endpoint

Each origin uses the previous fiscal year's complete annual report as published
before May 1. Older annual histories and quarterly reports are no longer part
of the active extraction queue. Corrections before cutoff remain available;
post-cutoff revisions cannot replace the input version. The same report supplies
12 ratios and MD&A text. The ratios use year-end denominators explicitly; none
requires beginning balances, shares, capex or interest expense. At most three
of twelve missing ratios are allowed only after source review. Training data
alone determine imputation and transformations.

The target is a new ST/*ST implementation over the following twelve months in
a firm verified non-ST at baseline. Two-quarter losses and nonstandard-audit
losses are no longer part of the endpoint or exclusion rule. ST is a specific
exchange risk designation, not proof of every type of corporate financial
distress. Historical baseline and complete event coverage remain necessary;
unknown is not negative. Endpoint ascertainment does not require downloading
every quarterly report under the retired composite definition.

## Models and evaluation

The registered minimal comparison uses financial-only, text-only, concatenation
and cross-attention models with three fixed seeds. Text uses training-only
character TF-IDF/SVD representations of multiple bounded chunks. The attention
model queries these chunks using financial features. No external pretrained
language model, five-year Transformer, quarterly LSTM or fusion gate is required.
Chronological splits are unchanged: 2017–2021 training, 2022–2023 validation,
2024–2025 test. Labels must be available at the corresponding fitting boundaries.
Thresholds are selected on validation; paired test differences use company-cluster
bootstrap intervals. Repeated seeds are not additional independent observations.

The manuscript will focus on incremental text information and the matched fusion
comparison. Three standalone theoretical propositions, gate claims and claims
about all-cause distress are retired. All previous performance figures remain
unverified and cannot be carried into the redesigned results. An inconclusive
comparison must be reported as such; a smaller sample does not guarantee power.

## Implemented status

The live pipeline selects annual documents for the reduced study, structures
the archived statements, and writes `data/derived/annual_st/status.json`,
`sample_inventory.csv` and `candidate_inputs.zip`. The latter contains explicitly
unverified candidate financial values/text and, where available, separate
previously verified financial values. Statement checks do not certify labels.
The inventory reuses only historical financial-sector and baseline-ST exclusions
from the legacy audit, not the retired quarterly/audit-loss exclusions.

New input certification, ST coverage review, the simplified frozen exporter and
experiment runner are still required. The old MMAN training job is explicitly
disabled for this design so it cannot silently consume incompatible annual-only
inputs. README final-sample figures, filing_summary and a frozen manifest will
be synchronized after a real sample freeze, not at collection-scope registration.
