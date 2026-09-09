import json,sqlite3,tempfile,unittest
from decimal import Decimal
from pathlib import Path
from distress.database import create,asof_fact,quarter_value,pair_distress,baseline_status,incident_label,conjunction,audit_database
from distress.build import populate
from distress.features import annual,matrices,missingness_allowed,assess_missingness

class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.con=create(Path(cls.tmp.name)/'db.sqlite');cls.report=populate(cls.con)
    @classmethod
    def tearDownClass(cls):cls.con.close();cls.tmp.cleanup()

    def test_database_integrity_and_units(self):
        r=audit_database(self.con);self.assertTrue(r['passed'],r['errors']);self.assertEqual(r['counts']['facts'],188)
    def test_vanke_statement_identities_and_publication_cutoff(self):
        def v(metric,year,scope='consolidated'):
            basis='END' if metric in ['assets','liabilities','equity'] else 'YTD'
            return Decimal(asof_fact(self.con,'000002.SZ',metric,f'{year}-12-31',basis,'2025-04-30',scope)['value_normalized'])
        for year in [2023,2024]:
            self.assertEqual(v('assets',year),v('liabilities',year)+v('equity',year))
            self.assertEqual(v('net_profit',year),v('profit_before_tax',year)-v('income_tax',year))
            self.assertEqual(v('net_profit',year),v('parent_profit',year,'parent_attributable')+v('minority_profit',year))
            self.assertEqual(v('ocf',year),v('operating_cash_inflow',year)-v('operating_cash_outflow',year))
        self.assertIsNone(asof_fact(self.con,'000002.SZ','net_profit','2023-12-31','YTD','2024-04-30'))
        values=annual(self.con,'000002.SZ',2024,'2025-04-30')
        self.assertTrue(all(v.number is not None and v.sources for v in values.values()))
        self.assertEqual(values['free_cash_flow'].number,Decimal('-719764542.25'))
    def test_incomplete_records_are_not_eligible(self):
        self.assertEqual(self.report['counts']['analytical_eligible'],0)
        self.assertEqual(self.report['counts']['sample_register'],4)
    def test_quarter_controls(self):
        self.assertEqual(len(self.report['quarter_controls']),28)
        self.assertTrue(all(r['status']=='pass' and Decimal(r['difference_cny'])==0 for r in self.report['quarter_controls']))
    def test_q4_is_not_cumulative_profit(self):
        q=quarter_value(self.con,'003032.SZ','net_profit',2023,4,'2024-04-30')
        self.assertEqual(q['value'],Decimal('-86202035.91'))
        self.assertEqual(q['available_date'],'2024-04-16');self.assertEqual(len(q['fact_ids']),2)
    def test_baseline_distress_not_future_incident(self):
        self.assertEqual(pair_distress(self.con,'003032.SZ',[(2023,4),(2024,1)],'2024-04-30'),1)
        row=self.con.execute("SELECT * FROM sample_register WHERE sample_id='003032.SZ:2024'").fetchone()
        self.assertEqual(row['baseline_status'],'excluded');self.assertIsNone(row['outcome'])
    def test_future_restatement_not_backfilled(self):
        old=asof_fact(self.con,'000333.SZ','cogs','2024-03-31','YTD','2024-04-30')
        new=asof_fact(self.con,'000333.SZ','cogs','2024-03-31','YTD','2025-04-30')
        self.assertEqual(Decimal(old['value_normalized']),Decimal('77114398000'))
        self.assertEqual(Decimal(new['value_normalized'])-Decimal(old['value_normalized']),Decimal('790632000'))
    def test_consolidated_profit_not_parent_profit(self):
        a=asof_fact(self.con,'003032.SZ','net_profit','2025-03-31','YTD','2025-04-30')
        b=asof_fact(self.con,'003032.SZ','parent_profit','2025-03-31','YTD','2025-04-30','parent_attributable')
        self.assertEqual(Decimal(a['value_normalized'])-Decimal(b['value_normalized']),Decimal('-69791.97'))
    def test_unknown_and_excluded_never_imputed_as_normal(self):
        self.assertEqual(baseline_status([None,1,0]),'excluded')
        self.assertEqual(baseline_status([None,0,0]),'unresolved')
        self.assertEqual(baseline_status([0,0,0]),'clear')
        self.assertIsNone(incident_label('excluded',[1,0,0],[True]*3))
        self.assertIsNone(incident_label('clear',[0,None,0],[True]*3))
        self.assertIsNone(incident_label('clear',[0,0,0],[False,True,True]))
        self.assertEqual(incident_label('clear',[0,0,0],[True]*3),0)
        self.assertEqual(conjunction([0,None]),0)
    def test_sql_forbids_labeling_excluded_records(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("UPDATE sample_register SET outcome=1 WHERE sample_id='003032.SZ:2024'")
        self.con.rollback()
    def test_adjacency_required(self):
        with self.assertRaises(ValueError):pair_distress(self.con,'000333.SZ',[(2024,1),(2024,3)],'2025-04-30')
    def test_complete_one_annual_vector_with_real_sources(self):
        values=annual(self.con,'000333.SZ',2024,'2025-04-30')
        self.assertEqual(len(values),18);self.assertTrue(all(v.number is not None and v.sources for v in values.values()))
        self.assertEqual(values['free_cash_flow'].number,Decimal('52671936000'))
        self.assertNotAlmostEqual(float(values['net_profit_end_share_proxy'].number),5.44,places=2)
    def test_feature_matrix_shapes_and_explicit_missingness(self):
        x=matrices(self.con,'000333.SZ',2025)
        self.assertEqual((len(x['annual']),len(x['annual'][0])),(5,18))
        self.assertEqual((len(x['quarterly']),len(x['quarterly'][0])),(4,8))
        self.assertGreater(x['missing_annual'],0)
    def test_existing_database_not_overwritten(self):
        with self.assertRaises(FileExistsError):create(Path(self.tmp.name)/'db.sqlite')
    def test_missingness_boundary_depends_on_explicit_denominator(self):
        f={'missing_annual':28,'missing_quarterly':0}
        self.assertTrue(missingness_allowed(f,{'maximum_fraction':.3,'denominator':'all_122'}))
        self.assertFalse(missingness_allowed(f,{'maximum_fraction':.3,'denominator':'each_branch_90_32'}))
        f['missing_annual']=27
        self.assertTrue(missingness_allowed(f,{'maximum_fraction':.3,'denominator':'each_branch_90_32'}))
        with self.assertRaises(ValueError):missingness_allowed(f,{'maximum_fraction':.3,'denominator':None})
        policy={'maximum_fraction':.3,'denominator':'each_branch_90_32'}
        for a,s,allowed in [(27,9,True),(28,9,False),(27,10,False),(0,10,False),(28,0,False),(28,10,False)]:
            features={'missing_annual':a,'missing_quarterly':s}
            with self.subTest(annual=a,quarterly=s):
                self.assertEqual(missingness_allowed(features,policy),allowed)
                self.assertEqual(assess_missingness(features,policy,True)['exclude_for_missingness'],not allowed)
                self.assertIsNone(assess_missingness(features,policy,False)['exclude_for_missingness'])
                self.assertEqual(assess_missingness(features,policy,False)['status'],'pending_collection')
