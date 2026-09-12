"""Verified adapter for the compact representation; full source manifest is archived unchanged."""
import hashlib,json
from pathlib import Path

def load_frozen(root):
    root=Path(root)
    registry=json.loads((root/'file_manifest.json').read_text())
    for name,digest in registry.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Package hash mismatch: '+name)
    m=json.loads((root/'evidence/frozen_manifest.json').read_text())
    audit=json.loads((root/'evidence/representation_audit.json').read_text())
    if m['dataset_sha256']!=audit['source_dataset_sha256']:
        raise ValueError('Source dataset identity mismatch')
    records=[json.loads(line) for line in (root/'data/model_inputs.jsonl').read_text().splitlines()]
    if len(records)!=843 or len({r['sample_id'] for r in records})!=843:
        raise ValueError('Sample keys/count mismatch')
    for split,(n,p) in {'train':(503,9),'validation':(124,2),'test':(216,11)}.items():
        part=[r for r in records if r['split']==split]
        if len(part)!=n or sum(r['label'] for r in part)!=p:raise ValueError('Split mismatch')
    for r in records:
        # Original chunks() removes whitespace, splits at 256 characters, and
        # only subsamples if >16 chunks. Rejoining these <=16 selected chunks
        # therefore gives exactly the original ordered chunks (audited on 843/843).
        # text_sha256 remains the FULL SOURCE text hash, not this reconstructed string.
        r['text']=''.join(r['text_chunks'])
    m['limitations']=m['limitations']+['Training input loaded from verified compact selected chunks; complete source MD&A is archived at the source commit.']
    return m,records
