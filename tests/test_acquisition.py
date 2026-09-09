import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('collect_disclosures', Path(__file__).resolve().parents[1] / 'analysis/collect_disclosures.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class AcquisitionTests(unittest.TestCase):
    def test_out_of_range_page_fails_before_network(self):
        with self.assertRaises(ValueError):
            collector.get_page('2017-01-01','2017-04-30',101,Path('/unused'))

    def test_large_range_is_partitioned_without_gaps(self):
        def response(start,end,page,cache):
            n = 4000 if start=='2017-01-01' and end=='2017-01-04' else 2000
            return start,end,page,{'totalAnnouncement':n},'a'*64
        with patch.object(collector,'get_page',side_effect=response):
            first,jobs=collector.plan_range('2017-01-01','2017-01-04',None)
        self.assertEqual([(x[0],x[1]) for x in first], [('2017-01-01','2017-01-02'),('2017-01-03','2017-01-04')])
        self.assertTrue(all(p<=100 for _,_,p in jobs))
        self.assertEqual(len(jobs),132)

    def test_duplicate_page_cannot_pass_completeness(self):
        stamp=int(dt.datetime(2017,4,1,tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp()*1000)
        row=dict(secCode='000333',orgId='fixture',announcementId='fixture-doc',
                 announcementTitle='2016\u5e74\u5e74\u5ea6\u62a5\u544a',announcementTime=stamp,adjunctUrl='fixture.pdf')
        records=[row]*30
        pages=[('2017-04-01','2017-04-01',p,{'totalAnnouncement':60,'announcements':records},'a'*64) for p in [1,2]]
        with tempfile.TemporaryDirectory() as tmp:
            result=collector.write_index(pages,Path(tmp)/'index.sqlite')
        self.assertFalse(result['ranges'][0]['pagination_complete'])
        self.assertEqual(result['ranges'][0]['unique_records'],1)
        self.assertEqual(result['analytical_eligible'],0)

    def test_later_report_is_not_a_prior_origin_predictor(self):
        stamp=int(dt.datetime(2017,4,1,tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp()*1000)
        rows=[dict(secCode='000333',orgId='fixture',announcementId=str(y),
                   announcementTitle=f'{y}\u5e74\u5e74\u5ea6\u62a5\u544a',announcementTime=stamp,adjunctUrl=f'{y}.pdf') for y in [2015,2016]]
        pages=[('2017-04-01','2017-04-01',1,{'totalAnnouncement':2,'announcements':rows},'a'*64)]
        with tempfile.TemporaryDirectory() as tmp:
            result=collector.write_index(pages,Path(tmp)/'index.sqlite')
        self.assertTrue(result['ranges'][0]['pagination_complete'])
        self.assertEqual(result['candidate_origins'],1)

if __name__=='__main__': unittest.main()
