"""Recompute a complete review suite from aligned, hashed predictions; never infer missing runs."""
import argparse,csv,hashlib,json
from pathlib import Path
import numpy as np
from distress.database import ROOT
from distress.metrics import classification_metrics,paired_firm_bootstrap

METRICS=('accuracy','precision','recall','specificity','f1','roc_auc','average_precision','brier')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')

def load_run(path):
    path=Path(path);r=json.loads((path/'run_manifest.json').read_text())
    if r['status']!='completed' or r['purpose']!='research':raise ValueError('Incomplete or nonresearch run')
    required={'test_predictions.json','test_metrics.json','history.json','config.json','environment.json'}
    if not required.issubset(r['files_sha256']):raise ValueError('Incomplete file provenance')
    for name in required:
        if sha(path/name)!=r['files_sha256'][name]:raise ValueError(f'Run file changed: {name}')
    if sha(path/'best.pt')!=r['checkpoint_sha256']:raise ValueError('Checkpoint changed')
    rows=json.loads((path/'test_predictions.json').read_text())
    if not rows or len({x['sample_id'] for x in rows})!=len(rows):raise ValueError('Empty or duplicate test sample')
    rows=sorted(rows,key=lambda x:x['sample_id'])
    for x in rows:
        if x['split']!='test' or x['origin'] not in ('2024-05-01','2025-05-01'):raise ValueError('Not the prescribed temporal test sample')
    classification_metrics([x['label'] for x in rows],[x['probability'] for x in rows],r['threshold'])
    if {x['label'] for x in rows}!={0,1}:raise ValueError('Pooled test sample requires both outcome classes')
    cfg=json.loads((path/'config.json').read_text())
    if cfg['seed']!=r['seed'] or cfg['variant']!=r['variant']:raise ValueError('Config and receipt differ')
    r['shared_config']={k:v for k,v in cfg.items() if k not in ('seed','variant')}
    return r,rows

def summarize(runs,protocol,output,figures=True):
    cfg=json.loads(Path(protocol).read_text());runs=Path(runs);output=Path(output)
    loaded={};reference=None;provenance=None;shared=None
    for seed in cfg['seeds']:
        for variant in cfg['variants']:
            path=runs/f'{variant}-seed{seed}';receipt,rows=load_run(path)
            if (receipt['variant'],receipt['seed'],receipt['threshold'])!=(variant,seed,cfg['threshold']):raise ValueError('Run identity or threshold differs')
            key=[(x['sample_id'],x['firm_id'],x['origin'],x['label']) for x in rows]
            origin=(receipt['dataset_id'],receipt['manifest_sha256'])
            if reference is None:reference=key;provenance=origin;shared=receipt['shared_config']
            if key!=reference or origin!=provenance:raise ValueError('Predictions do not share the identical sample and labels')
            if shared!=receipt['shared_config']:raise ValueError('Unmatched model/training configuration')
            loaded[variant,seed]=(receipt,rows,path)
    y=np.array([x[3] for x in reference]);firms=np.array([x[1] for x in reference]);years=np.array([x[2][:4] for x in reference])
    records=[];contrasts=[]
    for (variant,seed),(receipt,rows,path) in loaded.items():
        scores=np.array([r['probability'] for r in rows])
        for period in ('pooled','2024','2025'):
            mask=np.ones(len(y),dtype=bool) if period=='pooled' else years==period
            if not mask.any():raise ValueError('Missing test year')
            m=classification_metrics(y[mask],scores[mask],cfg['threshold'])
            records.append({'model':variant,'seed':seed,'period':period,**m})
        recomputed=records[-3];saved=json.loads((path/'test_metrics.json').read_text())
        for k in ('n','positive','tp','fp','tn','fn',*METRICS):
            a,b=recomputed[k],saved.get(k)
            if (a is None)!=(b is None) or a is not None and not np.isclose(a,b,rtol=0,atol=1e-10):
                raise ValueError(f'Saved metric differs from predictions: {variant}/{seed}/{k}')
    for seed in cfg['seeds']:
        full=np.array([x['probability'] for x in loaded['sequence_cross_attention',seed][1]])
        for contrast,control in cfg['contrasts'].items():
            other=np.array([x['probability'] for x in loaded[control,seed][1]])
            for metric in ('f1','roc_auc'):
                interval=paired_firm_bootstrap(y,full,other,firms,metric=metric,
                  repetitions=cfg['bootstrap_repetitions'],seed=seed,threshold=cfg['threshold'])
                contrasts.append({'contrast':contrast,'control':control,'training_seed':seed,**interval})
    aggregates=[]
    for model in cfg['variants']:
        for period in ('pooled','2024','2025'):
            selected=[r for r in records if r['model']==model and r['period']==period]
            metrics={}
            for metric in METRICS:
                values=[r[metric] for r in selected if r[metric] is not None]
                metrics[metric]={'mean':float(np.mean(values)) if values else None,
                  'seed_sd':float(np.std(values,ddof=1)) if len(values)>1 else None,'defined_seeds':len(values)}
            aggregates.append({'model':model,'period':period,'metrics':metrics})
    result={'status':'recomputed_from_completed_runs','dataset_id':provenance[0],
      'manifest_sha256':provenance[1],'protocol_sha256':sha(protocol),'completed_runs':len(loaded),
      'test_samples':len(y),'test_firms':len(set(firms)),'test_positives':int(y.sum()),
      'per_run_metrics':records,'seed_summaries':aggregates,'paired_conditional_intervals':contrasts,
      'interpretation':'Seed SD is not a confidence interval. Bootstrap intervals condition on each fitted model pair. No familywise significance, semantic causality or early textual lead time is inferred.'}
    output.mkdir(parents=True,exist_ok=True);write(output/'results.json',result)
    with (output/'metrics.csv').open('w',newline='') as f:
        fields=['model','seed','period','n','positive','tp','fp','tn','fn',*METRICS,'threshold']
        writer=csv.DictWriter(f,fields,extrasaction='ignore');writer.writeheader();writer.writerows(records)
    if figures:plot(loaded,cfg,output)
    return result

