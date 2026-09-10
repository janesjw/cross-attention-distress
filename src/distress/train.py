"""Train only a frozen, certified database export. Does not recreate lost metrics."""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
import argparse,copy,hashlib,json,platform,random,sys
from pathlib import Path
import numpy as np
import torch
from transformers import AutoModel
from .database import ROOT,connect
from .dataset import load_frozen,split_for_origin
from .model import MMAN,focal_loss,VARIANTS
from .preprocess import FinancialPreprocessor
from .metrics import classification_metrics

def seed_all(seed):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    if torch.cuda.is_available():torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.use_deterministic_algorithms(True)

def batches(n,batch_size,rng=None):
    if n<2 or batch_size<2:raise ValueError('BatchNorm training requires at least two observations')
    idx=np.arange(n) if rng is None else rng.permutation(n)
    chunks=[idx[i:i+batch_size] for i in range(0,n,batch_size)]
    if len(chunks)>1 and len(chunks[-1])==1:
        chunks[-2]=np.concatenate([chunks[-2],chunks[-1]]);chunks.pop()
    return chunks

def environment():
    import transformers,sklearn
    return {'python':sys.version,'platform':platform.platform(),'torch':torch.__version__,
      'transformers':transformers.__version__,'numpy':np.__version__,'sklearn':sklearn.__version__,
      'cuda':torch.version.cuda,'deterministic_algorithms':torch.are_deterministic_algorithms_enabled()}

def prepare(rows):
    labels=np.array([r['label'] for r in rows],dtype=np.float32)
    industries=[r['industry'] for r in rows]
    parts=np.array([split_for_origin(r['origin']) for r in rows]);train=parts=='train'
    preprocessors={};tensors={};missing={}
    for name in ['annual','quarterly']:
        raw=np.asarray([r[name] for r in rows],dtype=float)
        prep=FinancialPreprocessor().fit(raw[train],[v for v,k in zip(industries,train) if k])
        processed,mask=prep.transform(raw,industries)
        tensors[name]=torch.tensor(processed);preprocessors[name]=prep.to_dict();missing[name]={'count':int(mask.sum()),'mask':mask.tolist()}
    for name in ['input_ids','attention_mask']:
        tensors[name]=torch.tensor([r[name] for r in rows],dtype=torch.long)
    tensors['labels']=torch.tensor(labels)
    return tensors,parts,preprocessors,missing

def evaluate(model,tensors,idx,device,batch_size,alpha=.75,gamma=2.):
    model.eval();prob=[];loss_sum=0.
    with torch.no_grad():
        for offset in range(0,len(idx),batch_size):
            select=idx[offset:offset+batch_size]
            z={k:v[select].to(device) for k,v in tensors.items()}
            out=model(z['annual'],z['quarterly'],z['input_ids'],z['attention_mask'])
            loss_sum+=float(focal_loss(out['logits'],z['labels'],alpha,gamma))*len(select)
            prob.extend(torch.sigmoid(out['logits']).cpu().tolist())
    return loss_sum/len(idx),np.asarray(prob)

