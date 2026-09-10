"""Checks that prevent false certification, leakage and mutation of frozen data."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'analysis')]
from distress.annual_audit import audit,parse_annual
from distress.annual_freeze import minimum_support,split_counts,load_frozen
from structure_financials import parse


class AnnualAuditTest(unittest.TestCase):
    def setUp(self):
        with zipfile.ZipFile(ROOT/'data/automation/extracted/1219823600.zip') as z:self.raw=json.loads(z.read('pages.json'))
    def test_reviewed_source_passes_without_old_model_fields(self):
        p=parse(self.raw)
        p['rows']=[r for r in p['rows'] if r['metric'] not in ('interest_expense','capex_cash')]
        p['issues']+=['income:interest_expense:row_count:0','cashflow:capex_cash:row_count:0']
        a=audit(self.raw,p)
        self.assertTrue(a['financial_pass']);self.assertTrue(a['text_pass'])
        self.assertEqual(a['verification_tier'],'rule_based_source_checks_not_manual_review')
    def test_reversed_columns_not_certified_from_title(self):
        raw=copy.deepcopy(self.raw)
        for page in raw['pages']:
            import re
            page['text']=re.sub(r'2023 年度(\s+)2022 年度',r'2022 年度\g<1>2023 年度',page['text'])
        a=audit(raw,parse(raw));self.assertFalse(a['financial_pass'])
    def test_formal_statements_separate_from_adoption_notes(self):
        for did in ('1213263535','1213137834','1203312386','1204669529'):
            with zipfile.ZipFile(ROOT/f'data/automation/extracted/{did}.zip') as z:raw=json.loads(z.read('pages.json'))
            p=parse_annual(raw,parse);result=audit(raw,p)
            self.assertTrue(p.get('statement_block'),did)
            self.assertTrue(result['financial_pass'],(did,result['issues']))
    def test_cancelled_report_is_excluded(self):
        from distress.annual_st import annual_matches
        row=dict(self.raw['source']);row['source_title']+='（已取消）'
        self.assertFalse(annual_matches(row,'2024-05-01'))
    def test_missing_required_row_not_imputed(self):
        p=parse(self.raw);p['rows']=[r for r in p['rows'] if r['metric']!='inventory']
        self.assertFalse(audit(self.raw,p)['financial_pass'])
    def test_source_company_mismatch_rejected(self):
        raw=copy.deepcopy(self.raw);raw['source']['firm_id']='999999.SZ'
        a=audit(raw,parse(raw));self.assertFalse(a['financial_pass']);self.assertFalse(a['text_pass'])
    def test_row_anchor_mutation_rejected(self):
        p=parse(self.raw);p['rows'][0]['source_line']='changed'
        self.assertFalse(audit(self.raw,p)['financial_pass'])
    def test_one_company_cannot_satisfy_cluster_gate(self):
        rows=[{'split':s,'firm_id':'one','label':y} for s in ('train','validation','test') for y in (0,1)]
        self.assertEqual(len(minimum_support(split_counts(rows))),3)


class AnnualTrainingTest(unittest.TestCase):
    def test_train_statistics_do_not_use_test_values(self):
        from distress.annual_train import FinancialTransform
        train=np.array([[1.,2.],[2.,4.],[3.,6.]])
        t=FinancialTransform().fit(train);before=t.median.copy()
        t.transform(np.array([[1e9,np.nan]]));np.testing.assert_array_equal(t.median,before)
    def test_attention_has_multiple_masked_keys(self):
        import torch
        from distress.annual_train import Model
        torch.manual_seed(4);m=Model('cross_attention').eval()
        f=torch.randn(2,24);t=torch.randn(2,3,64);mask=torch.tensor([[False,False,True],[False,False,True]])
        a=m(f,t,mask);t[:,2,:]=10000
        self.assertTrue(torch.allclose(a,m(f,t,mask),atol=1e-6))
        t[:,1,:]+=3
        self.assertFalse(torch.allclose(a,m(f,t,mask)))
    def test_equal_fusion_parameter_budget(self):
        from distress.annual_train import Model
        counts=[sum(p.numel() for p in Model(v).parameters() if p.requires_grad) for v in ('concat','cross_attention')]
        self.assertEqual(counts[0],counts[1])
    def test_threshold_is_computed_from_supplied_validation(self):
        from distress.annual_train import choose_threshold
        self.assertAlmostEqual(choose_threshold(np.array([0,0,1,1]),np.array([.1,.3,.6,.8])),.6)
    def test_synthetic_full_runner_and_tamper_guard(self):
        from distress.annual_train import run
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'data/derived/annual_st';out.mkdir(parents=True)
            records=[]
            for s in ('train','validation','test'):
                for i in range(8):
                    records.append({'sample_id':f'{s}-{i}','firm_id':f'firm{i}','split':s,'label':i%2,
                        'features':[float((i+j)%5) for j in range(12)],'text':('稳定经营收入增长' if i%2==0 else '亏损负债经营下降')*100})
            dataset=out/'frozen_samples.jsonl';dataset.write_text(''.join(json.dumps(r)+'\n' for r in records))
            protocol=json.loads((ROOT/'configs/simplified_protocol.json').read_text());protocol['model']['seeds']=[17,42]
            m={'dataset_path':dataset.relative_to(root).as_posix(),'dataset_sha256':hashlib.sha256(dataset.read_bytes()).hexdigest(),
               'summary':{'final_sample_count':len(records),'splits':split_counts(records)},'protocol':protocol,'limitations':['SYNTHETIC TEST ONLY']}
            manifest=out/'frozen_manifest.json';manifest.write_text(json.dumps(m))
            (root/'file_manifest.json').write_text(json.dumps({manifest.relative_to(root).as_posix():hashlib.sha256(manifest.read_bytes()).hexdigest()}))
            result=run(root,root/'test_output',epochs=2,bootstrap=5)
            self.assertEqual(len(result['runs']),8)
            for r in result['runs']:self.assertEqual(sum(map(sum,r['test']['confusion_matrix'])),8)
            dataset.write_text(dataset.read_text()+'\n')
            with self.assertRaises(ValueError):load_frozen(root)


if __name__=='__main__':unittest.main()
