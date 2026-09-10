"""Register only predictions whose frozen dataset digest matches the manifest."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
result=json.loads((ROOT/'data/derived/annual_st/results/results.json').read_text())
frozen=json.loads((ROOT/'data/derived/annual_st/frozen_manifest.json').read_text())
if result['dataset_sha256']!=frozen['dataset_sha256']:raise ValueError('Results belong to another dataset')
summary_path=ROOT/'data/derived/filing_summary.json';summary=json.loads(summary_path.read_text())
if summary['annual_st_frozen_sample']!=frozen['summary']:raise ValueError('Summary disagrees with frozen sample')
summary['training_completed']=True
summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
m=json.loads((ROOT/'file_manifest.json').read_text())
for p in [summary_path,*list((ROOT/'data/derived/annual_st/results').iterdir())]:
    if p.is_file():m[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
(ROOT/'file_manifest.json').write_text(json.dumps(dict(sorted(m.items())),indent=2)+'\n')
