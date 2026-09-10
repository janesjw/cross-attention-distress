"""Reject dangerous parsing shortcuts and compare against reviewed source values."""
import importlib.util
import json
from pathlib import Path
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('structure_financials', ROOT/'analysis/structure_financials.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def packet(text):
    return {'source': {'document_id': '1', 'firm_id': '000001.SZ',
                       'source_title': '2023年三季度报告', 'disclosed_date': '2023-10-30'},
            'pdf_sha256': 'a'*64, 'pages': [{'page': 1, 'text': text}]}


class StructureFinancialsTest(unittest.TestCase):
    def test_parent_scope_is_never_used(self):
        raw = packet('1、合并资产负债表\n单位：元\n资产总计 100 200\n负债合计 30 50\n所有者权益合计 70 150\n2、母公司资产负债表\n单位：元\n资产总计 999 999')
        result = module.parse(raw)
        self.assertEqual(next(r['values'] for r in result['rows'] if r['metric']=='assets'), ['100', '200'])
        self.assertFalse(result['analytical_verified'])

    def test_blank_comparative_does_not_borrow_next_row(self):
        result = module.parse(packet('1、合并资产负债表\n单位：元\n应收账款 100\n存货 200'))
        self.assertFalse(result['rows'])

    def test_wrong_units_block_rows(self):
        result = module.parse(packet('1、合并资产负债表\n单位：万元\n资产总计 100 200'))
        self.assertFalse(result['rows'])
        self.assertIn('balance:unit_not_unambiguous_yuan', result['issues'])

    def test_accounting_mismatch_is_not_passed(self):
        result = module.parse(packet('1、合并资产负债表\n单位：元\n资产总计 100 200\n负债合计 30 50\n所有者权益合计 60 150'))
        self.assertIn('accounting_identity_failed', result['issues'])

    def test_period_is_not_inferred_from_disclosure_year(self):
        self.assertEqual(module.infer_period('2022年年度报告（更新后）'), '2022-12-31')
        self.assertIsNone(module.infer_period('关于三季度报告的更正公告'))
        raw = packet('')
        raw['source']['disclosed_date'] = '2023-04-30'
        self.assertIn('unresolved_or_postdisclosure_period', module.parse(raw)['issues'])

    def test_two_statement_versions_require_review(self):
        text = '1、合并资产负债表\n单位：元\n资产总计 100 200\n'
        result = module.parse(packet(text + text))
        self.assertFalse(result['rows'])
        self.assertIn('balance:statement_count:2', result['issues'])

    def test_parsed_numbers_match_registered_visual_reviews(self):
        matched = 0
        for path in (ROOT/'data/verification/reviewed').glob('*.json'):
            reviewed = json.loads(path.read_text())
            did = reviewed['source']['document_id']
            with zipfile.ZipFile(ROOT/f'data/automation/extracted/{did}.zip') as archive:
                parsed = module.parse(json.loads(archive.read('pages.json')))
            rows = {r['metric']: r for r in parsed['rows']}
            for fact in reviewed['facts']:
                row = fact['record']
                candidate = rows.get(row['metric'])
                if candidate:
                    self.assertEqual(candidate['values'][fact['source_column']-1], row['value_normalized'])
                    self.assertEqual(candidate['page'], row['page'])
                    matched += 1
        self.assertGreaterEqual(matched, 100)


if __name__ == '__main__': unittest.main()
