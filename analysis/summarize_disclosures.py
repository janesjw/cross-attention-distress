"""Summarize preserved source collection and prepare the next PDF-processing batch."""
import argparse
import json
from pathlib import Path
import re
import sqlite3


def summarize(root,output,batch_output):
    summaries=[];reports=[];errors=[];seen=set()
    for path in sorted(root.glob('filings-*/derived/filings.sqlite')):
        con=sqlite3.connect(path);con.row_factory=sqlite3.Row
        if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Corrupt filing index')
        rows=con.execute('SELECT * FROM collection_status').fetchall()
        if seen.intersection(r['firm_id'] for r in rows):raise ValueError('Issuer appears in multiple buckets')
        seen.update(r['firm_id'] for r in rows)
        complete=sum(r['status']=='complete_periodic_disclosure_query' for r in rows)
        summaries.append(dict(bucket=path.parts[-3],issuers=len(rows),complete=complete,filings=con.execute('SELECT COUNT(*) FROM filings').fetchone()[0]))
        errors.extend(dict(r) for r in rows if r['status']!='complete_periodic_disclosure_query')
        reports.extend(dict(r) for r in con.execute("SELECT * FROM filings WHERE report_kind IN ('annual_report','interim_report','quarterly_report')"))
        con.close()
    if len(summaries)!=8:raise ValueError('All eight collection buckets are required')
    expected=len(json.loads(Path('data/raw/disclosure_firms.json').read_text())['firms'])
    result=dict(expected_issuers=expected,registered_issuers=len(seen),complete_issuers=sum(r['complete'] for r in summaries),
                filings=sum(r['filings'] for r in summaries),buckets=summaries,incomplete=errors,
                formal_sample_ready=False,training_completed=False)
    output.write_text(json.dumps(result,indent=2)+'\n')
    market=json.loads(Path('data/raw/market_records.json').read_text())
    industries={r['firm_id']:r['industry_code_snapshot'] for r in market['listings']}
    existing={r['document_id'] for r in json.loads(Path('data/raw/records.json').read_text())['documents']}
    reports=[r for r in reports if r['document_id'] not in existing and not re.search(r'\u82f1\u6587|\u82f1\u6587\u7248|\u6458\u8981',r['source_title'])]
    reports.sort(key=lambda r:(industries.get(r['firm_id'])=='J',r['firm_id'],r['disclosed_date'],r['document_id']))
    batch_output.write_text(json.dumps(dict(purpose='PDF processing queue only; does not select the analytical sample',reports=reports[:256]),ensure_ascii=True,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('buckets','incomplete')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();summarize(a.root,Path('data/derived/filing_summary.json'),Path('data/derived/report_batch.json'))
