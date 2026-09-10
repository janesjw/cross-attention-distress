"""Source-anchored, rule-based audit of annual inputs; not a human review."""
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
from .annual_st import annual_matches, annual_features, mda_candidate

VERSION = 'annual-input-rules-v2'
NEEDED = {'assets','liabilities','equity','current_assets','current_liabilities',
          'inventory','receivables','revenue','net_profit','operating_profit',
          'management_expense','ocf'}


def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def audit(raw, parsed):
    issues=[]; source=raw['source']
    year=int(parsed['period_end_candidate'][:4]) if parsed.get('period_end_candidate') else 0
    cover='\n'.join(p['text'] for p in raw['pages'][:15])
    if not year or not annual_matches(source,f'{year+1}-05-01'):issues.append('annual_period_or_cutoff')
    if source['firm_id'][:6] not in cover:issues.append('stock_code_not_in_front_matter')
    if not re.search(rf'{year}\s*年\s*年?度报告',cover):issues.append('annual_year_not_in_front_matter')
    if parsed['pdf_sha256']!=raw['pdf_sha256'] or parsed['source']!=source:issues.append('source_identity')
    if not re.fullmatch(r'[0-9a-f]{64}',raw['pdf_sha256']):issues.append('invalid_pdf_hash')
    periods={}
    for kind in ('balance','income','cashflow'):
        headers=parsed['headers'].get(kind,[])
        # Require the actual table header, never infer column order from report title.
        lines=[''.join(x['text'].split()) for x in headers]
        dates=rf'{year}年12月31日.*(?:{year-1}年12月31日|{year}年0?1月0?1日)'
        annual=rf'{year}年度?.*{year-1}年度?'
        matching=[s for s in lines if '项目' in s and re.search(dates if kind=='balance' else annual,s)]
        if not matching and parsed.get('statement_block'):
            # Explicit dated balance sheet within the annual statements block
            # disambiguates standard current/prior column labels.
            balance_header=''.join(x['text'] for x in parsed['headers'].get('balance',[]))
            dated_balance=re.search(rf'{year}年12月31日',''.join(balance_header.split())) is not None
            generic=(r'(?:项目|资产).*期末余额.*(?:期初余额|上年年末余额)' if kind=='balance' else r'项目.*本期(?:发生额|金额).*上期(?:发生额|金额)')
            matching=[line for line in lines if dated_balance and re.search(generic,line)]
        if len(matching)!=1:issues.append(kind+':current_comparative_header')
        else:periods[kind]=matching[0]
        if any(s.startswith(kind+':statement_count:') or s.startswith(kind+':unit_') for s in parsed['issues']):
            issues.append(kind+':scope_or_unit_or_duplicate_statement')
    rows={r['metric']:r for r in parsed['rows']}
    for metric in sorted(NEEDED):
        if metric not in rows:issues.append('missing_required_row:'+metric)
    # These three identities are essential. Attribution is an additional check
    # when both printed components exist; blanks are never changed to zero.
    checks={(c['name'],c['column']):c['status'] for c in parsed['checks']}
    for name in ('balance_identity','profit_after_tax','operating_cashflow'):
        for col in (1,2):
            if checks.get((name,col))!='pass':issues.append(f'{name}:column{col}')
    if any(c['status']=='fail' for c in parsed['checks']):issues.append('accounting_identity_failed')
    page_map={p['page']:p['text'].splitlines() for p in raw['pages']}
    for r in parsed['rows']:
        lines=page_map.get(r['page'],[]);n=len(r['source_line'].splitlines())
        anchor='\n'.join(s.strip() for s in lines[r['line']-1:r['line']-1+n])
        if anchor!=r['source_line']:issues.append('row_anchor_mismatch:'+r['metric'])
    values={m:Decimal(r['values'][0]) for m,r in rows.items()}
    features=annual_features(values)
    # Missing ratios only from known zero denominators can pass the registered
    # <=3 rule; an uncollected required source row cannot pass by imputation.
    if sum(v is None for v in features)>3:issues.append('too_many_missing_ratios')
    financial_ok=not issues
    text=mda_candidate(raw)
    text_issues=[]
    if text is None:text_issues.append('ambiguous_mda_boundaries')
    elif len(re.sub(r'\s+','',text['text']))<1000:text_issues.append('mda_too_short_for_automatic_acceptance')
    if issues and any(x in issues for x in ('annual_period_or_cutoff','stock_code_not_in_front_matter','annual_year_not_in_front_matter','source_identity')):
        text_issues.append('document_identity_or_period')
    return {'method':VERSION,'verification_tier':'rule_based_source_checks_not_manual_review',
            'source':source,'pdf_sha256':raw['pdf_sha256'],'financial_pass':financial_ok,
            'text_pass':not text_issues,'features':features if financial_ok else None,
            'text':text if not text_issues else None,'issues':issues,'text_issues':text_issues,
            'period_headers':periods,'accounting_checks':parsed['checks'],
            'statement_block':parsed.get('statement_block'),'row_evidence':[r for r in parsed['rows'] if r['metric'] in NEEDED]}


