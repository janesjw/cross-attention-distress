"""Real Chinese checkpoint + real disclosure text; synthetic numbers/targets for software checks only."""
import argparse,hashlib,json,time
from pathlib import Path
import fitz
import torch
from transformers import AutoModel,AutoTokenizer
from distress.database import ROOT
from distress.model import MMAN,focal_loss
from distress.preprocess import encode_disclosure
from distress.train import seed_all,environment

p=argparse.ArgumentParser();p.add_argument('--model-path',required=True);p.add_argument('--pdf',required=True);p.add_argument('--report',required=True)
a=p.parse_args();seed_all(42);torch.set_num_threads(2)
cfg=json.loads((ROOT/'configs/model.json').read_text())
checkpoint_manifest=json.loads((ROOT/'configs/text_checkpoint_files.json').read_text())
for name,digest in checkpoint_manifest['sha256'].items():
    if hashlib.sha256((Path(a.model_path)/name).read_bytes()).hexdigest()!=digest:
        raise ValueError('Pretrained checkpoint file mismatch: '+name)
pdf=Path(a.pdf);raw=pdf.read_bytes()
seed=json.loads((ROOT/'data/verified_seed.json').read_text());expected=next(d['sha256'] for d in seed['documents'] if d['document_id']=='1222951181')
if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Expected the registered Midea FY2024 annual report')
tokenizer=AutoTokenizer.from_pretrained(a.model_path,local_files_only=True)
backbone=AutoModel.from_pretrained(a.model_path,local_files_only=True)
# First MD&A page (PDF p12), starting after the section/subsection headings.
page=fitz.open(pdf)[11].get_text();start=page.index('美的是一家')
encoded=encode_disclosure(tokenizer,[page[start:]],512)
model=MMAN(backbone);annual=torch.randn(2,5,18);short=torch.randn(2,4,8)
ids=torch.tensor([encoded['input_ids']]*2);mask=torch.tensor([encoded['attention_mask']]*2)
t=time.perf_counter();model.eval()
with torch.no_grad():out=model(annual,short,ids,mask)
elapsed=time.perf_counter()-t
assert out['logits'].shape==(2,) and torch.isfinite(out['logits']).all()
assert all(w.shape[-1]>1 for w in out['attentions'])
model.train();result=model(annual,short,ids,mask)
loss=focal_loss(result['logits'],torch.tensor([0,1]));loss.backward()
text_gradient=float(model.text_encoder.embeddings.word_embeddings.weight.grad.abs().max())
gate_gradient=float(model.gate[0].weight.grad.abs().max())
assert text_gradient>0 and gate_gradient>0
assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
weights=Path(a.model_path)/'model.safetensors'
report={'status':'passed','purpose':'synthetic_software_test_not_financial_distress_experiment',
 'text_model':cfg['text_model'],'revision':cfg['text_revision'],
 'weights_sha256':hashlib.sha256(weights.read_bytes()).hexdigest(),
 'checkpoint_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(a.model_path).iterdir() if p.is_file()},
 'text_source_document':'1222951181','text_source_pdf_page':12,'text_source_sha256':expected,
 'text_preprocessing':encoded['audit'],'financial_inputs':'synthetic normal random numbers; not reconstructed sample observations',
 'targets':'synthetic [0,1] solely to test gradients','training_steps':0,
 'total_parameters':sum(p.numel() for p in model.parameters()),'text_parameters':sum(p.numel() for p in backbone.parameters()),
 'attention_shapes':[list(w.shape) for w in out['attentions']],
 'gate_sums':out['gates'].sum(-1).tolist(),'forward_seconds_one_cpu_call':elapsed,
 'text_embedding_max_abs_gradient':text_gradient,'gate_max_abs_gradient':gate_gradient,
 'environment':environment(),
 'limitations':['No empirical metrics or trained distress weights produced','One timing measurement is not a benchmark','Unknown pretraining corpus cutoff; no historical-availability claim']}
Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:report[k] for k in ['status','total_parameters','text_parameters','attention_shapes','text_embedding_max_abs_gradient','gate_max_abs_gradient']}))
