"""18 annual features and 8 quarterly changes with raw-fact lineage."""
from dataclasses import dataclass
from decimal import Decimal
from .database import asof_fact,quarter_value,quarter_end

@dataclass
class Value:
    number: Decimal | None
    sources: tuple = ()

def combine(a,b,operation):
    sources=tuple(sorted(set(a.sources+b.sources)))
    if a.number is None or b.number is None:
        return Value(None,sources)
    if operation=='/' and b.number==0:
        return Value(None,sources)
    return Value({'+':lambda:a.number+b.number,'-':lambda:a.number-b.number,
                  '/':lambda:a.number/b.number}[operation](),sources)

def div(a,b): return combine(a,b,'/')
def sub(a,b): return combine(a,b,'-')
def add(a,b): return combine(a,b,'+')
def avg(a,b): return div(add(a,b),Value(Decimal(2)))
def change(a,b): return div(sub(a,b),b)

ANNUAL_NAMES=['liabilities_assets','current_ratio','quick_ratio','interest_coverage',
 'return_assets','return_equity','operating_margin','net_profit_end_share_proxy',
 'receivables_turnover','inventory_turnover','assets_turnover','revenue_growth',
 'net_profit_growth','assets_growth','ocf_current_liabilities','ocf_interest_expense',
 'ocf_per_share','free_cash_flow']
QUARTER_NAMES=['revenue','net_profit','ocf','debt_ratio','receivables','inventory','gross_margin','management_expense_ratio']

def missingness_allowed(features,policy):
    a,s=features['missing_annual'],features['missing_quarterly']
    t=Decimal(str(policy['maximum_fraction']))
    if policy['denominator']=='all_122':return Decimal(a+s)<=122*t
    if policy['denominator']=='each_branch_90_32':return Decimal(a)<=90*t and Decimal(s)<=32*t
    raise ValueError('Missingness denominator not yet selected')

def assess_missingness(features,policy,collection_complete=False):
    """Uncollected sources must not be counted as verified issuer-level data absence."""
    passes=missingness_allowed(features,policy)
    return {'annual_missing':features['missing_annual'],'annual_total':90,
            'quarterly_missing':features['missing_quarterly'],'quarterly_total':32,
            'denominator':policy['denominator'],'maximum_fraction':policy['maximum_fraction'],
            'evaluated_before_imputation':True,'source_review_complete':bool(collection_complete),
            'status':('pass' if passes else 'exclude') if collection_complete else 'pending_collection',
            'exclude_for_missingness':not passes if collection_complete else None}

def annual(con,firm,year,cutoff):
    def f(m,offset=0):
        basis='END' if m in ['liabilities','assets','current_assets','inventory','current_liabilities','equity','receivables','shares'] else 'YTD'
        row=asof_fact(con,firm,m,f'{year+offset}-12-31',basis,cutoff,'total_shares' if m=='shares' else 'consolidated')
        return Value(None) if row is None else Value(Decimal(row['value_normalized']),(row['fact_id'],))
    np,ocf,rev=f('net_profit'),f('ocf'),f('revenue')
    assets,liab,cl=f('assets'),f('liabilities'),f('current_liabilities')
    vals=[div(liab,assets),div(f('current_assets'),cl),div(sub(f('current_assets'),f('inventory')),cl),
      div(add(f('profit_before_tax'),f('interest_expense')),f('interest_expense')),
      div(np,avg(assets,f('assets',-1))),div(np,avg(f('equity'),f('equity',-1))),
      div(f('operating_profit'),rev),div(np,f('shares')),
      div(rev,avg(f('receivables'),f('receivables',-1))),div(f('cogs'),avg(f('inventory'),f('inventory',-1))),
      div(rev,avg(assets,f('assets',-1))),change(rev,f('revenue',-1)),change(np,f('net_profit',-1)),
      change(assets,f('assets',-1)),div(ocf,cl),div(ocf,f('interest_expense')),div(ocf,f('shares')),sub(ocf,f('capex_cash'))]
    return dict(zip(ANNUAL_NAMES,vals))

def quarter_base(con,firm,year,q,cutoff):
    def f(m,flow=True):
        if flow:
            r=quarter_value(con,firm,m,year,q,cutoff)
            return Value(None) if r is None else Value(r['value'],tuple(r['fact_ids']))
        r=asof_fact(con,firm,m,quarter_end(year,q),'END',cutoff)
        return Value(None) if r is None else Value(Decimal(r['value_normalized']),(r['fact_id'],))
    rev=f('revenue')
    return dict(zip(QUARTER_NAMES,[rev,f('net_profit'),f('ocf'),div(f('liabilities',False),f('assets',False)),
       f('receivables',False),f('inventory',False),div(sub(rev,f('cogs')),rev),div(f('management_expense'),rev)]))

def matrices(con,firm,origin_year):
    cutoff=f'{origin_year}-04-30'
    longs=[annual(con,firm,y,cutoff) for y in range(origin_year-5,origin_year)]
    bases=[quarter_base(con,firm,origin_year-1,q,cutoff) for q in range(1,5)] + [quarter_base(con,firm,origin_year,1,cutoff)]
    shorts=[{m:change(bases[i][m],bases[i-1][m]) for m in QUARTER_NAMES} for i in range(1,5)]
    def rows(items):
        return [[None if v.number is None else float(v.number) for v in row.values()] for row in items]
    return {'annual':rows(longs),'quarterly':rows(shorts),
        'annual_names':ANNUAL_NAMES,'quarterly_names':['qoq_'+m for m in QUARTER_NAMES],
        'fact_ids':sorted({s for row in longs+shorts for v in row.values() for s in v.sources}),
        'missing_annual':sum(v.number is None for row in longs for v in row.values()),
        'missing_quarterly':sum(v.number is None for row in shorts for v in row.values()),
        'status':'candidate_features_not_analytical_eligibility'}
