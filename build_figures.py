"""Draw the five paper figures from archived inputs using Matplotlib.

Standalone: python plot_figures.py
Repository: python build_figures.py --root . --output manuscript/figures
No fitting, smoothing, simulated data or generated artwork is used.
"""
from pathlib import Path
import argparse, csv, hashlib, json, os
os.environ.setdefault('MPLCONFIGDIR', str(Path(os.environ.get('TMPDIR', '/tmp')) / 'st-paper-matplotlib'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator

P=Path(__file__).resolve().parent
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--root',type=Path,default=P/'data' if (P/'data/results').exists() else P)
ap.add_argument('--output',type=Path,default=None)
a=ap.parse_args();R=a.root;O=a.output or (P/'manuscript/figures' if (P/'manuscript').exists() else P/'figures');O.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'serif','font.serif':['STIXGeneral','DejaVu Serif'],'mathtext.fontset':'stix','font.size':10,'axes.labelsize':10,'xtick.labelsize':9,'ytick.labelsize':9,'axes.linewidth':.7,'axes.spines.top':False,'axes.spines.right':False,'xtick.direction':'out','ytick.direction':'out','xtick.major.width':.6,'ytick.major.width':.6,'savefig.facecolor':'white','svg.fonttype':'none','svg.hashsalt':'annual-st-v2-figures','pdf.fonttype':42,'ps.fonttype':42})
variants=['financial_only','text_only','concat','cross_attention'];names=['Financial neural','Text neural','Concatenation','Cross-attention'];seeds=[17,42,2026];seed_styles=['-','--',':']
used=['evidence/candidate_manifest.json','evidence/training_correlation.csv','results/predictions.csv','results/training_log.json','baseline/predictions.csv']
def csvrows(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
m=json.loads((R/used[0]).read_text());assert m['dataset_sha256']=='fdcfe6bda4f1f05f36669ff70ccee1091078149dfdd78a295658910e1fa4e263'
pr=csvrows(R/'results/predictions.csv');lp=csvrows(R/'baseline/predictions.csv');logs=json.loads((R/'results/training_log.json').read_text())
assert len(pr)==11628 and len(lp)==969

def save(fig,n):
 fig.savefig(O/f'figure_{n}.png',dpi=300)
 fig.savefig(O/f'figure_{n}.svg',metadata={'Date':None,'Creator':'Matplotlib; plot_figures.py'})
 fig.savefig(O/f'figure_{n}.pdf',metadata={'CreationDate':None,'ModDate':None,'Creator':'Matplotlib; plot_figures.py'})
 plt.close(fig)

def box(ax,x,y,w,h,text,fontsize=10):
 ax.add_patch(Rectangle((x,y),w,h,fc='white',ec='black',lw=.7))
 ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=fontsize,linespacing=1.25)
def arrow(ax,a,b):ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','lw':.7,'color':'black','shrinkA':0,'shrinkB':0})
def line(ax,x,y):ax.plot(x,y,color='black',lw=.7)

# Figure 1: straight connectors and unfilled rectangles.
fig,ax=plt.subplots(figsize=(7,3.45));fig.subplots_adjust(left=.02,right=.98,top=.98,bottom=.03);ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
s=m['summary'];assert s['n']==969 and s['positive']==26
box(ax,.25,.79,.50,.19,'Source inventory\n471 firms; 3,335 firm-years')
arrow(ax,(.50,.79),(.50,.59));line(ax,[.50,.76],[.69,.69]);arrow(ax,(.76,.69),(.79,.69));ax.text(.80,.69,'2,366 excluded\nor unresolved',ha='left',va='center',fontsize=9)
box(ax,.25,.40,.50,.19,'Analysis sample\n155 firms; 969 firm-years; 26 events')
line(ax,[.50,.50],[.40,.31]);line(ax,[.16,.84],[.31,.31])
for x,txt in zip([.16,.50,.84],['Training: 2017–2021\n503 firm-years; 9 events','Validation: 2022–2023\n250 firm-years; 6 events','Test: 2024–2025\n216 firm-years; 11 events']):
 arrow(ax,(x,.31),(x,.22));box(ax,x-.15,.02,.30,.20,txt,9)
save(fig,1)

