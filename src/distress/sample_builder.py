"""Evidence-driven adjudication of the fixed cohort, without inventing coverage."""
import csv
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from .database import asof_fact, baseline_status, pair_distress
from .features import matrices, assess_missingness

PREFIX='sample_builder_v1: '


def annual_title(title,year):
    import re
    title=re.sub(r'\s+','',title).lower()
    return not any(s in title for s in ['摘要','summary','半年度','semiannual']) and (
        re.search(rf'(?<!\d){year}年?年度报告',title) is not None or
        re.search(rf'(?<!\d){year}annualreport',title) is not None)


def annual_sections(con,firm,origin):
    year=int(origin[:4])-1
    rows=con.execute('''SELECT s.*,d.disclosed_date,d.title,d.version_kind FROM text_sections s
        JOIN documents d USING(document_id) WHERE d.firm_id=? AND d.disclosed_date<?
        AND s.verification='verified' AND d.verification='verified'
        ORDER BY d.disclosed_date DESC,s.section_id''',(firm,origin)).fetchall()
    rows=[r for r in rows if annual_title(r['title'],year)]
    if not rows:return []
    latest=[r for r in rows if r['disclosed_date']==rows[0]['disclosed_date']]
    docs={r['document_id'] for r in latest}
    if len(docs)>1:
        corrected={r['document_id'] for r in latest if r['version_kind']=='corrected'}
        if len(corrected)!=1:return [] # Ambiguous simultaneous report versions remain pending.
        selected=next(iter(corrected))
    else:selected=next(iter(docs))
    return sorted([r for r in latest if r['document_id']==selected],
                  key=lambda r:(r['section_name'] not in ('MD&A','management_discussion_and_analysis'),r['section_id']))


def external_evidence(con,sid,stage,criterion,origin=None):
    rows=con.execute('''SELECT e.*,d.disclosed_date,d.verification AS doc_verified
        FROM sample_evidence e LEFT JOIN documents d USING(document_id)
        WHERE sample_id=? AND stage=? AND criterion=?''',(sid,stage,criterion)).fetchall()
    return [r for r in rows if not r['note'].startswith(PREFIX) and r['note'].strip()
            and (origin is None or (r['document_id'] and r['doc_verified']=='verified' and r['disclosed_date']<origin))]


def component_from_evidence(rows):
    states={r['status'] for r in rows}&{'verified_absent','verified_present'}
    if len(states)>1:raise ValueError('Contradictory reviewed component evidence')
    return 1 if 'verified_present' in states else 0 if 'verified_absent' in states else None


def audit_component(con,firm,year,cutoff):
    profit=asof_fact(con,firm,'net_profit',f'{year-1}-12-31','YTD',cutoff)
    audits=con.execute('''SELECT a.*,d.disclosed_date FROM audit_opinions a
        JOIN documents d USING(document_id) WHERE d.firm_id=? AND a.fiscal_year=?
        AND a.audit_scope='financial_statements' AND d.disclosed_date<=?
        AND d.verification='verified' ORDER BY d.disclosed_date DESC''',(firm,year-1,cutoff)).fetchall()
    if audits:
        newest=[r for r in audits if r['disclosed_date']==audits[0]['disclosed_date']]
        if len({r['opinion'] for r in newest})>1:raise ValueError('Conflicting same-day audit opinions')
        a=audits[0]
        if a['opinion']=='standard_unqualified':return 0,a['document_id'],'Standard financial-statement audit; conjunction false.'
    if profit and Decimal(profit['value_normalized'])>=0:
        return 0,profit['document_id'],'Annual consolidated net profit nonnegative; conjunction false.'
    if audits and audits[0]['opinion'] not in ('standard_unqualified','unresolved') and profit:
        return int(Decimal(profit['value_normalized'])<0),audits[0]['document_id'],'Nonstandard financial-statement audit and consolidated loss.'
    return None,None,'Annual audit/loss conjunction unresolved.'