def plot(loaded,cfg,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve,precision_recall_curve
    def save(fig,name):
        fig.tight_layout();fig.savefig(output/(name+'.svg'));fig.savefig(output/(name+'.png'),dpi=300);plt.close(fig)
    for seed in cfg['seeds']:
        fig,axes=plt.subplots(1,2,figsize=(11,4.4))
        cm,grid=plt.subplots(2,4,figsize=(12,6))
        for i,variant in enumerate(cfg['variants']):
            _,rows,_=loaded[variant,seed];y=np.array([r['label'] for r in rows]);p=np.array([r['probability'] for r in rows])
            m=classification_metrics(y,p,cfg['threshold']);fpr,tpr,_=roc_curve(y,p);precision,recall,_=precision_recall_curve(y,p)
            axes[0].plot(fpr,tpr,label=f"{variant} ({m['roc_auc']:.3f})")
            axes[1].plot(recall,precision,label=variant)
            ax=grid.flat[i];matrix=np.array([[m['tn'],m['fp']],[m['fn'],m['tp']]])
            ax.imshow(matrix,cmap='Blues');ax.set_title(variant,fontsize=9)
            ax.set_xticks([0,1],['0','1']);ax.set_yticks([0,1],['0','1']);ax.set_xlabel('Predicted');ax.set_ylabel('Observed')
            for (row,col),value in np.ndenumerate(matrix):ax.text(col,row,str(value),ha='center',va='center',color='white' if value>matrix.max()/2 else 'black')
        for ax in list(grid.flat)[len(cfg['variants']):]:ax.axis('off')
        axes[0].plot([0,1],[0,1],'k--',lw=.8);axes[0].set(xlabel='False positive rate',ylabel='True positive rate',title=f'ROC — seed {seed}')
        axes[1].axhline(float(y.mean()),ls='--',c='k',lw=.8);axes[1].set(xlabel='Recall',ylabel='Precision',title=f'Precision–recall — seed {seed}')
        for ax in axes:ax.legend(fontsize=6);ax.set_xlim(0,1);ax.set_ylim(0,1)
        save(fig,f'curves_seed{seed}');save(cm,f'confusion_matrices_seed{seed}')
    fig,axes=plt.subplots(1,len(cfg['seeds']),figsize=(11,3.5),squeeze=False)
    for ax,seed in zip(axes.flat,cfg['seeds']):
        history=json.loads((loaded['sequence_cross_attention',seed][2]/'history.json').read_text())
        ax.plot([h['epoch'] for h in history],[h['train_focal_loss'] for h in history],label='Training')
        ax.plot([h['epoch'] for h in history],[h['validation_focal_loss'] for h in history],label='Validation')
        ax.set(xlabel='Epoch',ylabel='Focal loss',title=f'MMAN — seed {seed}');ax.legend()
    save(fig,'training_curves')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runs',type=Path,required=True)
    p.add_argument('--protocol',type=Path,default=ROOT/'configs/fast_review_protocol.json');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=summarize(a.runs,a.protocol,a.output);print(json.dumps({k:result[k] for k in ('status','completed_runs','test_samples','test_positives')}))
