from pathlib import Path
import json,csv,pickle,hashlib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from distress.annual_train import FinancialTransform,choose_threshold,metrics
from distress.annual_freeze import load_frozen
R=Path(__file__).resolve().parent;O=R/'baseline';O.mkdir(exist_ok=True);m,rows=load_frozen(R);train=np.array([i for i,r in enumerate(rows) if r['split']=='train']);val=np.array([i for i,r in enumerate(rows) if r['split']=='validation']);test=np.array([i for i,r in enumerate(rows) if r['split']=='test']);y=np.array([r['label'] for r in rows]);a=np.array([r['features'] for r in rows],float);transform=FinancialTransform().fit(a[train]);x=transform.transform(a);weight=(len(train)-y[train].sum())/y[train].sum();model=LogisticRegression(C=1.0,solver='lbfgs',max_iter=10000,class_weight={0:1.,1:float(weight)},tol=1e-4);model.fit(x[train],y[train]);p=model.predict_proba(x)[:,1];threshold=choose_threshold(y[val],p[val]);assert max(model.n_iter_)<10000
result={'model':'L2_logistic_regression','C':1,'solver':'lbfgs','max_iter':10000,'iterations':model.n_iter_.tolist(),'class_weight':{'negative':1,'positive':float(weight)},'preprocessing':'Same train-only FinancialTransform as neural financial model; 12 ratios plus12missingness flags','threshold_selection':'validation F1 maximum','threshold':threshold,'validation':metrics(y[val],p[val],threshold),'test':metrics(y[test],p[test],threshold),'dataset_sha256':m['dataset_sha256'],'training_records':len(train),'hyperparameter_search':False,'fit_replicates':1}
(O/'results.json').write_text(json.dumps(result,indent=2)+'\n');(O/'model.pkl').write_bytes(pickle.dumps({'model':model,'transform':transform}));q=[]
for r,prob in zip(rows,p):q.append({k:r[k] for k in ['sample_id','firm_id','split','label']}|{'probability':float(prob),'threshold':threshold,'variant':'logistic_regression'})
with (O/'predictions.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(q[0]));w.writeheader();w.writerows(q)
reloaded=pickle.loads((O/'model.pkl').read_bytes());assert np.array_equal(p,reloaded['model'].predict_proba(reloaded['transform'].transform(a))[:,1]);print(json.dumps(result,indent=2))
