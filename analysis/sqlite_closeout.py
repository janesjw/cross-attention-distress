"""Read-only closeout checks; prints evidence without artifact storage."""
import sqlite3,json,pathlib,hashlib
root=pathlib.Path('.')
outputs=[]
registry=json.loads((root/'file_manifest.json').read_text())
for p in (root/'data/derived').glob('*.sqlite'):
    con=sqlite3.connect(f'file:{p}?mode=ro',uri=True)
    tables=[x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    outputs.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'matches_file_manifest':hashlib.sha256(p.read_bytes()).hexdigest()==registry[str(p)],'integrity':con.execute('PRAGMA integrity_check').fetchall(),'foreign_key_errors':con.execute('PRAGMA foreign_key_check').fetchall(),'tables':{t:con.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0] for t in tables}})
    con.close()
with sqlite3.connect('file:data/derived/distress.sqlite?mode=ro',uri=True) as con:
    frozen=[json.loads(x) for x in pathlib.Path('data/derived/annual_st/frozen_samples.jsonl').read_text().splitlines()]
    candidate={x[0] for x in con.execute('SELECT candidate_id FROM candidate_register')}
    linkage={'frozen_sample_count':len(frozen),'linked_candidate_ids':sum(x['sample_id'] in candidate for x in frozen),'annual_training_uses':'immutable JSONL; not legacy sample_register','legacy_eligible_count':con.execute('SELECT COUNT(*) FROM sample_register WHERE analytical_eligible=1').fetchone()[0]}
    assert linkage['linked_candidate_ids']==len(frozen)
print('CLOSEOUT_SQLITE_JSON='+json.dumps({'databases':outputs,'linkage':linkage},sort_keys=True))
assert outputs and all(x['integrity']==[('ok',)] and not x['foreign_key_errors'] and x['matches_file_manifest'] for x in outputs)
