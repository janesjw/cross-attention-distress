"""Run the minimal registered-sample experiment; refuse unverified data before work."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
from distress.database import connect,ROOT
from distress.dataset import load_frozen

def run(database,manifest,output,protocol,device='cpu',check_only=False):
    with connect(database) as con:data=load_frozen(manifest,con)
    cfg=json.loads(Path(protocol).read_text())
    expected=hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    jobs=[(v,s) for s in cfg['seeds'] for v in cfg['variants']]
    if check_only:
        return {'ready':True,'dataset_id':data['dataset_id'],'planned_runs':len(jobs),'completed_runs':0}
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    saved=output/'protocol.json'
    if saved.exists() and saved.read_bytes()!=Path(protocol).read_bytes():raise ValueError('Protocol changed; use a new suite output')
    if Path(protocol).resolve()!=saved.resolve():shutil.copyfile(protocol,saved)
    for variant,seed in jobs:
        path=output/f'{variant}-seed{seed}'
        if (path/'run_manifest.json').exists():
            from summarize_review import load_run
            receipt,_=load_run(path)
            if receipt['manifest_sha256']!=expected or receipt['variant']!=variant or receipt['seed']!=seed:
                raise ValueError('Saved run does not match this experiment')
            continue
        if path.exists():raise ValueError(f'Incomplete run retained at {path}; resolve it or use a new output directory')
        db=output/f'{variant}-seed{seed}.sqlite';shutil.copyfile(database,db)
        subprocess.run([sys.executable,'-m','distress.train','--database',str(db),'--manifest',str(manifest),
          '--output',str(path),'--variant',variant,'--seed',str(seed),'--device',device],check=True)
    subprocess.run([sys.executable,str(ROOT/'analysis/summarize_review.py'),'--runs',str(output),
      '--protocol',str(saved),'--output',str(output/'summary')],check=True)
    return {'ready':True,'dataset_id':data['dataset_id'],'completed_runs':len(jobs)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True,type=Path);p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--protocol',type=Path,default=ROOT/'configs/fast_review_protocol.json')
    p.add_argument('--device',default='cpu');p.add_argument('--check-only',action='store_true');a=p.parse_args()
    print(json.dumps(run(a.database,a.manifest,a.output,a.protocol,a.device,a.check_only)))
