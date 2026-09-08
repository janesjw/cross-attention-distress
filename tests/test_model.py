import io,unittest
import torch
from torch import nn
from transformers import BertConfig,BertModel
from distress.model import MMAN,focal_loss,VARIANTS
from distress.train import seed_all,batches

torch.set_num_threads(2)
def tiny():
    return BertModel(BertConfig(vocab_size=100,hidden_size=32,num_hidden_layers=1,num_attention_heads=4,intermediate_size=64,hidden_dropout_prob=0,attention_probs_dropout_prob=0))
def inputs():
    return torch.randn(3,5,18),torch.randn(3,4,8),torch.randint(1,100,(3,12)),torch.tensor([[1]*8+[0]*4,[1]*10+[0]*2,[1]*12])

class ModelTests(unittest.TestCase):
    def setUp(self):seed_all(42)
    def test_singleton_attention_has_zero_query_gradient(self):
        layer=nn.MultiheadAttention(32,4,batch_first=True,dropout=0).eval()
        q=torch.randn(3,1,32,requires_grad=True);kv=torch.randn(3,1,32)
        a,w=layer(q,kv,kv,average_attn_weights=False);b,_=layer(q+100,kv,kv)
        self.assertTrue(torch.equal(a,b));self.assertTrue(torch.all(w==1))
        a.sum().backward();self.assertEqual(q.grad.abs().max().item(),0)
    def test_multikey_attention_is_query_sensitive(self):
        layer=nn.MultiheadAttention(32,4,batch_first=True,dropout=0).eval()
        q=torch.randn(3,1,32,requires_grad=True);kv=torch.randn(3,8,32)
        a,w=layer(q,kv,kv,average_attn_weights=False);b,_=layer(q+1,kv,kv)
        self.assertGreater((a-b).abs().max().item(),1e-5)
        a.square().sum().backward();self.assertGreater(q.grad.abs().max().item(),1e-5)
    def test_padding_is_ignored_end_to_end(self):
        model=MMAN(tiny(),d_model=32).eval();x=inputs()
        with torch.no_grad():
            a=model(*x);ids=x[2].clone();ids[x[3]==0]=99;b=model(x[0],x[1],ids,x[3])
        self.assertTrue(torch.allclose(a['logits'],b['logits'],atol=1e-6))
        self.assertTrue(torch.all(a['attentions'][0][0,:,:,8:]==0))
    def test_gates_are_sample_dependent_convex_weights(self):
        model=MMAN(tiny(),d_model=32).eval();out=model(*inputs());g=out['gates']
        self.assertTrue(torch.allclose(g.sum(-1),torch.ones(3),atol=1e-6));self.assertTrue(torch.all(g>=0))
        self.assertFalse(torch.allclose(g[0],g[1]))
    def test_manuscript_gate_is_global_and_paths_singleton(self):
        model=MMAN(tiny(),'manuscript_singleton',32).eval();out=model(*inputs())
        self.assertTrue(torch.equal(out['gates'][0],out['gates'][1]))
        self.assertTrue(all(torch.all(a==1) for a in out['attentions']))
    def test_all_ablation_variants_forward_and_backward(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                text=None if variant in ('long_only','short_only','numerical_only') else tiny()
                model=MMAN(text,variant,32);out=model(*inputs())
                self.assertEqual(out['logits'].shape,(3,))
                loss=focal_loss(out['logits'],torch.tensor([0,1,0]));loss.backward()
                self.assertTrue(torch.isfinite(loss));self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))
    def test_focal_loss_extremes_are_finite(self):
        z=torch.tensor([-1000.,1000.,0.,1000.],requires_grad=True);loss=focal_loss(z,torch.tensor([1,0,1,1]))
        loss.backward();self.assertTrue(torch.isfinite(loss));self.assertTrue(torch.isfinite(z.grad).all())
    def test_checkpoint_roundtrip(self):
        model=MMAN(tiny(),d_model=32).eval();x=inputs();a=model(*x)['logits']
        file=io.BytesIO();torch.save(model.state_dict(),file);file.seek(0)
        restored=MMAN(tiny(),d_model=32).eval();restored.load_state_dict(torch.load(file,weights_only=True))
        self.assertTrue(torch.equal(a,restored(*x)['logits']))
    def test_seed_reproducible_on_this_cpu(self):
        seed_all(7);a=MMAN(tiny(),d_model=32).eval();seed_all(7);b=MMAN(tiny(),d_model=32).eval();x=inputs()
        self.assertTrue(torch.equal(a(*x)['logits'],b(*x)['logits']))
    def test_batchnorm_no_singleton_and_no_dropped_samples(self):
        chunks=batches(65,32);self.assertEqual([len(c) for c in chunks],[32,33])
        self.assertEqual(sorted(int(x) for c in chunks for x in c),list(range(65)))
