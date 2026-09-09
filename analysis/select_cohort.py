"""Freeze a finite, outcome-blind industry-stratified collection cohort."""
import argparse,hashlib,json,math,sqlite3
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def select(root,target=5142,seed=42):
    market_path=root/'data/raw/market_records.json'
    issuer_path=root/'data/raw/disclosure_firms.json'
    market=json.loads(market_path.read_text())
    issuers={r['firm_id'] for r in json.loads(issuer_path.read_text())['firms']}
    listing={r['firm_id']:r for r in market['listings']}
    origins=defaultdict(list)
    with sqlite3.connect(root/'data/derived/distress.sqlite') as con:
        # Do not select using baseline distress, subsequent outcomes or model performance.
        for firm,origin in con.execute('SELECT firm_id,origin FROM candidate_register ORDER BY firm_id,origin'):
            if firm in issuers:origins[firm].append(origin)
    strata=defaultdict(list)
    for firm in origins:
        industry=listing[firm]['industry_code_snapshot']
        strata[industry if industry and industry!='0' else 'unknown'].append(firm)
    size=len(origins);potential=sum(map(len,origins.values()))
    n=min(size,math.ceil(target*size/potential))
    quota={k:n*len(v)//size for k,v in strata.items()}
    for k in sorted(strata,key=lambda k:(-(n*len(strata[k])%size),k))[:n-sum(quota.values())]:quota[k]+=1
    rows=[];summary=[]
    for industry in sorted(strata):
        ordered=sorted(strata[industry],key=lambda firm:hashlib.sha256(f'{seed}:{firm}'.encode()).hexdigest())
        chosen=ordered[:quota[industry]]
        summary.append({'industry_snapshot':industry,'frame_firms':len(ordered),'selected_firms':len(chosen)})
        for firm in chosen:
            years=[int(x[:4]) for x in origins[firm]]
            rows.append({'firm_id':firm,'industry_snapshot':industry,'origins':origins[firm],
                         'reports_start':f'{min(years)-6}-01-01','reports_end_exclusive':f'{max(years)+1}-05-01'})
    return {'version':'finite-cohort-v1','seed':seed,'target_firm_years':target,
            'status':'frozen_collection_cohort_not_final_analytical_sample',
            'selection':'Proportional industry strata, largest-remainder firm quotas, SHA256 seed:firm_id ranking',
            'industry_basis':'Available exchange snapshot for collection stratification only; financial-sector and industry eligibility must be checked at each origin. Unknown classifications and delisted firms are retained where the source frame includes them.',
            'limitation':'The historical source frame remains incomplete. This is not a claim of representative coverage of all historical A-share firms.',
            'stopping_rule':'Process only these firms and windows. Retain all eligible selected firm-years; no outcome-dependent replacement or exact-count quota.',
            'source_hashes':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [market_path,issuer_path]},
            'candidate_frame_sha256':hashlib.sha256(json.dumps(dict(sorted(origins.items())),sort_keys=True).encode()).hexdigest(),
            'frame_firms':size,'frame_firm_years':potential,'selected_firms':len(rows),
            'selected_candidate_firm_years':sum(len(r['origins']) for r in rows),
            'strata':summary,'firms':sorted(rows,key=lambda r:r['firm_id'])}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'configs/collection_cohort.json');a=p.parse_args()
    if a.output.exists():raise SystemExit('Frozen cohort already exists; do not silently redraw')
    data=select(ROOT);a.output.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({k:data[k] for k in ['frame_firms','frame_firm_years','selected_firms','selected_candidate_firm_years']}))
