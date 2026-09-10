"""Annual-only ST study: collection selection and unverified input inventory."""
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zipfile


def active(root):
    path=Path(root)/'configs/active_study.json'
    if not path.exists():return False
    mode=json.loads(path.read_text())['study']
    if mode not in ('annual_st_v1','legacy'):raise ValueError('Unknown active study')
    return mode=='annual_st_v1'


def annual_matches(row,origin):
    title=re.sub(r'\s+','',row['source_title'])
    year=int(origin[:4])-1
    return (row.get('report_kind')=='annual_report'
            and re.search(rf'(?<!\d){year}年(?:年?度)?报告',title) is not None
            and not any(s in title for s in ('英文','摘要','半年度'))
            and f'{year}-12-31'<row['disclosed_date']<origin)


def restrict(root,queue):
    scope=json.loads((Path(root)/'configs/simplified_cohort.json').read_text())
    firms={r['firm_id']:r for r in scope['firms']}
    return [r for r in queue if r['firm_id'] in firms and
            any(annual_matches(r,o) for o in firms[r['firm_id']]['origins'])]


def annual_features(values):
    def div(a,b):
        x,y=values.get(a),values.get(b)
        return None if x is None or y in (None,Decimal(0)) else float(x/y)
    ca,inv=values.get('current_assets'),values.get('inventory')
    v=dict(values)
    values=v
    values['quick_assets']=None if ca is None or inv is None else ca-inv
    ratios=[('liabilities','assets'),('current_assets','current_liabilities'),
            ('quick_assets','current_liabilities'),('net_profit','assets'),
            ('net_profit','equity'),('operating_profit','revenue'),
            ('net_profit','revenue'),('receivables','assets'),('inventory','assets'),
            ('ocf','assets'),('ocf','current_liabilities'),('management_expense','revenue')]
    return [div(a,b) for a,b in ratios]


