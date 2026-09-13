from pathlib import Path
import numpy as np,json,csv
from sklearn.metrics import average_precision_score
R=Path(__file__).resolve().parent;p=list(csv.DictReader((R/'results/predictions.csv').open()));l=list(csv.DictReader((R/'baseline/predictions.csv').open()));test=sorted([x for x in l if x['split']=='test'],key=lambda x:x['sample_id']);ids=[x['sample_id'] for x in test];y=np.array([int(x['label']) for x in test]);groups=np.array([x['firm_id'] for x in test]);lp=np.array([float(x['probability']) for x in test]);variants=['financial_only','text_only','concat','cross_attention'];neural={}
for v in variants:
 a=[]
 for seed in [17,42,2026]:
  q={x['sample_id']:float(x['probability']) for x in p if x['variant']==v and int(x['seed'])==seed and x['split']=='test'};a.append(np.array([q[i] for i in ids]))
 neural[v]=a
rng=np.random.default_rng(2026);firms=np.unique(groups);ixs={f:np.flatnonzero(groups==f) for f in firms};diff={v:[] for v in variants};ap=[]
for _ in range(2000):
 ix=np.concatenate([ixs[f] for f in rng.choice(firms,len(firms),replace=True)])
 if len(np.unique(y[ix]))<2:continue
 a=average_precision_score(y[ix],lp[ix]);ap.append(float(a))
 for v in variants:diff[v].append(float(np.mean([average_precision_score(y[ix],q[ix]) for q in neural[v]])-a))
r={'paired_company_bootstrap_replicates':2000,'valid_replicates':len(ap),'logistic_AP_95CI':np.quantile(ap,[.025,.975]).tolist(),'neural_mean_AP_minus_logistic_AP_95CI':{v:np.quantile(a,[.025,.975]).tolist() for v,a in diff.items()},'estimand':'Mean of three prespecified neural single-run APs minus one deterministic logistic fit; paired identical company resamples'};(R/'baseline/paired_intervals.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
