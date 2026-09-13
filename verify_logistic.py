from pathlib import Path
import json,csv,math
R=Path(__file__).resolve().parent;p=list(csv.DictReader((R/'baseline/predictions.csv').open()));r=json.loads((R/'baseline/results.json').read_text());assert len(p)==len({x['sample_id'] for x in p})==969
checks=[]
for sp in ['validation','test']:
 q=[x for x in p if x['split']==sp];y=[int(x['label']) for x in q];scores=[float(x['probability']) for x in q];t=r['threshold'];tp=sum(a and b>=t for a,b in zip(y,scores));fp=sum(not a and b>=t for a,b in zip(y,scores));fn=sum(y)-tp;tn=len(y)-tp-fp-fn;seen=cum=0;ap=0
 for v in sorted(set(scores),reverse=True):
  g=[a for a,b in zip(y,scores) if b==v];seen+=len(g);cum+=sum(g);ap+=sum(g)/sum(y)*cum/seen
 pos=[b for a,b in zip(y,scores) if a];neg=[b for a,b in zip(y,scores) if not a];auc=sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg));actual=dict(average_precision=ap,roc_auc=auc,precision=tp/max(1,tp+fp),recall=tp/sum(y),f1=2*tp/max(1,2*tp+fp+fn),accuracy=(tp+tn)/len(y));assert [[tn,fp],[fn,tp]]==r[sp]['confusion_matrix'];assert all(math.isclose(v,r[sp][k],abs_tol=1e-12) for k,v in actual.items());checks.append(sp)
(R/'evidence/logistic_verification.json').write_text(json.dumps({'rows':969,'independent_metric_checks':checks,'passed':True,'fit_count':1},indent=2)+'\n');print('Logistic predictions and both metric groups independently verified.')
