"""Load the explicitly versioned annual study; retain original trainer interface."""
import gzip,hashlib,json
from pathlib import Path

def load_frozen(root):
 root=Path(root);m=json.loads((root/'evidence/candidate_manifest.json').read_text());compressed=(root/'data/model_inputs.jsonl.gz').read_bytes()
 if hashlib.sha256(compressed).hexdigest()!=m['compressed_sha256']:raise ValueError('Compressed input hash mismatch')
 raw=gzip.decompress(compressed)
 if hashlib.sha256(raw).hexdigest()!=m['dataset_sha256']:raise ValueError('Input hash mismatch')
 rows=[json.loads(x) for x in raw.splitlines()]
 if len(rows)!=969 or len({r['sample_id'] for r in rows})!=969:raise ValueError('Unexpected sample keys')
 for sp,(n,p) in {'train':(503,9),'validation':(250,6),'test':(216,11)}.items():
  q=[r for r in rows if r['split']==sp]
  if len(q)!=n or sum(r['label'] for r in q)!=p:raise ValueError('Split mismatch')
 for r in rows:r['text']=''.join(r['text_chunks'])
 return m,rows
