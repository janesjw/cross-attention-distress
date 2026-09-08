"""Offline release validation; fixtures are software checks, never study results."""
import io,json,platform,sys,tempfile,time,unittest
from pathlib import Path
from distress.database import ROOT,create
from distress.build import populate
from distress.train import environment

stream=io.StringIO();suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
t=time.perf_counter();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
report={'purpose':'software_validation','passed':result.wasSuccessful(),'tests_run':result.testsRun,
 'failures':len(result.failures),'errors':len(result.errors),'seconds':time.perf_counter()-t,
 'environment':environment(),'details':stream.getvalue()}
with tempfile.TemporaryDirectory() as tmp:
    con=create(Path(tmp)/'fresh.sqlite');db=populate(con);con.close()
    report['fresh_database_build_passed']=db['passed']
    report['fresh_database_counts']=db['counts']
    report['passed']=report['passed'] and db['passed']
(ROOT/'reports/software_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:report[k] for k in ['passed','tests_run','failures','errors','fresh_database_build_passed']}))
if not report['passed']:raise SystemExit(1)
