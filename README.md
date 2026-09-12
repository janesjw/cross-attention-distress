# Annual ST risk: compact paper reproduction package

This package preserves all 843 frozen company-years (154 firms, 22 positives), all 12 saved prediction runs and their actual model inputs. Total tracked file payload is below 10,000,000 bytes, without compression. It is a compact representation of annual-st-sz-v1, not a newly selected sample.

Train: 503 rows / 9 positives. Validation: 124 / 2. Test: 216 / 11. Seeds: 17, 42, 2026. Four models. Company-cluster bootstrap: 2,000 replicates.

Test AP: financial_only 0.3642; text_only 0.0536; concat 0.3638; cross_attention 0.3641. Paired AP 95% CI for cross_attention minus concat is [-0.0361, 0.0289]; minus financial_only is [-0.0868, 0.0538]. These results do not establish a stable attention gain or equivalence.

## What was reduced

The source dataset stores complete MD&A (62,862,819 bytes). Original training deterministically removes whitespace, splits text into 256-character pieces and selects at most 16 evenly spaced pieces. `data/model_inputs.jsonl` stores exactly those selected pieces, together with every original non-text field. Ordered chunk equality and non-text field equality were verified for all 843 rows against the frozen original. The unchanged original training code fits TF-IDF on these selected training chunks; no omitted full-text material enters that fit.

The loader rejoins the selected pieces so the unchanged original chunk function returns precisely the same ordered sequence. This preserves token counts, boundaries and training vocabulary inputs. Numeric training was not rerun merely to reduce file size. This package omits raw extraction archives, complete MD&A, legacy SQLite databases, automated collection caches and model checkpoints. It supports model-input reproduction and independent verification of saved metrics; it does not independently reproduce raw document extraction. Training creates checkpoints under an ignored output directory.

## Provenance

Full original evidence remains at [source commit e92becd6](https://github.com/janesjw/cross-attention-distress/tree/e92becd6ff0f4b2078d29985767cb1f6afced1e2). The original manifest is preserved byte-for-byte in `evidence/frozen_manifest.json`. Its historical `protocol.status: not_frozen` is embedded pre-freeze protocol text; the enclosing manifest has `frozen: true`. Do not overwrite it.

Original full-data SHA-256: `105a29b64a0f485dcd33a92711e015cc5e0f29cca0e31ee3d819f03dca6bea6c`.
Compact-data SHA-256: `8042ecb6d52f506571b659fd02f0e2b367c57008973bbbb1127f5036dcf0b795`.
These are different byte representations. `text_sha256` identifies the FULL original text, not joined selected chunks. The original manifest's paths describe the archived source tree and need not exist in this compact package. `file_manifest.json` covers files in this package. Neither hash is a Git blob identifier.

## Verify and optionally reproduce

Run `python verify.py` using Python 3.12 (standard library only). This checks file integrity, sample keys/counts and all 12 runs' validation and test metrics, including thresholds and confusion matrices.

For optional full training, install `requirements.txt`, then run `PYTHONPATH=src python -m distress.annual_train --root . --output rerun`. Original runtime: Python 3.12.14, NumPy 2.3.5, scikit-learn 1.8.0, PyTorch 2.8.0+cpu. Use the corresponding CPU wheel when matching that environment. No new training was performed during compacting. Bootstrap intervals are retained from the frozen experiment; the optional training entry also recomputes them. This package has no automatic collection schedule.

Financial ratios retain year-end denominators. The text representation is character TF-IDF + SVD, not FinBERT. ST/*ST is a regulatory risk endpoint, not all financial distress. Only two validation positives make threshold selection unstable. Source availability limits generalization.

The under-10-MB limit concerns current package files. Keeping an archive commit preserves Git history and does not make a full historical clone smaller.
