"""CPU experiments on an immutable annual-ST dataset. No external text weights."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import numpy as np
import torch
from torch import nn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import (average_precision_score,roc_auc_score,precision_recall_curve,
    precision_score,recall_score,f1_score,accuracy_score,confusion_matrix,roc_curve)
from .annual_freeze import load_frozen

VARIANTS=('financial_only','text_only','concat','cross_attention')


class FinancialTransform:
    def fit(self,x):
        x=np.asarray(x,float)
        if np.isnan(x).all(axis=0).any():raise ValueError('A financial feature is missing in every training row')
        self.lo=np.nanquantile(x,.01,axis=0);self.hi=np.nanquantile(x,.99,axis=0)
        z=np.clip(x,self.lo,self.hi);self.median=np.nanmedian(z,axis=0)
        z=np.where(np.isnan(z),self.median,z);self.mean=z.mean(0);self.std=z.std(0)
        self.std[self.std<1e-8]=1
        return self
    def transform(self,x):
        x=np.asarray(x,float);missing=np.isnan(x);z=np.clip(x,self.lo,self.hi)
        z=np.where(missing,self.median,z)
        return np.concatenate(((z-self.mean)/self.std,missing.astype(float)),axis=1).astype('float32')


def chunks(text,max_chunks=16,characters=256):
    text=''.join(text.split())
    pieces=[text[i:i+characters] for i in range(0,len(text),characters)]
    # Deterministically cover the whole MD&A; do not restrict all features to its opening.
    if len(pieces)>max_chunks:pieces=[pieces[i] for i in np.linspace(0,len(pieces)-1,max_chunks,dtype=int)]
    return pieces or [' ']


def text_arrays(records,train,settings):
    docs=[chunks(r['text'],settings['max_chunks'],settings['max_characters_per_chunk']) for r in records]
    training_chunks=[c for i in train for c in docs[i]]
    vectorizer=TfidfVectorizer(analyzer='char',ngram_range=(1,2),min_df=1,max_features=20000,sublinear_tf=True)
    matrix=vectorizer.fit_transform(training_chunks)
    dimensions=min(settings['svd_dimensions'],matrix.shape[0]-1,matrix.shape[1]-1)
    if dimensions<1:raise ValueError('Insufficient training text variation')
    svd=TruncatedSVD(n_components=dimensions,random_state=17);svd.fit(matrix)
    output=np.zeros((len(docs),settings['max_chunks'],settings['svd_dimensions']),dtype='float32')
    mask=np.ones(output.shape[:2],dtype=bool)
    for i,doc in enumerate(docs):
        output[i,:len(doc),:dimensions]=svd.transform(vectorizer.transform(doc));mask[i,:len(doc)]=False
    return output,mask,vectorizer,svd


class Model(nn.Module):
    def __init__(self,variant,width=64,text_dim=64):
        super().__init__();self.variant=variant
        self.fin=nn.Sequential(nn.Linear(24,width),nn.ReLU())
        self.txt=nn.Sequential(nn.Linear(text_dim,width),nn.ReLU())
        self.attention=nn.MultiheadAttention(width,4,batch_first=True) if variant=='cross_attention' else None
        if variant=='financial_only':self.txt.requires_grad_(False)
        if variant=='text_only':self.fin.requires_grad_(False)
        self.head=nn.Sequential(nn.Linear(width*(2 if variant in ('concat','cross_attention') else 1),width),nn.ReLU(),nn.Dropout(.1),nn.Linear(width,1))
    def forward(self,financial,text,mask):
        f=self.fin(financial);t=self.txt(text)
        pooled=(t*(~mask).unsqueeze(-1)).sum(1)/(~mask).sum(1,keepdim=True)
        if self.variant=='financial_only':x=f
        elif self.variant=='text_only':x=pooled
        elif self.variant=='concat':x=torch.cat((f,pooled),1)
        else:
            context,_=self.attention(f[:,None,:],t,t,key_padding_mask=mask,need_weights=False)
            x=torch.cat((f,context[:,0,:]),1)
        return self.head(x).squeeze(1)


def choose_threshold(y,p):
    precision,recall,thresholds=precision_recall_curve(y,p)
    score=2*precision[:-1]*recall[:-1]/np.maximum(precision[:-1]+recall[:-1],1e-12)
    return float(thresholds[np.argmax(score)])


def metrics(y,p,threshold):
    pred=(p>=threshold).astype(int)
    return {'n':len(y),'positive':int(y.sum()),'average_precision':float(average_precision_score(y,p)),
            'roc_auc':float(roc_auc_score(y,p)),'accuracy':float(accuracy_score(y,pred)),
            'precision':float(precision_score(y,pred,zero_division=0)),
            'recall':float(recall_score(y,pred,zero_division=0)),
            'f1':float(f1_score(y,pred,zero_division=0)),
            'confusion_matrix':confusion_matrix(y,pred,labels=[0,1]).tolist()}


def cluster_intervals(y,groups,predictions,replicates=2000,seed=2026):
    rng=np.random.default_rng(seed);firms=np.unique(groups);indices={f:np.flatnonzero(groups==f) for f in firms}
    values={m:[] for m in VARIANTS};differences={m:[] for m in VARIANTS if m!='cross_attention'};valid=0
    for _ in range(replicates):
        ix=np.concatenate([indices[f] for f in rng.choice(firms,len(firms),replace=True)])
        if len(np.unique(y[ix]))<2:continue
        score={m:float(np.mean([average_precision_score(y[ix],p[ix]) for p in predictions[m]])) for m in VARIANTS}
        for m in VARIANTS:values[m].append(score[m])
        for m in differences:differences[m].append(score['cross_attention']-score[m])
        valid+=1
    def interval(v):return np.quantile(v,[.025,.975]).tolist() if v else None
    return {'estimand':'Mean single-run test average precision across prespecified seeds; paired company-cluster bootstrap',
            'replicates_requested':replicates,'replicates_valid':valid,
            'model_AP_95CI':{m:interval(v) for m,v in values.items()},
            'cross_attention_minus_baseline_AP_95CI':{m:interval(v) for m,v in differences.items()},
            'note':'Conditional on this frozen sample and fitted models; not a population-representative or causal interval. Training variability is reported separately across seeds.'}


def run(root,output,epochs=100,bootstrap=None):
    root=Path(root);out=Path(output);out.mkdir(parents=True,exist_ok=True)
    m,records=load_frozen(root);protocol=m['protocol']
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    ix={s:np.array([i for i,r in enumerate(records) if r['split']==s]) for s in ('train','validation','test')}
    y=np.array([r['label'] for r in records]);raw=np.array([r['features'] for r in records],dtype=float)
    transform=FinancialTransform().fit(raw[ix['train']]);financial=transform.transform(raw)
    text,mask,vectorizer,svd=text_arrays(records,ix['train'],protocol['text'])
    import pickle,platform,sklearn
    (out/'preprocessing.pkl').write_bytes(pickle.dumps({'financial':transform,'tfidf':vectorizer,'svd':svd}))
    x=torch.from_numpy(financial);t=torch.from_numpy(text);padding=torch.from_numpy(mask);target=torch.tensor(y,dtype=torch.float32)
    train,val,test=(ix[s] for s in ('train','validation','test'))
    weight=torch.tensor((len(train)-y[train].sum())/y[train].sum(),dtype=torch.float32)
    all_results=[];test_predictions={v:[] for v in VARIANTS};logs=[];prediction_rows=[]
    for variant in VARIANTS:
        for seed in protocol['model']['seeds']:
            random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
            model=Model(variant,protocol['model']['width'],protocol['text']['svd_dimensions'])
            optimizer=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=.0001)
            lossfn=nn.BCEWithLogitsLoss(pos_weight=weight);best=-1;best_state=None;stale=0;best_epoch=0
            for epoch in range(1,epochs+1):
                model.train();order=np.random.permutation(train);total=0.
                for start in range(0,len(order),64):
                    batch=order[start:start+64];optimizer.zero_grad()
                    loss=lossfn(model(x[batch],t[batch],padding[batch]),target[batch]);loss.backward()
                    nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step();total+=float(loss.detach())*len(batch)
                model.eval()
                with torch.no_grad():vp=torch.sigmoid(model(x[val],t[val],padding[val])).numpy()
                ap=float(average_precision_score(y[val],vp));logs.append({'variant':variant,'seed':seed,'epoch':epoch,'train_loss':total/len(train),'validation_AP':ap})
                if ap>best+1e-8:best=ap;best_state=copy.deepcopy(model.state_dict());stale=0;best_epoch=epoch
                else:stale+=1
                if stale>=15:break
            model.load_state_dict(best_state);model.eval()
            with torch.no_grad():prob=torch.sigmoid(model(x,t,padding)).numpy()
            threshold=choose_threshold(y[val],prob[val]);test_predictions[variant].append(prob[test])
            result={'variant':variant,'seed':seed,'best_epoch':best_epoch,'threshold':threshold,
                    'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad),
                    'validation':metrics(y[val],prob[val],threshold),'test':metrics(y[test],prob[test],threshold)}
            all_results.append(result);torch.save(best_state,out/f'{variant}-seed{seed}.pt')
            for i,r in enumerate(records):prediction_rows.append({'sample_id':r['sample_id'],'firm_id':r['firm_id'],'split':r['split'],'label':int(y[i]),'probability':float(prob[i]),'threshold':threshold,'variant':variant,'seed':seed})
            print(json.dumps(result),flush=True)
    import csv
    with (out/'predictions.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(prediction_rows[0]));w.writeheader();w.writerows(prediction_rows)
    (out/'training_log.json').write_text(json.dumps(logs,indent=2)+'\n')
    ci=cluster_intervals(y[test],np.array([records[i]['firm_id'] for i in test]),test_predictions,bootstrap or protocol['evaluation']['bootstrap_replicates'])
    aggregate={v:{metric:{'mean':float(np.mean([r['test'][metric] for r in all_results if r['variant']==v])),
                         'seed_sd':float(np.std([r['test'][metric] for r in all_results if r['variant']==v],ddof=1))}
                    for metric in ('average_precision','roc_auc','f1','precision','recall','accuracy')} for v in VARIANTS}
    result={'dataset_sha256':m['dataset_sha256'],'frozen_summary':m['summary'],'runs':all_results,'aggregate':aggregate,'intervals':ci,
            'runtime':{'python':platform.python_version(),'numpy':np.__version__,'sklearn':sklearn.__version__,'torch':torch.__version__},
            'training':{'max_epochs':epochs,'batch_size':64,'learning_rate':.001,'weight_decay':.0001,'patience':15,'selection':'validation AP checkpoint; validation F1 threshold'},
            'limitations':m['limitations']+['Intervals may be wide because positive events are sparse. No gate contribution is tested in this simplified design.']}
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for v in VARIANTS:
        # Each line is a prespecified seed, never a best-test seed or ensemble.
        for j,p in enumerate(test_predictions[v]):
            pr,rc,_=precision_recall_curve(y[test],p);fpr,tpr,_=roc_curve(y[test],p)
            axes[0].plot(rc,pr,label=f'{v} / {protocol["model"]["seeds"][j]}',alpha=.65)
            axes[1].plot(fpr,tpr,alpha=.65)
    axes[0].axhline(y[test].mean(),color='gray',linestyle=':');axes[0].set(xlabel='Recall',ylabel='Precision')
    axes[1].plot([0,1],[0,1],'k:');axes[1].set(xlabel='False positive rate',ylabel='True positive rate')
    axes[0].legend(fontsize=5);fig.tight_layout();fig.savefig(out/'test_curves.png',dpi=300);plt.close(fig)
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='output_manifest.json'}
    (out/'output_manifest.json').write_text(json.dumps(files,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--output',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=100);p.add_argument('--bootstrap',type=int)
    a=p.parse_args();run(a.root,a.output,a.epochs,a.bootstrap)
