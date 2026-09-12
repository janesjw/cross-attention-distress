"""Verify package integrity and all 12 saved runs; no training and no external libraries."""
import csv,json,sys,math
from pathlib import Path
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'src'))
from distress.annual_freeze import load_frozen
m,rows=load_frozen(R);keys={r['sample_id']:r for r in rows}
assert len({(r['firm_id'],r['origin']) for r in rows})==843
assert len({r['firm_id'] for r in rows})==154
pred=list(csv.DictReader((R/'results/predictions.csv').open(newline='')))
result=json.loads((R/'results/results.json').read_text())
assert result['dataset_sha256']==m['dataset_sha256']
assert len(pred)==12*843
checks=0
for run in result['runs']:
    pp=[r for r in pred if r['variant']==run['variant'] and int(r['seed'])==run['seed']]
    assert len(pp)==843 and len({r['sample_id'] for r in pp})==843
    for r in pp:
        s=keys[r['sample_id']];assert r['firm_id']==s['firm_id'] and r['split']==s['split'] and int(r['label'])==s['label']
        assert float(r['threshold'])==run['threshold'] and 0<=float(r['probability'])<=1
    for split in ('validation','test'):
        pp2=[r for r in pp if r['split']==split]; y=[int(r['label']) for r in pp2];p=[float(r['probability']) for r in pp2]
        scores={v:[] for v in p}
        for a,b in zip(y,p):scores[b].append(a)
        tp=seen=0;ap=0.;positives=sum(y)
        for v in sorted(scores,reverse=True):
            group=scores[v];tp+=sum(group);seen+=len(group);ap+=sum(group)/positives*tp/seen
        ps=[b for a,b in zip(y,p) if a];ns=[b for a,b in zip(y,p) if not a]
        auc=sum((a>b)+.5*(a==b) for a in ps for b in ns)/(len(ps)*len(ns))
        c=[[0,0],[0,0]]
        for a,b in zip(y,p):c[a][int(b>=run['threshold'])]+=1
        tn,fp=c[0];fn,tp=c[1]
        actual={'average_precision':ap,'roc_auc':auc,'accuracy':(tn+tp)/len(y),'precision':tp/max(1,tp+fp),'recall':tp/positives,'f1':2*tp/max(1,2*tp+fp+fn)}
        assert c==run[split]['confusion_matrix']
        for k,v in actual.items():assert math.isclose(v,run[split][k],abs_tol=1e-12),(run['variant'],run['seed'],split,k)
        checks+=1
print(json.dumps({'package_hashes':'pass','rows':843,'firms':154,'positive':22,'saved_runs':12,'validation_test_metric_checks':checks,'training_rerun':False}))
