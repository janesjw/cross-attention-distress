"""Freeze a source-availability subset before inspecting model performance."""
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import zipfile


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def truth(v):return v is True or v=='True'
def dumps(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False)


def split_counts(rows):
    result={}
    for split in ('train','validation','test'):
        selected=[r for r in rows if r['split']==split]
        result[split]={'rows':len(selected),'firms':len({r['firm_id'] for r in selected}),
            'positive':sum(int(r['label']) for r in selected),
            'negative':sum(1-int(r['label']) for r in selected),
            'positive_firms':len({r['firm_id'] for r in selected if int(r['label'])==1}),
            'negative_firms':len({r['firm_id'] for r in selected if int(r['label'])==0})}
    return result


def minimum_support(counts):
    # Technical identifiability/cluster-resampling floor, NOT evidence of power.
    return [f'{s}: requires at least two distinct firms in each class' for s,c in counts.items()
            if min(c['positive_firms'],c['negative_firms'])<2]


def freeze(root):
    root=Path(root);out=root/'data/derived/annual_st';frozen=out/'frozen_manifest.json'
    if frozen.exists():
        m,records=load_frozen(root);return {'frozen':True,'already_frozen':True,'summary':m['summary']}
    manifest=json.loads((root/'file_manifest.json').read_text())
    paths=['configs/simplified_protocol.json','configs/simplified_cohort.json',
           'data/derived/annual_st/sample_inventory.csv','data/derived/annual_st/candidate_inputs.zip',
           'data/verification/annual_st/labels.csv','data/verification/annual_st/input_audit.zip',
           'data/verification/annual_st/source_selection.json','data/derived/sample_decisions.csv']
    evidence={}
    for name in paths:
        p=root/name
        if not p.exists() or manifest.get(name)!=sha(p):raise ValueError('Unregistered or changed freeze input: '+name)
        evidence[name]=sha(p)
    rows=list(csv.DictReader((root/paths[2]).open()))
    selected=[r for r in rows if truth(r['analytical_eligible'])]
    if len({r['sample_id'] for r in rows})!=len(rows):raise ValueError('Duplicate sample ID')
    counts=split_counts(selected);reasons=minimum_support(counts)
    check={'frozen':False,'eligible_samples':len(selected),'splits':counts,'blocking_reasons':reasons,
           'adequacy_note':'Two firms per class is only a computation floor. Event counts and confidence intervals determine how limited the conclusions must be.'}
    (out/'freeze_readiness.json').write_text(json.dumps(check,indent=2)+'\n')
    manifest['data/derived/annual_st/freeze_readiness.json']=sha(out/'freeze_readiness.json')
    if reasons:
        (root/'file_manifest.json').write_text(json.dumps(dict(sorted(manifest.items())),indent=2)+'\n')
        return check
    records=[]
    with zipfile.ZipFile(root/paths[3]) as z:
        for r in sorted(selected,key=lambda r:r['sample_id']):
            p=json.loads(z.read(r['document_id']+'.json'))
            features=p['verified_features'] if r['financial_verification_tier']=='manual_source_review' else p['rule_checked_features']
            text=p['verified_text']
            if hashlib.sha256(text.encode()).hexdigest()!=p['verified_text_sha256']:raise ValueError('Text hash mismatch')
            if len(features)!=12 or sum(x is None for x in features)>3 or not text:raise ValueError('Incomplete inputs')
            if p['source']['disclosed_date']>=r['origin']:raise ValueError('Postorigin input')
            if r['industry_status']!='verified_nonfinancial' or not all(truth(r[k]) for k in ('membership_verified','baseline_ST_verified','registry_label_verified','input_certified')):raise ValueError('Uncertified sample')
            records.append({k:r[k] for k in ('sample_id','firm_id','origin','split','document_id','label_available_date','financial_verification_tier','text_verification_tier')}|
                           {'label':int(r['label']),'features':features,'text':text,'text_sha256':p['verified_text_sha256'], 'disclosed_date':p['source']['disclosed_date']})
    dataset=out/'frozen_samples.jsonl'
    dataset.write_text(''.join(dumps(r)+'\n' for r in records))
    summary={'sample_version':'annual-st-sz-v1','candidate_firms':len({r['firm_id'] for r in rows}),
             'candidate_firm_years':len(rows),'final_firms':len({r['firm_id'] for r in records}),
             'final_sample_count':len(records),'positive':sum(r['label'] for r in records),
             'negative':sum(1-r['label'] for r in records),'origin_min':min(r['origin'] for r in records),
             'origin_max':max(r['origin'] for r in records),'splits':counts}
    m={'frozen':True,'created_at':datetime.now(timezone.utc).isoformat(),'summary':summary,
       'dataset_path':dataset.relative_to(root).as_posix(),'dataset_sha256':sha(dataset),'evidence_hashes':evidence,
       'protocol':json.loads((root/paths[0]).read_text()),
       'selection_rule':'All eligible rows at this source-availability snapshot; common sample across all four models, no selection by model results. Pending/ambiguous/missing source and industry cases excluded with reasons in the hashed inventory.',
       'excluded_or_unresolved':dict(Counter(r['reason']+';'+r['unresolved_requirements'] for r in rows if not truth(r['analytical_eligible']))),
       'limitations':['Source-availability selection may be nonrandom; results do not represent all Shenzhen firms.','Rule-based source checks are not manual audits.','Technical class-support minimum does not establish statistical power.','Registered ST changes measure a regulatory endpoint, not all financial distress.']}
    frozen.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    fs=root/'data/derived/filing_summary.json';filings=json.loads(fs.read_text())
    filings.update(formal_sample_ready=True,training_completed=False,annual_st_frozen_sample=summary)
    fs.write_text(json.dumps(filings,ensure_ascii=False,indent=2)+'\n')
    readme=root/'README.md';content=readme.read_text()
    begin='<!-- ANNUAL_ST_FROZEN_START -->';end='<!-- ANNUAL_ST_FROZEN_END -->'
    block=begin+'\n## Frozen annual ST sample\n\n```json\n'+json.dumps(summary,indent=2)+'\n```\n\nThe same summary is recorded in `data/derived/filing_summary.json` and `data/derived/annual_st/frozen_manifest.json`. Source-availability and automatic-validation limitations are recorded in the manifest. Freezing is not completion of training.\n'+end
    if begin in content:content=content[:content.index(begin)]+block+content[content.index(end)+len(end):]
    else:content+='\n'+block+'\n'
    readme.write_text(content)
    status_path=out/'status.json'
    if status_path.exists():
        status=json.loads(status_path.read_text())
        status.update(frozen=True,final_sample_count=len(records),training_candidate=True,status='frozen_dataset_with_live_inventory')
        status_path.write_text(json.dumps(status,indent=2)+'\n')
        manifest[status_path.relative_to(root).as_posix()]=sha(status_path)
    for p in (dataset,frozen,fs,readme):manifest[p.relative_to(root).as_posix()]=sha(p)
    check.update(frozen=True,summary=summary);(out/'freeze_readiness.json').write_text(json.dumps(check,indent=2)+'\n')
    manifest['data/derived/annual_st/freeze_readiness.json']=sha(out/'freeze_readiness.json')
    (root/'file_manifest.json').write_text(json.dumps(dict(sorted(manifest.items())),indent=2)+'\n')
    load_frozen(root)
    return check


