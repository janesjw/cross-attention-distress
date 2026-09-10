# MMAN revision evidence

The gating-only variant previously entered the single-modality branch because its name ends in `_only`. It returned the annual vector; the gate, short-term vector and text vector did not participate in the output. The explicit single-modality allowlist corrects this. A regression test checks nonzero gradients in all three modality projections and the gate.

`original_mean` averages the three original vectors without attention. It completes the attention-by-gating comparison. `numerical_cross_attention` retains the annual-query/quarterly-key interaction and gates the two original financial vectors and their interaction. It avoids removing this financial path when removing text. The old `numerical_only` variant is retained as a numerical gating baseline.

Validation: 13 model tests passed on CPU with a tiny randomly initialized test encoder. Tests cover forward/backward computation, padding, query sensitivity, sample-dependent gates, no-text attention, checkpoint round trips and reproducibility. These are synthetic software checks, not company-data experiments. No research training, confidence interval or significance result was produced.

The experiment specification is `configs/ablation_protocol.json`. Execution remains blocked by the frozen-data admission check. The mathematical revisions limit the cost claim to explicit token lengths, distinguish gate-conditional bounds from end-to-end robustness, and distinguish focal loss weights from logit-gradient weights. H1, H2 and H3 remain empirically unverified.

The original manuscript's eight accuracies were independently checked again: none is an integer correct count divided by 833 rounded to four decimal places. This statement assumes single-run unweighted accuracy. Original predictions, the feature panel and epoch histories are still unavailable, so the reported curves and metrics cannot be reconstructed from their printed values.

Do not change the README sample totals, filing summary or create a frozen dataset manifest based on this code repair.
