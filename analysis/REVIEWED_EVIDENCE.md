# Reviewed source registration

The September 10 review registered two original CSG Holding disclosures for the
fixed cohort firm 000012.SZ: FY2023 annual report 1219823600 (April 26, 2024) and
Q1 2024 report 1219854723 (April 29, 2024). Both downloaded PDF hashes matched the
existing extraction archive. The reviewer checked the printed consolidated
statements, currency unit and column periods against the extracted text.

The reviewed bundles contain 50 financial facts, one standard unqualified
financial-statement audit opinion, and the annual MD&A section (PDF pages 10–32).
Balance facts use the current column only. The annual opening balance headed
January 1 is not silently relabelled December 31. Income and cash-flow
comparatives retain the later document's actual disclosure date. Cross-document
comparability remains unreviewed, and share capital is not treated as a share count.

For the May 1, 2024 origin, the Q1 consolidated profit is CNY 317,932,830, distinct
from parent-attributable profit CNY 325,377,538. Positive Q1 profit rules out the
Q4/Q1 joint negative-profit-and-operating-cash-flow condition; the standard audit
rules out the nonstandard-audit-and-loss condition. ST status, full input history
and 12-month outcome remain unresolved. The record is not analytically eligible.

`analysis/import_reviewed_evidence.py` checks archive hashes, source identity,
page anchors, numeric columns and section hashes, then imports reviewed bundles
transactionally without overwriting conflicting evidence. It does not automatically
review other reports or assign negative outcome labels. Scheduled extraction runs
apply these bundles before checking readiness and preserve the database and texts.
Three source-backed software tests cover idempotence, source alteration and changed
values. No model-performance result was produced.

Final sample counts in README, filing_summary.json and the frozen manifest remain
pending the certified sample; these source-registration counts are not substitutes.

## Annual history extension

Four further original annual reports have now been checked against hash-matched
PDFs: 2019 (1207683744), 2020 (1209687499), 2021 (1213059469), and 2022
(1216593484). The bundles add 121 consolidated financial facts, taking this
reviewed set to six documents and 171 facts. The 2019–2021 statements explicitly
label the comparative balance column December 31; those values retain their
actual later disclosure dates. The 2022 opening column is January 1 and is not
silently converted to a prior December 31 balance.

Some later reports revise comparative income/cash-flow figures. The different
versions remain separately identifiable. Cross-report comparability is still
unreviewed, so these cells do not certify complete model inputs or an eligible
sample. No share counts are inferred from share capital.
