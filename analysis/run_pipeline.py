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

def restrict_queue(root,queue):
    cohort=json.loads((root/'configs/collection_cohort.json').read_text())
    allowed={r['firm_id']:r for r in cohort['firms']}
    return [r for r in queue if r['firm_id'] in allowed and
            allowed[r['firm_id']]['reports_start']<=r['disclosed_date']<allowed[r['firm_id']]['reports_end_exclusive']]

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
    decision_path=root/'data/derived/sample_decisions.json'
    decisions=json.loads(decision_path.read_text()) if decision_path.exists() else None
    return {'eligible_samples':eligible,'verified_text_sections':texts,'training_candidate':not reasons,'blocking_reasons':reasons,
            'sample_adjudication_implemented':decisions is not None,
            'sample_decisions':None if decisions is None else decisions['decisions'],
            'completion_tasks':'data/derived/sample_completion_tasks.json' if decisions is not None else None}

def process_document(root,row,attempts,expected_hash=None):
    directory=root/'data/automation';key=row['document_id']
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
        expected=expected_hash
        if expected and digest(pdf)!=expected:raise ValueError('Registered source hash changed')
        result=extract(pdf,row);dest=directory/'extracted'/f'{key}.zip';dest.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('pages.json',json.dumps(result,ensure_ascii=True))
        with zipfile.ZipFile(dest) as z:
            if z.testzip() is not None:raise ValueError('Extraction archive integrity failure')
        entry={'status':'extracted','attempts':attempts,'firm_id':row['firm_id'],
            'extraction_path':dest.relative_to(root).as_posix(),'extraction_sha256':digest(dest),
            'pdf_sha256':result['pdf_sha256'],'pages':len(result['pages']),
            'financial_candidates':len(result['financial_candidates']),'review_status':result['review_status']}
    except Exception as exc:
        entry={'status':'retry_pending' if attempts<3 else 'needs_review','attempts':attempts,'firm_id':row['firm_id'],'error':f'{type(exc).__name__}: {exc}'[:500]}
    return entry

def run(root,limit,minutes,workers=1):
    if not 1<=workers<=4 or not 1<=limit<=1000 or not 1<=minutes<=25:
        raise ValueError('workers 1..4, limit 1..1000 and minutes 1..25 required')
    directory=root/'data/automation';statepath=directory/'progress.json'
    state=json.loads(statepath.read_text()) if statepath.exists() else {'schema_version':1,'documents':{}}
    queue=restrict_queue(root,candidates(root))
    queue=[r for r in queue if not re.search('英文|摘要',r['source_title'])]
    queue.sort(key=lambda r:(r['firm_id'],r['disclosed_date'],r['document_id']))
    unique={};[unique.setdefault(r['document_id'],r) for r in queue];queue=list(unique.values())
    jobs=[]
    for row in queue:
        key=row['document_id']
        if not re.fullmatch(r'\d+',key):raise ValueError('Invalid source document ID')
        previous=state['documents'].get(key,{})
        if previous.get('status')=='extracted':
            path=root/previous['extraction_path']
            if path.exists() and digest(path)==previous['extraction_sha256']:continue
            previous={}
        if previous.get('attempts',0)<3:jobs.append((row,previous.get('attempts',0)+1))
    record_path=root/'data/raw/records.json'
    expected={d['document_id']:d['sha256'] for d in json.loads(record_path.read_text())['documents']} if record_path.exists() else {}
    deadline=time.monotonic()+minutes*60;processed=0;errors=0
    def record(row,entry):
        nonlocal processed,errors
        processed+=1;errors+=entry['status']!='extracted'
        state['documents'][row['document_id']]=entry
        save(statepath,state)
        print(json.dumps({'document_id':row['document_id'],**entry}),flush=True)
    if workers==1:
        for row,attempts in jobs[:limit]:
            if time.monotonic()>=deadline:break
            record(row,process_document(root,row,attempts,expected.get(row['document_id'])))
    else:
        # MuPDF is not thread-safe. Each worker owns its PDF and writes unique files.
        # Only the parent mutates progress, and at most `workers` jobs are in flight.
        from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
        iterator=iter(jobs[:limit]);pending={};exhausted=False
        with ProcessPoolExecutor(max_workers=workers) as pool:
            while pending or not exhausted:
                while len(pending)<workers and not exhausted and time.monotonic()<deadline:
                    job=next(iterator,None)
                    if job is None:exhausted=True;break
                    row,attempts=job
                    future=pool.submit(process_document,root,row,attempts,expected.get(row['document_id']))
                    pending[future]=(row,attempts)
                if time.monotonic()>=deadline:exhausted=True
                if not pending:break
                done,_=wait(pending,return_when=FIRST_COMPLETED)
                for future in done:
                    row,attempts=pending.pop(future)
                    try:entry=future.result()
                    except Exception as exc:
                        entry={'status':'retry_pending' if attempts<3 else 'needs_review','attempts':attempts,
                               'firm_id':row['firm_id'],'error':f'{type(exc).__name__}: {exc}'[:500]}
                    record(row,entry)
    status={'updated_at':datetime.now(timezone.utc).isoformat(),'queue_documents':len(queue),
        'extracted_documents':sum(r['status']=='extracted' for r in state['documents'].values()),
        'failed_documents':sum(r['status']!='extracted' for r in state['documents'].values()),
        'scope':'finite-cohort-v1','selected_queue_extracted':sum(state['documents'].get(r['document_id'],{}).get('status')=='extracted' for r in queue),
        'attempted_this_run':processed,'errors_this_run':errors,'workers':workers,
        'elapsed_seconds':round(minutes*60-(deadline-time.monotonic()),2),
        'automatic_verification_implemented':False,
        'next_required_stage':'Complete sample_completion_tasks with source-reviewed evidence; rerun build_samples after registration. Extraction and sample adjudication do not automatically verify missing sources.',**readiness(root)}
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
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=500)
    p.add_argument('--minutes',type=int,default=25);p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    run(ROOT,a.limit,a.minutes,a.workers)
