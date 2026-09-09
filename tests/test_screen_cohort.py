import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('screen',Path(__file__).resolve().parents[1]/'analysis/screen_cohort.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ScreeningTests(unittest.TestCase):
    def setUp(self):self.source=dict(public_date='2020-04-14',period='2020Q1',sha256='a'*64,url='https://example.invalid/source.pdf')
    def test_merged_category_and_broken_category_do_not_cross_contaminate(self):
        rows=[['金融业(J)','66','货币金融服务','000001','Bank'],[None,None,None,'600000','Bank2'],['居民服务、修理和','80','repair','300736','Repair'],['教育(P)','82','education','000526','School']]
        r=m.industry_rows(self.source,[dict(page=1,cells=x) for x in rows])
        self.assertEqual(r['600000.SH']['group'],'J');self.assertNotIn('300736.SZ',r);self.assertEqual(r['000526.SZ']['group'],'P')
    def test_modern_table_and_duplicate_codes(self):
        row=dict(page=2,cells=['000002','Vanke','K','real estate','','','70','real estate'])
        self.assertEqual(m.industry_rows(self.source,[row])['000002.SZ']['industry_code'],'K70')
        with self.assertRaises(ValueError):m.industry_rows(self.source,[row,row])
