"""Verify the current payload and saved metrics; no training is performed."""
from pathlib import Path
import json,hashlib,runpy,csv,gzip
R=Path(__file__).resolve().parent
manifest=json.loads((R/'file_manifest.json').read_text())
for n,h in manifest.items():
 p=R/n
 assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==h,n
size=sum((R/n).stat().st_size for n in manifest)+(R/'file_manifest.json').stat().st_size
assert size<10_000_000,size
runpy.run_path(str(R/'verify_candidate.py'),run_name='__main__')
runpy.run_path(str(R/'verify_logistic.py'),run_name='__main__')
rows={r['sample_id']:r for r in map(json.loads,gzip.decompress((R/'data/model_inputs.jsonl.gz').read_bytes()).splitlines())}
for p in csv.DictReader((R/'baseline/predictions.csv').open()):
 r=rows[p['sample_id']]
 assert int(p['label'])==r['label'] and p['split']==r['split'] and p['firm_id']==r['firm_id']
for n,k in [('annual_budgets.csv',39),('validation_stress.csv',78),('preannounced_sensitivity.csv',13)]:
 assert len(list(csv.DictReader((R/'results'/n).open())))==k,n
for n,h in manifest.items():assert hashlib.sha256((R/n).read_bytes()).hexdigest()==h,n
print(f'All 26 validation/test metric groups and {len(manifest)+1} files verified; current payload {size:,} bytes.')
