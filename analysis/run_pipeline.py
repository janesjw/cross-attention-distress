"""Resumable disclosure extraction and explicit analytical readiness checks."""
import argparse, hashlib, json, os, re, sqlite3, tempfile, time, urllib.request, zipfile
from pathlib import Path
from datetime import datetime, timezone
import fitz

ROOT=Path(__file__).resolve().parents[1]
LABELS=('资产总计','负债合计','流动资产合计','流动负债合计','应收账款','存货','营业收入','营业总收入','营业成本','管理费用','利息费用','利润总额','净利润','现金流量净额','股东权益合计')

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=True,indent=2)+'\n');tmp.replace(path)

def candidates(root):
    archive=root/'data/raw/filing_sources.zip'
    if not archive.exists():
        return json.loads((root/'data/derived/report_batch.json').read_text())['reports']
    manifest=json.loads((root/'file_manifest.json').read_text())
    if digest(archive)!=manifest['data/raw/filing_sources.zip']:raise ValueError('Filing archive digest mismatch')
    rows=[]
    with zipfile.ZipFile(archive) as z, tempfile.TemporaryDirectory() as tmp:
        for name in z.namelist():
            if not name.endswith('/derived/filings.sqlite'):continue
            db=Path(tmp)/'index.sqlite';db.write_bytes(z.read(name))
            with sqlite3.connect(db) as con:
                con.row_factory=sqlite3.Row
                rows.extend(dict(r) for r in con.execute("SELECT * FROM filings WHERE report_kind IN ('annual_report','interim_report','quarterly_report')"))
    if not rows:raise ValueError('No periodic reports in source archive')
    return rows

def extract(path,meta):
    pages=[];hits=[]
    with fitz.open(path) as doc:
        if doc.is_encrypted:raise ValueError('Encrypted PDF requires review')
        for i,page in enumerate(doc):
            text=page.get_text(sort=True);pages.append({'page':i+1,'text':text})
            lines=text.splitlines()
            for j,line in enumerate(lines):
                compact=re.sub(r'\s+','',line)
                if any(label in compact for label in LABELS):
                    hits.append({'page':i+1,'line':j+1,'context':'\n'.join(lines[max(0,j-2):j+7]),'status':'needs_scope_unit_period_review'})
    chars=sum(len(p['text'].strip()) for p in pages)
    return {'source':meta,'pdf_sha256':digest(path),'pdf_bytes':path.stat().st_size,
            'pages':pages,'financial_candidates':hits,'text_characters':chars,
            'review_status':'needs_financial_and_section_review' if chars>=100 else 'needs_ocr',
            'analytical_verified':False}

def readiness(root):
    protocol=json.loads((root/'configs/protocol.json').read_text());reasons=list(protocol['pending_before_full_dataset'])
    db=root/'data/derived/distress.sqlite'
    with sqlite3.connect(f'file:{db}?mode=ro',uri=True) as con:
        if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Analysis database integrity failure')
        eligible=con.execute('SELECT COUNT(*) FROM sample_register WHERE analytical_eligible=1').fetchone()[0]
        if not eligible:reasons.append('No eligible analytical samples')
        texts=con.execute("SELECT COUNT(*) FROM text_sections WHERE verification='verified'").fetchone()[0]
        if not texts:reasons.append('No verified annual text sections')
    manifest=root/'data/derived/frozen_dataset.json'
    if not manifest.exists():reasons.append('No registered frozen dataset manifest')
    return {'eligible_samples':eligible,'verified_text_sections':texts,'training_candidate':not reasons,'blocking_reasons':reasons}

