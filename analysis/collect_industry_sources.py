"""Download official historical industry tables and inspect table extraction."""
import hashlib,json,re,urllib.request,urllib.parse,zipfile
from pathlib import Path
import fitz
SOURCES=[
(2017,"2016Q4","2017-02-21","https://www.capco.org.cn/xhgg/hyfl/hyfljg/201909/20190904/j_2019090416011700015675841291298181.html"),
(2018,"2017Q4","2018-01-19","https://www.csrc.gov.cn/csrc/c100103/c1452004/content.shtml"),
(2019,"2019Q1","2019-04-19","https://www.csrc.gov.cn/csrc/c100103/c1451999/content.shtml"),
(2020,"2020Q1","2020-04-14","https://www.csrc.gov.cn/csrc/c100103/c1451995/content.shtml"),
(2021,"2021Q1","2021-04-14","https://www.csrc.gov.cn/csrc/c100103/c29a6845e0d0b4912adcc1cdfa5f679eb/content.shtml"),
(2022,"2021Q3","2021-11-10","https://www.csrc.gov.cn/csrc/c100103/c1558619/content.shtml"),
(2024,"2023H2","2024-04-03","https://www.capco.org.cn/xhgg/hyfl/hyfljg/202404/20240403/j_2024040315552200017121310425305369.html"),
(2025,"2024H2","2025-04-18","https://www.capco.org.cn/xhgg/hyfl/hyfljg/202504/20250418/j_2025041815003000017449597508305299.html")]
root=Path("data/raw/industry");root.mkdir(parents=True,exist_ok=True)
results=[]
for year,period,public,page_url in SOURCES:
    result=dict(origin_year=year,period=period,public_date=public,page_url=page_url)
    try:
        req=urllib.request.Request(page_url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=30) as r:html=r.read()
        (root/f"{year}.html").write_bytes(html)
        decoded=html.decode("utf-8",errors="replace")
        links=re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',decoded,re.I)
        if not links:raise ValueError("No PDF links found")
        # Prefer the code-sorted table when the official page offers both orders.
        links.sort(key=lambda x:("股票代码" not in urllib.parse.unquote(x),x))
        link=urllib.parse.urljoin(page_url,links[0])
        parsed=urllib.parse.urlsplit(link)
        link=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,urllib.parse.quote(urllib.parse.unquote(parsed.path),safe="/"),parsed.query,""))
        with urllib.request.urlopen(link,timeout=45) as r:raw=r.read()
        pdf=root/f"{year}.pdf";pdf.write_bytes(raw)
        tables=[];preview=[]
        with fitz.open(pdf) as doc:
            for i,p in enumerate(doc):
                if i<2:preview.append(p.get_text(sort=True)[:3500])
                for t in p.find_tables().tables:
                    tables.extend({"page":i+1,"cells":row} for row in t.extract())
        payload={"tables":tables,"preview":preview}
        out=root/f"{year}_tables.json";out.write_text(json.dumps(payload,ensure_ascii=True))
        result.update(url=link,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),table_rows=len(tables),preview=preview,status="downloaded_tables_pending_validation")
    except Exception as exc:result.update(status="failed",error=f"{type(exc).__name__}: {exc}")
    results.append(result)
    print(json.dumps({k:v for k,v in result.items() if k!="preview"}),flush=True)
Path("data/derived/industry_source_status.json").write_text(json.dumps(results,ensure_ascii=True,indent=2)+"\n")
manifest=json.loads(Path("file_manifest.json").read_text())
for p in list(root.glob("*"))+[Path("data/derived/industry_source_status.json")]:
    manifest[p.as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
Path("file_manifest.json").write_text(json.dumps(dict(sorted(manifest.items())),indent=2)+"\n")
