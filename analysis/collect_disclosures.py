"""Collect complete, single-page CNINFO queries for an outcome-independent firm list.

All annual, interim and quarterly disclosures are retained. Date ranges split
when a firm has more than 30 hits, avoiding unstable cross-page ordering.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import urllib.parse
import urllib.request

URL='https://www.cninfo.com.cn/new/hisAnnouncement/query'
HEADERS={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/',
         'Content-Type':'application/x-www-form-urlencoded'}
CATEGORY='category_ndbg_szsh;category_bndbg_szsh;category_yjdbg_szsh;category_sjdbg_szsh;'


def get_query(firm,start,end,cache,category=CATEGORY):
    payload=dict(pageNum='1',pageSize='30',column='szse',tabName='fulltext',
                 stock=firm['stock_code']+','+firm['org_id'],searchkey='',secid='',
                 plate='',category=category,trade='',seDate=f'{start}~{end}',
                 sortName='time',sortType='asc',isHLtitle='false')
    suffix="" if category==CATEGORY else "_"+hashlib.sha256(category.encode()).hexdigest()[:12]
    path=cache/f"{firm['firm_id']}_{start}_{end}{suffix}.json"
    if path.exists(): raw=path.read_bytes()
    else:
        req=urllib.request.Request(URL,data=urllib.parse.urlencode(payload).encode(),headers=HEADERS)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req,timeout=25) as response:raw=response.read()
                data=json.loads(raw)
                if 'announcements' not in data or not isinstance(data.get('totalAnnouncement'),int):
                    raise ValueError('Unexpected CNINFO response')
                tmp=path.with_suffix('.tmp');tmp.write_bytes(raw);tmp.replace(path)
                break
            except Exception:
                if attempt==3:raise
                time.sleep([5,15,45][attempt])
        time.sleep(0.2)
    data=json.loads(raw)
    return data,hashlib.sha256(raw).hexdigest()


def collect_firm(firm,start,end,cache,category=CATEGORY):
    data,digest=get_query(firm,start,end,cache,category)
    total=data['totalAnnouncement']
    if total>30:
        lo,hi=dt.date.fromisoformat(start),dt.date.fromisoformat(end)
        if lo==hi:
            if category!=CATEGORY:
                raise ValueError(f'More than 30 reports on {start} in {category}; further source review required')
            ranges=[]
            for part in CATEGORY.strip(';').split(';'):
                ranges.extend(collect_firm(firm,start,end,cache,part+';'))
            identities={r['announcementId'] for item in ranges for r in item[3]}
            if len(identities)!=total:
                raise ValueError(f'Category union does not reconcile on {start}: {len(identities)} != {total}')
            return ranges
        mid=lo+(hi-lo)//2
        return collect_firm(firm,start,mid.isoformat(),cache,category)+collect_firm(firm,(mid+dt.timedelta(days=1)).isoformat(),end,cache,category)
    rows=data['announcements'] or []
    if len(rows)!=total or data.get('hasMore'):
        raise ValueError('Single-page query is incomplete')
    for row in rows:
        if row.get('orgId')!=firm['org_id']:
            raise ValueError('Query returned a different issuer')
    return [(firm,start,end,rows,digest,category)]


def initialize(path):
    con=sqlite3.connect(path)
    con.executescript('''
    CREATE TABLE IF NOT EXISTS query_ranges(
      firm_id TEXT, start TEXT, end TEXT, response_sha256 TEXT, returned_records INTEGER,
      PRIMARY KEY(firm_id,start,end));
    CREATE TABLE IF NOT EXISTS filings(
      document_id TEXT, firm_id TEXT, source_stock_code TEXT, org_id TEXT,
      source_title TEXT, disclosed_date TEXT, url TEXT, report_kind TEXT,
      PRIMARY KEY(document_id,firm_id));
    CREATE TABLE IF NOT EXISTS collection_status(
      firm_id TEXT PRIMARY KEY, start TEXT, end TEXT, status TEXT, error TEXT);
    ''')
    con.execute("""CREATE TABLE IF NOT EXISTS query_partitions(
      firm_id TEXT, start TEXT, end TEXT, category TEXT, response_sha256 TEXT,
      returned_records INTEGER, PRIMARY KEY(firm_id,start,end,category))""")
    return con


def save_firm(con,firm,start,end,ranges):
    tz=dt.timezone(dt.timedelta(hours=8))
    with con:
        for _,lo,hi,rows,digest,category in ranges:
            con.execute('INSERT OR REPLACE INTO query_partitions VALUES (?,?,?,?,?,?)',
                        (firm['firm_id'],lo,hi,category,digest,len(rows)))
            if category==CATEGORY:
                con.execute('INSERT OR REPLACE INTO query_ranges VALUES (?,?,?,?,?)',
                            (firm['firm_id'],lo,hi,digest,len(rows)))
            for r in rows:
                date=dt.datetime.fromtimestamp(r['announcementTime']/1000,tz).date().isoformat()
                if not lo<=date<=hi:raise ValueError('Disclosure date outside query window')
                title=re.sub('<[^>]*>','',r['announcementTitle'])
                kind='periodic_disclosure'
                if '\u6458\u8981' in title:kind='summary'
                elif '\u516c\u544a' in title or '\u8bf4\u660e' in title:kind='periodic_notice'
                elif '\u534a\u5e74\u5ea6\u62a5\u544a' in title:kind='interim_report'
                elif '\u5e74\u5ea6\u62a5\u544a' in title:kind='annual_report'
                elif '\u5b63\u5ea6\u62a5\u544a' in title:kind='quarterly_report'
                con.execute('INSERT OR REPLACE INTO filings VALUES (?,?,?,?,?,?,?,?)',
                            (r['announcementId'],firm['firm_id'],r['secCode'],r['orgId'],title,date,
                             'https://static.cninfo.com.cn/'+r['adjunctUrl'],kind))
        con.execute('INSERT OR REPLACE INTO collection_status VALUES (?,?,?,?,?)',
                    (firm['firm_id'],start,end,'complete_periodic_disclosure_query',''))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--firms',type=Path,default=Path('data/raw/disclosure_firms.json'))
    parser.add_argument('--start',default='2011-01-01')
    parser.add_argument('--end',default='2026-04-30')
    parser.add_argument('--bucket',type=int,default=0)
    parser.add_argument('--buckets',type=int,default=1)
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--cache',type=Path,default=Path('data/query_cache/firm_reports'))
    parser.add_argument('--output',type=Path,default=Path('data/derived/filings.sqlite'))
    args=parser.parse_args()
    if not 0<=args.bucket<args.buckets:raise ValueError('Invalid bucket')
    data=json.loads(args.firms.read_text())
    if data.get('unmatched_firms'):raise ValueError('Resolve issuer IDs before collection')
    firms=[f for i,f in enumerate(sorted(data['firms'],key=lambda x:x['firm_id'])) if i%args.buckets==args.bucket]
    args.cache.mkdir(parents=True,exist_ok=True);args.output.parent.mkdir(parents=True,exist_ok=True)
    con=initialize(args.output)
    done={r[0] for r in con.execute("SELECT firm_id FROM collection_status WHERE status='complete_periodic_disclosure_query' AND start=? AND end=?",(args.start,args.end))}
    pending=[f for f in firms if f['firm_id'] not in done];errors=[]
    print(json.dumps(dict(bucket=args.bucket,firms=len(firms),remaining=len(pending))),flush=True)
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(collect_firm,f,args.start,args.end,args.cache):f for f in pending}
        for i,future in enumerate(cf.as_completed(futures),1):
            firm=futures[future]
            try:save_firm(con,firm,args.start,args.end,future.result())
            except Exception as exc:
                errors.append(dict(firm_id=firm['firm_id'],error=str(exc)))
                with con:con.execute('INSERT OR REPLACE INTO collection_status VALUES (?,?,?,?,?)',
                                     (firm['firm_id'],args.start,args.end,'incomplete',str(exc)))
            if i%25==0:print(json.dumps(dict(processed=i,pending=len(pending)-i,errors=len(errors))),flush=True)
    result=dict(bucket=args.bucket,selected_firms=len(firms),
                completed_firms=con.execute("SELECT COUNT(*) FROM collection_status WHERE status='complete_periodic_disclosure_query'").fetchone()[0],
                filings=con.execute('SELECT COUNT(*) FROM filings').fetchone()[0],errors=errors,
                interpretation='Periodic disclosure metadata; financial extraction and distress labels remain separate.')
    con.close();args.output.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    if errors:raise SystemExit('Some issuers remain incomplete. Cached successful queries can be resumed.')

if __name__=='__main__':main()
