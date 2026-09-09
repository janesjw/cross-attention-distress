import importlib.util,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('pipeline',Path(__file__).resolve().parents[1]/'analysis/run_pipeline.py')
pipeline=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(pipeline)

class PipelineTests(unittest.TestCase):
    def test_missing_data_blocks_training(self):
        result=pipeline.readiness(pipeline.ROOT)
        self.assertFalse(result['training_candidate'])
        self.assertIn('No eligible analytical samples',result['blocking_reasons'])
    def test_failed_download_is_checkpointed_and_retry_is_capped(self):
        row={'document_id':'123','firm_id':'000002.SZ','source_title':'Annual report','disclosed_date':'2025-04-01','url':'https://static.cninfo.com.cn/finalpage/2025-04-01/123.PDF'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'file_manifest.json').write_text('{}')
            with patch.object(pipeline,'candidates',return_value=[row]),patch.object(pipeline,'readiness',return_value={'training_candidate':False}),patch.object(pipeline.urllib.request,'urlopen',side_effect=TimeoutError('test timeout')) as request:
                for _ in range(4):pipeline.run(root,1,1)
                self.assertEqual(request.call_count,3)
            state=json.loads((root/'data/automation/progress.json').read_text())
            self.assertEqual(state['documents']['123']['status'],'needs_review')
            self.assertEqual(state['documents']['123']['attempts'],3)
    def test_extraction_keeps_page_and_unverified_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'sample.pdf'
            with pipeline.fitz.open() as doc:
                page=doc.new_page();page.insert_text((72,72),'A financial disclosure with an explicit page reference. '*4);doc.save(p)
            result=pipeline.extract(p,{'document_id':'test'})
            self.assertEqual(result['pages'][0]['page'],1)
            self.assertFalse(result['analytical_verified'])
            self.assertEqual(result['pdf_sha256'],pipeline.digest(p))
