# Incremental Value of Multimodal Models and Early-Warning Limitations in Annual ST Risk Prediction: Evidence from Chinese Listed Companies

## Abstract

This study examines whether annual-report narratives and multimodal fusion improve the prediction of new ST/*ST implementations among Chinese listed companies. The analysis covers 969 firm-year observations from 155 Shenzhen-listed firms. Twelve financial ratios and management discussion and analysis from reports published before each May 1 prediction date are evaluated using an L2-regularized logistic regression benchmark and four neural specifications: financial-only, text-only, concatenation and cross-attention. Text features are learned from training reports using character TF-IDF and truncated singular value decomposition. Chronological evaluation and paired company-cluster resampling show mean test average precision of 0.3798 for the financial neural model, compared with 0.2177 for logistic regression, 0.3685 for concatenation and 0.3547 for cross-attention. The financial neural model outperforms the specified logistic benchmark in the paired comparison, whereas neither fusion comparison establishes a stable advantage from cross-attention. At validation-selected thresholds, the financial and fusion models each recover an average of 12.12% of test events. Source-level announcement review further distinguishes the prediction of regulatory implementation from warning about events not yet announced. The findings support evaluating additional modelling complexity through both incremental ranking performance and the operational consequences of alert thresholds.

JEL classification: C45, C53, G32, G33

Keywords: ST risk; financial distress prediction; logistic regression; annual reports; multimodal learning; early warning

## Introduction


Financial distress prediction asks whether information available at a specified date identifies firms that will encounter difficulty within a future horizon. Accounting information describes liabilities, earnings, liquidity and cash generation. Management narratives can describe operating conditions, uncertainty and expectations that are difficult to represent with ratios alone. Whether those narratives improve prediction is an empirical question. It requires a comparison using the same eligible observations, the same prediction dates and information that was available before each prediction.

Financial ratios are established inputs to failure prediction (Altman, 1968, p. 589; Beaver, 1966, p. 71; Ohlson, 1980, p. 109). Their interpretation nevertheless depends on the outcome, sampling rules and evaluation horizon. A model for bankruptcy need not perform similarly for a stock exchange's risk-warning designation. Likewise, a study restricted to reports that can be extracted and certified does not automatically describe all listed firms. We therefore distinguish the observed ST/*ST endpoint from the broader economic concept of financial distress throughout the analysis.

The present study first benchmarks the financial neural model against a fixed L2-regularized logistic regression, then asks two related questions. First, does the implemented annual-report text representation improve prediction beyond the same report's financial ratios? Second, does financial-query cross-attention outperform direct concatenation at an equal trainable parameter count? The first question concerns the practical value of adding this representation to the model family studied. The second concerns a fusion choice under a more controlled capacity comparison. Neither question assumes that additional complexity produces a benefit.

The design uses one recent annual report, an annual prediction origin and a subsequent 12-month regulatory outcome. It compares five model families on a version-locked set of 969 firm-years. The chronological test period comprises 2024–2025 origins; all preprocessing is fitted using training observations, and model checkpoints and thresholds use validation data. Company-cluster resampling retains repeated observations from the same firm. The contribution is an evaluation of incremental model value at a reproducible annual decision date, accompanied by alert-capacity and announcement-timing analyses. It connects the comparison of financial and textual models to the practical distinction between ranking regulatory risk and detecting an event before its definitive announcement.

## Literature Review

Classical accounting studies provide a foundation for the financial input set. Beaver (1966, pp. 71, 100) evaluates individual financial ratios, Altman (1968, p. 589) combines ratios through discriminant analysis, and Ohlson (1980, p. 109) develops a probabilistic specification. Zmijewski (1984, p. 59) addresses methodological issues associated with estimation and sampling. These contributions motivate the use of solvency, profitability and cash-flow measures without implying that a fixed indicator set or classification rule is universally optimal.

Temporal structure is also material. Shumway (2001, p. 101) models bankruptcy dynamically, while Campbell, Hilscher and Szilagyi (2008, Abstract, para. 1) study distress risk using accounting, market and firm information. Their settings differ from an annual regulatory designation. The relevant lesson for the present design is to state the prediction horizon and information set explicitly, and to avoid interpreting randomly separated records from repeated firms as evidence of prospective deployment.

Text research provides several routes to measuring corporate information. Loughran and McDonald (2011, p. 35) show why general-purpose negative-word dictionaries can misclassify financial language, while Kogan, Levin, Routledge, Sagi and Smith (2009, p. 272) study future stock-return volatility using financial-report text. Mai, Tian, Lee and Ma (2019, p. 743) and Matin, Hansen, Hansen and Mølgaard (2018, p. 1) investigate deep textual representations for bankruptcy or distress prediction. These studies motivate testing narrative information; their reported performance cannot be transferred to a different endpoint, language, sample or validation design.

More recent work also precludes a claim that prior multimodal research is limited to simple concatenation. Che, Wang, Jiang and Abedin (2024, accepted manuscript p. 1) study an attentive and regularized multimodal method. Hajek and Munk (2024, Abstract, para. 1) analyse risk-related annual-report language with contextual representations and a semi-supervised prediction approach. Jiang, Lyu, Yuan, Wang and Ding (2022, Abstract, para. 1) examine semantic features in current reports from unlisted Chinese public firms. These are useful conceptual comparators, but their reporting frequency, populations and text models differ from those used here.

Attention provides a way for a query to weight a sequence of representations (Vaswani et al., 2017, pp. 3–4). Its predictive value must be separated from the effect of supplying more information or more parameters. An improvement over text-only could arise from the financial inputs; it does not identify the contribution of attention. Conversely, a nonsignificant comparison with concatenation does not prove that every attention architecture is ineffective. A useful assessment specifies the exact representation, comparator and uncertainty rather than treating architecture names as explanations.


## Methodology


### Sample and prediction task

The prediction origin is May 1 at 00:00 Asia/Shanghai, using information published by the end of April 30. The annual report covers the preceding financial year; disclosure date determines availability. Inputs comprise the latest eligible annual report's financial statements and MD&A. The outcome equals one when a firm not under ST/*ST at the origin experiences a new implementation during the following 12 months. The follow-up interval is [May 1 Y, May 1 Y+1). Labels are reconstructed from the unfiltered Shenzhen Stock Exchange short-name change register and reconciled with official counts and listing/delisting records. A negative label requires complete interval coverage without a qualifying transition or earlier delisting; unresolved coverage is not converted into a negative. ST/*ST is a regulatory designation; the analysis concerns this observed endpoint rather than every form of economic financial distress.

The source inventory contains 3,335 candidate firm-years from 471 firms. Source and eligibility verification produces 969 observations from 155 firms, with 26 positive outcomes. The other 2,366 candidate records remain excluded or unresolved under the recorded source, membership, baseline-status, follow-up and input requirements. The revision adds the complete set of 126 origin-2023 records whose financial and text evidence had passed but whose industry classification required corroboration. Both positive and negative records follow the same admission rule.

Broad financial/nonfinancial eligibility is established using the latest verified pre-origin official classification together with the annual report's business and disposal disclosures. Detailed historical industry codes are not automatically carried forward. Serving financial clients, holding investments or having a minority financial segment does not by itself make an issuer a financial-sector firm. Annual ratios retain the report's consolidated scope. In one reviewed case, payment operations were deconsolidated before the origin but remained in part of the preceding year's flow measures; this exposure is recorded rather than replaced with estimated continuing-operation figures.

Training covers 2017–2021, validation 2022–2023 and testing 2024–2025. All five specifications use the same observations and temporal partitions. The source recovery and benchmark addition form a documented revision after inspection of the original test results; the original dataset and results remain archived.

[TABLE2]

Figure 1 shows the source inventory and common sample. Training labels are available before May 1, 2022, and validation labels before May 1, 2024. A fixed model and threshold are applied to both test years, without rolling retraining. Firms can recur across partitions: the test assesses later observations of the eligible population, not exclusively firms unseen during training.

[FIG1]

### Financial and textual inputs

Table 2 defines the twelve financial ratios. Asset and equity denominators are year-end balances. Financial source checks retain consolidated scope, units and current-year column identification.

[TABLE1]

Input certification checks filing identity and year, report timing and version, consolidated scope, units, current-year column headers, anchored statement rows and accounting identities. MD&A requires an unambiguous section boundary and at least 1,000 non-space characters. Up to three ratios may be missing after source review: a known zero denominator is missing, whereas an uncollected required row remains pending. For the 126 additions, 1,512 ratio values were recomputed and their source and label links checked. These structural checks are distinguished from a signed independent human audit.

Financial preprocessing is fitted on the training observations only. Ratios are winsorized using training 1st and 99th percentiles, missing values are replaced with training medians, and values are standardized using training moments. Twelve missingness indicators accompany the 12 transformed ratios. The identical 24-dimensional financial input is supplied to logistic regression and the financial components of the neural models.

MD&A is drawn from the same pre-origin annual report. Whitespace is removed and text is split into non-overlapping chunks of 256 characters. When more than sixteen are available, sixteen evenly spaced chunk positions span the disclosure. The procedure omits passages in long reports and is not full-document semantic comprehension. Training-only character unigram/bigram TF-IDF uses sublinear term frequency, a minimum document frequency of one training chunk and at most 20,000 features. Truncated SVD with random state 17 reduces the representation to 64 dimensions. Padding masks distinguish available chunks. All text-containing neural models share the fitted representation; no pretrained language model is used.

### Traditional benchmark and neural comparisons

The traditional benchmark is one financial-only logistic regression with L2 regularization, C=1, and the lbfgs solver. The maximum iteration count is 10,000. Positive observations receive the training negative-to-positive weight of 494/9, matching the class-weighting principle used by the neural loss. These settings are fixed before fitting the benchmark; no test-based regularization search is performed. The deterministic model is fitted once, rather than represented as three independent seed runs.

The neural comparisons comprise financial-only, text-only, concatenation and cross-attention. Financial and text projections have width 64. Concatenation combines the financial projection with mean-pooled text, while four-head cross-attention uses the financial representation to query the text chunks. The two fusion models each have 30,721 trainable parameters. Financial-only and text-only contain 5,825 and 8,385 trainable parameters, respectively. This controls the parameter budget in the fusion comparison.

The concatenation head has hidden width 192 and the cross-attention head width 64, producing the matched parameter count. Each classification head uses a rectified linear activation, dropout 0.1 and an output logit. Figure 2 shows the attention architecture. One financial query weights multiple text chunks; a single pooled key would instead have constant softmax weight one. Matching parameters does not equate expressiveness or optimization paths, and learned attention weights are not interpreted causally.

[FIG2]

The neural models use weighted binary cross-entropy, Adam with learning rate 0.001 and weight decay 0.0001, batches of 64, gradient clipping at 5, and a maximum of 100 epochs. Checkpoints maximize validation AP with patience 15. Seeds 17, 42 and 2026 are all reported. Enlarging validation can change the selected checkpoint as well as the threshold; the final analysis therefore evaluates the models on the revised common sample.

### Performance and announcement timing

Average precision is the primary ranking metric, calculated as precision weighted by recall increments rather than trapezoidal PR area. Neural results average the three single-run APs; probabilities are not averaged into an ensemble. Seed standard deviations are reported separately from company-resampling intervals. Each model's classification threshold maximizes validation F1 and is then applied to the test set. Precision, recall, confusion counts and annual alert budgets of 5%, 10% and 20% describe the consequences of score-based screening. Budget selections rank firms separately within each test year, use the ceiling of the budget times annual sample size, and break score ties by sample identifier. Threshold ties use the first validation-F1 maximum in the implementation. The budget analyses are descriptive and do not identify a cost-optimal operating policy.

Paired bootstrap resampling draws companies, retaining their test observations together, over 2,000 replicates. Neural performance is the mean AP across the three prespecified runs. Comparisons with logistic regression subtract the single fitted logistic AP from that neural mean under identical company resamples. The 2.5th and 97.5th bootstrap percentiles define the intervals; all 2,000 replicates contain both outcome classes. Intervals condition on observed companies and fitted scores, without refitting or incorporating data-collection uncertainty, and are not multiplicity-adjusted. Leave-one-positive validation checks remove each of the six validation events in turn and recompute thresholds without refitting the models.

For all 26 positive events, original company notices provide the definitive implementation-announcement date separately from the ST effective date. Five definitive notices were published before their prediction origin. The main endpoint retains these implementations; a supplementary evaluation removes the one documented preannounced test event while keeping fitted scores and thresholds unchanged. This separates a known implementation from advance warning without treating the sensitivity subset as a new independently trained cohort.


The anonymous supplement contains versioned selected-chunk inputs, candidate decisions, notice chronology, code, saved predictions and epoch logs. The decompressed input SHA-256 is fdcfe6bda4f1f05f36669ff70ccee1091078149dfdd78a295658910e1fa4e263; it identifies model inputs, not full original MD&A. All twelve neural runs and the single logistic fit were verified from saved predictions for validation and testing. Saved neural checkpoints and preprocessing replay the scores within 10⁻⁷; the logistic model also reproduces its scores on reload. Hardware and dependency changes can affect reruns, so archived predictions define the reported analysis.

## Results


### Sample and descriptive checks

The common sample contains 969 firm-years with 26 events. Table 1 reports the chronological partitions; individual firms can recur across years, so this is an unbalanced panel. The enlarged validation set contributes six events, while the test set retains eleven. These denominators apply to every model comparison.

Training-only descriptive statistics in Table 3 summarize the raw financial ratios before preprocessing. All twelve ratios are observed in each of the 503 training records. Ratios with small equity or revenue denominators can have extreme raw values; the medians and dispersion are therefore useful alongside means. Figure 3 uses this same complete training panel for every correlation cell. Its minimum eigenvalue is approximately 0.00708, consistent with a common-observation Pearson matrix. Neither display is used for test-driven feature selection.

[TABLE3]

[FIG3]

### Traditional baseline and multimodal comparisons

The financial neural model has the highest mean test AP among the evaluated specifications. Logistic regression converges in 42 iterations. The table reports one logistic fit and means over the three neural seeds.

[TABLE4]

The financial neural model's mean AP exceeds the specified logistic benchmark by 0.1622; its paired 95% interval is [0.0136, 0.4066]. This comparison supports better ranking by this financial neural specification than by the fixed linear benchmark in the observed sample. It does not establish superiority over every logistic specification or other conventional models.

The cross-attention-minus-financial AP difference is −0.0251, with a paired 95% interval of [−0.1087, 0.0276]. Against concatenation, the difference is −0.0137, with an interval of [−0.0645, 0.0262]. Thus the evidence does not establish incremental value from cross-attention relative to these financial and fusion benchmarks. It also does not establish equivalence. Table 5 reports paired differences directly; overlap between separate model intervals is not used as a test of their difference. The intervals are unadjusted, conditional comparisons. Conclusions about text apply to the implemented character TF-IDF/SVD representation.

[TABLE5]

The text-only mean AP is 0.0579, compared with test event prevalence of 0.0509. The cross-attention contrast against text-only is positive, but that comparison also introduces financial information. It therefore cannot establish that attention adds information beyond the financial model. Figure 4 plots every neural seed and the single logistic fit; no best-test run is selected for display.

[FIG4]

### Ranking and warning performance

The financial and fusion models each identify two test events in seed 17 and one in each of the other seeds, yielding mean recall of 12.12%. Logistic regression identifies two of eleven events and generates six alerts, corresponding to precision of one third. The text model achieves higher average recall by issuing more alerts, with mean classification precision of 5.92% at the selected thresholds. These results show why ranking performance and threshold-specific warning performance should be reported separately.

Leaving out one of the six validation events produces test-alert ranges of 1–3 for financial-only and concatenation, 1–4 for cross-attention, and 16–199 for text-only. Table 6 reports the common annual-budget comparisons. No operating point is selected retrospectively from its test performance.

### Implementation dates and advance warning

The source audit identifies three pre-origin definitive notices in training, one in validation and one in testing. All financial and fusion runs detect the preannounced test record. Excluding this record for descriptive evaluation leaves ten positive test events: each of these model families detects one in seed 17 and none in the other two seeds. Their classification successes consequently provide limited evidence of warning about events not already announced. On the same sensitivity set, logistic regression detects one of ten events with five alerts. The text model detects one, four and five events across the seeds, with 16, 72 and 84 alerts, respectively.


### Alert capacity and optimization records

At the 5% annual budget, the financial neural model captures four of eleven test events in every seed, with eleven alerts overall. The same budget gives two captured events for logistic regression and three for cross-attention. At 10%, the financial neural model captures four to five events and cross-attention captures four, with twenty-two alerts overall. At 20%, financial-only captures eight to ten events, compared with six for logistic regression and eight to nine for cross-attention, with forty-four alerts. Increasing review capacity recovers additional events while increasing false alerts; the budget results do not establish an optimal capacity.

[TABLE6]

Figure 5 shows the actual weighted training loss and validation AP histories for all twelve neural runs. Checkpoint selection uses validation AP, so the selected epoch need not minimize training loss. Validation loss was not recorded and is not reconstructed. The logistic solver converges in 42 iterations; its deterministic fit does not have a comparable neural epoch history. Supplementary Table S1 records every test confusion matrix, selected threshold and neural checkpoint epoch, keeping optimization records separate from the evidence on out-of-time performance.

[FIG5]

## Discussion


The traditional benchmark gives the multimodal comparison a useful financial interpretation. The tested financial neural model captures a stronger risk ranking than the specified regularized linear model, while adding the implemented narrative representation and cross-attention does not establish a further gain. Model selection should therefore distinguish the value of financial modelling from the separate value of additional data modalities and fusion complexity.

A distinction between text information and its measurement is essential. Character n-grams and dimension reduction provide a reproducible, inexpensive representation, but their performance cannot determine whether every narrative passage is useful. A relevant disclosure may appear in a chunk that was not selected or require context that these features do not retain. Alternatively, a passage may restate conditions already expressed in the ratios. The present comparison identifies the performance of the implemented procedures; it does not identify which of these mechanisms explains the absence of an established fusion gain.

The operating results also matter for financial users. A model that ranks risk reasonably well may recover few events at a validation-selected threshold. Conversely, a model can increase recall while producing many false alerts. Credit screening, investor monitoring and supervisory review should therefore relate performance to an explicit alert capacity and report the associated missed events and false positives. Without observed intervention costs and benefits, these experiments cannot specify an economically optimal policy.

The announcement audit clarifies the information being predicted. ST implementation after a definitive public notice can be relevant for monitoring, but it is distinct from discovering an unannounced risk. Reporting both dates makes this distinction visible and allows the practical claim to match the empirical endpoint.

The sample contains six validation and eleven test events and reflects verifiable public-source availability. These features determine the precision and scope of the estimates. The revised analysis is exploratory because the original test results were already observed. The findings concern annual ST implementation, the specified financial inputs and the implemented text representation; they should not be generalized to all financial distress endpoints or language models.


For researchers, the corresponding design priority is a larger independently evaluated event cohort with complete disclosure chronology, followed by tests of alternative representations under the same eligibility rules. For users of risk dashboards, the immediate lesson is to show the number of alerts and missed events next to a ranking metric. A high-ranking score can support prioritization, but its decision value depends on the chosen workload and whether the event was already publicly known. Model complexity should be justified by that incremental evidence.

## Conclusions


In a common sample of 969 firm-years from 155 Chinese listed firms, a financial neural model improves test risk ranking relative to the specified L2 logistic benchmark, while cross-attention does not demonstrate a stable incremental advantage over the financial or concatenation models. Threshold-specific performance and announcement timing qualify how that ranking can be used for early warning. The study supports evaluating multimodal risk models through a transparent traditional baseline, matched comparisons and explicitly dated regulatory outcomes.

## References

Altman, E. I. (1968). Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy. The Journal of Finance, 23(4), 589–609. https://doi.org/10.1111/j.1540-6261.1968.tb00843.x

Beaver, W. H. (1966). Financial Ratios as Predictors of Failure. Journal of Accounting Research, 4, 71–111. https://doi.org/10.2307/2490171

Campbell, J. Y., Hilscher, J., & Szilagyi, J. (2008). In Search of Distress Risk [Abstract]. The Journal of Finance, 63(6), 2899–2939. https://doi.org/10.1111/j.1540-6261.2008.01416.x

Che, W., Wang, Z., Jiang, C., & Abedin, M. Z. (2024). Predicting Financial Distress Using Multimodal Data: An Attentive and Regularized Deep Learning Method. Information Processing & Management, 61(4), 103703. https://doi.org/10.1016/j.ipm.2024.103703

Hajek, P., & Munk, M. (2024). Corporate Financial Distress Prediction Using the Risk-Related Information Content of Annual Reports [Abstract]. Information Processing & Management, 61(5), 103820. https://doi.org/10.1016/j.ipm.2024.103820

Jiang, C., Lyu, X., Yuan, Y., Wang, Z., & Ding, Y. (2022). Mining Semantic Features in Current Reports for Financial Distress Prediction: Empirical Evidence from Unlisted Public Firms in China [Abstract]. International Journal of Forecasting, 38(3), 1086–1099. https://doi.org/10.1016/j.ijforecast.2021.06.011

Kogan, S., Levin, D., Routledge, B. R., Sagi, J. S., & Smith, N. A. (2009). Predicting Risk from Financial Reports with Regression. In Proceedings of Human Language Technologies: The 2009 Annual Conference of the North American Chapter of the ACL (pp. 272–280). Association for Computational Linguistics. https://aclanthology.org/N09-1031/

Loughran, T., & McDonald, B. (2011). When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks. The Journal of Finance, 66(1), 35–65. https://doi.org/10.1111/j.1540-6261.2010.01625.x

Mai, F., Tian, S., Lee, C., & Ma, L. (2019). Deep Learning Models for Bankruptcy Prediction Using Textual Disclosures. European Journal of Operational Research, 274(2), 743–758. https://doi.org/10.1016/j.ejor.2018.10.024

Matin, R., Hansen, C., Hansen, C., & Mølgaard, P. (2018). Predicting Distresses Using Deep Learning of Text Segments in Annual Reports [Preprint]. arXiv:1811.05270. https://arxiv.org/abs/1811.05270

Ohlson, J. A. (1980). Financial Ratios and the Probabilistic Prediction of Bankruptcy. Journal of Accounting Research, 18(1), 109–131. https://doi.org/10.2307/2490395

Shumway, T. (2001). Forecasting Bankruptcy More Accurately: A Simple Hazard Model. The Journal of Business, 74(1), 101–124. https://doi.org/10.1086/209665

Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, Ł., & Polosukhin, I. (2017). Attention Is All You Need. In Advances in Neural Information Processing Systems 30 (pp. 5998–6008). Curran Associates. https://proceedings.neurips.cc/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html

Zmijewski, M. E. (1984). Methodological Issues Related to the Estimation of Financial Distress Prediction Models. Journal of Accounting Research, 22, 59–82. https://doi.org/10.2307/2490859


## Appendix A Abbreviations and notation

Table A1: Abbreviations and notation

| Abbreviation / symbol | Full form or meaning |
|---|---|
| ACL | Association for Computational Linguistics |
| Adam | Adaptive moment estimation; neural optimizer |
| AP | Average precision; recall-weighted precision |
| AR/A | Accounts receivable / assets |
| AUC | Area under the curve; here, the ROC curve |
| BCE | Binary cross-entropy; training loss |
| C | Inverse regularization strength in logistic regression |
| CI | Confidence interval |
| CR | Current ratio; current assets / current liabilities |
| F1 | Harmonic mean of precision and recall |
| FN | False negatives; missed events |
| FP | False positives; false alerts |
| INV/A | Inventory / assets |
| JEL | Journal of Economic Literature classification |
| L/A | Liabilities / assets |
| L2 | Squared-coefficient regularization penalty |
| lbfgs | Limited-memory Broyden–Fletcher–Goldfarb–Shanno solver |
| MD&A | Management discussion and analysis |
| ME/R | Management expenses / revenue |
| n | Number of observations |
| NM | Net margin; consolidated net profit / revenue |
| NP/A | Consolidated net profit / year-end assets |
| NP/E | Consolidated net profit / year-end equity |
| OCF/A | Operating cash flow / assets |
| OCF/CL | Operating cash flow / current liabilities |
| OM | Operating margin; operating profit / revenue |
| PR | Precision–recall |
| QR | Quick ratio; (current assets − inventory) / current liabilities |
| ROC | Receiver operating characteristic |
| SD | Standard deviation |
| SHA-256 | Secure Hash Algorithm; 256-bit file fingerprint |
| ST | Special treatment; other risk warning |
| *ST | Special treatment indicating delisting risk |
| SVD | Singular value decomposition |
| TF-IDF | Term frequency–inverse document frequency |
| TN | True negatives; correctly classified non-events |
| TP | True positives; correctly identified events |
| Y | Calendar year of the May 1 prediction origin |

Source: Terms used in the text, figures and tables, including Supplementary Table S1. Ratio denominators follow Table 2.
