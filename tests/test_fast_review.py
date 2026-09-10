"""Software tests with temporary synthetic fixtures, never research estimates."""
import importlib.util,sys,json,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from distress.metrics import classification_metrics,paired_firm_bootstrap

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis'))
import run_pipeline as pipeline
import summarize_review as report

class FastReviewTests(unittest.TestCase):
    def test_fractional_labels_and_invalid_thresholds_rejected(self):
        with self.assertRaises(ValueError):classification_metrics([0,1.2],[.2,.8])
        for threshold in (float('nan'),-1,2):
            with self.assertRaises(ValueError):classification_metrics([0,1],[.2,.8],threshold)
    def test_undefined_precision_is_not_reported_as_zero(self):
        m=classification_metrics([0,1],[.1,.2])
        self.assertIsNone(m['precision']);self.assertIn('precision',m['undefined_metrics'])
        self.assertEqual(m['recall'],0);self.assertEqual(m['f1'],0)
    def test_f1_bootstrap_uses_given_threshold(self):
        m=paired_firm_bootstrap([0,1,0,1],[.1,.6,.2,.6],[.1,.8,.2,.8],['A','A','B','B'],
          metric='f1',repetitions=20,threshold=.7)
        self.assertEqual(m['difference'],-1);self.assertEqual(m['ci95'],[-1,-1])
    def test_parallel_results_are_checkpointed_once_and_limit_is_respected(self):
        # Fake download workers use threads solely to test the parent's state writer.
        # Production uses isolated MuPDF processes.
        rows=[{'document_id':str(i),'firm_id':'A','source_title':'Annual report','disclosed_date':'2020-04-01'} for i in range(10)]
        def worker(root,row,attempts,expected):
            return {'status':'retry_pending','attempts':attempts,'firm_id':'A','error':'fixture'}
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'configs').mkdir();(root/'file_manifest.json').write_text('{}')
            (root/'configs/collection_cohort.json').write_text(json.dumps({'firms':[{'firm_id':'A','reports_start':'2010-01-01','reports_end_exclusive':'2026-05-01'}]}))
            with patch.object(pipeline,'candidates',return_value=rows),patch.object(pipeline,'readiness',return_value={'training_candidate':False}),patch.object(pipeline,'process_document',side_effect=worker),patch('concurrent.futures.ProcessPoolExecutor',ThreadPoolExecutor):
                pipeline.run(root,5,1,workers=3)
            state=json.loads((root/'data/automation/progress.json').read_text())
            self.assertEqual(len(state['documents']),5)
            self.assertTrue(all(x['attempts']==1 for x in state['documents'].values()))
            status=json.loads((root/'data/automation/status.json').read_text())
            self.assertEqual(status['attempted_this_run'],5);self.assertFalse(status['training_candidate'])
    def make_run(self,path,variant,seed,flip=False):
        path.mkdir(parents=True)
        rows=[dict(sample_id=f'{firm}:{year}',firm_id=firm,origin=f'{year}-05-01',split='test',label=label,probability=p)
              for year in (2024,2025) for firm,label,p in [('A',0,.1),('B',1,.9)]]
        if flip:rows[0]['firm_id']='X'
        files={'test_predictions.json':rows,'test_metrics.json':classification_metrics([x['label'] for x in rows],[x['probability'] for x in rows]),
               'history.json':[{'epoch':1,'train_focal_loss':.2,'validation_focal_loss':.3}],
               'config.json':{'variant':variant,'seed':seed,'width':128},'environment.json':{'purpose':'temporary synthetic test'}}
        for name,data in files.items():(path/name).write_text(json.dumps(data))
        (path/'best.pt').write_bytes(b'TEMPORARY SYNTHETIC TEST CHECKPOINT; not a trained model')
        receipt={'status':'completed','purpose':'research','dataset_id':'temporary-software-test','variant':variant,'seed':seed,
          'threshold':.5,'manifest_sha256':'temporary-fixture','checkpoint_sha256':report.sha(path/'best.pt'),
          'files_sha256':{name:report.sha(path/name) for name in files}}
        (path/'run_manifest.json').write_text(json.dumps(receipt))
    def test_process_pool_can_dispatch_and_return_failures(self):
        row={'document_id':'123','firm_id':'A','url':'invalid-fixture-url'}
        from concurrent.futures import ProcessPoolExecutor
        with tempfile.TemporaryDirectory() as t,ProcessPoolExecutor(max_workers=2) as pool:
            r=pool.submit(pipeline.process_document,Path(t),row,1,None).result(timeout=10)
            self.assertEqual(r['status'],'retry_pending')
            self.assertIn('Unexpected source URL',r['error'])
    def fixture(self,root,flip=False):
        cfg={'seeds':[42],'variants':['sequence_cross_attention','gating_only'],'threshold':.5,
          'contrasts':{'attention':'gating_only'},'bootstrap_repetitions':10}
        path=root/'protocol.json';path.write_text(json.dumps(cfg))
        for variant in cfg['variants']:self.make_run(root/f'{variant}-seed42',variant,42,flip and variant=='gating_only')
        return path
    def test_recomputation_and_cluster_pairing(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cfg=self.fixture(root)
            result=report.summarize(root,cfg,root/'out',figures=True)
            self.assertEqual(result['test_samples'],4);self.assertEqual(result['test_positives'],2)
            self.assertEqual(result['completed_runs'],2)
            self.assertTrue(all(x['ci95']==[0,0] for x in result['paired_conditional_intervals']))
            self.assertTrue((root/'out/curves_seed42.svg').exists())
            self.assertTrue((root/'out/training_curves.png').exists())
    def test_different_firm_identity_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cfg=self.fixture(root,flip=True)
            with self.assertRaises(ValueError):report.summarize(root,cfg,root/'out',figures=False)
            self.assertFalse((root/'out').exists())
    def test_tampered_predictions_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cfg=self.fixture(root)
            (root/'gating_only-seed42/test_predictions.json').write_text('[]')
            with self.assertRaises(ValueError):report.summarize(root,cfg,root/'out',figures=False)
    def test_missing_model_cannot_create_a_complete_report(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cfg=self.fixture(root)
            (root/'gating_only-seed42/run_manifest.json').unlink()
            with self.assertRaises(FileNotFoundError):report.summarize(root,cfg,root/'out',figures=False)
            self.assertFalse((root/'out').exists())