def load_frozen(root):
    root=Path(root);path=root/'data/derived/annual_st/frozen_manifest.json'
    m=json.loads(path.read_text());registry=json.loads((root/'file_manifest.json').read_text())
    if registry.get(path.relative_to(root).as_posix())!=sha(path):raise ValueError('Frozen manifest changed')
    dataset=root/m['dataset_path']
    if sha(dataset)!=m['dataset_sha256']:raise ValueError('Frozen dataset changed')
    records=[json.loads(line) for line in dataset.read_text().splitlines()]
    if len(records)!=m['summary']['final_sample_count'] or split_counts(records)!=m['summary']['splits']:raise ValueError('Frozen counts mismatch')
    # Inventory may continue to grow; it is not read as a model input after freeze.
    # The protocol embedded in the hashed frozen manifest is the training contract.
    return m,records


def training_required(root):
    """Avoid rerunning a completed experiment on each collection schedule."""
    root=Path(root);frozen,_=load_frozen(root)
    result_path=root/'data/derived/annual_st/results/results.json'
    if not result_path.exists():return True
    result=json.loads(result_path.read_text())
    expected={(v,s) for v in frozen['protocol']['model']['variants'] for s in frozen['protocol']['model']['seeds']}
    actual={(r['variant'],r['seed']) for r in result.get('runs',[])}
    return (result.get('dataset_sha256')!=frozen['dataset_sha256'] or
            result.get('training_code_sha256')!=sha(root/'src/distress/annual_train.py') or actual!=expected)
