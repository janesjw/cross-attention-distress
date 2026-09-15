# Incremental Value of Multimodal Models and Early-Warning Limitations in Annual ST Risk Prediction

Data, fitted models, source records and reproduction code for annual ST risk prediction.

## Complete data release

**[Download the complete dataset and code](https://github.com/janesjw/cross-attention-distress/releases/download/annual-st-v2-20260915/Supplementary_Data.zip)** · [Version annual-st-v2-20260915](https://github.com/janesjw/cross-attention-distress/releases/tag/annual-st-v2-20260915)

The release asset `Supplementary_Data.zip` contains all 73 files for the reported analyses: model inputs, twelve fitted neural checkpoints, preprocessing and fixed logistic objects, predictions, the eight-value logistic and 16-candidate boosted-tree searches, sensitivity analyses, source records, five PNG/SVG figure pairs and reproduction scripts. The archive README describes each folder and the required software versions. The archive contains no manuscript, Title Page or submission instructions.

Archive SHA-256: `2b4a3673bc5eb7696526fec137c742dbb12732ddf81930c1e88fd79897d32531`. `data_release.json` records the archive size, version, dataset fingerprint and individual file checksums. Original annual reports remain with their providers; the release contains derived inputs and bounded MD&A extracts with source links. Third-party rights remain applicable.

## Study and results

Annual-ST-SZ-v2 includes **969 firm-years, 155 firms and 26 implementation events**. Training, validation and test contain 503/9, 250/6 and 216/11 observations/events. Twelve annual financial ratios and training-fitted character TF-IDF/SVD text representations are used. Sample assembly and baseline specifications were finalized after preliminary test inspection; all comparisons are exploratory.

Test average precision is 0.3798 for the financial neural model, 0.3674 for validation-tuned logistic regression, 0.2009 for tuned boosted trees, 0.3685 for concatenation and 0.3547 for cross-attention. The financial-neural minus tuned-logistic paired 95% interval is [-0.0338, 0.0796]. The results do not establish an advantage over tuned logistic regression or an incremental cross-attention benefit. Removing the definitively preannounced test event exposes limited warning performance; full results and uncertainty are provided in the release.

## Verification and reproduction

Extract the release archive, enter `Supplementary_Data`, and run:

```sh
python scripts/verify_saved_outputs.py
```

This standard-library check verifies the 969 model inputs, 30 validation/test score sets, 24 additional candidate-validation sets and six event-omission checks. To refit baselines or regenerate analyses, install the archive's `requirements.txt` and follow its README. The archive includes the fitted neural checkpoints, so verification does not require neural retraining.

## Repository versions

The complete current analysis is the versioned release linked above. Existing root-level data, scripts and figures preserve the earlier compact analysis, including the fixed-C logistic comparator; they are not a substitute for the full release's tuned comparisons. Existing historical paper files are not the current submission documents. No new manuscript or Title Page is included in this data update.

The tracked working tree remains below 10,000,000 bytes. Larger fitted-model and provenance files are supplied through GitHub Releases. Git history and earlier evidence are preserved without rewriting commits. The existing `python verify.py` verifies the compact tracked files; use the release verifier for the complete current analysis.
