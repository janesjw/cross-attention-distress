# Official ST-register review

`verify_exchange_register.py` reconstructs the active study's registered ST
endpoint from the unfiltered SZSE short-name change export and official listing
and delisting tables. Original XLSX files and API controls are retained in
`data/raw/szse_register_20260910.zip`, with URLs, byte counts and SHA-256 hashes.

The XLSX contains 7,478 records. The API independently reports 7,478 records and
374 pages. All 58 records on the first, middle and last pages match the export
after decoding HTML nonbreaking spaces. The script rejects duplicate rows,
source hash changes, nonempty filter defaults, count mismatches and inconsistent
API controls. It checks complete normalized names, not just whether each name
contains ST. All 471 selected companies have one listing identity, a consistent
name chain and a terminal name matching the current listing/delisting export.
Their complete name histories also agree with the prior snapshot.

The operational assumption is that the official unfiltered register contains
all ST/*ST name transitions. These checks establish that the downloaded export
is complete as reported by the exchange. They cannot prove that the underlying
register itself has no errors or omitted transitions. This limitation belongs
in the manuscript. The outcome is the registered ST endpoint, not every form of
financial distress. Later retrieval is used to ascertain historical endpoints,
not to replace the annual financial/text inputs available at each prediction date.

Before historical-industry and annual-input exclusions, the 3,335 candidate
origins have 3,214 reconstructed outcomes (71 positive, 3,143 negative), 113
baseline-ST exclusions and eight right-censored windows. A positive event before
delisting remains observed; a delisting without ST before the follow-up end is
not silently negative. The origin and end boundaries are tested explicitly.

The batch writes source and company evidence, `labels.csv`, and a summary under
`data/verification/annual_st/`. The annual-study inventory joins these records,
checks window identity, applies historical-industry exclusions and retains
specific missing requirements. Twelve previously verified financial ratios and
a hash-verified pre-origin text section can certify an input record. Machine-only
statement rows and automatically found MD&A boundaries do not pass this gate.
An eligible record still does not freeze the cohort or authorize the retired
MMAN training job. All labels and inputs are preserved for later frozen export.

The pipeline registers these results before downloading another batch, then
rebuilds the annual inventory after statement extraction. This makes completed
ST work available even while financial source collection continues.
