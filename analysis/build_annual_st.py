"""Inventory the simplified annual-only/ST-only study; does not freeze or train."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from distress.annual_st import inventory

if __name__=='__main__':print(json.dumps(inventory(ROOT),indent=2))
