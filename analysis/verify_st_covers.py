"""Corroborate positive exchange-name ST screens with pre-origin Q1 covers."""
import concurrent.futures as cf,hashlib,json,re,sqlite3,tempfile,urllib.request,zipfile
from pathlib import Path
import fitz
ROOT=Path(__file__).resolve().parents[1]
def main():
    cohort=json.loads((ROOT/'configs/collection_cohort.json').read_text());ids={f['firm_id'] for f in cohort['firms']}
    with sqlite3.connect(ROOT/'data/derived/distress.sqlite') as con:
        targets=[dict(sample_id=sid,firm_id=f,origin=o) for sid,f,o in con.execute('SELECT candidate_id,firm_id,origin FROM candidate_register WHERE baseline_st_from_name=1') if f in ids]
    filings=[]
    with zipfile.ZipFile(ROOT/'data/raw/filing_sources.zip') as z,tempfile.TemporaryDirectory() as tmp:
        for name in z.namelist():
            if not name.endswith('/derived/filings.sqlite'):continue
            db=Path(tmp)/'index.sqlite';db.write_bytes(z.read(name))
            with sqlite3.connect(db) as con:
                con.row_factory=sqlite3.Row
                filings.extend(dict(r) for r in con.execute("SELECT * FROM filings WHERE report_kind='quarterly_report'"))
    def verify(t):
        year=t['origin'][:4]
        choices=[r for r in filings if r['firm_id']==t['firm_id'] and r['disclosed_date']<t['origin'] and r['disclosed_date']>=year+'-01-01' and year in r['source_title'] and re.search('第一季度|一季度',r['source_title']) and '英文' not in r['source_title']]
        if not choices:return t['sample_id'],dict(status='no_preorigin_q1_report')
        source=max(choices,key=lambda x:(x['disclosed_date'],x['document_id']))
        result=dict(url=source['url'],public_date=source['disclosed_date'],document_id=source['document_id'])
        try:
            with urllib.request.urlopen(source['url'],timeout=35) as r:raw=r.read()
            snippets=[]
            with fitz.open(stream=raw,filetype='pdf') as doc:
                for i in range(min(3,len(doc))):
                    for line in doc[i].get_text(sort=True).splitlines():
                        if re.search('股票简称|证券简称',line):snippets.append(dict(page=i+1,text=line.strip()))
            matches=[s for s in snippets if re.search(r'(?:股票|证券)简称\s*[：:]?\s*[*＊]?\s*ST',s['text'],re.I)]
            # A positive cover observation corroborates the independently reconstructed name history.
            result.update(status='st_cover_confirmed' if matches else 'cover_requires_review',sha256=hashlib.sha256(raw).hexdigest(),evidence=matches or snippets)
        except Exception as exc:result.update(status='download_failed',error=str(exc))
        return t['sample_id'],result
    path=ROOT/'data/derived/st_cover_evidence.json';results=json.loads(path.read_text()) if path.exists() else {}
    pending=[t for t in targets if results.get(t['sample_id'],{}).get('status')!='st_cover_confirmed']
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        for sid,result in pool.map(verify,pending):
            results[sid]=result;path.write_text(json.dumps(results,ensure_ascii=True,indent=2)+'\n')
            print(json.dumps(dict(sample_id=sid,status=result['status'])),flush=True)
if __name__=='__main__':main()
