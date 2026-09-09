import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

spec=importlib.util.spec_from_file_location('restore_disclosures',Path(__file__).resolve().parents[1]/'analysis/restore_disclosures.py')
restore_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(restore_module)

class RestoreTests(unittest.TestCase):
    def test_saved_completion_and_response_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/'source.sqlite'
            c=sqlite3.connect(db);c.execute('CREATE TABLE collection_status(firm_id TEXT,status TEXT)');c.execute("INSERT INTO collection_status VALUES ('000333.SZ','complete_periodic_disclosure_query')");c.commit();c.close()
            archive=root/'saved.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.write(db,'filings-0/derived/filings.sqlite');z.writestr('filings-0/query_cache/firm_reports/source.json','{"totalAnnouncement": 0}')
            (root/'file_manifest.json').write_text(json.dumps({'saved.zip':hashlib.sha256(archive.read_bytes()).hexdigest()}))
            restore_module.restore(archive,0,root)
            self.assertEqual(db.read_bytes(),(root/'data/derived/filings.sqlite').read_bytes())
            self.assertTrue((root/'data/query_cache/firm_reports/source.json').exists())
            with self.assertRaises(FileExistsError):restore_module.restore(archive,0,root)

    def test_changed_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'saved.zip';archive.write_bytes(b'changed')
            (root/'file_manifest.json').write_text(json.dumps({'saved.zip':'0'*64}))
            with self.assertRaises(ValueError):restore_module.restore(archive,0,root)

if __name__=='__main__':unittest.main()
