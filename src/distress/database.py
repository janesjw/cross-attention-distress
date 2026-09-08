"""Versioned financial facts and conservative incident-disease-style risk sets."""
import hashlib
import json
import sqlite3
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con

def create(path, seed_path=None):
    """Refuses overwrite. Rebuild into a new filename to preserve existing annotations."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = connect(path)
    con.executescript((Path(__file__).with_name('schema.sql')).read_text())
    seed_path = Path(seed_path or ROOT / 'data/verified_seed.json')
    seed = json.loads(seed_path.read_text())
    with con:
        for table in ['firms', 'documents', 'facts', 'events', 'audit_opinions']:
            for row in seed[table]:
                keys = list(row)
                con.execute(f'INSERT INTO {table} ({",".join(keys)}) VALUES ({",".join("?" for _ in keys)})', [row[k] for k in keys])
        con.executemany('INSERT INTO metadata VALUES (?,?)', [
            ('status', 'verification_database_not_full_study'),
            ('seed_sha256', hashlib.sha256(seed_path.read_bytes()).hexdigest()),
            ('protocol_sha256', hashlib.sha256((ROOT/'configs/protocol.json').read_bytes()).hexdigest())])
    return con

def asof_fact(con, firm, metric, period, basis, cutoff, scope='consolidated'):
    """Date-granular cutoff. Ambiguous simultaneous versions raise; IDs are not clocks."""
    rows = con.execute('''SELECT f.*,d.disclosed_date,d.version_kind
       FROM facts f JOIN documents d USING(document_id)
       WHERE f.firm_id=? AND metric=? AND period_end=? AND basis=? AND scope=?
       AND d.disclosed_date<=? AND f.verification='verified'
       ORDER BY d.disclosed_date DESC''', (firm,metric,period,basis,scope,cutoff)).fetchall()
    if not rows:
        return None
    latest = [r for r in rows if r['disclosed_date']==rows[0]['disclosed_date']]
    if len(latest)>1:
        corrected = [r for r in latest if r['version_kind']=='corrected']
        if len(corrected)==1:
            return corrected[0]
        if len({r['value_normalized'] for r in latest})!=1:
            raise ValueError('Conflicting same-day disclosures: manual version ordering required')
    return latest[0]

def quarter_end(year, quarter):
    return f'{year}-{["03-31","06-30","09-30","12-31"][quarter-1]}'

def quarter_value(con, firm, metric, year, quarter, cutoff, scope='consolidated', persist=False):
    end = quarter_end(year, quarter)
    current = asof_fact(con,firm,metric,end,'YTD',cutoff,scope)
    prior = asof_fact(con,firm,metric,quarter_end(year,quarter-1),'YTD',cutoff,scope) if quarter>1 else None
    if current is None or (quarter>1 and prior is None):
        return None
    if prior is not None and (current['comparability_group']=='unreviewed' or current['comparability_group']!=prior['comparability_group']):
        return None
    dependencies = [current] + ([prior] if prior is not None else [])
    value = Decimal(current['value_normalized']) - (Decimal(prior['value_normalized']) if prior is not None else 0)
    available = max(r['disclosed_date'] for r in dependencies)
    key = f'{firm}:{metric}:{scope}:{end}:{cutoff}:quarter'
    if persist:
        con.execute('''INSERT INTO derived_values VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(derived_id) DO UPDATE SET value=excluded.value,available_date=excluded.available_date''',
           (key,firm,metric,end,cutoff,str(value),available,'YTD(q)-YTD(q-1); Q1=YTD(Q1)','verified'))
        con.executemany('INSERT OR IGNORE INTO lineage VALUES (?,?)', [(key,r['fact_id']) for r in dependencies])
    return {'id':key,'value':value,'available_date':available,'fact_ids':[r['fact_id'] for r in dependencies]}

def conjunction(values):
    if 0 in values:
        return 0
    return 1 if all(v==1 for v in values) else None

def baseline_status(components):
    if 1 in components:
        return 'excluded'
    return 'clear' if all(v==0 for v in components) else 'unresolved'

def incident_label(baseline, component_followup, complete_coverage):
    if baseline!='clear':
        return None
    if 1 in component_followup:
        return 1
    if all(v==0 for v in component_followup) and all(complete_coverage):
        return 0
    return None

def quarter_distress(con,firm,year,quarter,cutoff,persist=False):
    vals = [quarter_value(con,firm,m,year,quarter,cutoff,persist=persist) for m in ('ocf','net_profit')]
    return conjunction([None if v is None else int(v['value']<0) for v in vals])

def pair_distress(con,firm,pairs,cutoff,persist=False):
    a,b = pairs
    if b[0]*4+b[1] - (a[0]*4+a[1]) != 1:
        raise ValueError('Quarters must be adjacent')
    return conjunction([quarter_distress(con,firm,*p,cutoff,persist) for p in pairs])

def audit_database(con):
    errors = []
    if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok': errors.append('integrity')
    if con.execute('PRAGMA foreign_key_check').fetchall(): errors.append('foreign_keys')
    for row in con.execute('SELECT * FROM facts'):
        if Decimal(row['raw_value'])*Decimal(row['multiplier'])*row['sign_adjustment']!=Decimal(row['value_normalized']):
            errors.append('unit:'+row['fact_id'])
    for row in con.execute('''SELECT v.derived_id,d.disclosed_date,v.asof_date
         FROM derived_values v JOIN lineage l USING(derived_id) JOIN facts f USING(fact_id)
         JOIN documents d USING(document_id) WHERE d.disclosed_date>v.asof_date'''):
        errors.append('future_source:'+row['derived_id'])
    invalid=con.execute("SELECT sample_id FROM sample_register WHERE baseline_status!='clear' AND (outcome IS NOT NULL OR analytical_eligible=1)").fetchall()
    errors += ['excluded_labeled:'+r[0] for r in invalid]
    counts = {table:con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in
       ['firms','documents','facts','derived_values','lineage','events','audit_opinions','sample_register','text_sections','training_runs','predictions']}
    counts['analytical_eligible']=con.execute('SELECT COUNT(*) FROM sample_register WHERE analytical_eligible=1').fetchone()[0]
    return {'passed':not errors,'errors':errors,'counts':counts}