def main():
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--manifest',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seed',type=int,default=42)
    p.add_argument('--variant',choices=VARIANTS,default='sequence_cross_attention');p.add_argument('--device',default='cpu')
    a=p.parse_args();con=connect(a.database)
    # Fail before model downloads, output creation or any training on incomplete data.
    data=load_frozen(a.manifest,con)
    cfg=json.loads((ROOT/'configs/model.json').read_text());cfg.update(seed=a.seed,variant=a.variant)
    a.output.mkdir(parents=True,exist_ok=False);seed_all(a.seed);device=torch.device(a.device)
    text=None if a.variant in ('long_only','short_only','numerical_only','numerical_cross_attention') else AutoModel.from_pretrained(cfg['text_model'],revision=cfg['text_revision'])
    model=MMAN(text,a.variant,d_model=cfg['d_model'],settings=cfg).to(device)
    groups=[{'params':[v for k,v in model.named_parameters() if not k.startswith('text_encoder.')],'lr':cfg['learning_rate']}]
    if text is not None:groups.append({'params':model.text_encoder.parameters(),'lr':cfg['text_learning_rate']})
    optimizer=torch.optim.AdamW(groups,weight_decay=cfg['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=cfg['max_epochs'])
    tensors,parts,preprocessing,missing=prepare(data['rows'])
    train_idx=np.flatnonzero(parts=='train');val_idx=np.flatnonzero(parts=='validation');test_idx=np.flatnonzero(parts=='test')
    env=environment();run_id=f'{data["dataset_id"]}:{a.variant}:seed{a.seed}'
    con.execute('INSERT INTO training_runs VALUES (?,?,?,?,?,?,?,?)',
      (run_id,data['dataset_id'],a.seed,json.dumps(cfg),json.dumps(env),'research',None,'running'));con.commit()
    (a.output/'config.json').write_text(json.dumps(cfg,indent=2));(a.output/'environment.json').write_text(json.dumps(env,indent=2))
    (a.output/'preprocessing.json').write_text(json.dumps(preprocessing,indent=2));(a.output/'missing_masks.json').write_text(json.dumps(missing))
    history=[];best=float('inf');wait=0;rng=np.random.default_rng(a.seed)
    for epoch in range(cfg['max_epochs']):
        model.train();loss_sum=0.
        for local_idx in batches(len(train_idx),cfg['batch_size'],rng):
            idx=train_idx[local_idx];z={k:v[idx].to(device) for k,v in tensors.items()}
            optimizer.zero_grad(set_to_none=True)
            out=model(z['annual'],z['quarterly'],z['input_ids'],z['attention_mask'])
            loss=focal_loss(out['logits'],z['labels'],cfg['focal_alpha'],cfg['focal_gamma'])
            if not torch.isfinite(loss):raise FloatingPointError('Non-finite training loss')
            loss.backward();optimizer.step();loss_sum+=float(loss.detach())*len(idx)
        val_loss,_=evaluate(model,tensors,val_idx,device,cfg['batch_size'],cfg['focal_alpha'],cfg['focal_gamma'])
        history.append({'epoch':epoch+1,'train_focal_loss':loss_sum/len(train_idx),'validation_focal_loss':val_loss,'learning_rates':scheduler.get_last_lr()})
        scheduler.step()
        if val_loss<best:
            best=val_loss;wait=0
            torch.save({'model':model.state_dict(),'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict(),
                'epoch':epoch+1,'validation_loss':best,'config':cfg,'dataset_id':data['dataset_id'],
                'manifest_sha256':hashlib.sha256(Path(a.manifest).read_bytes()).hexdigest(),
                'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
                'numpy_rng':np.random.get_state(),'python_rng':random.getstate(),'shuffle_rng':rng.bit_generator.state},a.output/'best.pt')
        else:wait+=1
        (a.output/'history.json').write_text(json.dumps(history,indent=2))
        if wait>=cfg['early_stopping_patience']:break
    # This is a locally generated checkpoint; do not load untrusted pickle checkpoints.
    best_checkpoint=torch.load(a.output/'best.pt',map_location=device,weights_only=False)
    model.load_state_dict(best_checkpoint['model'])
    test_loss,prob=evaluate(model,tensors,test_idx,device,cfg['batch_size'],cfg['focal_alpha'],cfg['focal_gamma'])
    labels=tensors['labels'][test_idx].numpy().astype(int)
    results=classification_metrics(labels,prob);results.update(test_focal_loss=test_loss,best_epoch=best_checkpoint['epoch'],stopping_epoch=history[-1]['epoch'])
    (a.output/'test_metrics.json').write_text(json.dumps(results,indent=2))
    predictions=[{'sample_id':data['rows'][int(idx)]['sample_id'],'firm_id':data['rows'][int(idx)]['firm_id'],
      'origin':data['rows'][int(idx)]['origin'],'split':'test','label':int(y),'probability':float(p)} for idx,y,p in zip(test_idx,labels,prob)]
    (a.output/'test_predictions.json').write_text(json.dumps(predictions,indent=2))
    con.executemany('INSERT INTO predictions VALUES (?,?,?,?,?)',[(run_id,r['sample_id'],'test',r['probability'],r['label']) for r in predictions])
    digest=hashlib.sha256((a.output/'best.pt').read_bytes()).hexdigest()
    con.execute('UPDATE training_runs SET checkpoint_sha256=?,status=? WHERE run_id=?',(digest,'completed',run_id));con.commit();con.close()
    receipt={'status':'completed','purpose':'research','dataset_id':data['dataset_id'],'variant':a.variant,
      'seed':a.seed,'threshold':results['threshold'],'manifest_sha256':best_checkpoint['manifest_sha256'],
      'checkpoint_sha256':digest,'parameter_count':sum(p.numel() for p in model.parameters()),
      'files_sha256':{name:hashlib.sha256((a.output/name).read_bytes()).hexdigest() for name in
         ('test_predictions.json','test_metrics.json','history.json','config.json','environment.json')}}
    (a.output/'run_manifest.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(results))

if __name__=='__main__':main()
