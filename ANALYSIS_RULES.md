# Analysis rules for manuscript revision

Recorded before traditional-baseline fitting and final-cohort rerun, 2026-09-12. Title: Incremental Value of Multimodal Models and Early-Warning Limitations in Annual ST Risk Prediction: Evidence from Chinese Listed Companies.

## Cohort and source scope

Retain the annual effective-date endpoint: baseline non-ST at May 1, followed for a new ST/*ST implementation within the next 12 months. Publication of a definite notice is recorded separately from the effective date. The primary task predicts regulatory implementation risk, not necessarily an unknown event. Do not remove positive records merely because their risk was publicly discussed.

Use the prior verified official nonfinancial classification corroborated by the latest pre-origin annual report's business and disposal disclosures. Certify broad sector eligibility separately from a detailed code. Financial clients, minority financial segments and investment activities are not automatic financial-sector exclusions. Annual consolidated financial ratios retain the report's actual consolidation scope; do not invent continuing-operation figures. Material business disposal is an interpretation flag, not an outcome-dependent exclusion.

Under this uniform rule, 002316.SZ:2023 is retained: the pre-origin annual report documents payment-business disposal and deconsolidation from December 2022, with retained network businesses. Keep its substantial disposed-payment exposure in the 2022 flow ratios explicitly flagged. This resolves the earlier temporary hold without changing any ratio. The cohort is parent v1 plus all 126 industry-resolved records (969/26; validation250/6). Other inventory records still fail one or more existing source or eligibility requirements; they are not added selectively. Broader population representativeness is not claimed.

## Announcement timing

For all 26 events, preserve original company notices and distinguish definitive implementation-announcement date from effective date. Report the five already identified pre-origin definitive notices. The descriptive evaluation removing the one known preannounced test event keeps scores/thresholds unchanged and is not a refitted unknown-event cohort. It cannot establish absence of every earlier warning in retained firms. No new claim of comprehensive risk-signal screening is made.

## Traditional benchmark

One deterministic financial-only L2 logistic regression, C=1, lbfgs, max_iter=10000. Same train-only winsorization, median imputation, standardization and missingness indicators as neural financial inputs (24 transformed predictors from 12 ratios). Class weights use training negative/positive ratio, matching the neural loss weighting. No C grid search or test tuning; fit once on the 503 training records. Choose threshold by the same validation-F1 rule on all250 validation records. Compare one fitted logistic benchmark with the mean of the three prespecified neural seeds using paired company-bootstrap AP intervals (2000 replicates). Do not duplicate the deterministic benchmark into three pseudo-independent runs.

All five model families use identical969 records and temporal splits. The four neural architectures retain the original implementation and seed protocol. Enlarged validation changes checkpoint selection and thresholds. Preserve all candidate968 and original843 evidence under their original paths. This analysis is an exploratory revision after original test inspection; do not describe it as independent confirmation. Report selection, uncertainty and sample coverage once where relevant rather than repeatedly foregrounding limitations.
