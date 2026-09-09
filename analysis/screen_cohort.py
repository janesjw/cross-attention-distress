"""Evidence-linked screening of the fixed company-year cohort."""
import csv,hashlib,json,re,sqlite3
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def industry_rows(source,tables):
    current_group=current_code=current_name=None;out={}
    for row in tables:
        cells=row['cells']
        if len(cells)==8:
            if not re.fullmatch(r'\d{6}',cells[0] or ''):continue
            current_group=cells[2];current_code=cells[6];current_name=cells[7]
            code=cells[0];name=cells[1]
        elif len(cells)==5:
            if '代码' in str(cells[3]):continue
            if cells[0]:
                found=re.findall(r'[（(]([A-S])[）)]',cells[0])
                current_group=found[-1] if found else None
            if cells[1]:current_code=re.sub(r'\s+','',cells[1])
            if cells[2]:current_name=cells[2].replace('\n','')
            code=cells[3];name=cells[4]
            if not code:continue
        else:raise ValueError('Unexpected industry table layout')
        if not re.fullmatch(r'\d{6}',code):raise ValueError('Invalid stock code')
        if not current_group or not current_code:
            continue  # An incomplete category cell stays unmatched; never inherit the preceding category.
        if not re.fullmatch(r'(?:00\d|30\d|60\d|688)\d{3}',code):continue
        firm=code+('.SH' if code.startswith('6') else '.SZ')
        if firm in out:raise ValueError('Duplicate stock in industry table')
        out[firm]=dict(firm_id=firm,group=current_group,industry_code=current_group+current_code,
                      public_date=source['public_date'],period=source['period'],page=row['page'],
                      source_sha256=source['sha256'],url=source['url'],source_name=name)
    return out

def main():
    sources=json.loads((ROOT/'data/derived/industry_source_status.json').read_text());byyear={};normalized=[];errors=[]
    for source in sources:
        if source['status']!='downloaded_tables_pending_validation':continue
        year=source['origin_year']
        try:
            tables=json.loads((ROOT/f'data/raw/industry/{year}_tables.json').read_text())['tables']
            mapped=industry_rows(source,tables)
            if source['public_date']>=f'{year}-05-01':raise ValueError('Industry information was published after origin')
            byyear[year]=mapped
            normalized.extend(dict(origin_year=year,**r) for r in mapped.values())
        except ValueError as exc:errors.append(dict(year=year,error=str(exc)))
    cohort=json.loads((ROOT/'configs/collection_cohort.json').read_text())
    stpath=ROOT/'data/derived/st_cover_evidence.json';st=json.loads(stpath.read_text()) if stpath.exists() else {}
    records=[]
    with sqlite3.connect(ROOT/'data/derived/distress.sqlite') as con:
        con.row_factory=sqlite3.Row
        for firm in cohort['firms']:
            for origin in firm['origins']:
                sid=firm['firm_id']+':'+origin[:4]
                c=con.execute('SELECT * FROM candidate_register WHERE candidate_id=?',(sid,)).fetchone()
                ind=byyear.get(int(origin[:4]),{}).get(firm['firm_id'])
                industry='pending' if ind is None else ('exclude_financial' if ind['group']=='J' else 'pass_preorigin_classification')
                cover=st.get(sid,{})
                st_confirmed=c['baseline_st_from_name']==1 and cover.get('status')=='st_cover_confirmed'
                state='exclude_existing_st' if st_confirmed else 'pending'
                # Existing financial observations are insufficient for these selected firms.
                # Never turn uncollected inputs into an issuer-level missingness exclusion.
                facts=con.execute('SELECT COUNT(*) FROM facts f JOIN documents d USING(document_id) WHERE f.firm_id=? AND d.disclosed_date<?',(firm['firm_id'],origin)).fetchone()[0]
                records.append(dict(sample_id=sid,firm_id=firm['firm_id'],origin=origin,
                    industry_status=industry,industry_code=None if ind is None else ind['industry_code'],
                    industry_public_date=None if ind is None else ind['public_date'],industry_source_page=None if ind is None else ind['page'],
                    industry_source_url=None if ind is None else ind['url'],
                    baseline_st_name_evidence=c['baseline_st_from_name'],baseline_st=1 if st_confirmed else None,
                    st_source_url=cover.get('url'),st_source_public_date=cover.get('public_date'),
                    baseline_quarter=None,baseline_audit=None,baseline_status=state,
                    available_financial_facts=facts,annual_missing=None,quarterly_missing=None,
                    completeness_status='pending_source_review',
                    screening_status='excluded' if industry=='exclude_financial' or st_confirmed else 'pending',
                    analytical_eligible=0))
    out=ROOT/'data/derived';out.mkdir(exist_ok=True)
    with (out/'cohort_screening.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    db=out/'cohort_screening.sqlite';temp=db.with_suffix('.tmp.sqlite')
    if temp.exists():temp.unlink()
    with sqlite3.connect(temp) as screening:
        columns=list(records[0])
        screening.execute('CREATE TABLE cohort_screening ('+','.join('"'+c+'"' for c in columns)+',PRIMARY KEY(sample_id))')
        screening.executemany('INSERT INTO cohort_screening VALUES ('+','.join('?' for _ in columns)+')',[[r[c] for c in columns] for r in records])
        assert screening.execute('SELECT COUNT(*) FROM cohort_screening').fetchone()[0]==5250
        assert screening.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    temp.replace(db)
    summary={'candidate_firms':cohort['selected_firms'],'candidate_firm_years':len(records),
             'industry_status':dict(Counter(r['industry_status'] for r in records)),
             'baseline_st_name_evidence':dict(Counter(str(r['baseline_st_name_evidence']) for r in records)),
             'baseline_st_confirmed_exclusions':sum(r['baseline_st']==1 for r in records),
             'screening_status':dict(Counter(r['screening_status'] for r in records)),
             'financial_source_review_pending':len(records),'analytical_eligible':0,
             'industry_source_validation_errors':errors,
             'note':'Industry results use the identified pre-origin official tables. Missing source periods, ST histories, quarter/audit criteria and uncollected inputs remain unresolved.'}
    (out/'cohort_screening_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    selected={r['firm_id'] for r in cohort['firms']}
    (out/'historical_industry.json').write_text(json.dumps([r for r in normalized if r['firm_id'] in selected],ensure_ascii=True,indent=2)+'\n')
    manifest=json.loads((ROOT/'file_manifest.json').read_text())
    for name in ['cohort_screening.sqlite','cohort_screening.csv','cohort_screening_summary.json','historical_industry.json','st_cover_evidence.json']:
        p=out/name
        if p.exists():manifest[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    (ROOT/'file_manifest.json').write_text(json.dumps(dict(sorted(manifest.items())),indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
