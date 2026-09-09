"""Collect historical annual-report metadata with verified CNINFO pagination.

CNINFO returns page 1 again for page numbers above 100. Date ranges are
therefore bisected until every request needs at most 100 pages. The resulting
company-year frame remains subject to listing, industry and data checks.
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

URL = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.cninfo.com.cn/',
           'Content-Type': 'application/x-www-form-urlencoded'}


def get_page(start, end, page, cache):
    if not 1 <= page <= 100:
        raise ValueError('CNINFO pagination limit: narrow the date range')
    payload = dict(pageNum=str(page), pageSize='30', column='szse',
                   tabName='fulltext', stock='', searchkey='', secid='', plate='',
                   category='category_ndbg_szsh;', trade='', seDate=f'{start}~{end}',
                   sortName='time', sortType='asc', isHLtitle='false')
    path = cache / f'{start}_{end}_{page:03d}.json'
    if path.exists():
        raw = path.read_bytes()
    else:
        request = urllib.request.Request(URL, data=urllib.parse.urlencode(payload).encode(), headers=HEADERS)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=25) as response:
                    raw = response.read()
                data = json.loads(raw)
                if 'announcements' not in data or not isinstance(data.get('totalAnnouncement'), int):
                    raise ValueError('Unexpected announcement response')
                temp = path.with_suffix('.tmp'); temp.write_bytes(raw); temp.replace(path)
                break
            except Exception:
                if attempt == 2: raise
                time.sleep(1 + attempt)
        time.sleep(0.15)
    data = json.loads(raw)
    return start, end, page, data, hashlib.sha256(raw).hexdigest()


def plan_range(start, end, cache):
    first = get_page(start, end, 1, cache)
    total = first[3]['totalAnnouncement']
    if total <= 3000:
        return [first], [(start, end, p) for p in range(2, (total+29)//30 + 1)]
    lo, hi = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if lo == hi:
        raise ValueError(f'More than 3000 announcements on {start}; exchange partition required')
    mid = lo + (hi-lo)//2
    left, ljobs = plan_range(start, mid.isoformat(), cache)
    right, rjobs = plan_range((mid+dt.timedelta(days=1)).isoformat(), end, cache)
    return left+right, ljobs+rjobs


def write_index(results, output):
    temp = output.with_suffix('.building.sqlite')
    if temp.exists(): temp.unlink()
    con = sqlite3.connect(temp)
    con.executescript('''
    CREATE TABLE query_pages(
      start TEXT, end TEXT, page INTEGER, total_records INTEGER,
      returned_records INTEGER, response_sha256 TEXT, PRIMARY KEY(start,end,page));
    CREATE TABLE disclosures(
      document_id TEXT, stock_code TEXT, org_id TEXT, source_title TEXT,
      report_title TEXT, fiscal_year INTEGER, disclosed_date TEXT, url TEXT,
      report_kind TEXT, PRIMARY KEY(document_id,stock_code));
    CREATE TABLE page_documents(
      start TEXT, end TEXT, page INTEGER, document_id TEXT, stock_code TEXT,
      PRIMARY KEY(start,end,page,document_id,stock_code));
    CREATE TABLE candidate_origins(
      firm_id TEXT, origin TEXT, status TEXT NOT NULL, PRIMARY KEY(firm_id,origin));
    ''')
    tz = dt.timezone(dt.timedelta(hours=8))
    for start, end, page, data, digest in results:
        records = data['announcements'] or []
        con.execute('INSERT INTO query_pages VALUES (?,?,?,?,?,?)',
                    (start,end,page,data['totalAnnouncement'],len(records),digest))
        for row in records:
            code = row['secCode']; title = re.sub('<[^>]*>', '', row['announcementTitle'])
            match = re.search(r'(20\d{2})\s*\u5e74?\s*\u5e74\u5ea6\u62a5\u544a', title)
            fiscal = int(match[1]) if match else None
            kind = 'other'
            if match:
                kind = 'full_annual_report'
                if any(s in title for s in ['\u6458\u8981','\u82f1\u6587','\u8bf4\u660e','\u53d6\u6d88','\u66f4\u6b63\u516c\u544a','\u4fee\u8ba2\u516c\u544a']):
                    kind = 'summary_or_notice'
            date = dt.datetime.fromtimestamp(row['announcementTime']/1000, tz).date().isoformat()
            if not start <= date <= end:
                raise ValueError('Announcement falls outside requested dates')
            english = f'{fiscal} Annual Report' if kind == 'full_annual_report' else 'Annual Reporting Disclosure'
            con.execute('INSERT OR REPLACE INTO disclosures VALUES (?,?,?,?,?,?,?,?,?)',
                        (row['announcementId'],code,row.get('orgId'),title,english,fiscal,
                         date,'https://static.cninfo.com.cn/'+row['adjunctUrl'],kind))
            con.execute('INSERT OR IGNORE INTO page_documents VALUES (?,?,?,?,?)',
                        (start,end,page,row['announcementId'],code))
    summaries = []
    for start,end in con.execute('SELECT DISTINCT start,end FROM query_pages ORDER BY start'):
        pages,min_total,max_total,count = con.execute(
            'SELECT COUNT(*),MIN(total_records),MAX(total_records),SUM(returned_records) FROM query_pages WHERE start=? AND end=?', (start,end)).fetchone()
        unique = con.execute('SELECT COUNT(*) FROM (SELECT DISTINCT document_id,stock_code FROM page_documents WHERE start=? AND end=?)',(start,end)).fetchone()[0]
        complete = pages == max(1,(max_total+29)//30) and min_total == max_total == count == unique
        summaries.append(dict(start=start,end=end,pages=pages,expected_records=max_total,
                              records=count,unique_records=unique,pagination_complete=complete))
    candidates = []
    for code,fiscal in con.execute("SELECT DISTINCT stock_code,fiscal_year FROM disclosures WHERE report_kind='full_annual_report' AND CAST(substr(disclosed_date,1,4) AS INTEGER)=fiscal_year+1"):
        if re.fullmatch(r'(?:00[0-3]|30[01]|60[0135]|688)\d{3}',code):
            candidates.append((code+('.SH' if code.startswith('6') else '.SZ'),f'{fiscal+1}-05-01',
                               'listing_industry_baseline_features_and_followup_pending'))
    con.executemany('INSERT INTO candidate_origins VALUES (?,?,?)',sorted(candidates))
    con.commit()
    result = dict(ranges=summaries,disclosure_records=con.execute('SELECT COUNT(*) FROM disclosures').fetchone()[0],
                  candidate_origins=len(candidates),candidate_firms=len({c[0] for c in candidates}),
                  analytical_eligible=0,scope='Historical annual-report disclosure index; not a complete exchange membership register.')
    con.close(); temp.replace(output)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--years',nargs='+',type=int,default=list(range(2017,2026)))
    parser.add_argument('--cache',type=Path,default=Path('data/query_cache/annual_ranges'))
    parser.add_argument('--output',type=Path,default=Path('data/derived/disclosures.sqlite'))
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args();args.cache.mkdir(parents=True,exist_ok=True);args.output.parent.mkdir(parents=True,exist_ok=True)
    results=[];errors=[];jobs=[]
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        first={pool.submit(plan_range,f'{y}-01-01',f'{y}-04-30',args.cache):y for y in args.years}
        for future in cf.as_completed(first):
            try:
                pages,planned=future.result();results.extend(pages);jobs.extend(planned)
                print(json.dumps(dict(year=first[future],ranges=len(pages),remaining_pages=len(planned))),flush=True)
            except Exception as exc: errors.append(dict(year=first[future],error=str(exc)))
        futures={pool.submit(get_page,s,e,p,args.cache):(s,e,p) for s,e,p in jobs}
        for i,future in enumerate(cf.as_completed(futures),1):
            try: results.append(future.result())
            except Exception as exc: errors.append(dict(query=futures[future],error=str(exc)))
            if i%100==0:
                print(json.dumps(dict(completed_pages=len(results),pending=len(jobs)-i,errors=len(errors))),flush=True)
                write_index(sorted(results,key=lambda x:x[:3]),args.output)
    result=write_index(sorted(results,key=lambda x:x[:3]),args.output);result['errors']=errors
    args.output.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    if errors or not all(y['pagination_complete'] for y in result['ranges']):
        raise SystemExit('Incomplete collection; cached pages retained for retry.')

if __name__=='__main__': main()
