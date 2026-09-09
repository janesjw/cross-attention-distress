"""Exchange listing snapshots and historical name-based screening evidence."""
import datetime as dt
import hashlib
import json
import re
from collections import defaultdict


def st_name(name):
    return int('ST' in re.sub(r'\s+', '', name or '').upper())


def historical_st(listing, changes, origin):
    """Resolve the name-based ST state; inconsistent histories stay unknown.

This field is screening evidence. It does not establish financial/audit
eligibility or a negative composite distress label.
"""
    changes = sorted(changes, key=lambda r: (r['effective_date'], r['source_row']))
    if not changes:
        return (st_name(listing['name_original']), 'no_changes_in_exchange_register') if listing['snapshot_status']=='listed' else (None,'history_unresolved')
    if len({r['effective_date'] for r in changes}) != len(changes):
        return None, 'same_day_changes_require_review'
    if any(a['st_after'] != b['st_before'] for a,b in zip(changes,changes[1:])):
        return None, 'risk_state_chain_inconsistent'
    if listing['snapshot_status']=='listed' and changes[-1]['st_after'] != st_name(listing['name_original']):
        return None, 'terminal_name_inconsistent'
    before = [r for r in changes if r['effective_date'] <= origin]
    state = before[-1]['st_after'] if before else changes[0]['st_before']
    return state, 'consistent_exchange_name_history'


def populate_market(con, path):
    raw = path.read_bytes(); data = json.loads(raw)
    with con:
        for table,key in [('market_sources','sources'),('listing_records','listings'),('name_changes','name_changes')]:
            for row in data[key]:
                keys=list(row)
                con.execute(f'INSERT INTO {table} ({",".join(keys)}) VALUES ({",".join("?" for _ in keys)})',[row[k] for k in keys])
        con.execute('INSERT INTO metadata VALUES (?,?)',('market_sha256',hashlib.sha256(raw).hexdigest()))
        by_firm=defaultdict(list)
        for row in data['name_changes']: by_firm[row['firm_id']].append(row)
        for listing in data['listings']:
            if not listing['listing_date']: continue
            firm=listing['firm_id']
            if not re.fullmatch(r'(?:00\d|30\d|60\d|688)\d{3}\.(?:SZ|SH)',firm): continue
            for year in range(2017,2026):
                origin=f'{year}-05-01'; end=f'{year+1}-05-01'
                if listing['listing_date'] > f'{year-3}-05-01': continue
                if listing['delisting_date'] and listing['delisting_date'] <= origin: continue
                if listing['exchange']=='SZSE':
                    st, status=historical_st(listing,by_firm[firm],origin)
                    new_st=int(any(origin<=r['effective_date']<end and r['st_before']==0 and r['st_after']==1 for r in by_firm[firm]))
                    if new_st==0 and st is None: new_st=None
                else: st,status,new_st=None,'name_history_pending',None
                con.execute('INSERT INTO candidate_register VALUES (?,?,?,?,?,?,?,?,?)',
                            (firm+':'+str(year),firm,origin,listing['source_id'],st,status,new_st,
                             'historical_industry_and_listing_events_pending',
                             'st_at_origin_requires_event_confirmation' if st==1 else 'financial_text_and_label_collection_pending'))
