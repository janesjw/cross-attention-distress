"""Register explicitly reviewed, source-hashed evidence; never certify a sample."""
import argparse
import hashlib
import json
import re
import sqlite3
import zipfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compact(text):
    return re.sub(r'\s+', '', text)


def insert_identical(con, table, row, keys):
    old = con.execute(f'SELECT * FROM {table} WHERE ' + ' AND '.join(k+'=?' for k in keys),
                      [row[k] for k in keys]).fetchone()
    if old is not None:
        if any(old[k] != v for k, v in row.items()):
            raise ValueError('Conflicting registered evidence: '+table)
        return
    con.execute(f'INSERT INTO {table} ({",".join(row)}) VALUES ({",".join("?" for _ in row)})', list(row.values()))


def apply_reviewed(root=ROOT):
    root = Path(root)
    files = sorted((root/'data/verification/reviewed').glob('*.json'))
    cohort = {r['firm_id'] for r in json.loads((root/'configs/collection_cohort.json').read_text())['firms']}
    manifest = json.loads((root/'file_manifest.json').read_text())
    con = sqlite3.connect(root/'data/derived/distress.sqlite')
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    output_texts = {}
    totals = dict(reviewed_documents=0, reviewed_facts=0, reviewed_text_sections=0)
    try:
        with con:
            for path in files:
                pack = json.loads(path.read_text())
                if pack['review_method'] != 'source_pdf_visual_and_text_review_v1':
                    raise ValueError('Unsupported review method')
                source = pack['source']
                fid, did = source['firm_id'], source['document_id']
                if fid not in cohort or not re.fullmatch(r'\d+', did):
                    raise ValueError('Evidence outside collection cohort')
                rel = f'data/automation/extracted/{did}.zip'
                data = (root/rel).read_bytes()
                if sha(data) != pack['extraction_sha256'] or sha(data) != manifest[rel]:
                    raise ValueError('Extraction hash mismatch')
                with zipfile.ZipFile(root/rel) as z:
                    raw = json.loads(z.read('pages.json'))
                if raw['source'] != source or raw['pdf_sha256'] != pack['pdf_sha256']:
                    raise ValueError('Source identity mismatch')
                pages = {p['page']: p['text'] for p in raw['pages']}
                if len(pages) != len(raw['pages']):
                    raise ValueError('Duplicate page index')
                if not con.execute('SELECT 1 FROM firms WHERE firm_id=?', (fid,)).fetchone():
                    listing = con.execute('SELECT * FROM listing_records WHERE firm_id=?', (fid,)).fetchone()
                    if listing is None:
                        raise ValueError('Missing listing record')
                    con.execute('INSERT INTO firms (firm_id,name,exchange,cninfo_org_id,universe_status) VALUES (?,?,?,?,?)',
                                (fid,pack['issuer_name'],listing['exchange'],source['org_id'],'coverage_pending'))
                doc = dict(document_id=did,firm_id=fid,title=source['source_title'],
                    disclosed_date=source['disclosed_date'],url=source['url'],sha256=raw['pdf_sha256'],
                    bytes=raw['pdf_bytes'],pages=len(pages),version_kind=pack['version_kind'],
                    cache_path=f'data/automation_downloads/{did}.pdf',time_precision='date',verification='verified')
                insert_identical(con,'documents',doc,['document_id'])
                for item in pack['facts']:
                    row = item['record']
                    if row['document_id'] != did or row['firm_id'] != fid or row['verification'] != 'verified':
                        raise ValueError('Fact identity mismatch')
                    if compact(item['source_line']) not in compact(pages[row['page']]):
                        raise ValueError('Fact source anchor mismatch')
                    values=re.findall(r'(?<!\d)-?\d{1,3}(?:,\d{3})+(?:\.\d+)?',item['source_line'])
                    col=item['source_column']
                    if col not in (1,2) or len(values)!=2 or Decimal(values[col-1].replace(',','')) != Decimal(row['raw_value']):
                        raise ValueError('Fact value does not match reviewed source column')
                    if Decimal(row['raw_value'])*Decimal(row['multiplier'])*row['sign_adjustment'] != Decimal(row['value_normalized']):
                        raise ValueError('Unit conversion mismatch')
                    if row['period_end'] > source['disclosed_date']:
                        raise ValueError('Period after disclosure')
                    insert_identical(con,'facts',row,['fact_id'])
                if pack.get('audit'):
                    audit = pack['audit']
                    if compact(audit['source_line']) not in compact(pages[audit['record']['page']]):
                        raise ValueError('Audit anchor mismatch')
                    insert_identical(con,'audit_opinions',audit['record'],['document_id'])
                if pack.get('text_section'):
                    section = pack['text_section']
                    start,end=section['page_start'],section['page_end']
                    if not (1 <= start <= end < len(pages)):
                        raise ValueError('Invalid section bounds')
                    if compact(section['start_heading']) not in compact(pages[start]) or compact(section['next_heading']) not in compact(pages[end+1]):
                        raise ValueError('Text section boundary mismatch')
                    text='\n\n'.join(pages[p] for p in range(start,end+1))+'\n'
                    if sha(text.encode()) != section['text_sha256']:
                        raise ValueError('Text content mismatch')
                    text_rel=f'data/verified_text/{did}_mda.txt'
                    output_texts[root/text_rel]=text
                    row=dict(section_id=f'{did}:mda',document_id=did,section_name='management_discussion_and_analysis',
                             page_start=start,page_end=end,text_sha256=section['text_sha256'],text_path=text_rel,verification='verified')
                    insert_identical(con,'text_sections',row,['section_id'])
                    totals['reviewed_text_sections']+=1
                totals['reviewed_documents']+=1
                totals['reviewed_facts']+=len(pack['facts'])
            # This reviewed case resolves only two baseline components. It is not
            # an eligible observation and has no assigned future outcome.
            fid='000012.SZ'
            profit=con.execute("SELECT value_normalized FROM facts WHERE fact_id=?",
                               ('1219854723:net_profit:2024-03-31:consolidated',)).fetchone()
            audit=con.execute("SELECT opinion FROM audit_opinions WHERE document_id='1219823600'").fetchone()
            if profit and Decimal(profit[0])>0 and audit and audit[0]=='standard_unqualified':
                sid=f'{fid}:2024'
                if not con.execute('SELECT 1 FROM sample_register WHERE sample_id=?',(sid,)).fetchone():
                    con.execute('INSERT INTO sample_register VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (sid,fid,'2024-05-01','2025-05-01',None,0,0,'unresolved','pending_collection',None,None,'unresolved',0,
                         'Reviewed Q1 consolidated profit positive and standard FY2023 audit. ST history, inputs and future outcome unresolved.'))
                    for criterion,did,note in [
                        ('quarter','1219854723','Q1 net profit 317932830 CNY > 0; therefore Q4/Q1 joint negative-profit-and-OCF condition is false regardless of Q4.'),
                        ('audit_loss','1219823600','FY2023 financial-statement opinion standard unqualified; nonstandard-opinion-and-loss condition is false.')]:
                        con.execute('INSERT INTO sample_evidence VALUES (?,?,?,?,?,?,?)',
                                    (sid,'baseline',criterion,'verified_absent',did,None,note))
                    for criterion in ['ST','quarter','audit_loss']:
                        con.execute('INSERT INTO coverage VALUES (?,?,?,?,?,?)',
                                    (sid,criterion,'2024-05-01','2025-05-01','unresolved','Follow-up has not been certified.'))
            if con.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Foreign-key failure')
        for path,text in output_texts.items():
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(text,encoding='utf-8')
        totals['eligible_samples']=con.execute('SELECT COUNT(*) FROM sample_register WHERE analytical_eligible=1').fetchone()[0]
        totals['status']='partial_source_registration_not_sample_freeze'
        totals['remaining']='Historical membership, ST coverage, quarter comparability, complete feature histories and future outcomes remain unresolved.'
        status=root/'data/verification/status.json'
        status.write_text(json.dumps(totals,indent=2)+'\n')
    finally:
        con.close()
    for p in [root/'data/derived/distress.sqlite',root/'data/verification/status.json',*files,*output_texts]:
        manifest[p.relative_to(root).as_posix()]=sha(p.read_bytes())
    (root/'file_manifest.json').write_text(json.dumps(dict(sorted(manifest.items())),indent=2)+'\n')
    return totals


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    print(json.dumps(apply_reviewed(parser.parse_args().root),indent=2))
