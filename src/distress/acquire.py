"""Read-only CNINFO acquisition with cached query responses and full pagination."""
import datetime as dt
import hashlib,json,re,time
from pathlib import Path
import urllib.parse,urllib.request

HEADERS={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}

def fetch(request):
    last=None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request,timeout=45) as response:return response.read()
        except Exception as exc:
            last=exc
            if attempt<2:time.sleep(attempt+1)
    raise last

def query(stock,org,start,end,output,keyword='',category=''):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    records=[];seen=set();page=1
    while True:
        payload={'pageNum':str(page),'pageSize':'50','column':'szse','tabName':'fulltext',
          'stock':f'{stock},{org}','searchkey':keyword,'secid':'','plate':'','trade':'','category':category,
          'seDate':f'{start}~{end}','sortName':'time','sortType':'asc','isHLtitle':'false'}
        signature=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:16]
        path=output/f'query_{signature}.json'
        if path.exists():data=json.loads(path.read_text())
        else:
            request=urllib.request.Request('https://www.cninfo.com.cn/new/hisAnnouncement/query',
                data=urllib.parse.urlencode(payload).encode(),headers={**HEADERS,'Content-Type':'application/x-www-form-urlencoded'})
            data=json.loads(fetch(request));path.write_text(json.dumps(data,ensure_ascii=False,indent=2))
        if 'announcements' not in data or 'hasMore' not in data:raise ValueError('Unexpected CNINFO response, not an empty dataset')
        for a in data['announcements'] or []:
            if a['secCode']!=stock:continue
            identity=a['announcementId']
            if identity in seen:continue
            seen.add(identity)
            date=dt.datetime.fromtimestamp(a['announcementTime']/1000,dt.timezone(dt.timedelta(hours=8))).date().isoformat()
            records.append({'document_id':identity,'stock':stock,'title':re.sub('<[^>]*>','',a['announcementTitle']),
              'disclosed_date':date,'url':'https://static.cninfo.com.cn/'+a['adjunctUrl'],
              'query_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'review_status':'metadata_only'})
        if not data['hasMore']:break
        page+=1
        if page>1000:raise RuntimeError('Pagination exceeds bound; narrow date range. No completeness claim.')
    manifest={'query':payload,'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),
              'pages':page,'records':records,'interpretation':'Search metadata only; no-hit keyword search does not establish non-distress.'}
    out=output/f'manifest_{stock}_{start}_{end}_{hashlib.sha256((keyword+category).encode()).hexdigest()[:8]}.json'
    out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2));return out

def download_verified(documents,root):
    root=Path(root);result=[]
    for doc in documents:
        path=root/doc['cache_path'];path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            raw=fetch(urllib.request.Request(doc['url'],headers=HEADERS))
            if hashlib.sha256(raw).hexdigest()!=doc['sha256']:raise ValueError('Source bytes changed: '+doc['document_id'])
            temp=path.with_suffix('.tmp');temp.write_bytes(raw);temp.replace(path)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=doc['sha256']:raise ValueError('Cache digest mismatch: '+str(path))
        result.append({'document_id':doc['document_id'],'sha256':digest})
    return result

def extract_section(con,root,document_id,name,start,end):
    """Candidate extraction only. PDF page boundaries do not prove tables/headers were removed."""
    import fitz
    doc=con.execute('SELECT * FROM documents WHERE document_id=?',(document_id,)).fetchone()
    if doc is None:raise ValueError('Document not registered')
    root=Path(root);pdf=root/doc['cache_path']
    if hashlib.sha256(pdf.read_bytes()).hexdigest()!=doc['sha256']:raise ValueError('PDF digest mismatch')
    source=fitz.open(pdf)
    if not 1<=start<=end<=len(source):raise ValueError('Invalid PDF page range')
    text='\n'.join(source[i].get_text() for i in range(start-1,end))
    relative=f'data/text/{document_id}_{start}_{end}.txt';target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
    raw=text.encode();digest=hashlib.sha256(raw).hexdigest()
    if target.exists() and target.read_bytes()!=raw:raise ValueError('Do not overwrite edited section')
    target.write_bytes(raw)
    sid=f'{document_id}:{name}:{start}-{end}'
    con.execute('INSERT INTO text_sections VALUES (?,?,?,?,?,?,?,?)',
      (sid,document_id,name,start,end,digest,relative,'candidate_requires_semantic_review'));con.commit()
    return {'section_id':sid,'sha256':digest,'status':'candidate_requires_semantic_review'}