def run(root,limit,minutes):
    directory=root/'data/automation';statepath=directory/'progress.json'
    state=json.loads(statepath.read_text()) if statepath.exists() else {'schema_version':1,'documents':{}}
    queue=candidates(root)
    queue=[r for r in queue if not re.search('英文|摘要',r['source_title'])]
    queue.sort(key=lambda r:(r['firm_id'],r['disclosed_date'],r['document_id']))
    unique={};[unique.setdefault(r['document_id'],r) for r in queue];queue=list(unique.values())
    started=time.monotonic();processed=0;errors=0
    for row in queue:
        key=row['document_id']
        if not re.fullmatch(r'\d+',key):raise ValueError('Invalid source document ID')
        previous=state['documents'].get(key,{})
        if previous.get('status')=='extracted':
            p=root/previous['extraction_path']
            if p.exists() and digest(p)==previous['extraction_sha256']:continue
            previous={}
        if previous.get('attempts',0)>=3:continue
        if processed>=limit or time.monotonic()-started>minutes*60:break
        processed+=1;attempts=previous.get('attempts',0)+1
        try:
            url=row['url']
            if not re.fullmatch(r'https://static\.cninfo\.com\.cn/finalpage/[0-9-]+/[0-9]+\.PDF',url):raise ValueError('Unexpected source URL')
            pdf=root/'data/automation_downloads'/f'{key}.pdf';pdf.parent.mkdir(parents=True,exist_ok=True)
            with urllib.request.urlopen(url,timeout=40) as response:
                with pdf.open('wb') as out:
                    size=0
                    while chunk:=response.read(1024*1024):
                        size+=len(chunk)
                        if size>80*1024*1024:raise ValueError('PDF exceeds 80 MiB limit; review separately')
                        out.write(chunk)
            if not pdf.read_bytes()[:5]==b'%PDF-':raise ValueError('Response is not a PDF')
            expected=next((d['sha256'] for d in json.loads((root/'data/raw/records.json').read_text())['documents'] if d['document_id']==key),None)
            if expected and digest(pdf)!=expected:raise ValueError('Registered source hash changed')
            result=extract(pdf,row);dest=directory/'extracted'/f'{key}.zip';dest.parent.mkdir(parents=True,exist_ok=True)
            with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('pages.json',json.dumps(result,ensure_ascii=True))
            with zipfile.ZipFile(dest) as z:
                if z.testzip() is not None:raise ValueError('Extraction archive integrity failure')
            state['documents'][key]={'status':'extracted','attempts':attempts,'firm_id':row['firm_id'],
                'extraction_path':dest.relative_to(root).as_posix(),'extraction_sha256':digest(dest),
                'pdf_sha256':result['pdf_sha256'],'pages':len(result['pages']),
                'financial_candidates':len(result['financial_candidates']),'review_status':result['review_status']}
        except Exception as exc:
            errors+=1;state['documents'][key]={'status':'retry_pending' if attempts<3 else 'needs_review','attempts':attempts,'firm_id':row['firm_id'],'error':f'{type(exc).__name__}: {exc}'[:500]}
        save(statepath,state)
        print(json.dumps({'document_id':key,**state['documents'][key]}),flush=True)
    status={'updated_at':datetime.now(timezone.utc).isoformat(),'queue_documents':len(queue),
        'extracted_documents':sum(r['status']=='extracted' for r in state['documents'].values()),
        'failed_documents':sum(r['status']!='extracted' for r in state['documents'].values()),
        'attempted_this_run':processed,'errors_this_run':errors,**readiness(root)}
    save(directory/'status.json',status)
    manifest=json.loads((root/'file_manifest.json').read_text())
    for path in directory.rglob('*'):
        if path.is_file():manifest[path.relative_to(root).as_posix()]=digest(path)
    save(root/'file_manifest.json',dict(sorted(manifest.items())))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('ready='+str(status['training_candidate']).lower()+'\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
            f.write('## Pipeline status\n\n```json\n'+json.dumps(status,indent=2)+'\n```\n')
    print(json.dumps(status,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=25);p.add_argument('--minutes',type=int,default=25);a=p.parse_args()
    if not 1<=a.limit<=100 or not 1<=a.minutes<=25:raise SystemExit('Limit must be 1..100; minutes 1..25')
    run(ROOT,a.limit,a.minutes)
