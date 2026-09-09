"""Restore one saved collection bucket so completed issuers are not requested again."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def restore(archive,bucket,root=Path('.')):
    if not archive.exists():
        print(json.dumps(dict(restored=False,reason='No previous archive')));return
    manifest=json.loads((root/'file_manifest.json').read_text())
    expected=manifest.get(archive.relative_to(root).as_posix())
    if not expected or hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
        raise ValueError('Saved source archive hash mismatch')
    prefix=f'filings-{bucket}/';restored=0
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if not item.filename.startswith(prefix) or item.is_dir():continue
            relative=Path(item.filename[len(prefix):])
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('Invalid archive path')
            if relative.parts[0] not in ('derived','query_cache'):continue
            target=root/'data'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():raise FileExistsError(target)
            with z.open(item) as source,target.open('wb') as dest:shutil.copyfileobj(source,dest)
            restored+=1
    print(json.dumps(dict(restored=True,bucket=bucket,files=restored)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,default=Path('data/raw/filing_sources.zip'));p.add_argument('--bucket',type=int,required=True);a=p.parse_args();restore(a.archive,a.bucket)
