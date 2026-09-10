# Annual ST empirical reanalysis

Frozen sample: **843 company-years, 154 firms**, 22 positive and 821 negative outcomes.

| Split | Rows | Firms | Positive | Negative | Positive firms |
|---|---:|---:|---:|---:|---:|
| train | 503 | 143 | 9 | 494 | 9 |
| validation | 124 | 124 | 2 | 122 | 2 |
| test | 216 | 127 | 11 | 205 | 11 |

All methods use the same frozen sample. Preprocessing, checkpoint selection and thresholds use training/validation data only. Concatenation and cross-attention have equal trainable parameter budgets.

| Model | AP mean ± seed SD | AP cluster 95% CI | ROC AUC mean | F1 mean |
|---|---:|---|---:|---:|
| financial_only | 0.3642 ± 0.0191 | [0.1517, 0.6467] | 0.8859 | 0.1941 |
| text_only | 0.0536 ± 0.0067 | [0.0285, 0.1210] | 0.4743 | 0.0445 |
| concat | 0.3638 ± 0.0071 | [0.1441, 0.6326] | 0.8888 | 0.1581 |
| cross_attention | 0.3641 ± 0.0104 | [0.1362, 0.6341] | 0.8820 | 0.1624 |

Paired company-cluster intervals for cross-attention minus each baseline (average precision, averaged over prespecified runs):

- financial_only: [-0.0868, 0.0538]; interval includes zero; improvement not established.
- text_only: [0.0788, 0.5836]; interval above zero in this sample.
- concat: [-0.0361, 0.0289]; interval includes zero; improvement not established.

Metric audit: all 12 model/seed outputs reproduce from the saved raw predictions, including test sample IDs, labels, confusion matrices and metrics.

Limitations: the dataset is a source-availability subset, with exclusions for unresolved inputs and historical industry. Positive-event counts and interval widths limit inference. Automatic source checks are not full manual audits. The target is new registered ST/*ST, not every form of financial distress. The simplified design does not test a gating mechanism. These results do not validate the original manuscript’s numerical claims or its three theoretical propositions.

No positive conclusion should be inferred merely because training completed. The cross-attention versus concatenation comparison addresses fusion choice at matched parameter count; the other contrasts and multiple pairwise intervals should be interpreted cautiously.

Dataset SHA-256: `105a29b64a0f485dcd33a92711e015cc5e0f29cca0e31ee3d819f03dca6bea6c`.
