"""Preserve successful and incomplete collection outputs without approving samples."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def archive(root,output):
    files=sorted(p for p in root.rglob('*') if p.is_file())
    if not files:raise ValueError('No collected sources to preserve')
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.tmp.zip')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for file in files:z.write(file,file.relative_to(root))
    if temp.stat().st_size>95_000_000:
        raise ValueError('Source archive exceeds repository file budget; retain workflow artifacts')
    temp.replace(output)
    manifest_path=Path('file_manifest.json');manifest=json.loads(manifest_path.read_text())
    for path in [output,Path('data/derived/filing_summary.json'),Path('data/derived/report_batch.json')]:
        if path.exists():manifest[path.as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(dict(sorted(manifest.items())),indent=2)+'\n')
    print(json.dumps(dict(files=len(files),archive=str(output),bytes=output.stat().st_size)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args();archive(a.root,a.output)
