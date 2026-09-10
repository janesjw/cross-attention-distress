import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('verify_exchange_register',ROOT/'analysis/verify_exchange_register.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class ExchangeRegisterTests(unittest.TestCase):
    def review(self,changes=None,delisted=None):
        return {'issues':[],'listing':{'name':'正常公司','listing_date':'2000-01-01','delisting_date':delisted},'changes':changes or []}

    def test_complete_negative_and_truncated_followup(self):
        r=self.review()
        self.assertEqual(module.classify(r,'2024-05-01','2025-05-01','2026-09-10')['registry_label'],0)
        self.assertIsNone(module.classify(r,'2024-05-01','2025-05-01','2025-03-31')['registry_label'])

    def test_delisting_without_event_is_censored(self):
        r=module.classify(self.review(delisted='2024-09-01'),'2024-05-01','2025-05-01','2026-09-10')
        self.assertEqual(r['status'],'right_censored');self.assertIsNone(r['registry_label'])

    def test_positive_before_delisting_remains_observed(self):
        event={'effective_date':'2024-07-01','before':'正常公司','after':'*ST公司','source_row':7}
        r=module.classify(self.review([event],'2024-09-01'),'2024-05-01','2025-05-01','2026-09-10')
        self.assertEqual(r['registry_label'],1);self.assertEqual(r['event_source_row'],7)

    def test_origin_and_end_boundaries(self):
        event={'effective_date':'2024-05-01','before':'正常公司','after':'ST公司','source_row':7}
        self.assertEqual(module.classify(self.review([event]),'2024-05-01','2025-05-01','2026-09-10')['status'],'excluded')
        event['effective_date']='2025-05-01'
        self.assertEqual(module.classify(self.review([event]),'2024-05-01','2025-05-01','2026-09-10')['registry_label'],0)

    def test_full_name_chain_not_just_ST_flags(self):
        l=[{'name':'丙公司','listing_date':'2000-01-01','delisting_date':None,'status':'listed'}]
        changes=[{'effective_date':'2010-01-01','before':'甲公司','after':'乙公司','source_row':3},
                 {'effective_date':'2011-01-01','before':'另一公司','after':'丙公司','source_row':4}]
        self.assertIn('broken_full_name_chain',module.company_review(l,changes)['issues'])

    def test_risk_prefix_and_full_source_reconciliation(self):
        self.assertEqual(module.is_st('ＢＥＳＴ股份'),0)
        self.assertEqual(module.is_st('Ｓ＊ＳＴ公司'),1)
        listing,changes,proof=module.read_sources(ROOT)
        self.assertEqual(proof['name_register_records'],7478)
        self.assertEqual(sum(r['rows_checked'] for r in proof['api_export_controls']),58)
        self.assertTrue(listing['000012.SZ']);self.assertTrue(changes['000012.SZ'])

if __name__=='__main__':unittest.main()
