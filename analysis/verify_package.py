"""Check package files, database contents, CSV views, and offline tests."""
import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from build_database import build
from import_market import normalize
from distress.database import ROOT, audit_database, connect
from import_reviewed_evidence import apply_reviewed
from distress.sample_builder import build as build_samples


def main():
    manifest = json.loads((ROOT / 'file_manifest.json').read_text())
    for name, digest in manifest.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'File hash mismatch: {name}')
    included = ROOT / 'data/derived'
    con = connect(included / 'distress.sqlite')
    try:
        result = audit_database(con)
        if con.execute("SELECT COUNT(*) FROM candidate_register WHERE firm_id LIKE '689%'").fetchone()[0]:
            raise ValueError('CDR included in A-share candidate frame')
        if not result['passed']:
            raise ValueError(result['errors'])
        metadata = dict(con.execute('SELECT key,value FROM metadata'))
        market = json.loads((ROOT / 'data/raw/market_records.json').read_text())
        if normalize(ROOT / 'data/raw/market_sources.zip') != market:
            raise ValueError('Exchange source normalization mismatch')
        for key, path in [('seed_sha256', ROOT / 'data/raw/records.json'),
                          ('protocol_sha256', ROOT / 'configs/protocol.json'),
                          ('market_sha256', ROOT / 'data/raw/market_records.json')]:
            if metadata[key] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError(f'Database input mismatch: {key}')
        with tempfile.TemporaryDirectory() as tmp:
            replay = Path(tmp)
            output = replay / 'data/derived'
            build(output)
            # These two CSVs are the original seed views, retained for recovery.
            for name in ('financials.csv', 'samples.csv'):
                if (output / name).read_bytes() != (included / name).read_bytes():
                    raise ValueError(f'CSV mismatch: {name}')
            registered_documents={r[0] for r in con.execute('SELECT document_id FROM documents')}
            packs=[]
            for path in (ROOT/'data/verification/reviewed').glob('*.json'):
                pack=json.loads(path.read_text())
                # A newly committed review may await the next ingestion job.
                # Replay every review already represented in the database.
                if pack['source']['document_id'] in registered_documents:packs.append(path)
            replay_files=['file_manifest.json','configs/collection_cohort.json','configs/protocol.json']
            for path in packs:
                replay_files += [path.relative_to(ROOT).as_posix(),
                    'data/automation/extracted/'+json.loads(path.read_text())['source']['document_id']+'.zip']
            adjudicated=(included/'sample_decisions.json').exists()
            if adjudicated:
                replay_files += ['data/derived/historical_industry.json','data/derived/industry_source_status.json',
                                 'data/derived/st_cover_evidence.json']
            for rel in replay_files:
                dest=replay/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
            if packs:apply_reviewed(replay)
            if adjudicated:
                build_samples(replay)
                for name in ['sample_decisions.csv','sample_decisions.json','sample_completion_tasks.json']:
                    if (output/name).read_bytes()!=(included/name).read_bytes():
                        raise ValueError('Replayed sample decision mismatch: '+name)
            with sqlite3.connect(output / 'distress.sqlite') as rebuilt:
                for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                    actual = sorted(repr(tuple(r)) for r in con.execute(f'SELECT * FROM {table}'))
                    expected = sorted(repr(r) for r in rebuilt.execute(f'SELECT * FROM {table}'))
                    if actual != expected:
                        raise ValueError(f'Database table mismatch: {table}')
    finally:
        con.close()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    tests = unittest.TextTestRunner(verbosity=1).run(suite)
    if not tests.wasSuccessful():
        raise SystemExit(1)
    print(json.dumps({'passed': True, 'tests': tests.testsRun,
                      'files': len(manifest) + 1, 'counts': result['counts']}, indent=2))


if __name__ == '__main__':
    main()
