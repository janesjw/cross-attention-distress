"""Audit the finite cohort without freezing it or inferring missing outcomes.

Run from any directory: python analysis/audit_sample_readiness.py
The two outputs are evidence inventories, not a frozen dataset manifest.
"""
import csv
import gzip
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = [
    'configs/collection_cohort.json', 'configs/protocol.json',
    'data/derived/cohort_screening.csv',
    'data/derived/cohort_screening_summary.json',
    'data/derived/distress.sqlite', 'data/derived/historical_industry.json',
    'data/derived/st_cover_evidence.json',
    'data/derived/industry_source_status.json',
    'data/derived/filing_summary.json',
]


def read_json(path):
    return json.loads((ROOT / path).read_text())


def audit():
    cohort = read_json(INPUTS[0])
    protocol = read_json(INPUTS[1])
    with (ROOT / INPUTS[2]).open(newline='') as stream:
        screens = list(csv.DictReader(stream))
    expected = {f['firm_id'] + ':' + o[:4] for f in cohort['firms'] for o in f['origins']}
    ids = [r['sample_id'] for r in screens]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError('Screening rows do not match the selected cohort exactly')
    if len(expected) != cohort['selected_candidate_firm_years']:
        raise ValueError('Collection cohort count mismatch')
    sources = {s['origin_year']: s for s in read_json(INPUTS[7])}
    industry = {(r['firm_id'], r['origin_year']): r for r in read_json(INPUTS[5])}
    covers = read_json(INPUTS[6])
    errors = []
    with sqlite3.connect(f'file:{ROOT / INPUTS[4]}?mode=ro', uri=True) as con:
        con.row_factory = sqlite3.Row
        if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Database integrity check failed')
        candidates = {r['candidate_id']: dict(r) for r in con.execute('SELECT * FROM candidate_register')}
        registered = {r['sample_id']: dict(r) for r in con.execute('SELECT * FROM sample_register')}
        verified_facts = Counter(r[0] for r in con.execute("SELECT firm_id FROM facts WHERE verification='verified'"))
        text_firms = {r[0] for r in con.execute("SELECT d.firm_id FROM text_sections t JOIN documents d USING(document_id) WHERE t.verification='verified'")}
    rows = []
    for s in screens:
        sid = s['sample_id']; firm = s['firm_id']; origin = s['origin']; year = int(origin[:4])
        c = candidates[sid]; formal = registered.get(sid); ind = industry.get((firm, year)); cover = covers.get(sid, {})
        if c['firm_id'] != firm or c['origin'] != origin:
            errors.append(sid + ':candidate_identity')
        if s['industry_status'] != 'pending':
            source = sources.get(year, {})
            if not ind or not source or ind['public_date'] >= origin or ind['source_sha256'] != source.get('sha256'):
                errors.append(sid + ':industry_provenance')
            elif ind['industry_code'] != s['industry_code'] or ind['url'] != s['industry_source_url']:
                errors.append(sid + ':industry_mapping')
        if s['baseline_st'] == '1':
            if c['baseline_st_from_name'] != 1 or cover.get('status') != 'st_cover_confirmed' or not cover.get('public_date', '') < origin:
                errors.append(sid + ':baseline_st_provenance')
        financial_exclusion = s['industry_status'] == 'exclude_financial'
        baseline_exclusion = s['baseline_st'] == '1'
        decision = 'excluded' if financial_exclusion or baseline_exclusion else 'pending'
        if decision != s['screening_status']:
            errors.append(sid + ':screening_decision')
        # Exchange name changes are review leads. In particular, zero is not
        # verified event absence, and one is not a composite incident outcome.
        label_status = 'not_applicable_excluded' if decision == 'excluded' else 'pending_adjudication'
        if formal is not None:
            label_status = 'registered_requires_evidence_review'
        reasons = []
        if decision == 'pending':
            if s['industry_status'] == 'pending': reasons.append('historical_industry')
            reasons += ['baseline_ST_quarter_audit', 'followup_ST_quarter_audit',
                        'point_in_time_financials', 'annual_90_quarterly_32_missingness', 'annual_report_text']
        rows.append({
            'sample_id': sid, 'firm_id': firm, 'origin': origin,
            'followup_end_exclusive': f'{year + 1}-05-01',
            'industry_status': s['industry_status'],
            'industry_evidence_sha256': None if ind is None else ind['source_sha256'],
            'baseline_st': 1 if baseline_exclusion else None,
            'baseline_quarter': s['baseline_quarter'] or None,
            'baseline_audit': s['baseline_audit'] or None,
            'followup_ST_name_change_lead': c['new_st_name_in_followup'],
            'formal_sample_registered': int(formal is not None),
            'outcome': None, 'outcome_status': label_status,
            'verified_financial_facts_for_firm': verified_facts[firm],
            'verified_text_for_firm': int(firm in text_firms),
            'annual_missing': s['annual_missing'] or None,
            'quarterly_missing': s['quarterly_missing'] or None,
            'screening_status': decision,
            'unresolved_requirements': ';'.join(reasons),
        })
    summary = {
        'schema_version': 1, 'status': 'pre_freeze_evidence_audit',
        'collection_version': cohort['version'], 'protocol_version': protocol['version'],
        'candidate_firms': len({r['firm_id'] for r in rows}), 'candidate_firm_years': len(rows),
        'prediction_year_range': [min(r['origin'][:4] for r in rows), max(r['origin'][:4] for r in rows)],
        'industry_status': dict(Counter(r['industry_status'] for r in rows)),
        'screening_status': dict(Counter(r['screening_status'] for r in rows)),
        'selected_rows_in_formal_sample_register': sum(r['formal_sample_registered'] for r in rows),
        'selected_firms_with_verified_financial_facts': len({r['firm_id'] for r in rows if r['verified_financial_facts_for_firm']}),
        'selected_firms_with_verified_text': len({r['firm_id'] for r in rows if r['verified_text_for_firm']}),
        'followup_ST_name_change_leads': dict(Counter(str(r['followup_ST_name_change_lead']) for r in rows)),
        'final_sample_count': None, 'frozen': False,
        'evidence_consistency_errors': errors,
        'by_origin_year': {str(y): dict(Counter(r['screening_status'] for r in rows if r['origin'].startswith(str(y)))) for y in range(2017, 2026)},
        'rules': {
            'followup': protocol['confirmed']['followup'],
            'baseline': 'All three components must be verified absent to enter the incident-risk set.',
            'outcome': 'Name-change flags are leads only; do not assign 0 or 1 without event and coverage adjudication.',
            'missingness': protocol['missingness'],
            'collection': cohort['stopping_rule'],
        },
        'limitations': [
            'Historical source frame remains incomplete; this audit does not establish representative historical coverage.',
            'Industry mapping and stored source hashes are cross-checked; source PDFs are not independently re-adjudicated here.',
            'Excluded rows need no outcome for analysis; their outcome remains null.',
            'Uncollected financials are unresolved collection, not verified issuer missingness.',
            'Passing this inventory audit does not authorize a dataset freeze.',
        ],
        'input_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in INPUTS},
    }
    if errors:
        raise ValueError(json.dumps(errors))
    previous = read_json(INPUTS[3])
    for key in ['candidate_firms', 'candidate_firm_years', 'industry_status', 'screening_status']:
        if summary[key] != previous[key]:
            raise ValueError('Stored screening summary disagrees: ' + key)
    directory = ROOT / 'data/derived'
    with (directory / 'sample_readiness_audit.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    raw = (directory / 'sample_readiness_audit.csv').read_bytes()
    (directory / 'sample_readiness_audit.csv.gz').write_bytes(gzip.compress(raw, mtime=0))
    summary['audit_ledger'] = {'path': 'data/derived/sample_readiness_audit.csv.gz',
                             'uncompressed_csv_sha256': hashlib.sha256(raw).hexdigest()}
    (directory / 'sample_readiness_audit.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ['rules', 'input_sha256', 'limitations']}, indent=2))


if __name__ == '__main__':
    audit()