def parse_annual(raw, parse):
    """Bound annual statements before company/accounting notes, preserving
    physical page and line coordinates. Ambiguous boundaries stay unresolved."""
    import copy
    positions=[(p['page'],i,line) for p in raw['pages'] for i,line in enumerate(p['text'].splitlines())]
    compact=lambda line:re.sub(r'\s+','',line)
    starts=[i for i,(_,_,line) in enumerate(positions) if re.fullmatch(r'二[、．.]财务报表',compact(line))]
    if len(starts)!=1:return parse(raw)
    start=starts[0]
    ends=[i for i,(_,_,line) in enumerate(positions) if i>start and re.fullmatch(r'(?:三[、．.]公司基本情况|[一三][、．.]财务报表附注)',compact(line))]
    if not ends:return parse(raw)
    end=ends[0];allowed={(p,i) for p,i,_ in positions[start:end]};bounded=copy.deepcopy(raw)
    for p in bounded['pages']:
        p['text']='\n'.join(line if (p['page'],i) in allowed else '' for i,line in enumerate(p['text'].splitlines()))
    result=parse(bounded)
    result['statement_block']={'page_start':positions[start][0],'page_end':positions[end][0],
                              'start_heading':positions[start][2],'end_heading':positions[end][2]}
    return result


def run(root):
    root=Path(root);sys.path.insert(0,str(root/'analysis'))
    from structure_financials import parse
    from run_pipeline import candidates
    manifest=json.loads((root/'file_manifest.json').read_text())
    scope=json.loads((root/'configs/simplified_cohort.json').read_text())
    queue=candidates(root);byfirm={}
    for s in queue:byfirm.setdefault(s['firm_id'],[]).append(s)
    selection={}; docs={}
    for firm in scope['firms']:
        for origin in firm['origins']:
            sid=f'{firm["firm_id"]}:{origin[:4]}'
            eligible={s['document_id']:s for s in byfirm.get(firm['firm_id'],[]) if annual_matches(s,origin)}
            latest=max((s['disclosed_date'] for s in eligible.values()),default=None)
            choices=[s for s in eligible.values() if s['disclosed_date']==latest]
            selection[sid]={'document_id':choices[0]['document_id'] if len(choices)==1 else None,
                'status':'selected_latest_indexed_preorigin' if len(choices)==1 else ('ambiguous_latest_version' if choices else 'no_indexed_preorigin_report')}
            if len(choices)==1:docs[choices[0]['document_id']]=choices[0]
    packets={};counts=Counter();issues=Counter()
    for did,expected in sorted(docs.items()):
        path=root/f'data/automation/extracted/{did}.zip'
        if not path.exists():counts['selected_not_downloaded']+=1;continue
        if digest(path)!=manifest.get(path.relative_to(root).as_posix()):raise ValueError('Archive hash mismatch '+did)
        with zipfile.ZipFile(path) as z:raw=json.loads(z.read('pages.json'))
        for key in ('document_id','firm_id','source_title','disclosed_date','url'):
            if raw['source'].get(key)!=expected.get(key):raise ValueError('Filing-index identity mismatch '+did+' '+key)
        p=audit(raw,parse_annual(raw,parse));p['extraction_sha256']=digest(path)
        packets[did]=p;counts['audited_documents']+=1
        counts['financial_pass']+=p['financial_pass'];counts['text_pass']+=p['text_pass']
        counts['both_pass']+=p['financial_pass'] and p['text_pass']
        issues.update(p['issues']+p['text_issues'])
    out=root/'data/verification/annual_st';out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out/'input_audit.zip','w',zipfile.ZIP_DEFLATED) as z:
        for did,p in packets.items():
            info=zipfile.ZipInfo(did+'.json',(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,json.dumps(p,ensure_ascii=False,sort_keys=True))
    status={'method':VERSION,'counts':dict(counts),'issue_counts':dict(issues),
            'scope':'Latest indexed preorigin reports; rule-based checks, not manual review or a frozen dataset.',
            'limitations':['PDF extraction errors can survive internal checks.','Source/index completeness is assumed within the registered filing archive.','Missing or ambiguous cases remain unresolved.']}
    (out/'input_audit_status.json').write_text(json.dumps(status,indent=2)+'\n')
    (out/'source_selection.json').write_text(json.dumps(selection,sort_keys=True,indent=2)+'\n')
    for name in ('input_audit.zip','input_audit_status.json','source_selection.json'):
        p=out/name;manifest[p.relative_to(root).as_posix()]=digest(p)
    (root/'file_manifest.json').write_text(json.dumps(dict(sorted(manifest.items())),indent=2)+'\n')
    return status
