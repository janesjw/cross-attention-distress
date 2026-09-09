"""Export analytical records with complete baseline, feature, and outcome evidence."""
import hashlib,json
from datetime import date,timedelta
from pathlib import Path
import numpy as np
from .database import ROOT,connect
from .features import matrices,assess_missingness
from .preprocess import encode_disclosure

def split_for_origin(origin):
    y=int(origin[:4])
    if 2017<=y<=2021:return 'train'
    if 2022<=y<=2023:return 'validation'
    if 2024<=y<=2025:return 'test'
    raise ValueError('Origin outside the declared experiment')

def validate_timeline(rows):
    seen=set()
    for r in rows:
        if r['sample_id'] in seen:raise ValueError('Duplicate sample')
        seen.add(r['sample_id'])
        year=int(r['origin'][:4])
        if r['origin']!=f'{year}-05-01' or r['followup_end_exclusive']!=f'{year+1}-05-01':raise ValueError('Incorrect annual forecast window')
        if r['label'] not in (0,1):raise ValueError('Unknown/excluded labels cannot enter training')
        if max(r['feature_max_public_date'],r['text_max_public_date'])>=r['origin']:raise ValueError('Future feature/text disclosure')
        if not r['origin']<=r['label_available_date']<r['followup_end_exclusive'] and r['label']==1:
            raise ValueError('Positive label was not first established in follow-up')
        end_last_day=(date.fromisoformat(r['followup_end_exclusive'])-timedelta(days=1)).isoformat()
        if r['label']==0 and r['label_available_date']<end_last_day:
            raise ValueError('Negative label requires completed follow-up')
        split=split_for_origin(r['origin'])
        # Dates mean end-of-day for negative ascertainment. Last follow-up day is April 30.
        boundary='2022-04-30' if split=='train' else ('2024-04-30' if split=='validation' else '2026-04-30')
        if r['label_available_date']>boundary:raise ValueError('Label not observable by fitting/selection/evaluation boundary')