def mda_candidate(raw):
    lines=[(p['page'],line) for p in raw['pages'] for line in p['text'].splitlines()]
    pattern=r'^第[一二三四五六七八九十]+节(管理层讨论与分析|经营情况讨论与分析|董事会报告)$'
    starts=[i for i,(_,s) in enumerate(lines) if re.fullmatch(pattern,re.sub(r'\s+','',s))]
    if len(starts)!=1:return None
    start=starts[0]
    end=next((i for i in range(start+1,len(lines)) if re.match(r'^第[一二三四五六七八九十]+节',re.sub(r'\s+','',lines[i][1]))),None)
    if end is None:return None
    text='\n'.join(s for _,s in lines[start+1:end]).strip()
    if len(re.sub(r'\s+','',text))<100:return None
    return {'page_start':lines[start][0],'page_end':lines[end-1][0],
            'text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'verification':'candidate_boundary_not_certified'}


def inventory(root):
    root=Path(root)
    scope=json.loads((root/'configs/simplified_cohort.json').read_text())
    protocol=json.loads((root/'configs/simplified_protocol.json').read_text())
    manifest=json.loads((root/'file_manifest.json').read_text())
    archives={}
    for path in sorted((root/'data/automation/extracted').glob('*.zip')):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest.get(path.relative_to(root).as_posix()):
            raise ValueError('Source archive hash mismatch: '+path.name)
        with zipfile.ZipFile(path) as z:raw=json.loads(z.read('pages.json'))
        source=raw['source']
        # Quarterly and older source archives remain preserved but are not inputs.
        if source.get('report_kind')!='annual_report':continue
        archives.setdefault(source['firm_id'],[]).append((source,path))
    legacy={r['sample_id']:r for r in csv.DictReader((root/'data/derived/sample_decisions.csv').open())}
    label_path=root/'data/verification/annual_st/labels.csv'
    labels={}
    if label_path.exists():
        if hashlib.sha256(label_path.read_bytes()).hexdigest()!=manifest.get(label_path.relative_to(root).as_posix()):raise ValueError('Label audit hash mismatch')
        labels={r['sample_id']:r for r in csv.DictReader(label_path.open())}
    con=sqlite3.connect(f'file:{root / "data/derived/distress.sqlite"}?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    leads={r['candidate_id']:dict(r) for r in con.execute('SELECT * FROM candidate_register')}
    rows=[];packets={};counts=Counter();by_split={s:Counter() for s in protocol['split_years']}
    for firm in scope['firms']:
        for origin in firm['origins']:
            y=int(origin[:4]);sid=f'{firm["firm_id"]}:{y}'
            split=next(s for s,(a,b) in protocol['split_years'].items() if a<=y<=b)
            prior=legacy.get(sid,{})
            label=labels.get(sid,{})
            if label and (label['origin']!=origin or label['followup_end_exclusive']!=f'{y+1}-05-01'):raise ValueError('Label window mismatch')
            # Reuse only exclusions that remain part of the new endpoint.
            excluded=prior.get('industry_status')=='excluded_financial' or prior.get('baseline_st')=='1' or label.get('status') in ('excluded','right_censored')
            r={'sample_id':sid,'firm_id':firm['firm_id'],'origin':origin,'split':split,
               'decision':'excluded' if excluded else 'pending','document_id':None,
               'annual_feature_count':12,'candidate_feature_values':0,'verified_feature_values':0,
               'text_candidate':False,'text_verified':False,'label':None,
               'industry_status':prior.get('industry_status','pending'),
               'membership_verified':label.get('membership')=='verified_listing_interval',
               'baseline_ST_verified':label.get('baseline_ST')=='0',
               'registry_label_verified':label.get('status')=='verified_registry_endpoint',
               'label_available_date':label.get('label_available_date') or None,
               'input_certified':False,'unresolved_requirements':'',
               'baseline_ST_lead':leads.get(sid,{}).get('baseline_st_from_name'),
               'new_ST_followup_lead':leads.get(sid,{}).get('new_st_name_in_followup'),
               'lead_is_verified_label':False,'analytical_eligible':False}
            if excluded:
                r['reason']='known_incomplete_followup_due_to_delisting' if label.get('status')=='right_censored' else 'preorigin_financial_industry_or_confirmed_baseline_ST'
            else:
                choices=[(s,p) for s,p in archives.get(firm['firm_id'],[]) if annual_matches(s,origin)]
                if choices:
                    latest=max(s['disclosed_date'] for s,_ in choices)
                    chosen=[(s,p) for s,p in choices if s['disclosed_date']==latest]
                    if len(chosen)==1:
                        source,path=chosen[0];did=source['document_id'];r['document_id']=did
                        if did not in packets:
                            with zipfile.ZipFile(path) as z:raw=json.loads(z.read('pages.json'))
                            structured=root/f'data/automation/structured/{did}.zip'
                            values={}
                            if structured.exists():
                                if hashlib.sha256(structured.read_bytes()).hexdigest()!=manifest.get(structured.relative_to(root).as_posix()):raise ValueError('Structured archive hash mismatch')
                                with zipfile.ZipFile(structured) as z:packet=json.loads(z.read('statements.json'))
                                if packet['extraction_sha256']!=hashlib.sha256(path.read_bytes()).hexdigest():raise ValueError('Stale structured source')
                                values={r['metric']:Decimal(r['values'][0]) for r in packet['rows']}
                            period=f'{y-1}-12-31'
                            doc=con.execute('SELECT * FROM documents WHERE document_id=?',(did,)).fetchone()
                            if doc and (doc['sha256']!=raw['pdf_sha256'] or doc['firm_id']!=source['firm_id'] or doc['disclosed_date']!=source['disclosed_date']):raise ValueError('Registered document identity mismatch')
                            verified={r['metric']:Decimal(r['value_normalized']) for r in con.execute(
                                "SELECT * FROM facts WHERE document_id=? AND period_end=? AND scope='consolidated' AND verification='verified'",(did,period))}
                            if not doc or doc['verification']!='verified':verified={}
                            packets[did]={'source':source,'candidate_features':annual_features(values),
                                          'verified_features':annual_features(verified),'text':mda_candidate(raw),
                                'analytical_verified':False,'label':None}
                        p=packets[did]
                        r['candidate_feature_values']=sum(v is not None for v in p['candidate_features'])
                        r['verified_feature_values']=sum(v is not None for v in p['verified_features'])
                        r['text_candidate']=p['text'] is not None
                        sections=list(con.execute("SELECT * FROM text_sections WHERE document_id=? AND verification='verified'",(did,)))
                        if len(sections)==1:
                            section=sections[0];tp=root/section['text_path']
                            if not tp.exists() or hashlib.sha256(tp.read_bytes()).hexdigest()!=section['text_sha256'] or manifest.get(section['text_path'])!=section['text_sha256']:raise ValueError('Verified text hash mismatch')
                            p['verified_text']=tp.read_text()
                            p['verified_text_sha256']=section['text_sha256']
                            r['text_verified']=True
                    else:r['reason']='simultaneous_report_versions_need_review'
                r.setdefault('reason','ST_history_label_and_input_certification_pending')
                if r['registry_label_verified']:
                    r['label']=int(label['registry_label'])
                # Only all twelve previously reviewed values certify complete
                # collection here. Partially collected sources never pass by imputation.
                r['input_certified']=r['verified_feature_values']==12 and r['text_verified']
                missing=[]
                for valid,reason in [(r['membership_verified'],'listing_interval'),
                                     (r['baseline_ST_verified'],'baseline_ST'),
                                     (r['registry_label_verified'],'ST_followup_coverage'),
                                     (r['industry_status']=='verified_nonfinancial','historical_industry'),
                                     (r['verified_feature_values']==12,'annual_financial_certification'),
                                     (r['text_verified'],'annual_text_certification')]:
                    if not valid:missing.append(reason)
                r['unresolved_requirements']=';'.join(missing)
                if not missing:
                    r['analytical_eligible']=True;r['decision']='eligible_awaiting_freeze'
                    r['reason']='Annual financial/text inputs and registry-defined endpoint verified; full-cohort freeze pending.'
            rows.append(r);counts[r['decision']]+=1;by_split[split]['candidate_rows']+=1
            if r['label'] is not None:by_split[split]['registry_positive' if r['label'] else 'registry_negative']+=1
            if r['baseline_ST_lead']==0 and r['new_ST_followup_lead']==1:by_split[split]['new_ST_leads_not_labels']+=1
    con.close()
    output=root/'data/derived/annual_st';output.mkdir(parents=True,exist_ok=True)
    summary={'study_version':protocol['version'],'status':'inventory_not_frozen_dataset',
             'candidate_firms':len(scope['firms']),'candidate_firm_years':len(rows),
             'decisions':dict(counts),'eligible_samples':sum(r['analytical_eligible'] for r in rows),'frozen':False,'final_sample_count':None,
             'registry_labels_verified':sum(r['registry_label_verified'] and r['decision']!='excluded' for r in rows),
             'unresolved_requirements':dict(Counter(s for r in rows for s in r['unresolved_requirements'].split(';') if s)),
             'rows_with_selected_annual_report':sum(r['document_id'] is not None for r in rows),
             'rows_with_12_candidate_features':sum(r['candidate_feature_values']==12 for r in rows),
             'rows_with_12_verified_features':sum(r['verified_feature_values']==12 for r in rows),
             'rows_with_text_candidate':sum(r['text_candidate'] for r in rows),
             'verified_text_sections':sum(r['text_verified'] for r in rows),
             'splits':{k:dict(v) for k,v in by_split.items()},
             'training_candidate':False,'training_note':'Full-cohort input review and simplified frozen export/runner remain incomplete; legacy MMAN training disabled.'}
    (output/'status.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (output/'sample_inventory.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    # Only annual inputs for the reduced study are included; full disclosures stay archived.
    with zipfile.ZipFile(output/'candidate_inputs.zip','w',zipfile.ZIP_DEFLATED) as z:
        for did,p in sorted(packets.items()):
            info=zipfile.ZipInfo(did+'.json',(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,json.dumps(p,ensure_ascii=False,sort_keys=True))
    for p in output.iterdir():manifest[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    (root/'file_manifest.json').write_text(json.dumps(dict(sorted(manifest.items())),indent=2)+'\n')
    return summary
