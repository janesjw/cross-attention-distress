"""Reconstruct the registered ST endpoint from audited official SZSE exports.

Source assumption: the unfiltered official short-name register is complete for
ST/*ST name transitions. Count and pagination reconciliation establish export
completeness, not the absence of errors in the exchange's underlying register.
"""
from collections import Counter, defaultdict
import csv
from datetime import date, timedelta
import hashlib
import html
import io
import json
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE='data/raw/szse_register_20260910.zip'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def sha(b):return hashlib.sha256(b).hexdigest()
def norm(s):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(s))).upper()
def is_st(s):return int(bool(re.match(r'^(?:S\*?ST|\*?ST)',norm(s))))


def xlsx_rows(data):
    """Read original string/number cells; never trust worksheet dimensions."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(si.itertext()) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        rows=[]
        for row in sheet.findall('.//m:sheetData/m:row',NS):
            values={}
            for cell in row.findall('m:c',NS):
                if cell.find('m:f',NS) is not None:raise ValueError('Unexpected formula in source export')
                letters=re.match(r'[A-Z]+',cell.attrib['r'])[0]
                index=0
                for c in letters:index=index*26+ord(c)-64
                v=cell.find('m:v',NS)
                text='' if v is None else (v.text or '')
                if cell.attrib.get('t')=='s':text=shared[int(text)]
                elif cell.attrib.get('t')=='inlineStr':text=''.join(cell.find('m:is',NS).itertext())
                values[index-1]=text
            rows.append([values.get(i,'') for i in range(max(values,default=-1)+1)])
    header=rows[0]
    return [(i,dict(zip(header,r+['']*(len(header)-len(r))))) for i,r in enumerate(rows[1:],2)]


def read_sources(root):
    raw=(root/SOURCE).read_bytes();manifest=json.loads((root/'file_manifest.json').read_text())
    if sha(raw)!=manifest[SOURCE]:raise ValueError('Register archive hash mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        provenance=json.loads(z.read('sources.json'))
        bodies={name:z.read(name) for name in provenance['sources']}
    for name,meta in provenance['sources'].items():
        if sha(bodies[name])!=meta['sha256'] or len(bodies[name])!=meta['bytes']:raise ValueError('Source digest mismatch')
        if not meta['url'].startswith('https://www.szse.cn/api/report/ShowReport'):raise ValueError('Unexpected source host')
    rows=xlsx_rows(bodies['names.xlsx'])
    expected_header={'变更日期','证券代码','证券简称','变更前简称','变更后简称'}
    if set(rows[0][1])!=expected_header:raise ValueError('Name-register schema changed')
    controls=[]
    for filename in ('names_first.json','names_middle.json','names_last.json'):
        tab=next(t for t in json.loads(bodies[filename]) if t['metadata']['tabkey']=='tab2')
        meta=tab['metadata']
        if tab.get('error') is not None or meta['recordcount']!=len(rows):raise ValueError('Truncated or inconsistent register')
        if any(c.get('defaultValue') not in ('',None) for c in meta['conditions']):raise ValueError('Filtered source register')
        start=(meta['pageno']-1)*meta['pagesize']
        fields=['变更日期','证券代码','证券简称','变更前简称','变更后简称']
        keys=['bgrq','zqdm','zqjc','bgqzqjc','bghzqjc']
        actual=[[html.unescape(r[k]).replace('\u00a0',' ') for k in keys] for r in tab['data']]
        expected=[[r[f] for f in fields] for _,r in rows[start:start+meta['pagesize']]]
        if actual!=expected:raise ValueError('API/XLSX row mismatch')
        controls.append({'page':meta['pageno'],'rows_checked':len(actual),'total_rows':meta['recordcount']})
    if len({tuple(r.values()) for _,r in rows})!=len(rows):raise ValueError('Duplicate source row')
    changes=defaultdict(list)
    for idx,r in rows:
        date.fromisoformat(r['变更日期'])
        code=r['证券代码']
        if re.fullmatch(r'(?:00\d|30\d)\d{3}',code):
            changes[code+'.SZ'].append({'effective_date':r['变更日期'],'before':r['变更前简称'],
                                       'after':r['变更后简称'],'source_row':idx})
    listings=defaultdict(list)
    for filename,fields,kind in [('listed.xlsx',('A股代码','A股简称','A股上市日期',None),'listed'),
                                 ('delisted.xlsx',('证券代码','证券简称','上市日期','终止上市日期'),'delisted')]:
        for idx,r in xlsx_rows(bodies[filename]):
            code=r[fields[0]]
            if re.fullmatch(r'(?:00\d|30\d)\d{3}',code):
                listings[code+'.SZ'].append({'name':r[fields[1]],'listing_date':r[fields[2]],
                    'delisting_date':r[fields[3]] if fields[3] else None,'status':kind,
                    'source_file':filename,'source_row':idx})
    return listings,changes,{'archive_sha256':sha(raw),'retrieved_date':provenance['retrieved_date'],
        'name_register_records':len(rows),'api_export_controls':controls,'sources':provenance['sources']}


def company_review(listings,changes):
    issues=[]
    if len(listings)!=1:return {'issues':['listing_identity_conflict_or_absence']}
    listing=listings[0]
    for field in ('listing_date','delisting_date'):
        if listing[field] is not None:date.fromisoformat(listing[field])
    if listing['delisting_date'] and listing['delisting_date']<=listing['listing_date']:issues.append('invalid_listing_interval')
    changes=sorted(changes,key=lambda r:(r['effective_date'],r['source_row']))
    if len({r['effective_date'] for r in changes})!=len(changes):issues.append('same_day_changes')
    if any(norm(a['after'])!=norm(b['before']) for a,b in zip(changes,changes[1:])):issues.append('broken_full_name_chain')
    if changes and norm(changes[-1]['after'])!=norm(listing['name']):issues.append('terminal_name_mismatch')
    if listing['status']=='delisted' and not changes:issues.append('delisted_name_history_absent')
    return {'listing':listing,'changes':changes,'issues':issues}


def classify(review,origin,end,source_end):
    result={'membership':'unresolved','baseline_ST':None,'registry_label':None,
            'label_available_date':None,'event_date':None,'event_source_row':None,'status':'unresolved'}
    if review['issues']:result['reason']=';'.join(review['issues']);return result
    if origin>source_end:result['reason']='origin_after_source_snapshot';return result
    l=review['listing'];changes=review['changes'];delisted=l['delisting_date']
    if not (l['listing_date']<=origin and (not delisted or origin<delisted)):
        result.update(membership='excluded',status='excluded',reason='not_listed_at_origin');return result
    result['membership']='verified_listing_interval'
    before=[r for r in changes if r['effective_date']<=origin]
    name=before[-1]['after'] if before else changes[0]['before'] if changes else l['name']
    result['baseline_ST']=is_st(name)
    if result['baseline_ST']:
        result.update(status='excluded',reason='ST_at_origin');return result
    events=[r for r in changes if origin<r['effective_date']<end and not is_st(r['before']) and is_st(r['after'])
            and (not delisted or r['effective_date']<delisted) and r['effective_date']<=source_end]
    if events:
        event=events[0]
        result.update(registry_label=1,label_available_date=event['effective_date'],event_date=event['effective_date'],
                      event_source_row=event['source_row'],status='verified_registry_endpoint',reason='new_ST_name_transition')
    elif source_end<end:
        result['reason']='source_does_not_cover_followup_end'
    elif delisted and delisted<end:
        result.update(status='right_censored',reason='delisted_before_followup_end_without_observed_ST')
    else:
        result.update(registry_label=0,label_available_date=str(date.fromisoformat(end)-timedelta(days=1)),
                      status='verified_registry_endpoint',reason='complete_export_no_new_ST_transition')
    return result


def run(root=ROOT):
    root=Path(root);scope=json.loads((root/'configs/simplified_cohort.json').read_text())
    listings,changes,provenance=read_sources(root)
    # Independently compare the selected history with the prior day's normalized archive.
    old=json.loads((root/'data/raw/market_records.json').read_text())
    manifest=json.loads((root/'file_manifest.json').read_text())
    if sha((root/'data/raw/market_records.json').read_bytes())!=manifest['data/raw/market_records.json']:raise ValueError('Prior snapshot hash mismatch')
    old_changes=defaultdict(list)
    for r in old['name_changes']:old_changes[r['firm_id']].append((r['effective_date'],norm(r['name_before']),norm(r['name_after'])))
    reviews={};records=[];counts=Counter();splits=defaultdict(Counter)
    protocol=json.loads((root/'configs/simplified_protocol.json').read_text())
    for firm in scope['firms']:
        fid=firm['firm_id'];review=company_review(listings[fid],changes[fid])
        new=sorted((r['effective_date'],norm(r['before']),norm(r['after'])) for r in changes[fid])
        if new!=sorted(old_changes[fid]):review['issues'].append('selected_history_changed_between_snapshots_requires_review')
        reviews[fid]=review
        for origin in firm['origins']:
            y=int(origin[:4]);end=f'{y+1}-05-01'
            row={'sample_id':f'{fid}:{y}','firm_id':fid,'origin':origin,'followup_end_exclusive':end,
                 **classify(review,origin,end,provenance['retrieved_date'])}
            records.append(row);counts[row['status']]+=1
            if row['registry_label'] is not None:counts['positive' if row['registry_label'] else 'negative']+=1
            split=next(s for s,(a,b) in protocol['split_years'].items() if a<=y<=b)
            splits[split][row['status']]+=1
            if row['registry_label'] is not None:splits[split]['positive' if row['registry_label'] else 'negative']+=1
    output=root/'data/verification/annual_st';output.mkdir(parents=True,exist_ok=True)
    summary={'status':'official_register_audit_completed','candidate_firms':len(reviews),'candidate_firm_years':len(records),
             'company_chain_pass':sum(not r['issues'] for r in reviews.values()),'counts':dict(counts),
             'splits':{k:dict(v) for k,v in splits.items()},'provenance':provenance,
             'source_assumption':'Unfiltered SZSE short-name register is complete for ST/*ST name transitions. Export row counts, first/middle/last API pages, full name chains, terminal names and prior-snapshot agreement are checked. These controls cannot prove the underlying registry contains no omissions.',
             'scope':'Registered ST endpoint only. Historical industry, annual financial/text certification and analytical sample eligibility are separate.'}
    files={'register_review.json':summary,'company_evidence.json':reviews}
    for name,payload in files.items():(output/name).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    with (output/'labels.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    for p in output.iterdir():manifest[p.relative_to(root).as_posix()]=sha(p.read_bytes())
    (root/'file_manifest.json').write_text(json.dumps(dict(sorted(manifest.items())),indent=2)+'\n')
    return summary


if __name__=='__main__':print(json.dumps(run(),indent=2))
