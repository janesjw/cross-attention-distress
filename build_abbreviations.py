"""Export the manuscript abbreviation table without changing any research results."""
from pathlib import Path
import argparse,csv,json,os
os.environ.setdefault('MPLCONFIGDIR','/tmp/st-paper-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);a=p.parse_args();r=a.root
rows=json.loads((r/'manuscript/glossary.json').read_text());o=r/'manuscript/figures';o.mkdir(parents=True,exist_ok=True)
header=['Abbreviation / symbol','Full form or meaning']
with (o/'table_A1.csv').open('w',newline='') as f:w=csv.writer(f);w.writerow(header);w.writerows(rows)
plt.rcParams.update({'font.family':'serif','font.serif':['STIXGeneral','DejaVu Serif'],'svg.fonttype':'none','svg.hashsalt':'annual-st-abbreviations','pdf.fonttype':42})
fig,ax=plt.subplots(figsize=(8,10));ax.axis('off');fig.subplots_adjust(left=.025,right=.975,top=.965,bottom=.035)
t=ax.table(cellText=rows,colLabels=header,colWidths=[.19,.81],cellLoc='left',bbox=[0,0,1,1]);t.auto_set_font_size(False);t.set_fontsize(9)
for (i,j),c in t.get_celld().items():
 c.set_edgecolor('#999999');c.set_linewidth(.4);c.set_facecolor('#eeeeee' if i==0 else 'white')
 if i==0:c.get_text().set_fontweight('bold')
fig.savefig(o/'table_A1.png',dpi=300);fig.savefig(o/'table_A1.svg',metadata={'Date':None,'Creator':'build_abbreviations.py'});plt.close(fig)
print('Exported all',len(rows),'abbreviations and symbols to CSV, PNG and editable SVG.')
