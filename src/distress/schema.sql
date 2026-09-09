PRAGMA foreign_keys=ON;
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE firms(
 firm_id TEXT PRIMARY KEY, name TEXT NOT NULL, exchange TEXT NOT NULL,
 cninfo_org_id TEXT, listing_date TEXT, listing_source TEXT, listing_page INTEGER,
 universe_status TEXT NOT NULL DEFAULT 'coverage_pending'
);
CREATE TABLE documents(
 document_id TEXT PRIMARY KEY, firm_id TEXT NOT NULL REFERENCES firms,
 title TEXT NOT NULL, disclosed_date TEXT NOT NULL, url TEXT UNIQUE NOT NULL,
 sha256 TEXT NOT NULL CHECK(length(sha256)=64), bytes INTEGER NOT NULL, pages INTEGER NOT NULL,
 version_kind TEXT NOT NULL, cache_path TEXT NOT NULL,
 time_precision TEXT NOT NULL DEFAULT 'date', verification TEXT NOT NULL
);
CREATE INDEX document_asof ON documents(firm_id,disclosed_date);
CREATE TABLE facts(
 fact_id TEXT PRIMARY KEY, firm_id TEXT NOT NULL REFERENCES firms,
 document_id TEXT NOT NULL REFERENCES documents, page INTEGER NOT NULL CHECK(page>0),
 metric TEXT NOT NULL, period_end TEXT NOT NULL,
 basis TEXT NOT NULL CHECK(basis IN ('YTD','END','QUARTER','ANNUAL_RATE')),
 scope TEXT NOT NULL CHECK(scope IN ('consolidated','parent_attributable','total_shares')),
 raw_value TEXT NOT NULL, multiplier TEXT NOT NULL, sign_adjustment INTEGER NOT NULL CHECK(sign_adjustment IN(-1,1)), value_normalized TEXT NOT NULL,
 source_unit TEXT NOT NULL, verification TEXT NOT NULL, comparability_group TEXT NOT NULL DEFAULT 'unreviewed', note TEXT NOT NULL DEFAULT '',
 UNIQUE(document_id,metric,period_end,basis,scope)
);
CREATE INDEX fact_lookup ON facts(firm_id,metric,period_end,basis,scope);
CREATE TABLE derived_values(
 derived_id TEXT PRIMARY KEY, firm_id TEXT NOT NULL REFERENCES firms,
 metric TEXT NOT NULL, period_end TEXT NOT NULL, asof_date TEXT NOT NULL,
 value TEXT, available_date TEXT NOT NULL, formula TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE lineage(
 derived_id TEXT NOT NULL REFERENCES derived_values, fact_id TEXT NOT NULL REFERENCES facts,
 PRIMARY KEY(derived_id,fact_id)
);
CREATE TABLE events(
 event_id TEXT PRIMARY KEY, firm_id TEXT NOT NULL REFERENCES firms,
 event_type TEXT NOT NULL, public_date TEXT NOT NULL, effective_date TEXT,
 document_id TEXT NOT NULL REFERENCES documents, page INTEGER NOT NULL,
 confirmed INTEGER NOT NULL CHECK(confirmed IN (0,1)), detail TEXT NOT NULL
);
CREATE TABLE audit_opinions(
 document_id TEXT PRIMARY KEY REFERENCES documents, fiscal_year INTEGER NOT NULL,
 audit_scope TEXT NOT NULL CHECK(audit_scope IN ('financial_statements','internal_control')),
 opinion TEXT NOT NULL CHECK(opinion IN ('standard_unqualified','unqualified_with_explanatory_paragraph','qualified','adverse','disclaimer','unresolved')),
 page INTEGER NOT NULL, detail TEXT NOT NULL
);
CREATE TABLE sample_register(
 sample_id TEXT PRIMARY KEY, firm_id TEXT NOT NULL REFERENCES firms,
 origin TEXT NOT NULL, followup_end_exclusive TEXT NOT NULL,
 baseline_st INTEGER CHECK(baseline_st IN(0,1)),
 baseline_quarter INTEGER CHECK(baseline_quarter IN(0,1)),
 baseline_audit INTEGER CHECK(baseline_audit IN(0,1)),
 baseline_status TEXT NOT NULL CHECK(baseline_status IN('excluded','unresolved','clear')),
 feature_status TEXT NOT NULL, outcome INTEGER CHECK(outcome IN(0,1)), label_available_date TEXT,
 outcome_status TEXT NOT NULL, analytical_eligible INTEGER NOT NULL CHECK(analytical_eligible IN(0,1)),
 note TEXT NOT NULL,
 CHECK(baseline_status='clear' OR outcome IS NULL),
 CHECK(analytical_eligible=0 OR (baseline_status='clear' AND outcome IS NOT NULL)),
 UNIQUE(firm_id,origin)
);
CREATE TABLE sample_evidence(
 sample_id TEXT NOT NULL REFERENCES sample_register,
 stage TEXT NOT NULL, criterion TEXT NOT NULL, status TEXT NOT NULL,
 document_id TEXT REFERENCES documents, derived_id TEXT REFERENCES derived_values,
 note TEXT NOT NULL
);
CREATE TABLE coverage(
 sample_id TEXT NOT NULL REFERENCES sample_register, criterion TEXT NOT NULL,
 window_start TEXT NOT NULL, window_end_exclusive TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN('verified_absent','verified_present','unresolved')),
 evidence_note TEXT NOT NULL, PRIMARY KEY(sample_id,criterion)
);
CREATE TABLE text_sections(
 section_id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents,
 section_name TEXT NOT NULL, page_start INTEGER NOT NULL, page_end INTEGER NOT NULL,
 text_sha256 TEXT NOT NULL, text_path TEXT NOT NULL, verification TEXT NOT NULL
);
CREATE TABLE dataset_versions(
 version_id TEXT PRIMARY KEY, manifest_sha256 TEXT NOT NULL,
 protocol_sha256 TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE training_runs(
 run_id TEXT PRIMARY KEY, dataset_version TEXT NOT NULL REFERENCES dataset_versions,
 seed INTEGER NOT NULL, model_config_json TEXT NOT NULL, environment_json TEXT NOT NULL,
 purpose TEXT NOT NULL CHECK(purpose IN('synthetic_software_test','research')),
 checkpoint_sha256 TEXT, status TEXT NOT NULL
);
CREATE TABLE predictions(
 run_id TEXT NOT NULL REFERENCES training_runs,
 sample_id TEXT NOT NULL REFERENCES sample_register,
 split TEXT NOT NULL, probability REAL NOT NULL CHECK(probability>=0 AND probability<=1),
 label INTEGER NOT NULL CHECK(label IN(0,1)), PRIMARY KEY(run_id,sample_id)
);