def export_dataset(con,tokenizer,dataset_id,output):
    protocol=json.loads((ROOT/'configs/protocol.json').read_text())
    if protocol['pending_before_full_dataset']:raise ValueError('Historical sampling frame or event coverage is incomplete; see configs/protocol.json')
    approved=con.execute('SELECT * FROM sample_register WHERE analytical_eligible=1 ORDER BY origin,firm_id').fetchall()
    if not approved:raise ValueError('No eligible analytical records; complete the sample evidence before export')
    records=[]
    for r in approved:
        if r['outcome'] is None or r['label_available_date'] is None:raise ValueError('Missing verified label timing')
        if r['baseline_status']!='clear' or [r['baseline_st'],r['baseline_quarter'],r['baseline_audit']]!=[0,0,0]:
            raise ValueError('Baseline is not verified clear for all three criteria')
        if r['outcome']==0:
            coverage=con.execute('SELECT criterion,status FROM coverage WHERE sample_id=?',(r['sample_id'],)).fetchall()
            if {c[0]:c[1] for c in coverage}!={'ST':'verified_absent','quarter':'verified_absent','audit_loss':'verified_absent'}:
                raise ValueError('Negative outcome requires complete ascertainment')
        else:
            evidence=con.execute("SELECT 1 FROM sample_evidence WHERE sample_id=? AND stage='followup' AND status='verified_present' AND document_id IS NOT NULL",(r['sample_id'],)).fetchone()
            if not evidence:raise ValueError('Positive outcome lacks verified follow-up event evidence')
        features=matrices(con,r['firm_id'],int(r['origin'][:4]))
        reviewed={x[0] for x in con.execute("SELECT criterion FROM sample_evidence WHERE sample_id=? AND stage='feature_collection' AND status='verified_complete' AND note<>''",(r['sample_id'],))}
        assessment=assess_missingness(features,protocol['missingness'],{'annual','quarterly'}.issubset(reviewed))
        if assessment['status']=='pending_collection':raise ValueError('Financial source review incomplete; uncollected data cannot determine missingness eligibility')
        if assessment['status']=='exclude':raise ValueError('Sample fails confirmed branch-specific missingness criterion')
        secs=con.execute('''SELECT s.*,d.disclosed_date FROM text_sections s JOIN documents d USING(document_id)
          WHERE d.firm_id=? AND d.disclosed_date<? AND s.verification='verified'
          AND d.title LIKE ?
          ORDER BY d.disclosed_date DESC,CASE s.section_name WHEN 'MD&A' THEN 0 ELSE 1 END''',
          (r['firm_id'],r['origin'],f'%{int(r["origin"][:4])-1} Annual Report%')).fetchall()
        if not secs:raise ValueError('No reviewed annual text sections')
        # Select one most recent reviewed report; no mixing documents from different years.
        secs=[s for s in secs if s['document_id']==secs[0]['document_id']]
        sections=[]
        for s in secs:
            path=ROOT/s['text_path'];raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=s['text_sha256']:raise ValueError('Text digest mismatch')
            sections.append(raw.decode('utf-8'))
        tokens=encode_disclosure(tokenizer,sections)
        dates=[con.execute('SELECT disclosed_date FROM facts JOIN documents USING(document_id) WHERE fact_id=?',(f,)).fetchone()[0] for f in features['fact_ids']]
        if not dates:raise ValueError('No numerical source evidence')
        # Industry is required at forecast time. It is not guessed from a current classification.
        industry=con.execute('SELECT value FROM metadata WHERE key=?',('industry_at_origin:'+r['sample_id'],)).fetchone()
        if industry is None:raise ValueError('Missing reviewed industry-at-origin mapping')
        records.append({'sample_id':r['sample_id'],'firm_id':r['firm_id'],'origin':r['origin'],
          'followup_end_exclusive':r['followup_end_exclusive'],'label':r['outcome'],'label_available_date':r['label_available_date'],
          'feature_max_public_date':max(dates),'text_max_public_date':max(s['disclosed_date'] for s in secs),
          'industry':industry[0],'annual':features['annual'],'quarterly':features['quarterly'],
          'feature_fact_ids':features['fact_ids'],'text_section_ids':[s['section_id'] for s in secs],**tokens})
    validate_timeline(records)
    payload={'status':'frozen','dataset_id':dataset_id,'protocol_version':protocol['version'],'rows':records}
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    output.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False))
    con.execute('INSERT INTO dataset_versions VALUES (?,?,?,?,datetime(\'now\'))',
      (dataset_id,hashlib.sha256(output.read_bytes()).hexdigest(),hashlib.sha256((ROOT/'configs/protocol.json').read_bytes()).hexdigest(),'frozen'))
    con.commit()
    return payload

def load_frozen(manifest,con):
    manifest=Path(manifest);data=json.loads(manifest.read_text())
    r=con.execute('SELECT * FROM dataset_versions WHERE version_id=?',(data.get('dataset_id'),)).fetchone()
    if not r or r['status']!='frozen' or data.get('status')!='frozen':raise ValueError('Dataset is not registered and frozen')
    if hashlib.sha256(manifest.read_bytes()).hexdigest()!=r['manifest_sha256']:raise ValueError('Manifest digest mismatch')
    if hashlib.sha256((ROOT/'configs/protocol.json').read_bytes()).hexdigest()!=r['protocol_sha256']:raise ValueError('Protocol changed after freeze')
    rows=data['rows'];validate_timeline(rows)
    for row in rows:
        s=con.execute('SELECT * FROM sample_register WHERE sample_id=?',(row['sample_id'],)).fetchone()
        if s is None or not s['analytical_eligible'] or s['outcome']!=row['label']:raise ValueError('Unapproved sample')
    for split in ['train','validation','test']:
        selected=[r for r in rows if split_for_origin(r['origin'])==split]
        if len(selected)<2 or {r['label'] for r in selected}!={0,1}:raise ValueError(f'{split}: both outcome classes and at least two records required')
    return data
