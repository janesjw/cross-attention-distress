"""Evidence boundary tests; synthetic cases are not research observations."""
import sqlite3
import unittest
from pathlib import Path
from distress.sample_builder import annual_title,annual_sections,outcome,component_from_evidence


class SampleBuilderTests(unittest.TestCase):
    def setUp(self):
        self.con=sqlite3.connect(':memory:');self.addCleanup(self.con.close)
        self.con.row_factory=sqlite3.Row
        self.con.executescript((Path(__file__).parents[1]/'src/distress/schema.sql').read_text())
        self.con.execute("INSERT INTO firms (firm_id,name,exchange) VALUES ('T','test','test')")
        self.con.execute("INSERT INTO documents VALUES ('D','T','2023年年度报告','2024-04-29','https://example.org',?,1,1,'original','none','date','verified')",('a'*64,))
        self.con.execute("INSERT INTO sample_register VALUES ('T:2024','T','2024-05-01','2025-05-01',0,0,0,'clear','pending',NULL,NULL,'unresolved',0,'test')")
    def test_chinese_annual_report_and_corrected_version(self):
        self.assertTrue(annual_title('2023 年年度报告（修订版）',2023))
        self.assertTrue(annual_title('2023 Annual Report',2023))
        for title in ['2023年年度报告摘要','2023年半年度报告','2024年年度报告','2023年第三季度报告']:
            self.assertFalse(annual_title(title,2023))
    def test_future_annual_text_is_not_available(self):
        self.con.execute("INSERT INTO text_sections VALUES ('S','D','MD&A',1,1,?,'none','verified')",('b'*64,))
        self.assertEqual(len(annual_sections(self.con,'T','2024-05-01')),1)
        self.con.execute("UPDATE documents SET disclosed_date='2024-05-01'")
        self.assertEqual(annual_sections(self.con,'T','2024-05-01'),[])
    def test_incomplete_coverage_is_not_negative(self):
        for criterion in ['ST','quarter']:
            self.con.execute("INSERT INTO coverage VALUES ('T:2024',?,'2024-05-01','2025-05-01','verified_absent','reviewed test coverage')",(criterion,))
        self.assertIsNone(outcome(self.con,'T:2024','clear','2024-05-01','2025-05-01')[0])
        self.con.execute("INSERT INTO coverage VALUES ('T:2024','audit_loss','2024-05-01','2025-05-01','verified_absent','reviewed test coverage')")
        self.assertEqual(outcome(self.con,'T:2024','clear','2024-05-01','2025-05-01')[:2],(0,'2025-04-30'))
        self.con.execute("UPDATE coverage SET window_end_exclusive='2025-04-30' WHERE criterion='ST'")
        self.assertIsNone(outcome(self.con,'T:2024','clear','2024-05-01','2025-05-01')[0])
    def test_known_event_cannot_label_unresolved_baseline(self):
        self.con.execute("UPDATE documents SET disclosed_date='2024-06-01'")
        self.con.execute("INSERT INTO events VALUES ('E','T','ST_implementation_announcement','2024-06-01','2024-06-03','D',1,1,'test implementation')")
        self.assertEqual(outcome(self.con,'T:2024','clear','2024-05-01','2025-05-01')[:2],(1,'2024-06-01'))
        self.assertIsNone(outcome(self.con,'T:2024','unresolved','2024-05-01','2025-05-01')[0])
        self.con.execute("UPDATE events SET effective_date='2025-05-01'")
        self.assertIsNone(outcome(self.con,'T:2024','clear','2024-05-01','2025-05-01')[0])
    def test_conflicting_component_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError,'Contradictory'):
            component_from_evidence([{'status':'verified_absent'},{'status':'verified_present'}])

if __name__=='__main__':unittest.main()
