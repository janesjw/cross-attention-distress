# Automation

`Research data pipeline` runs every six hours and can also be started from Actions → Run workflow. Each run attempts up to 25 reports with a 25-minute processing budget. It limits the saved filing index to `configs/collection_cohort.json`, then skips intact completed extractions, and retries failed reports on up to three runs.

`data/automation/status.json` records progress and training blockers. Compressed page text, financial-table candidates, source hashes and page references are committed under `data/automation/`. Source PDFs are retained as Actions artifacts for 30 days; their public URLs and hashes remain in the extraction records. Re-downloads must match those hashes.

Extraction candidates require review of statement scope, units, periods, MD&A boundaries and historical event coverage before entering the analytical database. A completed extraction is not an eligible sample. The workflow does not infer unknown outcomes, promote candidates to verified facts, or remove protocol requirements.

Training is conditional on eligible samples, verified text, resolved protocol requirements and a registered frozen manifest at `data/derived/frozen_dataset.json`. The existing training loader then checks manifest hashes, labels and timelines before fitting. The initial training job uses CPU, seed 42 and a five-hour limit. Full multi-seed GPU training and interrupted-training resume are not yet configured. Training artifacts expire after 30 days and must be preserved before expiry.

Completed extraction progress survives subsequent runs. Three failed attempts require investigation and a deliberate reset of the affected progress entry. Unexpected job failures appear in Actions. Review `status.json` for scientific blockers even when the workflow succeeds. GitHub scheduling and account execution limits still apply.

The finite cohort is selected before outcome review, using fixed seed 42 and proportional industry-snapshot strata. Its approximate 5,142 firm-year target applies before final eligibility checks. Do not replace excluded records to meet an exact count. Historical industry and membership review still applies. `analysis/select_cohort.py` reproduces selection and refuses to overwrite an existing cohort.
