"""Update the fixed-cohort sample register from verified evidence."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from distress.sample_builder import build
if __name__=='__main__':
    result=build(ROOT)
    print(json.dumps(result,indent=2))