# Figure 2: actual financial-query attention and direct financial pathway.
fig,ax=plt.subplots(figsize=(7,3.50));fig.subplots_adjust(left=.02,right=.98,top=.98,bottom=.03);ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
box(ax,.04,.80,.38,.18,'12 financial ratios\n+ 12 missing indicators')
box(ax,.58,.80,.38,.18,'MD&A: selected text chunks\nCharacter TF-IDF + SVD')
arrow(ax,(.23,.80),(.23,.68));arrow(ax,(.77,.80),(.77,.68))
box(ax,.04,.52,.38,.16,'Financial projection\n64-dimensional query')
box(ax,.58,.52,.38,.16,'Text projection\n64-dimensional keys and values')
line(ax,[.23,.23,.40],[.52,.43,.43]);arrow(ax,(.40,.43),(.40,.34))
line(ax,[.77,.77,.60],[.52,.43,.43]);arrow(ax,(.60,.43),(.60,.34))
box(ax,.27,.19,.46,.15,'Four-head cross-attention\nPadding masked')
line(ax,[.08,.08,.27],[.52,.12,.12]);line(ax,[.50,.50],[.19,.12]);arrow(ax,(.27,.12),(.50,.12))
arrow(ax,(.50,.12),(.50,.085));ax.text(.50,.025,'Financial vector + text context → classifier',ha='center',va='center',fontsize=10)
save(fig,2)

# Figure 3: lower triangle avoids printing the symmetric entries twice.
with (R/'evidence/training_correlation.csv').open() as f:
 rr=list(csv.reader(f));c=np.array([[float(v) for v in row[1:]] for row in rr[1:]])
assert c.shape==(12,12) and np.allclose(c,c.T) and np.allclose(np.diag(c),1)
labels=['L/A','CR','QR','NP/A','NP/E','OM','NM','AR/A','INV/A','OCF/A','OCF/CL','ME/R']
fig,ax=plt.subplots(figsize=(7,5.10));fig.subplots_adjust(left=.14,right=.98,top=.97,bottom=.16)
masked=np.ma.masked_where(np.triu(np.ones_like(c),1).astype(bool),c)
cmap=plt.get_cmap('Greys').copy();cmap.set_bad('white')
ax.imshow(masked,cmap=cmap,vmin=-1,vmax=1,aspect='auto')
for i in range(12):
 for j in range(i+1):
  val=c[i,j];text=f'{val:.2f}' if abs(val)>=.005 else '0.00'
  ax.text(j,i,text,ha='center',va='center',fontsize=8,color='white' if val>.35 else 'black')
ax.set_xticks(range(12),labels,rotation=45,ha='right');ax.set_yticks(range(12),labels);ax.tick_params(length=0)
for sp in ax.spines.values():sp.set_visible(False)
# Numerical entries retain signed correlations; shading follows the same -1 to +1 scale.
save(fig,3)

# Exact empirical curves, retaining ties and every prespecified model run.
curve_rows=[]
def curve(q,model,seed):
 y=np.array([int(r['label']) for r in q]);p=np.array([float(r['probability']) for r in q]);assert len(y)==216 and y.sum()==11
 ix=np.argsort(-p,kind='stable');y=y[ix];p=p[ix];end=np.r_[np.flatnonzero(np.diff(p)),len(p)-1];tp=np.cumsum(y)[end];fp=end+1-tp
 rc=np.r_[0,tp/11];prec=np.r_[1,tp/(end+1)];fpr=np.r_[0,fp/205]
 for i,(r,p_,f) in enumerate(zip(rc,prec,fpr)):curve_rows.append({'model':model,'seed':seed,'point':i,'recall':float(r),'precision':float(p_),'false_positive_rate':float(f)})
 return rc,prec,fpr
