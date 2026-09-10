from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from distress.annual_audit import run
if __name__=='__main__':print(json.dumps(run(ROOT),indent=2))
