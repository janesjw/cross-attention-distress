"""Check package files, database contents, CSV views, and offline tests."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from build_database import build
from distress.database import ROOT, audit_database, connect


def main():
    manifest = json.loads((ROOT / 'file_manifest.json').read_text())
    for name, digest in manifest.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'File hash mismatch: {name}')
    included = ROOT / 'data/derived'
    con = connect(included / 'distress.sqlite')
    try:
        result = audit_database(con)
        if not result['passed']:
            raise ValueError(result['errors'])
        metadata = dict(con.execute('SELECT key,value FROM metadata'))
        for key, path in [('seed_sha256', ROOT / 'data/raw/records.json'),
                          ('protocol_sha256', ROOT / 'configs/protocol.json')]:
            if metadata[key] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError(f'Database input mismatch: {key}')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            build(output)
            for name in ('financials.csv', 'samples.csv'):
                if (output / name).read_bytes() != (included / name).read_bytes():
                    raise ValueError(f'CSV mismatch: {name}')
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
