"""Build the database and compact CSV views from the source records."""
import argparse
import csv
import json
from pathlib import Path

from distress.build import populate
from distress.database import ROOT, create


def write_csv(con, query, path):
    rows = con.execute(query)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow([column[0] for column in rows.description])
        writer.writerows(rows)


def build(output):
    output = Path(output)
    paths = [output / name for name in ('distress.sqlite', 'financials.csv', 'samples.csv')]
    for path in paths:
        if path.exists():
            raise FileExistsError(f'Output already exists: {path}. Use --output with a new directory.')
    output.mkdir(parents=True, exist_ok=True)
    con = create(paths[0])
    try:
        result = populate(con)
        if not result['passed']:
            raise ValueError('Database consistency checks failed')
        write_csv(con, '''SELECT f.fact_id, f.firm_id, f.metric, f.period_end,
            f.basis, f.scope, f.raw_value, f.source_unit, f.multiplier,
            f.sign_adjustment, f.value_normalized, d.disclosed_date,
            f.document_id, f.page, d.url
            FROM facts f JOIN documents d USING(document_id)
            ORDER BY f.fact_id''', paths[1])
        write_csv(con, '''SELECT s.sample_id, s.firm_id, f.name AS company,
            s.origin, s.followup_end_exclusive, s.baseline_st,
            s.baseline_quarter, s.baseline_audit, s.baseline_status,
            s.feature_status, s.outcome, s.outcome_status, s.analytical_eligible
            FROM sample_register s JOIN firms f USING(firm_id)
            ORDER BY s.sample_id''', paths[2])
        return result['counts']
    finally:
        con.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/derived/rebuilt')
    args = parser.parse_args()
    counts = build(args.output)
    print(json.dumps({'output': str(args.output), 'counts': counts}, indent=2))
