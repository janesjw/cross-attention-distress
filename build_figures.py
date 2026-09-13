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
def save(fig,n):
 fig.savefig(F/f'figure_{n}.png',dpi=250,bbox_inches='tight');fig.savefig(F/f'figure_{n}.svg',bbox_inches='tight');plt.close(fig)
def box(ax,x,y,text):ax.text(x,y,text,ha='center',va='center',fontsize=9,bbox=dict(boxstyle='round,pad=.5',fc='#f4f4f4',ec='#555'))
def arrow(ax,a,b):ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color='#555',lw=1.2))
fig,ax=plt.subplots(figsize=(7,3.3));ax.axis('off');ax.set(xlim=(0,1),ylim=(0,1))
box(ax,.5,.87,'Source inventory\n471 firms / 3,335 firm-years');box(ax,.5,.51,'Common analytical sample\n155 firms / 969 firm-years / 26 events');arrow(ax,(.5,.76),(.5,.63));ax.text(.98,.72,'2,366 excluded\nor unresolved',ha='right',fontsize=8)
for x,t in zip([.16,.5,.84],['Train 2017–2021\n503 rows / 9 events','Validation 2022–2023\n250 rows / 6 events','Test 2024–2025\n216 rows / 11 events']):box(ax,x,.13,t);arrow(ax,(.5,.40),(x,.25))
save(fig,1)
fig,ax=plt.subplots(figsize=(7,3.3));ax.axis('off');ax.set(xlim=(0,1),ylim=(0,1))
box(ax,.24,.86,'12 financial ratios\n+ 12 missing indicators');box(ax,.76,.86,'MD&A from same annual report\n≤16 chunks × 64 SVD dimensions');box(ax,.24,.52,'Financial projection\n64-dimensional query');box(ax,.76,.52,'Text projection\n64-dimensional chunk keys / values');arrow(ax,(.24,.73),(.24,.64));arrow(ax,(.76,.73),(.76,.64));box(ax,.5,.17,'Four-head cross-attention with padding mask\nFinancial vector + context → classifier');arrow(ax,(.24,.40),(.39,.29));arrow(ax,(.76,.40),(.61,.29));save(fig,2)
c=pd.read_csv(R/'evidence/training_correlation.csv',index_col=0);short=['L/A','CR','QR','NP/A','NP/E','OM','NM','AR/A','INV/A','OCF/A','OCF/CL','ME/R']
fig,ax=plt.subplots(figsize=(7,5));im=ax.imshow(c,vmin=-1,vmax=1,cmap='RdBu_r');ax.set_xticks(range(12),short,rotation=45,ha='right');ax.set_yticks(range(12),short)
for i in range(12):
 for j in range(12):ax.text(j,i,f'{c.iloc[i,j]:.2f}',ha='center',va='center',fontsize=6.5,color='white' if abs(c.iloc[i,j])>.6 else 'black')
fig.colorbar(im,ax=ax,label='Pearson correlation');fig.tight_layout();save(fig,3);c.to_csv(F/'figure_3_data.csv')
def curves(q):
 p=q.probability.to_numpy();y=q.label.to_numpy();ix=np.argsort(-p,kind='stable');p=p[ix];y=y[ix];end=np.r_[np.flatnonzero(np.diff(p)),len(p)-1];tp=np.cumsum(y)[end];fp=(end+1)-tp
 return np.r_[0,tp/y.sum()],np.r_[1,tp/(end+1)],np.r_[0,fp/(len(y)-y.sum())]
fig,axes=plt.subplots(1,2,figsize=(7,3.4))
for v,name,col in zip(variants,names,colors):
 for seed,style in zip(seeds,['-','--',':']):
  q=pred[(pred.variant==v)&(pred.seed==seed)&(pred.split=='test')];rc,pr,fp=curves(q);axes[0].step(rc,pr,where='pre',color=col,ls=style,lw=1);axes[1].plot(fp,rc,color=col,ls=style,lw=1,label=name if seed==17 else None)
