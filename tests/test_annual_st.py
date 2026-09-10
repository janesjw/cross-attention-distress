import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from distress.annual_st import annual_matches, annual_features, restrict, mda_candidate


class AnnualSTTest(unittest.TestCase):
    def row(self,title='2023年度报告',date='2024-04-30',kind='annual_report',firm='000012.SZ'):
        return {'source_title':title,'disclosed_date':date,'report_kind':kind,'firm_id':firm}

    def test_exact_annual_year_and_cutoff(self):
        for title in ('2023年度报告','2023年年度报告','2023年年度报告（更正后）'):
            self.assertTrue(annual_matches(self.row(title),'2024-05-01'))
        for row in (self.row(date='2024-05-01'),self.row('2022年度报告'),self.row('2023年度报告摘要'),
                    self.row('2023年半年度报告'),self.row('2024年一季度报告',kind='quarterly_report')):
            self.assertFalse(annual_matches(row,'2024-05-01'))

    def test_small_scope_removes_quarters_and_other_exchanges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'configs').mkdir()
            (root/'configs/simplified_cohort.json').write_text(json.dumps({'firms':[{'firm_id':'000012.SZ','origins':['2024-05-01']}]}))
            good=self.row()
            rows=[good,self.row(firm='600000.SH'),self.row('2019年度报告'),self.row(kind='quarterly_report')]
            self.assertEqual(restrict(root,rows),[good])

    def test_no_prior_year_and_no_blank_zero_substitution(self):
        f=annual_features({'assets':Decimal(100),'liabilities':Decimal(30),'net_profit':Decimal(-10),'revenue':Decimal(0)})
        self.assertEqual(len(f),12)
        self.assertEqual(f[0],.3)
        self.assertEqual(f[3],-.1)
        self.assertIsNone(f[6])
        self.assertIsNone(f[1])

    def test_text_is_bounded_before_governance_and_not_certified(self):
        body='经营活动分析和风险说明。'*30
        raw={'pages':[{'page':1,'text':'第三节 管理层讨论与分析\n'+body},
                      {'page':2,'text':'第四节 公司治理\n不属于输入文本'}]}
        result=mda_candidate(raw)
        self.assertEqual(result['text'],body)
        self.assertNotIn('公司治理',result['text'])
        self.assertEqual(result['verification'],'candidate_boundary_not_certified')


if __name__=='__main__':unittest.main()