# One model per row: model colour and seed line pattern are independent.
fig,axes=plt.subplots(5,2,figsize=(7,8.2))
fig.subplots_adjust(left=.10,right=.98,bottom=.10,top=.92,hspace=.55,wspace=.28)
colours=['#245A81','#696969','#24836B','#BC632D','#795582']
model_labels=names+['L2 logistic']
for i,(v,n,colour) in enumerate(zip(variants+['logistic_regression'],model_labels,colours)):
 runs=seeds if i<4 else [0]
 for seed,sty in zip(runs,seed_styles):
  q=[r for r in pr if r['variant']==v and int(r['seed'])==seed and r['split']=='test'] if i<4 else [r for r in lp if r['split']=='test']
  rc,precision,fpr=curve(q,v,seed)
  axes[i,0].step(rc,precision,where='pre',ls=sty,color=colour,lw=1.15)
  axes[i,1].plot(fpr,rc,ls=sty,color=colour,lw=1.15)
 axes[i,0].axhline(11/216,color='.72',lw=.65,ls=(0,(1,3)),zorder=0)
 axes[i,1].plot([0,1],[0,1],color='.72',lw=.65,ls=(0,(1,3)),zorder=0)
 for j,ax in enumerate(axes[i]):
  ax.set(xlim=(0,1),ylim=(0,1.03))
  ax.set_xticks([0,.25,.5,.75,1]);ax.set_yticks([0,.5,1])
  ax.tick_params(labelsize=8,pad=2)
  ax.set_axisbelow(True);ax.grid(axis='y',color='.92',lw=.5)
  ax.set_title(f'({chr(97+2*i+j)}) {n}',fontsize=9.5,color=colour,loc='left',pad=4)
 axes[i,0].set_ylabel('Precision',fontsize=9)
 axes[i,1].set_ylabel('True positive rate',fontsize=9)
axes[-1,0].set_xlabel('Recall',fontsize=9)
axes[-1,1].set_xlabel('False positive rate',fontsize=9)
fig.text(.30,.965,'Precision–recall',ha='center',fontsize=11)
fig.text(.80,.965,'Receiver operating characteristic',ha='center',fontsize=11)
handles=[Line2D([0],[0],color='.15',ls=sty,lw=1.15,label=f'Seed {s}') for s,sty in zip(seeds,seed_styles)]
fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.54,.027),ncol=3,frameon=False,fontsize=9,handlelength=3)
fig.text(.54,.012,'Neural models: three seeds per panel. L2 logistic: one deterministic fit.',ha='center',fontsize=8.5)
save(fig,4)
with (O/'figure_4_curve_data.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(curve_rows[0]));w.writeheader();w.writerows(curve_rows)

# Figure 5: unsmoothed logs, identical limits within each metric column.
fig,axes=plt.subplots(4,2,figsize=(7,6.10));fig.subplots_adjust(left=.12,right=.98,top=.94,bottom=.12,hspace=.42,wspace=.28)
for i,(v,n) in enumerate(zip(variants,names)):
 for seed,sty in zip(seeds,seed_styles):
  q=sorted([r for r in logs if r['variant']==v and r['seed']==seed],key=lambda r:r['epoch'])
  axes[i,0].plot([r['epoch'] for r in q],[r['train_loss'] for r in q],color='black',ls=sty,lw=.9)
  axes[i,1].plot([r['epoch'] for r in q],[r['validation_AP'] for r in q],color='black',ls=sty,lw=.9)
 axes[i,0].set_ylabel(n,fontsize=9);axes[i,0].set_ylim(0,1.45);axes[i,1].set_ylim(0,.45)
 for ax in axes[i]:ax.xaxis.set_major_locator(MaxNLocator(nbins=5,integer=True));ax.yaxis.set_major_locator(MaxNLocator(nbins=3));ax.tick_params(labelsize=8)
axes[0,0].set_title('Training loss (weighted BCE)',loc='left',fontsize=10);axes[0,1].set_title('Validation average precision',loc='left',fontsize=10)
for ax in axes[-1]:ax.set_xlabel('Epoch')
fig.legend(handles=[Line2D([0],[0],color='black',ls=sty,label=f'Seed {seed}') for seed,sty in zip(seeds,seed_styles)],ncol=3,loc='lower center',bbox_to_anchor=(.5,.012),frameon=False,fontsize=9)
save(fig,5)
checks={'renderer':'Python / Matplotlib','matplotlib_version':matplotlib.__version__,'numpy_version':np.__version__,'data_unchanged':True,'fits_rerun':0,'curves':13,'test_rows_per_curve':216,'test_events_per_curve':11,'neural_training_histories':12,'correlation_shape':[12,12],'source_sha256':{n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in used},'output_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.glob('figure_*')) if p.is_file()}}
(O/'figure_build_audit.json').write_text(json.dumps(checks,indent=2)+'\n')
print('Five figures exported to PNG (300 dpi), editable SVG and vector PDF; source inputs hashed.')
