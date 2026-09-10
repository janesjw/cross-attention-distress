from pathlib import Path
import json
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from distress.annual_freeze import freeze,training_required
if __name__=='__main__':
    result=freeze(ROOT)
    result['training_required']=result['frozen'] and training_required(ROOT)
    print(json.dumps(result,indent=2))
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('ready='+str(result['training_required']).lower()+'\n')
