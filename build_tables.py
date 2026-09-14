from pathlib import Path
import os,json,re
import numpy as np,pandas as pd
os.environ.setdefault('MPLCONFIGDIR',str(Path.home()/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent;O=R/'manuscript';F=O/'figures';F.mkdir(parents=True,exist_ok=True)
data=json.loads((R/'results/results.json').read_text());lr=json.loads((R/'baseline/results.json').read_text());lc=json.loads((R/'baseline/paired_intervals.json').read_text())
pred=pd.read_csv(R/'results/predictions.csv');logs=pd.read_json(R/'results/training_log.json');lp=pd.read_csv(R/'baseline/predictions.csv')
variants=['financial_only','text_only','concat','cross_attention'];names=['Financial neural','Text neural','Concatenation','Cross-attention'];colors=['#294e6c','#a36631','#4f7960','#784c78'];seeds=[17,42,2026]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
short=['L/A','CR','QR','NP/A','NP/E','OM','NM','AR/A','INV/A','OCF/A','OCF/CL','ME/R']
T={}
T['TABLE2']=('Table 1: Common sample by chronological partition',['Partition','Origins','Firm-years','Events'],[['Training','2017–2021','503','9'],['Validation','2022–2023','250','6'],['Test','2024–2025','216','11'],['Total','2017–2025','969','26']],'Source: Version 2 input manifest. Total unique firms = 155; firms may occur in more than one partition.')
defs=[('L/A','Liabilities / assets'),('CR','Current assets / current liabilities'),('QR','(Current assets − inventory) / current liabilities'),('NP/A','Consolidated net profit / year-end assets'),('NP/E','Consolidated net profit / year-end equity'),('OM','Operating profit / revenue'),('NM','Consolidated net profit / revenue'),('AR/A','Accounts receivable / assets'),('INV/A','Inventory / assets'),('OCF/A','Operating cash flow / assets'),('OCF/CL','Operating cash flow / current liabilities'),('ME/R','Management expenses / revenue')]
T['TABLE1']=('Table 2: Annual financial ratios',['Code','Definition'],defs,'Source: Annual feature protocol. Stock denominators are year-end balances; ratios are dimensionless. Zero denominators produce missing values.')
d=pd.read_csv(R/'evidence/training_descriptives.csv')
T['TABLE3']=('Table 3: Raw training financial ratios',['Code','Valid n','Mean','SD','Median'],[[short[i],str(row.valid_n),f'{row.mean:.3f}',f'{row.sd:.3f}',f'{row.median:.3f}'] for i,row in enumerate(d.itertuples(index=False))],'Source: The unchanged 503 training records, before winsorization, imputation or scaling.')
ag=data['aggregate'];ci=data['intervals']['model_AP_95CI']
rows=[['L2 logistic',f"{lr['test']['average_precision']:.4f}",f"[{lc['logistic_AP_95CI'][0]:.4f}, {lc['logistic_AP_95CI'][1]:.4f}]",f"{lr['test']['roc_auc']:.4f}",f"{lr['test']['recall']:.4f}"]]
rows += [[n,f"{ag[v]['average_precision']['mean']:.4f} ± {ag[v]['average_precision']['seed_sd']:.4f}",f'[{ci[v][0]:.4f}, {ci[v][1]:.4f}]',f"{ag[v]['roc_auc']['mean']:.4f}",f"{ag[v]['recall']['mean']:.4f}"] for v,n in zip(variants,names)]
T['TABLE4']=('Table 4: Test ranking and event recall',['Model','AP mean ± SD','AP 95% CI','ROC AUC','Recall'],rows,'Source: 216 test records, 11 events. Logistic is one fit; neural entries are three-seed means. SD is across seeds; confidence intervals use 2,000 company-cluster draws. Recall uses validation-selected thresholds.')
pair=data['intervals']['cross_attention_minus_baseline_AP_95CI'];rows=[]
for v,n in zip(variants[:3],names[:3]):rows.append(['Cross-attention − '+n,f"{ag['cross_attention']['average_precision']['mean']-ag[v]['average_precision']['mean']:.4f}",f'[{pair[v][0]:.4f}, {pair[v][1]:.4f}]'])
v='financial_only';a,b=lc['neural_mean_AP_minus_logistic_AP_95CI'][v];rows.append(['Financial neural − L2 logistic',f"{ag[v]['average_precision']['mean']-lr['test']['average_precision']:.4f}",f'[{a:.4f}, {b:.4f}]'])
T['TABLE5']=('Table 5: Paired test AP differences',['Comparison','Difference','Paired 95% CI'],rows,'Source: Identical company resamples across models, 2,000 valid draws. Intervals are conditional on fitted models and are not multiplicity-adjusted.')
budget=pd.read_csv(R/'results/annual_budgets.csv');rows=[]
for v,n in [('logistic_regression','L2 logistic')]+list(zip(variants,names)):
 q=budget[budget.model==v];row=[n]
 for b in [.05,.1,.2]:
  a=q[q.annual_budget==b];row.append(f'{a.precision.mean():.4f} / {a.recall.mean():.4f}')
 rows.append(row)
T['TABLE6']=('Table 6: Precision / recall at annual alert budgets',['Model','5% budget','10% budget','20% budget'],rows,'Source: Saved test scores ranked separately within each year. Rounded-up annual selections give 11, 22 and 44 total alerts. Entries are precision / recall; neural entries average three runs.')
rows=[['L2 logistic',f"{lr['threshold']:.6f}",'—',f"{lr['test']['average_precision']:.4f}",*[str(x) for row in lr['test']['confusion_matrix'] for x in row]]]
rows += [[names[variants.index(r['variant'])]+' / '+str(r['seed']),f"{r['threshold']:.6f}",str(r['best_epoch']),f"{r['test']['average_precision']:.4f}",*[str(x) for row in r['test']['confusion_matrix'] for x in row]] for r in data['runs']]
T['TABLE7']=('Supplementary Table S1: All test runs',['Model / seed','Threshold','Epoch','AP','TN','FP','FN','TP'],rows,'Source: Saved scores; each confusion matrix totals 216 records and 11 events. Logistic converged in 42 solver iterations; it has no neural epoch.')
(O/'tables.json').write_text(json.dumps(T,indent=2,ensure_ascii=False))
for k,(title,header,rows,note) in T.items():
 n={'TABLE1':2,'TABLE2':1}.get(k,int(k[-1]));name=f'table_{n}'
 pd.DataFrame(rows,columns=header).to_csv(F/(name+'.csv'),index=False)
 widths={'TABLE1':[.15,.85],'TABLE4':[.21,.23,.28,.14,.14],'TABLE5':[.52,.16,.32],'TABLE7':[.28,.14,.08,.10,.10,.10,.10,.10]}.get(k)
 fig,ax=plt.subplots(figsize=(9,max(1.3,.30*(len(rows)+2))));ax.axis('off');tb=ax.table(cellText=rows,colLabels=header,colWidths=widths,cellLoc='center',loc='center');tb.auto_set_font_size(False);tb.set_fontsize(8);tb.scale(1,1.5)
 for (i,j),cell in tb.get_celld().items():
  cell.set_edgecolor('#888');cell.set_linewidth(.5);cell.set_facecolor('#eee' if i==0 else 'white')
 fig.savefig(F/(name+'.png'),dpi=220,bbox_inches='tight');fig.savefig(F/(name+'.svg'),bbox_inches='tight');plt.close(fig)