def outcome(con,sid,baseline,origin,end):
    if baseline!='clear':return None,None,'not_applicable_excluded' if baseline=='excluded' else 'unresolved',[]
    positives=[]
    firm=sid.rsplit(':',1)[0]
    for r in con.execute('''SELECT e.*,d.disclosed_date,d.verification FROM events e
            JOIN documents d USING(document_id) WHERE e.firm_id=? AND e.confirmed=1''',(firm,)):
        if r['verification']!='verified' or not origin<=r['public_date']<end or r['disclosed_date']>r['public_date']:continue
        if r['event_type']=='ST_implementation_announcement':
            if not r['effective_date'] or not origin<=r['effective_date']<end:continue
            criterion='ST'
        elif r['event_type']=='two_quarter_loss_ocf':criterion='quarter'
        else:continue
        positives.append((r['public_date'],r['document_id'],criterion,r['detail']))
    for r in con.execute('''SELECT e.*,d.disclosed_date,d.verification FROM sample_evidence e
            JOIN documents d USING(document_id) WHERE e.sample_id=? AND e.stage='followup'
            AND e.status='verified_present' ''',(sid,)):
        if (not r['note'].startswith(PREFIX) and r['verification']=='verified'
            and r['criterion'] in ('ST','quarter','audit_loss') and origin<=r['disclosed_date']<end):
            positives.append((r['disclosed_date'],r['document_id'],r['criterion'],r['note']))
    if positives:return 1,min(p[0] for p in positives),'verified_present',positives
    coverage={r['criterion']:r for r in con.execute('SELECT * FROM coverage WHERE sample_id=?',(sid,))}
    if all(k in coverage and coverage[k]['status']=='verified_absent' and coverage[k]['window_start']==origin
           and coverage[k]['window_end_exclusive']==end and coverage[k]['evidence_note'].strip()
           for k in ('ST','quarter','audit_loss')):
        return 0,(date.fromisoformat(end)-timedelta(days=1)).isoformat(),'verified_absent',[]
    return None,None,'unresolved',[]


