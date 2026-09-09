"""Normalize the preserved exchange downloads using only the Python standard library."""
import argparse
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


def sheet_rows(raw):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(io.BytesIO(raw)) as book:
        root=ET.fromstring(book.read('xl/worksheets/sheet1.xml'))
    headers=None
    for row in root.findall('s:sheetData/s:row',ns):
        cells={}
        for cell in row.findall('s:c',ns):
            col=re.sub(r'\d','',cell.attrib['r'])
            value=''.join(cell.itertext()) if cell.attrib.get('t')=='inlineStr' else cell.findtext('s:v',default='',namespaces=ns)
            cells[col]=value
        if headers is None:headers=cells;continue
        yield int(row.attrib['r']),{name:cells.get(col,'') for col,name in headers.items()}


def clean(value):
    return str(value).strip() if value is not None and str(value).strip() not in ('','-') else None


def date(value):
    value=clean(value)
    if value and len(value)==8:return dt.datetime.strptime(value,'%Y%m%d').date().isoformat()
    return value


def normalize(archive):
    listings=[];changes=[]
    with zipfile.ZipFile(archive) as z:
        sources=json.loads(z.read('sources.json'))
        for source in sources:
            raw=z.read(source['source_id']+'.'+source['format'])
            if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('Source hash mismatch')
        for source in ['sz_listed','sz_delisted']:
            for rowno,r in sheet_rows(z.read(source+'.xlsx')):
                code=clean(r['A\u80a1\u4ee3\u7801'] if source=='sz_listed' else r['\u8bc1\u5238\u4ee3\u7801'])
                if not code or not re.fullmatch(r'(?:00\d|30\d)\d{3}',code):continue
                listings.append(dict(firm_id=code+'.SZ',exchange='SZSE',source_id=source,source_row=rowno,
                    name_en=clean(r.get('\u82f1\u6587\u540d\u79f0')),name_original=clean(r['A\u80a1\u7b80\u79f0'] if source=='sz_listed' else r['\u8bc1\u5238\u7b80\u79f0']),
                    listing_date=date(r['A\u80a1\u4e0a\u5e02\u65e5\u671f'] if source=='sz_listed' else r['\u4e0a\u5e02\u65e5\u671f']),
                    delisting_date=date(r.get('\u7ec8\u6b62\u4e0a\u5e02\u65e5\u671f')),industry_code_snapshot=(clean(r.get('\u6240\u5c5e\u884c\u4e1a')) or '')[:1] or None,
                    snapshot_status='listed' if source=='sz_listed' else 'delisted'))
        for source in ['sh_listed','sh_listed_page2','sh_delisted']:
            data=json.loads(z.read(source+'.json'))
            for i,r in enumerate(data['result']):
                code=r['A_STOCK_CODE']
                if not re.fullmatch(r'6\d{5}',code):raise ValueError('Unexpected SSE A-share code')
                listings.append(dict(firm_id=code+'.SH',exchange='SSE',source_id=source,source_row=i+1,
                    name_en=clean(r['FULL_NAME_IN_ENGLISH']),name_original=clean(r['COMPANY_ABBR']),listing_date=date(r['LIST_DATE']),
                    delisting_date=date(r['DELIST_DATE']),industry_code_snapshot=clean(r['CSRC_CODE']),snapshot_status='delisted' if source=='sh_delisted' else 'listed'))
        for rowno,r in sheet_rows(z.read('sz_names.xlsx')):
            code=clean(r['\u8bc1\u5238\u4ee3\u7801'])
            if not re.fullmatch(r'(?:00\d|30\d)\d{3}',code):continue
            before=clean(r['\u53d8\u66f4\u524d\u7b80\u79f0']);after=clean(r['\u53d8\u66f4\u540e\u7b80\u79f0'])
            changes.append(dict(firm_id=code+'.SZ',effective_date=date(r['\u53d8\u66f4\u65e5\u671f']),name_before=before,name_after=after,
                st_before=int('ST' in re.sub(r'\s+','',before).upper()),st_after=int('ST' in re.sub(r'\s+','',after).upper()),source_id='sz_names',source_row=rowno))
    return dict(sources=sources,listings=listings,name_changes=changes)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,default=Path('data/raw/market_sources.zip'));parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.write_text(json.dumps(normalize(args.archive),ensure_ascii=True,indent=2)+'\n')
