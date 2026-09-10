"""Independently recalculate saved test metrics and write a concise result report."""
from pathlib import Path
import csv
import hashlib
import json
import sys
import numpy as np
from sklearn.metrics import average_precision_score,roc_auc_score
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from distress.annual_freeze import split_counts


def summarize(root=ROOT):
    registry=json.loads((root/'file_manifest.json').read_text())
    frozen_path=root/'data/derived/annual_st/frozen_manifest.json'
    if hashlib.sha256(frozen_path.read_bytes()).hexdigest()!=registry[frozen_path.relative_to(root).as_posix()]:raise ValueError('Frozen manifest changed')
    frozen=json.loads(frozen_path.read_text())
    index_path=root/'data/derived/annual_st/sample_inventory.csv'
    if hashlib.sha256(index_path.read_bytes()).hexdigest()!=frozen['evidence_hashes'][index_path.relative_to(root).as_posix()]:raise ValueError('Use the inventory snapshot named by the frozen manifest')
    records=[r for r in csv.DictReader(index_path.open()) if r['analytical_eligible']=='True']
    for r in records:r['label']=int(r['label'])
    if split_counts(records)!=frozen['summary']['splits']:raise ValueError('Frozen index counts mismatch')
    folder=root/'data/derived/annual_st/results' 
    result=json.loads((folder/'results.json').read_text())
    if result['dataset_sha256']!=frozen['dataset_sha256']:raise ValueError('Results dataset digest mismatch')
    predictions=list(csv.DictReader((folder/'predictions.csv').open()))
    expected={r['sample_id']:r for r in records};checks=[]
    expected_runs={(v,s) for v in frozen['protocol']['model']['variants'] for s in frozen['protocol']['model']['seeds']}
    if {(r['variant'],r['seed']) for r in result['runs']}!=expected_runs or len(result['runs'])!=len(expected_runs):raise ValueError('Incomplete model/seed experiment set')
    if len(predictions)!=len(records)*len(expected_runs):raise ValueError('Unexpected prediction row count')
    for run in result['runs']:
        rows=[r for r in predictions if r['variant']==run['variant'] and int(r['seed'])==run['seed']]
        if len(rows)!=len(expected) or {r['sample_id'] for r in rows}!=set(expected):raise ValueError('Prediction sample IDs mismatch')
        for r in rows:
            if not 0<=float(r['probability'])<=1 or not np.isclose(float(r['threshold']),run['threshold'],rtol=1e-12):raise ValueError('Probability or threshold mismatch')
            if int(r['label'])!=expected[r['sample_id']]['label'] or r['split']!=expected[r['sample_id']]['split']:raise ValueError('Prediction labels/splits mismatch')
        rows=[r for r in rows if r['split']=='test'];y=np.array([int(r['label']) for r in rows]);p=np.array([float(r['probability']) for r in rows]);q=p>=run['threshold']
        tp=int(((y==1)&q).sum());fp=int(((y==0)&q).sum());tn=int(((y==0)&~q).sum());fn=int(((y==1)&~q).sum())
        recalculated={'n':len(rows),'positive':int(y.sum()),'average_precision':float(average_precision_score(y,p)),
            'roc_auc':float(roc_auc_score(y,p)),'accuracy':(tp+tn)/len(y),'precision':tp/(tp+fp) if tp+fp else 0.,
            'recall':tp/(tp+fn),'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,'confusion_matrix':[[tn,fp],[fn,tp]]}
        for key,value in recalculated.items():
            if key=='confusion_matrix':
                if value!=run['test'][key]:raise ValueError('Confusion matrix mismatch')
            elif not np.isclose(value,run['test'][key],rtol=1e-10,atol=1e-10):raise ValueError('Metric mismatch '+key)
        checks.append({'variant':run['variant'],'seed':run['seed'],'passed':True})
    summary=frozen['summary'];ci=result['intervals']
    lines=['# Annual ST empirical reanalysis','',f"Frozen sample: **{summary['final_sample_count']} company-years, {summary['final_firms']} firms**, {summary['positive']} positive and {summary['negative']} negative outcomes.",'',
           '| Split | Rows | Firms | Positive | Negative | Positive firms |','|---|---:|---:|---:|---:|---:|']
    for split,c in summary['splits'].items():lines.append(f"| {split} | {c['rows']} | {c['firms']} | {c['positive']} | {c['negative']} | {c['positive_firms']} |")
    lines+=['','All methods use the same frozen sample. Preprocessing, checkpoint selection and thresholds use training/validation data only. Concatenation and cross-attention have equal trainable parameter budgets.','',
            '| Model | AP mean ± seed SD | AP cluster 95% CI | ROC AUC mean | F1 mean |','|---|---:|---|---:|---:|']
    for model,a in result['aggregate'].items():
        bounds=ci['model_AP_95CI'][model]
        lines.append(f"| {model} | {a['average_precision']['mean']:.4f} ± {a['average_precision']['seed_sd']:.4f} | [{bounds[0]:.4f}, {bounds[1]:.4f}] | {a['roc_auc']['mean']:.4f} | {a['f1']['mean']:.4f} |")
    lines+=['','Paired company-cluster intervals for cross-attention minus each baseline (average precision, averaged over prespecified runs):','']
    for model,bounds in ci['cross_attention_minus_baseline_AP_95CI'].items():
        interpretation='interval includes zero; improvement not established' if bounds[0]<=0<=bounds[1] else ('interval above zero in this sample' if bounds[0]>0 else 'interval below zero in this sample')
        lines.append(f'- {model}: [{bounds[0]:.4f}, {bounds[1]:.4f}]; {interpretation}.')
    lines+=['',f"Metric audit: all {len(checks)} model/seed outputs reproduce from the saved raw predictions, including test sample IDs, labels, confusion matrices and metrics.",'',
        'Limitations: the dataset is a source-availability subset, with exclusions for unresolved inputs and historical industry. Positive-event counts and interval widths limit inference. Automatic source checks are not full manual audits. The target is new registered ST/*ST, not every form of financial distress. The simplified design does not test a gating mechanism. These results do not validate the original manuscript’s numerical claims or its three theoretical propositions.','',
        'No positive conclusion should be inferred merely because training completed. The cross-attention versus concatenation comparison addresses fusion choice at matched parameter count; the other contrasts and multiple pairwise intervals should be interpreted cautiously.','',
        f"Dataset SHA-256: `{frozen['dataset_sha256']}`."]
    report=folder/'empirical_reanalysis.md';report.write_text('\n'.join(lines)+'\n')
    audit=folder/'metric_recalculation.json';audit.write_text(json.dumps({'dataset_sha256':frozen['dataset_sha256'],'checks':checks,'all_passed':True},indent=2)+'\n')
    manifest=json.loads((root/'file_manifest.json').read_text())
    for p in (report,audit):manifest[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    (root/'file_manifest.json').write_text(json.dumps(dict(sorted(manifest.items())),indent=2)+'\n')
    return {'checked_runs':len(checks),'report':str(report)}


if __name__=='__main__':print(json.dumps(summarize()))
