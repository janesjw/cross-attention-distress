import unittest
from distress.market import historical_st

class MarketTests(unittest.TestCase):
    def test_incident_st_is_not_backdated(self):
        listing={'snapshot_status':'listed','name_original':'Normal'}
        rows=[{'effective_date':'2025-04-23','st_before':0,'st_after':1,'source_row':2},
              {'effective_date':'2026-06-11','st_before':1,'st_after':0,'source_row':3}]
        self.assertEqual(historical_st(listing,rows,'2024-05-01')[0],0)
        self.assertEqual(historical_st(listing,rows,'2025-05-01')[0],1)
        self.assertEqual(historical_st(listing,rows,'2026-07-01')[0],0)

    def test_inconsistent_risk_history_stays_unknown(self):
        listing={'snapshot_status':'listed','name_original':'Normal'}
        rows=[{'effective_date':'2020-01-01','st_before':0,'st_after':1,'source_row':2},
              {'effective_date':'2022-01-01','st_before':0,'st_after':0,'source_row':3}]
        self.assertIsNone(historical_st(listing,rows,'2021-05-01')[0])

    def test_delisted_name_without_history_is_not_assumed_normal(self):
        self.assertIsNone(historical_st({'snapshot_status':'delisted','name_original':'Exit'},[],'2020-05-01')[0])

if __name__=='__main__':unittest.main()
