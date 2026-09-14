# Figure source files

Run `python build_figures.py --root . --output manuscript/figures` after installing requirements.txt. This uses the existing results/, baseline/ and evidence/ files, with no duplicated source dataset and no model refitting. Five figures are exported as 300 dpi PNG, editable SVG with text objects, and vector PDF. The script retains all 13 empirical test curves and all 12 recorded training histories without smoothing. Figure 3 shows the lower triangle of the signed Pearson correlation matrix; lighter to darker shading represents −1 to +1. Figure 4 uses five model rows and two metric columns (PR/ROC), common axes, muted model colours and solid/dashed/dotted lines for neural seeds 17/42/2026. All twelve neural runs and one deterministic logistic fit remain visible. Row labels and seed line patterns also support monochrome printing. Figure 5 line patterns identify seeds.

`manuscript/figures/figure_build_audit.json` records input/output SHA-256 values. `manuscript/curve_verification.json` verifies AP and ROC AUC from plotted points. Original predictions, training logs and research conclusions are unchanged. `python build_tables.py` regenerates table exports separately (requires requirements-figures.txt).

The model-panel revision is documented in manuscript/panel_update_audit.json. Its curve-data CSV is byte-identical to the preceding version.
