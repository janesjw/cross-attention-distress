import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('collect_disclosures',Path(__file__).resolve().parents[1]/'analysis/collect_disclosures.py')
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
FIRM=dict(firm_id='000333.SZ',stock_code='000333',org_id='fixture')

class AcquisitionTests(unittest.TestCase):
    def test_large_query_splits_without_gaps(self):
        def query(firm,start,end,cache,category):
            n=31 if (start,end)==('2017-01-01','2017-01-04') else 0
            return {'totalAnnouncement':n,'announcements':[],'hasMore':n>0},'a'*64
        with patch.object(collector,'get_query',side_effect=query):
            ranges=collector.collect_firm(FIRM,'2017-01-01','2017-01-04',None)
        self.assertEqual([(x[1],x[2]) for x in ranges],[('2017-01-01','2017-01-02'),('2017-01-03','2017-01-04')])

    def test_truncated_response_cannot_pass(self):
        with patch.object(collector,'get_query',return_value=({'totalAnnouncement':2,'announcements':[{'orgId':'fixture'}],'hasMore':False},'a'*64)):
            with self.assertRaises(ValueError):collector.collect_firm(FIRM,'2017-01-01','2017-01-02',None)

    def test_different_issuer_cannot_pass(self):
        with patch.object(collector,'get_query',return_value=({'totalAnnouncement':1,'announcements':[{'orgId':'wrong'}],'hasMore':False},'a'*64)):
            with self.assertRaises(ValueError):collector.collect_firm(FIRM,'2017-01-01','2017-01-02',None)

    def test_overfull_day_is_not_silently_paginated(self):
        with patch.object(collector,'get_query',return_value=({'totalAnnouncement':31,'announcements':[],'hasMore':True},'a'*64)):
            with self.assertRaises(ValueError):collector.collect_firm(FIRM,'2017-01-01','2017-01-01',None)

    def test_category_partition_reconciles_all_reports(self):
        def query(firm,start,end,cache,category):
            if category==collector.CATEGORY:return {'totalAnnouncement':31,'announcements':[],'hasMore':True},'a'*64
            count=20 if category.startswith('category_ndbg') else 11 if category.startswith('category_bndbg') else 0
            rows=[{'announcementId':category+str(i),'orgId':'fixture'} for i in range(count)]
            return {'totalAnnouncement':count,'announcements':rows,'hasMore':False},'a'*64
        with patch.object(collector,'get_query',side_effect=query):
            rows=collector.collect_firm(FIRM,'2017-01-01','2017-01-01',None)
        self.assertEqual(sum(len(r[3]) for r in rows),31)
        self.assertEqual(len({r[5] for r in rows}),4)

    def test_overlapping_categories_do_not_hide_a_gap(self):
        def query(firm,start,end,cache,category):
            if category==collector.CATEGORY:return {'totalAnnouncement':31,'announcements':[],'hasMore':True},'a'*64
            rows=[{'announcementId':str(i),'orgId':'fixture'} for i in range(10)]
            return {'totalAnnouncement':10,'announcements':rows,'hasMore':False},'a'*64
        with patch.object(collector,'get_query',side_effect=query):
            with self.assertRaises(ValueError):collector.collect_firm(FIRM,'2017-01-01','2017-01-01',None)

if __name__=='__main__':unittest.main()
