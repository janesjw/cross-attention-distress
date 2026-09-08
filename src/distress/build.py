import argparse,json
from decimal import Decimal
from pathlib import Path
from .database import ROOT,create,asof_fact,quarter_value,pair_distress,baseline_status,audit_database
from .features import annual,matrices,assess_missingness

def populate(con):
    checks=[]
    # Cumulative-to-quarter arithmetic versus disclosed annual control rows.
    for c in con.execute("SELECT f.*,d.disclosed_date FROM facts f JOIN documents d USING(document_id) WHERE f.basis='QUARTER'").fetchall():
        if c['metric']=='parent_profit' and c['firm_id']=='003032.SZ':
            continue # Consolidated values are not silently equated with parent-attributable controls.
        y=int(c['period_end'][:4]);q=int(c['period_end'][5:7])//3
        v=quarter_value(con,c['firm_id'],c['metric'],y,q,c['disclosed_date'],c['scope'],persist=True)
        checks.append({'control_fact_id':c['fact_id'],'difference_cny':None if v is None else str(v['value']-Decimal(c['value_normalized'])),
                       'status':'unresolved' if v is None else ('pass' if v['value']==Decimal(c['value_normalized']) else 'fail')})
    for firm in ['000333.SZ','003032.SZ']:
        for year in [2024,2025]:
            origin=f'{year}-05-01';cutoff=f'{year}-04-30';sid=f'{firm}:{year}'
            st=1 if firm=='003032.SZ' and year==2025 else None
            q=pair_distress(con,firm,[(year-1,4),(year,1)],cutoff,True)
            audit=0 if (firm=='003032.SZ' or (firm=='000333.SZ' and year==2025)) else None
            state=baseline_status([st,q,audit])
            con.execute('INSERT INTO sample_register VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (sid,firm,origin,f'{year+1}-05-01',st,q,audit,state,'incomplete',None,None,
                 'not_applicable_excluded' if state=='excluded' else 'unresolved',0,
                 'Verification case only; not evidence of original sample membership. Missing ST history is unresolved.'))
            for row in con.execute('SELECT derived_id FROM derived_values WHERE firm_id=? AND asof_date=?',(firm,cutoff)).fetchall():
                con.execute('INSERT INTO sample_evidence VALUES (?,?,?,?,?,?,?)',
                    (sid,'baseline','quarter','calculated',None,row[0],'Quarter flow calculation with raw-fact lineage'))
            if audit==0:
                doc='1219619115' if year==2024 else ('1223197724' if firm=='003032.SZ' else '1222951181')
                con.execute('INSERT INTO sample_evidence VALUES (?,?,?,?,?,?,?)',
                    (sid,'baseline','audit_loss','verified_absent',doc,None,'Standard financial-statement audit' if firm=='003032.SZ' else 'Consolidated annual net profit positive; conjunction is false'))
            if st==1:
                con.execute('INSERT INTO sample_evidence VALUES (?,?,?,?,?,?,?)',
                    (sid,'baseline','ST','verified_present','1223197666',None,'ST formally announced before origin; 2025Q1 cover confirms continuing status'))
                con.execute('INSERT INTO sample_evidence VALUES (?,?,?,?,?,?,?)',
                    (sid,'baseline','ST','verified_present','1223406438',None,'2025Q1 report PDF p1 retains *ST stock abbreviation on 2025-04-30'))
            for criterion in ['ST','quarter','audit_loss']:
                con.execute('INSERT INTO coverage VALUES (?,?,?,?,?,?)',
                    (sid,criterion,origin,f'{year+1}-05-01','unresolved','Full follow-up ascertainment not yet certified'))
    # Verified component evidence only; never promote to a normal composite outcome.
    sid='000333.SZ:2025'
    vals=[pair_distress(con,'000333.SZ',pair,'2026-04-30',True) for pair in
       [[(2025,1),(2025,2)],[(2025,2),(2025,3)],[(2025,3),(2025,4)],[(2025,4),(2026,1)]]]
    if vals==[0,0,0,0]:
        con.execute("UPDATE coverage SET status='verified_absent',evidence_note=? WHERE sample_id=? AND criterion='quarter'",
          ('Scheduled consecutive-quarter comparisons each fail the OCF-negativity condition; not a certification of all later accounting corrections.',sid))
    con.execute("UPDATE coverage SET status='verified_absent',evidence_note=? WHERE sample_id=? AND criterion='audit_loss'",
       ('FY2025 financial-statement audit standard unqualified; report 1225065145 PDF p125.',sid))
    con.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)',
       ('003032:quarter:2024-04-26','003032.SZ','two_quarter_loss_ocf','2024-04-26',None,'1219815453',7,1,
        '2023Q4 derived from FY2023 less 2023Q3 cumulative; both 2023Q4 and 2024Q1 have negative consolidated profit and OCF. Already known at 2024 origin.'))
    con.commit()
    report=audit_database(con)
    report['quarter_controls']=checks
    report['passed']=report['passed'] and all(c['status']=='pass' for c in checks)
    report['annual_2024_midea']={k:{'value':None if v.number is None else str(v.number),'fact_ids':v.sources} for k,v in annual(con,'000333.SZ',2024,'2025-04-30').items()}
    report['feature_completeness']={f'{firm}:{year}':matrices(con,firm,year) for firm in ['000333.SZ','003032.SZ'] for year in [2024,2025]}
    policy=json.loads((ROOT/'configs/protocol.json').read_text())['missingness']
    report['missingness_assessments']={sid:assess_missingness(features,policy,False) for sid,features in report['feature_completeness'].items()}
    for sid,assessment in report['missingness_assessments'].items():
        con.execute('INSERT INTO sample_evidence VALUES (?,?,?,?,?,?,?)',
            (sid,'features','missingness',assessment['status'],None,None,json.dumps(assessment,sort_keys=True)))
    con.commit()
    report['samples']=[dict(r) for r in con.execute('SELECT * FROM sample_register ORDER BY sample_id')]
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--database',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();con=create(a.database)
    report=populate(con);con.close()
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'passed':report['passed'],'counts':report['counts']},ensure_ascii=False))
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
