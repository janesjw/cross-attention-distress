import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
from distress.database import create
from distress.dataset import validate_timeline,export_dataset
from distress.preprocess import FinancialPreprocessor,encode_disclosure
from distress.metrics import classification_metrics,paired_firm_bootstrap

class CharacterTokenizer:
    pad_token_id=0
    def num_special_tokens_to_add(self,pair=False):return 2
    def encode(self,s,add_special_tokens=False):return [ord(c)%90+10 for c in s]
    def build_inputs_with_special_tokens(self,ids):return [1]+ids+[2]

class ReproducibilityTests(unittest.TestCase):
    def test_preprocessing_fit_uses_training_only(self):
        train=np.arange(24,dtype=float).reshape(4,3,2);train[0,0,0]=np.nan
        p=FinancialPreprocessor().fit(train,['A','A','B','B']);saved=json.dumps(p.to_dict(),sort_keys=True)
        out,missing=p.transform(np.full((2,3,2),1e12),['C','C'])
        self.assertEqual(saved,json.dumps(p.to_dict(),sort_keys=True));self.assertTrue(np.isfinite(out).all())
        self.assertTrue(np.allclose(out,FinancialPreprocessor.from_dict(p.to_dict()).transform(np.full((2,3,2),1e12),['C','C'])[0]))
    def test_entirely_missing_training_feature_is_not_invented(self):
        with self.assertRaises(ValueError):FinancialPreprocessor().fit(np.full((2,5,18),np.nan),['A','B'])
    def test_sentence_boundary_and_padding(self):
        s='公司经营活动产生的现金流量持续改善。'
        r=encode_disclosure(CharacterTokenizer(),[s,s,'市场环境变化导致未来经营仍存在不确定性。'],max_length=35)
        self.assertEqual(len(r['input_ids']),35);self.assertEqual(r['audit']['retained_sentences'],1)
        self.assertTrue(r['audit']['truncated']);self.assertEqual(sum(r['attention_mask']),len(s)+2)
    def row(self):
        return dict(sample_id='X:2021',origin='2021-05-01',followup_end_exclusive='2022-05-01',label=0,
           label_available_date='2022-04-30',feature_max_public_date='2021-04-30',text_max_public_date='2021-04-30')
    def test_valid_forward_window(self):validate_timeline([self.row()])
    def test_future_features_rejected(self):
        r=self.row();r['text_max_public_date']='2021-05-01'
        with self.assertRaises(ValueError):validate_timeline([r])
    def test_immature_labels_rejected(self):
        r=self.row();r['label_available_date']='2022-03-31'
        with self.assertRaises(ValueError):validate_timeline([r])
    def test_training_labels_cannot_arrive_after_validation_origin(self):
        r=self.row();r['label_available_date']='2022-05-02'
        with self.assertRaises(ValueError):validate_timeline([r])
    def test_baseline_event_cannot_be_positive(self):
        r=self.row();r['label']=1;r['label_available_date']='2021-04-30'
        with self.assertRaises(ValueError):validate_timeline([r])
    def test_export_refuses_incomplete_reconstruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            con=create(Path(tmp)/'db.sqlite')
            with self.assertRaises(ValueError):export_dataset(con,None,'invalid',Path(tmp)/'dataset.json')
            self.assertFalse((Path(tmp)/'dataset.json').exists());con.close()
    def test_metrics_reconcile_to_integer_counts(self):
        r=classification_metrics([0,1,1,0],[.1,.9,.8,.7]);self.assertEqual((r['tp'],r['fp'],r['tn'],r['fn']),(2,1,1,0))
        self.assertAlmostEqual(r['f1'],.8);self.assertIsNone(classification_metrics([0,0],[.1,.2])['roc_auc'])
    def test_cluster_bootstrap_identical_predictions_have_zero_difference(self):
        p=[.1,.8,.2,.9];r=paired_firm_bootstrap([0,1,0,1],p,p,['A','A','B','B'],repetitions=30)
        self.assertEqual(r['ci95'],[0,0]);self.assertEqual(r['valid_resamples'],30)