def build(root):
    root=Path(root)
    cohort=json.loads((root/'configs/collection_cohort.json').read_text())
    protocol=json.loads((root/'configs/protocol.json').read_text())
    industry=json.loads((root/'data/derived/historical_industry.json').read_text())
    sources={s['origin_year']:s for s in json.loads((root/'data/derived/industry_source_status.json').read_text())}
    ind={}
    for r in industry:
        key=(r['firm_id'],r['origin_year'])
        if key in ind:raise ValueError('Duplicate historical industry evidence')
        source=sources.get(r['origin_year'],{})
        if source.get('sha256')!=r['source_sha256'] or source.get('url')!=r['url'] or source.get('public_date')!=r['public_date']:
            raise ValueError('Historical industry source mismatch')
        ind[key]=r
    covers=json.loads((root/'data/derived/st_cover_evidence.json').read_text())
    con=sqlite3.connect(root/'data/derived/distress.sqlite');con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    candidates={r['candidate_id']:r for r in con.execute('SELECT * FROM candidate_register')}
    has_facts={r[0] for r in con.execute("SELECT DISTINCT firm_id FROM facts WHERE verification='verified'")}
    expected={f['firm_id']+':'+o[:4] for f in cohort['firms'] for o in f['origins']}
    if len(expected)!=cohort['selected_candidate_firm_years']:raise ValueError('Cohort count mismatch')
    records=[];tasks=[]
    try:
        with con:
            for f in cohort['firms']:
                fid=f['firm_id']
                if not con.execute('SELECT 1 FROM firms WHERE firm_id=?',(fid,)).fetchone():
                    listing=con.execute('SELECT * FROM listing_records WHERE firm_id=?',(fid,)).fetchone()
                    if listing is None:raise ValueError('Missing listed firm')
                    con.execute('INSERT INTO firms (firm_id,name,exchange,universe_status) VALUES (?,?,?,?)',
                        (fid,listing['name_original'] or listing['name_en'] or fid,listing['exchange'],'coverage_pending'))
                for origin in f['origins']:
                    y=int(origin[:4]);sid=f'{fid}:{y}';end=f'{y+1}-05-01';cutoff=f'{y}-04-30'
                    candidate=candidates[sid]
                    if candidate['origin']!=origin or candidate['firm_id']!=fid:raise ValueError('Candidate identity mismatch')
                    con.execute("DELETE FROM sample_evidence WHERE sample_id=? AND substr(note,1,?)=?",(sid,len(PREFIX),PREFIX))
                    historical=ind.get((fid,y))
                    industry_state='pending'
                    if historical and historical['public_date']<origin:
                        industry_state='excluded_financial' if historical['group']=='J' else 'verified_nonfinancial'
                        con.execute('INSERT INTO metadata VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                            ('industry_at_origin:'+sid,historical['industry_code']))
                    else:con.execute('DELETE FROM metadata WHERE key=?',('industry_at_origin:'+sid,))
                    membership=any(r['status']=='verified_present' for r in external_evidence(con,sid,'eligibility','historical_membership',origin))
                    st_rows=external_evidence(con,sid,'baseline','ST',origin)
                    st=component_from_evidence(st_rows)
                    cover=covers.get(sid,{})
                    if (candidate['baseline_st_from_name']==1 and cover.get('status')=='st_cover_confirmed'
                            and cover.get('public_date','9999')<origin):
                        if st==0:raise ValueError('Contradictory ST evidence')
                        st=1
                    q=pair_distress(con,fid,[(y-1,4),(y,1)],cutoff,True) if fid in has_facts else None
                    a,adoc,anote=audit_component(con,fid,y,cutoff) if fid in has_facts else (None,None,'No verified financial facts.')
                    for criterion,computed in [('quarter',q),('audit_loss',a)]:
                        reviewed=external_evidence(con,sid,'baseline',criterion,origin)
                        supplied=component_from_evidence(reviewed)
                        if supplied is not None and computed is not None and supplied!=computed:
                            raise ValueError('Reviewed baseline conflicts with source calculation')
                        if computed is None and supplied is not None:
                            if criterion=='quarter':q=supplied
                            else:a,adoc,anote=supplied,reviewed[0]['document_id'],'Reviewed audit/loss component evidence.'
                    baseline=baseline_status([st,q,a])
                    features=matrices(con,fid,y) if fid in has_facts else {'missing_annual':90,'missing_quarterly':32,'fact_ids':[]}
                    complete=all(any(r['status']=='verified_complete' for r in external_evidence(con,sid,'feature_collection',k)) for k in ['annual','quarterly'])
                    missing=assess_missingness(features,protocol['missingness'],complete)
                    secs=annual_sections(con,fid,origin)
                    for s in secs:
                        raw=(root/s['text_path']).read_bytes()
                        if hashlib.sha256(raw).hexdigest()!=s['text_sha256']:raise ValueError('Reviewed text hash mismatch')
                    label,available,label_status,positive=outcome(con,sid,baseline,origin,end)
                    if industry_state=='excluded_financial' or baseline=='excluded' or missing['status']=='exclude':
                        decision='excluded';label=None;available=None;label_status='not_applicable_excluded'
                    else:decision='pending'
                    reasons=[]
                    if decision!='excluded':
                        if industry_state=='pending':reasons.append('historical_industry')
                        if not membership:reasons.append('historical_membership')
                        for name,v in [('baseline_ST',st),('baseline_quarter',q),('baseline_audit',a)]:
                            if v is None:reasons.append(name)
                        if missing['status']=='pending_collection':reasons.append('financial_source_review')
                        if not secs:reasons.append('annual_text')
                        if label is None:reasons.append('future_12_month_outcome')
                        bound='2022-04-30' if y<=2021 else '2024-04-30' if y<=2023 else '2026-04-30'
                        if available and available>bound:reasons.append('label_unavailable_by_split_boundary')
                        if not reasons:decision='eligible'
                    note=PREFIX+('Excluded: '+','.join(k for k,v in [('financial_industry',industry_state=='excluded_financial'),('baseline_distress',baseline=='excluded'),('missingness',missing['status']=='exclude')] if v) if decision=='excluded' else ';'.join(reasons) or 'All per-sample gates passed; global dataset freeze still required.')
                    con.execute('''INSERT INTO sample_register VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(sample_id) DO UPDATE SET
                        baseline_st=excluded.baseline_st,baseline_quarter=excluded.baseline_quarter,baseline_audit=excluded.baseline_audit,
                        baseline_status=excluded.baseline_status,feature_status=excluded.feature_status,outcome=excluded.outcome,
                        label_available_date=excluded.label_available_date,outcome_status=excluded.outcome_status,
                        analytical_eligible=excluded.analytical_eligible,note=excluded.note''',
                        (sid,fid,origin,end,st,q,a,baseline,missing['status'],label,available,label_status,int(decision=='eligible'),note))
                    if a is not None:
                        con.execute('INSERT INTO sample_evidence VALUES (?,?,?,?,?,?,?)',(sid,'baseline','audit_loss','verified_present' if a else 'verified_absent',adoc,None,PREFIX+anote))
                    for r in con.execute('SELECT derived_id FROM derived_values WHERE firm_id=? AND asof_date=?',(fid,cutoff)).fetchall():
                        con.execute('INSERT INTO sample_evidence VALUES (?,?,?,?,?,?,?)',(sid,'baseline','quarter','calculated',None,r[0],PREFIX+'Cumulative-to-quarter calculation with source lineage.'))
                    for _,did,criterion,detail in positive:
                        con.execute('INSERT INTO sample_evidence VALUES (?,?,?,?,?,?,?)',(sid,'followup',criterion,'verified_present',did,None,PREFIX+detail))
                    records.append(dict(sample_id=sid,firm_id=fid,origin=origin,followup_end_exclusive=end,
                        industry_status=industry_state,membership_verified=membership,baseline_st=st,baseline_quarter=q,baseline_audit=a,
                        baseline_status=baseline,annual_missing=features['missing_annual'],quarterly_missing=features['missing_quarterly'],
                        source_review_complete=complete,text_verified=bool(secs),outcome=label,label_available_date=available,
                        decision=decision,unresolved_requirements=';'.join(reasons),decision_note=note))
                    if decision=='pending':
                        tasks.append(dict(sample_id=sid,firm_id=fid,origin=origin,
                            unresolved_requirements=reasons,
                            annual_financial_years=list(range(y-5,y)),
                            beginning_balance_year=y-6,
                            quarterly_ytd_periods=[f'{y-1}-{m}' for m in ['03-31','06-30','09-30','12-31']]+[f'{y}-03-31'],
                            annual_text_year=y-1,feature_disclosure_cutoff=cutoff,
                            outcome_window=[origin,end],
                            instruction='Match original disclosures, review units/scope/version and cumulative comparability; do not mark absent merely because an extraction or fact is missing.'))
            if con.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Foreign key integrity failure')
            if len(records)!=len(expected):raise ValueError('Decision count mismatch')
    finally:con.close()
    folder=root/'data/derived'
    with (folder/'sample_decisions.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    summary=dict(status='sample_adjudication_not_frozen',candidate_firms=len(cohort['firms']),candidate_firm_years=len(records),
        decisions=dict(Counter(r['decision'] for r in records)),
        baseline_quarter_known=sum(r['baseline_quarter'] is not None for r in records),
        baseline_audit_known=sum(r['baseline_audit'] is not None for r in records),
        preorigin_annual_text_verified=sum(r['text_verified'] for r in records),
        unresolved_requirements=dict(Counter(k for r in records for k in r['unresolved_requirements'].split(';') if k)),
        final_sample_count=None,frozen=False)
    (folder/'sample_decisions.json').write_text(json.dumps(summary,indent=2)+'\n')
    (folder/'sample_completion_tasks.json').write_text(json.dumps(tasks,indent=2)+'\n')
    inputs=['configs/collection_cohort.json','configs/protocol.json','data/derived/historical_industry.json',
            'data/derived/industry_source_status.json','data/derived/st_cover_evidence.json']
    summary['input_sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in inputs}
    (folder/'sample_decisions.json').write_text(json.dumps(summary,indent=2)+'\n')
    manifest=json.loads((root/'file_manifest.json').read_text())
    for name in ['distress.sqlite','sample_decisions.csv','sample_decisions.json','sample_completion_tasks.json']:
        p=folder/name;manifest[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    (root/'file_manifest.json').write_text(json.dumps(dict(sorted(manifest.items())),indent=2)+'\n')
    return summary
