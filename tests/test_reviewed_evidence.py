"""Source-backed import checks. No model-performance fixture is produced."""
import copy
import importlib.util
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reviewed',ROOT/'analysis/import_reviewed_evidence.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ReviewedEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        files=['configs/collection_cohort.json','file_manifest.json',
               'data/verification/reviewed/1219823600.json','data/verification/reviewed/1219854723.json',
               'data/automation/extracted/1219823600.zip','data/automation/extracted/1219854723.zip']
        for name in files:
            dest=self.root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
        self.db=self.root/'data/derived/distress.sqlite';self.db.parent.mkdir(parents=True)
        with sqlite3.connect(self.db) as con:
            con.executescript((ROOT/'src/distress/schema.sql').read_text())
            con.execute("INSERT INTO market_sources VALUES ('test','https://example.org',?,0,'2026-09-10','test')",('0'*64,))
            con.execute("INSERT INTO listing_records VALUES ('000012.SZ','SZ','test',1,'CSG','南玻','1992-02-28',NULL,'C','pending')")

    def test_real_review_import_is_idempotent_and_not_a_sample_freeze(self):
        a=module.apply_reviewed(self.root);b=module.apply_reviewed(self.root)
        self.assertEqual(a,b);self.assertEqual(a['reviewed_facts'],50)
        self.assertEqual(a['reviewed_text_sections'],1);self.assertEqual(a['eligible_samples'],0)
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM facts').fetchone()[0],50)
            self.assertEqual(c.execute('SELECT baseline_st,baseline_quarter,baseline_audit,outcome,analytical_eligible FROM sample_register').fetchone(),(None,0,0,None,0))
            # Parent-attributable 325377538 must not replace consolidated 317932830.
            self.assertEqual(c.execute("SELECT value_normalized FROM facts WHERE fact_id='1219854723:net_profit:2024-03-31:consolidated'").fetchone()[0],'317932830')

    def test_changed_source_rolls_back(self):
        with (self.root/'data/automation/extracted/1219854723.zip').open('ab') as f:f.write(b'tamper')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):module.apply_reviewed(self.root)
        with sqlite3.connect(self.db) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM facts').fetchone()[0],0)

    def test_changed_value_rejected(self):
        p=self.root/'data/verification/reviewed/1219823600.json';x=json.loads(p.read_text())
        x['facts'][0]['record']['raw_value']='1';x['facts'][0]['record']['value_normalized']='1';p.write_text(json.dumps(x))
        with self.assertRaisesRegex(ValueError,'source column'):module.apply_reviewed(self.root)


if __name__=='__main__':unittest.main()
