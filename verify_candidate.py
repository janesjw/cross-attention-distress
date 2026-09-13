"""Verify candidate inputs and recompute all saved metrics without training."""
from pathlib import Path
import sys,json,csv,math,gzip,hashlib
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'src'))
from distress.annual_freeze import load_frozen
m,rows=load_frozen(R);keys={r['sample_id']:r for r in rows};pred=list(csv.DictReader((R/'results/predictions.csv').open()));results=json.loads((R/'results/results.json').read_text());assert len(pred)==12*969 and results['dataset_sha256']==m['dataset_sha256'];checks=[]
for run in results['runs']:
 q=[r for r in pred if r['variant']==run['variant'] and int(r['seed'])==run['seed']];assert len(q)==len({r['sample_id'] for r in q})==969
 for r in q:assert int(r['label'])==keys[r['sample_id']]['label'] and r['split']==keys[r['sample_id']]['split'] and r['firm_id']==keys[r['sample_id']]['firm_id']
 for sp in ['validation','test']:
  pp=[r for r in q if r['split']==sp];y=[int(r['label']) for r in pp];scores=[float(r['probability']) for r in pp];t=run['threshold'];tp=sum(a and b>=t for a,b in zip(y,scores));fp=sum(not a and b>=t for a,b in zip(y,scores));fn=sum(y)-tp;tn=len(y)-tp-fp-fn;ap=0;cum=0;seen=0
  for v in sorted(set(scores),reverse=True):
   group=[a for a,b in zip(y,scores) if b==v];cum+=sum(group);seen+=len(group);ap+=sum(group)/sum(y)*cum/seen
  pos=[b for a,b in zip(y,scores) if a];neg=[b for a,b in zip(y,scores) if not a];auc=sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg));actual=dict(average_precision=ap,roc_auc=auc,precision=tp/max(1,tp+fp),recall=tp/sum(y),f1=2*tp/max(1,2*tp+fp+fn),accuracy=(tp+tn)/len(y));assert [[tn,fp],[fn,tp]]==run[sp]['confusion_matrix']
  for k,v in actual.items():assert math.isclose(v,run[sp][k],abs_tol=1e-12)
  checks.append({'variant':run['variant'],'seed':run['seed'],'split':sp,'metrics_match':True})
report={'candidate_rows':969,'runs':12,'prediction_rows':len(pred),'metric_checks':len(checks),'all_passed':True,'training_rerun_by_verifier':False};(R/'evidence/metric_verification.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
