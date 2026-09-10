import numpy as np
from sklearn.metrics import roc_auc_score,average_precision_score

def classification_metrics(y,p,threshold=.5):
    y=np.asarray(y);p=np.asarray(p,dtype=float)
    if y.shape!=p.shape or y.ndim!=1 or not len(y):raise ValueError('Aligned nonempty arrays required')
    if not np.isin(y,[0,1]).all() or not np.isfinite(p).all() or ((p<0)|(p>1)).any():raise ValueError('Invalid labels/probabilities')
    if not np.isfinite(threshold) or not 0<=threshold<=1:raise ValueError('Invalid classification threshold')
    y=y.astype(int)
    pred=p>=threshold
    tp=int(((y==1)&pred).sum());fp=int(((y==0)&pred).sum())
    tn=int(((y==0)&~pred).sum());fn=int(((y==1)&~pred).sum())
    def ratio(a,b):return a/b if b else None
    return {'n':len(y),'positive':int(y.sum()),'tp':tp,'fp':fp,'tn':tn,'fn':fn,
      'accuracy':ratio(tp+tn,len(y)),'precision':ratio(tp,tp+fp),'recall':ratio(tp,tp+fn),
      'specificity':ratio(tn,tn+fp),'f1':ratio(2*tp,2*tp+fp+fn),
      'roc_auc':float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None,
      'average_precision':float(average_precision_score(y,p)) if len(np.unique(y))==2 else None,
      'brier':float(np.mean((y-p)**2)),'threshold':threshold,
      'undefined_metrics':[name for name,den in [('precision',tp+fp),('recall',tp+fn),('specificity',tn+fp),('f1',2*tp+fp+fn)] if not den]}

def paired_firm_bootstrap(y,p_a,p_b,firms,metric='roc_auc',repetitions=2000,seed=42,threshold=.5):
    """Resample firms, retaining all their years and multiplicity. Conditional on fixed models."""
    y,p_a,p_b,firms=map(np.asarray,(y,p_a,p_b,firms))
    if not (len(y)==len(p_a)==len(p_b)==len(firms)):raise ValueError('Predictions must align on the same samples')
    unique=np.unique(firms)
    if len(unique)<2:raise ValueError('Need at least two firms; more are required for a credible interval')
    if repetitions<2:raise ValueError('At least two resamples required')
    groups={f:np.flatnonzero(firms==f) for f in unique};rng=np.random.default_rng(seed);delta=[]
    if metric not in ('f1','roc_auc','average_precision','accuracy','precision','recall','specificity','brier'):raise ValueError('Unsupported bootstrap metric')
    a=classification_metrics(y,p_a,threshold)[metric];b=classification_metrics(y,p_b,threshold)[metric]
    def score(labels,scores):
        # F1 is the primary contrast: avoid computing unused ranking metrics 4,000 times.
        if metric=='f1':
            positive=scores>=threshold
            tp=np.sum((labels==1)&positive);den=np.sum(labels==1)+np.sum(positive)
            return float(2*tp/den) if den else None
        if metric=='roc_auc':return float(roc_auc_score(labels,scores)) if len(np.unique(labels))==2 else None
        return classification_metrics(labels,scores,threshold)[metric]
    for _ in range(repetitions):
        idx=np.concatenate([groups[f] for f in rng.choice(unique,len(unique),replace=True)])
        ma=score(y[idx],p_a[idx]);mb=score(y[idx],p_b[idx])
        if ma is not None and mb is not None:delta.append(ma-mb)
    return {'metric':metric,'difference':None if a is None or b is None else a-b,
      'ci95':np.quantile(delta,[.025,.975]).tolist() if len(delta)>=2 else None,
      'valid_resamples':len(delta),'requested_resamples':repetitions,'seed':seed,'threshold':threshold,
      'scope':'firm sampling uncertainty conditional on fitted models; does not replace repeated-seed training'}