q=lp[lp.split=='test'];rc,pr,fp=curves(q);axes[0].step(rc,pr,where='pre',color='#222',lw=1.3);axes[1].plot(fp,rc,color='#222',lw=1.3,label='L2 logistic')
axes[0].axhline(11/216,color='gray',ls=':',lw=.8);axes[1].plot([0,1],[0,1],color='gray',ls=':',lw=.8);axes[0].set(xlabel='Recall',ylabel='Precision',xlim=(0,1),ylim=(0,1.02));axes[1].set(xlabel='False positive rate',ylabel='True positive rate',xlim=(0,1),ylim=(0,1.02));axes[1].legend(fontsize=7,loc='lower right');fig.tight_layout();save(fig,4)
fig,axes=plt.subplots(4,2,figsize=(7,6))
for i,(v,name,col) in enumerate(zip(variants,names,colors)):
 for seed,style in zip(seeds,['-','--',':']):
  q=logs[(logs.variant==v)&(logs.seed==seed)];axes[i,0].plot(q.epoch,q.train_loss,ls=style,color=col,lw=1);axes[i,1].plot(q.epoch,q.validation_AP,ls=style,color=col,lw=1)
 axes[i,0].set_ylabel(name,fontsize=8);axes[i,1].set_ylim(0,max(.3,logs.validation_AP.max()*1.05))
axes[0,0].set_title('Training weighted BCE',fontsize=10);axes[0,1].set_title('Validation average precision',fontsize=10)
for ax in axes[-1]:ax.set_xlabel('Epoch')
fig.tight_layout();save(fig,5)
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
figs={1:['Figure 1: Source inventory and chronological evaluation','Source: Version 2 manifest and candidate decision inventory.'],2:['Figure 2: Financial-query cross-attention over MD&A chunks','Source: Implemented annual model. Concatenation uses mean-pooled text; both fusion models contain 30,721 parameters.'],3:['Figure 3: Common-observation training correlation matrix','Source: Raw ratios for the same 503 complete training observations. Codes are defined in Table 2.'],4:['Figure 4: Test precision–recall and ROC curves','Source: Saved predictions. Neural seeds 17 solid, 42 dashed and 2026 dotted; logistic is black. The PR reference is prevalence, 11/216.'],5:['Figure 5: Recorded neural optimization histories','Source: Actual training loss and validation AP logs. Seeds 17 solid, 42 dashed and 2026 dotted. Validation loss was not recorded.']}
(O/'tables.json').write_text(json.dumps(T,indent=2,ensure_ascii=False));(O/'figure_captions.json').write_text(json.dumps(figs,indent=2))
for k,(title,header,rows,note) in T.items():
 n={'TABLE1':2,'TABLE2':1}.get(k,int(k[-1]));name=f'table_{n}'
 pd.DataFrame(rows,columns=header).to_csv(F/(name+'.csv'),index=False)
 widths={'TABLE1':[.15,.85],'TABLE4':[.21,.23,.28,.14,.14],'TABLE5':[.52,.16,.32],'TABLE7':[.28,.14,.08,.10,.10,.10,.10,.10]}.get(k)
 fig,ax=plt.subplots(figsize=(9,max(1.3,.30*(len(rows)+2))));ax.axis('off');tb=ax.table(cellText=rows,colLabels=header,colWidths=widths,cellLoc='center',loc='center');tb.auto_set_font_size(False);tb.set_fontsize(8);tb.scale(1,1.5)
 for (i,j),cell in tb.get_celld().items():
  cell.set_edgecolor('#888');cell.set_linewidth(.5);cell.set_facecolor('#eee' if i==0 else 'white')
 fig.savefig(F/(name+'.png'),dpi=220,bbox_inches='tight');fig.savefig(F/(name+'.svg'),bbox_inches='tight');plt.close(fig)
