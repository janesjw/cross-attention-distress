from pathlib import Path
import csv,json,math
R=Path(__file__).resolve().parent;p=list(csv.DictReader((R/'results/predictions.csv').open()));runs=json.loads((R/'results/results.json').read_text())['runs'];out=[];stress=[];sens=[]
base=json.loads((R/'baseline/results.json').read_text());runs.append({'variant':'logistic_regression','seed':0,'threshold':base['threshold']});p += [dict(x,seed='0') for x in csv.DictReader((R/'baseline/predictions.csv').open())]
def met(q,a):
 n=len(q);pos=sum(int(x['label']) for x in q);tp=sum(int(x['label']) for x in a);k=len(a)
 return dict(n=n,positive=pos,alerts=k,TP=tp,FP=k-tp,FN=pos-tp,TN=n-k-pos+tp,precision=tp/k if k else 0,recall=tp/pos,alert_share=k/n)
def threshold(q):
 best=(-1,None);pos=sum(int(x['label']) for x in q)
 for t in sorted({float(x['probability']) for x in q}):
  a=[x for x in q if float(x['probability'])>=t];tp=sum(int(x['label']) for x in a);score=2*tp/(len(a)+pos)
  if score>best[0]:best=(score,t)
 return best[1]
for r in runs:
 q=[x for x in p if x['variant']==r['variant'] and int(x['seed'])==r['seed']];v=[x for x in q if x['split']=='validation'];test=[x for x in q if x['split']=='test'];assert threshold(v)==r['threshold'];base=dict(model=r['variant'],seed=r['seed'])
 for budget in [.05,.1,.2]:
  a=[]
  for year in ['2024','2025']:
   part=[x for x in test if x['sample_id'].endswith(year)];a+=sorted(part,key=lambda x:(-float(x['probability']),x['sample_id']))[:math.ceil(len(part)*budget)]
  out.append({**base,'annual_budget':budget,**met(test,a)})
 for x in v:
  if x['label']!='1':continue
  t=threshold([a for a in v if a['sample_id']!=x['sample_id']]);stress.append({**base,'removed_validation_positive':x['sample_id'],'original_threshold':r['threshold'],'stress_threshold':t,**met(test,[a for a in test if float(a['probability'])>=t])})
 clean=[x for x in test if x['sample_id']!='002325.SZ:2024'];sens.append({**base,'excluded_confirmed_preannounced':'002325.SZ:2024',**met(clean,[x for x in clean if float(x['probability'])>=r['threshold']])})
for name,rr in [('annual_budgets.csv',out),('validation_stress.csv',stress),('preannounced_sensitivity.csv',sens)]:
 with (R/'results'/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
print(len(out),'annual-budget rows,',len(stress),'stress rows,',len(sens),'source-conditioned sensitivities.')
for m in ['financial_only','text_only','concat','cross_attention']:
 q=[x for x in stress if x['model']==m];print(m,'stress alert range',min(x['alerts'] for x in q),max(x['alerts'] for x in q))
