import importlib.util,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('pipeline',Path(__file__).resolve().parents[1]/'analysis/run_pipeline.py')
pipeline=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(pipeline)

class PipelineTests(unittest.TestCase):
    def test_priority_targets_features_and_followup_not_ancillary_quarters(self):
        def rank(title,date):
            return pipeline.collection_priority({'source_title':title,'disclosed_date':date},['2017-05-01'])
        self.assertEqual(rank('2011年年度报告','2012-04-01'),0)
        self.assertEqual(rank('2012年一季度报告','2012-04-30'),2)
        self.assertEqual(rank('2017年一季度报告','2017-04-30'),0)
        self.assertEqual(rank('2018年一季度报告','2018-04-30'),0)
        self.assertEqual(rank('2016年年度报告（更正后）','2017-05-03'),0)
        self.assertEqual(rank('财务报告更新','2017-04-30'),1)
    def test_missing_data_blocks_training(self):
        result=pipeline.readiness(pipeline.ROOT)
        self.assertFalse(result['training_candidate'])
        self.assertIn('No eligible analytical samples',result['blocking_reasons'])
    def test_failed_download_is_checkpointed_and_retry_is_capped(self):
        row={'document_id':'123','firm_id':'000002.SZ','source_title':'Annual report','disclosed_date':'2025-04-01','url':'https://static.cninfo.com.cn/finalpage/2025-04-01/123.PDF'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'file_manifest.json').write_text('{}')
            (root/'configs').mkdir();(root/'configs/collection_cohort.json').write_text(json.dumps({'firms':[{'firm_id':'000002.SZ','reports_start':'2011-01-01','reports_end_exclusive':'2026-05-01'}]}))
            with patch.object(pipeline,'candidates',return_value=[row]),patch.object(pipeline,'readiness',return_value={'training_candidate':False}),patch.object(pipeline.urllib.request,'urlopen',side_effect=TimeoutError('test timeout')) as request:
                for _ in range(4):pipeline.run(root,1,1)
                self.assertEqual(request.call_count,3)
            state=json.loads((root/'data/automation/progress.json').read_text())
            self.assertEqual(state['documents']['123']['status'],'needs_review')
            self.assertEqual(state['documents']['123']['attempts'],3)
    def test_scope_excludes_other_firms_and_outside_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'configs').mkdir()
            (root/'configs/collection_cohort.json').write_text(json.dumps({'firms':[{'firm_id':'A','reports_start':'2011-01-01','reports_end_exclusive':'2026-05-01'}]}))
            rows=[{'firm_id':f,'disclosed_date':d} for f,d in [('A','2011-01-01'),('A','2026-04-30'),('A','2010-12-31'),('A','2026-05-01'),('B','2024-04-30')]]
            self.assertEqual(pipeline.restrict_queue(root,rows),rows[:2])
    def test_extraction_keeps_page_and_unverified_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'sample.pdf'
            with pipeline.fitz.open() as doc:
                page=doc.new_page();page.insert_text((72,72),'A financial disclosure with an explicit page reference. '*4);doc.save(p)
            result=pipeline.extract(p,{'document_id':'test'})
            self.assertEqual(result['pages'][0]['page'],1)
            self.assertFalse(result['analytical_verified'])
            self.assertEqual(result['pdf_sha256'],pipeline.digest(p))
