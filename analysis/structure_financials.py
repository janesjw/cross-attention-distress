"""Batch statement extraction and accounting checks, separate from certified facts.

Reads already hashed PDF text archives. Never fills blanks with zero, substitutes
parent-only statements, certifies disclosure completeness, or assigns labels.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HEAD = re.compile(r'^(?:[一二三四五六七八九十]+[、.．]|\d+[、.．]|[（(]\d+[）)])?(合并|母公司)(年初到报告期末)?(资产负债表|利润表|现金流量表)$')
NUMBER = re.compile(r'(?<![\d.,])[-−－]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\d.,])')
LABELS = {
    'balance': {
        'receivables': ['应收账款'], 'inventory': ['存货'],
        'current_assets': ['流动资产合计'], 'assets': ['资产总计'],
        'current_liabilities': ['流动负债合计'], 'liabilities': ['负债合计'],
        'equity': ['所有者权益合计', '股东权益合计', '所有者权益（或股东权益）合计'],
    },
    'income': {
        'revenue': ['营业收入'], 'cogs': ['营业成本'],
        'management_expense': ['管理费用'], 'interest_expense': ['利息费用'],
        'operating_profit': ['营业利润'], 'profit_before_tax': ['利润总额'],
        'net_profit': ['净利润'], 'income_tax': ['所得税费用'],
        'parent_profit': ['归属于母公司所有者的净利润', '归属于母公司股东的净利润'],
        'minority_profit': ['少数股东损益'],
    },
    'cashflow': {
        'ocf': ['经营活动产生的现金流量净额'],
        'operating_inflow': ['经营活动现金流入小计'],
        'operating_outflow': ['经营活动现金流出小计'],
        'capex_cash': ['购建固定资产、无形资产和其他长期资产支付的现金', '购建固定资产、无形资产和其他长期资产支付的'],
    },
}
CHECKS = [
    ('balance_identity', 'assets', 'liabilities', 'equity', '+'),
    ('profit_after_tax', 'net_profit', 'profit_before_tax', 'income_tax', '-'),
    ('profit_attribution', 'net_profit', 'parent_profit', 'minority_profit', '+'),
    ('operating_cashflow', 'ocf', 'operating_inflow', 'operating_outflow', '-'),
]
REQUIRED = {m for group in LABELS.values() for m in group} - {
    'income_tax', 'parent_profit', 'minority_profit', 'operating_inflow', 'operating_outflow'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compact(text):
    return re.sub(r'\s+', '', text)


def label_part(text):
    text = compact(text)
    return re.sub(r'^(?:(?:[一二三四五六七八九十]+|\d+)[、.．]|其中[：:]|减[：:]|加[：:])+', '', text)


def infer_period(title):
    title = compact(title)
    year = re.search(r'(20\d{2})年', title)
    if not year or any(s in title for s in ('摘要', '英文')):
        return None
    year = year.group(1)
    if re.search(r'(?:第一|一|1)季度', title): return year + '-03-31'
    if re.search(r'(?:第三|三|3)季度', title): return year + '-09-30'
    if '半年度' in title: return year + '-06-30'
    if '年度报告' in title: return year + '-12-31'
    return None


def parse(raw):
    source = raw['source']
    result = {'source': source, 'pdf_sha256': raw['pdf_sha256'],
              'status': 'needs_review', 'analytical_verified': False,
              'period_end_candidate': infer_period(source['source_title']),
              'comparative_period': None, 'comparability_group': 'unreviewed',
              'rows': [], 'headers': {}, 'checks': [], 'issues': []}
    period = result['period_end_candidate']
    if not period or period > source['disclosed_date']:
        result['issues'].append('unresolved_or_postdisclosure_period')
    sections = {'balance': [], 'income': [], 'cashflow': []}
    active = None
    occurrences = Counter()
    for page in raw['pages']:
        for line_no, line in enumerate(page['text'].splitlines(), 1):
            c = compact(line)
            heading = HEAD.fullmatch(c)
            if heading:
                active = None
                if heading[1] == '合并':
                    active = {'资产负债表': 'balance', '利润表': 'income', '现金流量表': 'cashflow'}[heading[3]]
                    occurrences[active] += 1
                continue
            # Stop before accounting notes / other sections in quarterly reports.
            if re.match(r'^[（(][二三四五六七八九十][）)]', c) and any(s in c for s in ('财务报表', '审计报告', '调整', '会计')):
                active = None
            if active and c:
                sections[active].append({'page': page['page'], 'line': line_no, 'text': line.strip()})
    by_metric = {}
    for kind, labels in LABELS.items():
        lines = sections[kind]
        if occurrences[kind] != 1:
            result['issues'].append(f'{kind}:statement_count:{occurrences[kind]}')
            continue
        header = '\n'.join(r['text'] for r in lines[:18])
        result['headers'][kind] = lines[:18]
        units = re.findall(r'^\s*单位[：:]\s*([^\n]+)', header, re.MULTILINE)
        if not units or any('万元' in u or '千元' in u for u in units) or not all(re.match(r'(?:人民币)?元(?:\s|$)', u.strip()) for u in units):
            result['issues'].append(f'{kind}:unit_not_unambiguous_yuan')
            continue
        for metric, alternatives in labels.items():
            hits = []
            for i, row in enumerate(lines):
                # Wrapped labels are allowed only on one physical PDF page.
                for count in (1, 2, 3):
                    chunk = lines[i:i + count]
                    if len(chunk) != count or chunk[-1]['page'] != row['page']: break
                    anchor = '\n'.join(r['text'] for r in chunk)
                    # Column numerals must follow a recognized complete row label.
                    match = next((s for s in alternatives if label_part(anchor).startswith(s)), None)
                    if match is None: continue
                    # Remove row numbering before numeric parsing.
                    numeric_text = re.sub(r'^\s*(?:\d+[.、．])', '', anchor)
                    number_lines = [NUMBER.findall(re.sub(r'^\s*(?:\d+[.、．])', '', r['text'])) for r in chunk]
                    if sum(bool(v) for v in number_lines) != 1: continue
                    values = NUMBER.findall(numeric_text)
                    if len(values) != 2: continue
                    tail = label_part(numeric_text).split(match, 1)[1]
                    # Reject labels that merely contain another target as prefix.
                    if tail and tail[0] not in '（(0123456789-−－': continue
                    hits.append({**row, 'source_line': anchor, 'values': [str(Decimal(v.replace(',', '').replace('−', '-').replace('－', '-'))) for v in values]})
                    break
            if len(hits) != 1:
                result['issues'].append(f'{kind}:{metric}:row_count:{len(hits)}')
                continue
            row = {k: v for k, v in hits[0].items() if k != 'text'}
            row.update(metric=metric, statement=kind, scope='consolidated', unit='CNY yuan',
                       basis='END' if kind == 'balance' else 'YTD',
                       column_interpretation='current_then_comparative_pending_period_review')
            result['rows'].append(row)
            by_metric[metric] = row
    for name, target, left, right, op in CHECKS:
        for column in (0, 1):
            check = {'name': name, 'column': column + 1, 'status': 'unavailable'}
            if all(m in by_metric for m in (target, left, right)):
                a, b, c = [Decimal(by_metric[m]['values'][column]) for m in (target, left, right)]
                residual = a - (b + c if op == '+' else b - c)
                # Three rounded yuan amounts can differ by at most a small absolute amount.
                check.update(status='pass' if abs(residual) <= Decimal('2') else 'fail', residual_yuan=str(residual))
            result['checks'].append(check)
    if any(c['status'] == 'fail' for c in result['checks']): result['issues'].append('accounting_identity_failed')
    if not result['issues'] and REQUIRED.issubset(by_metric) and all(c['status'] == 'pass' for c in result['checks']):
        result['status'] = 'machine_checks_passed_pending_source_and_period_review'
    result['remaining_review'] = ['period_and_column_headers', 'disclosure_versions_and_restatements',
                                  'cross_report_quarter_comparability', 'source_completeness']
    return result


def write_zip(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo('statements.json', (2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, json.dumps(payload, ensure_ascii=False, sort_keys=True).encode())
    tmp.replace(path)


def run(root=ROOT):
    started = time.monotonic()
    manifest_path = root / 'file_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    fingerprint = sha(Path(__file__).read_bytes())
    output = root / 'data/automation/structured'
    counts, issues = Counter(), Counter()
    exceptions = []
    newly_parsed = 0
    for path in sorted((root / 'data/automation/extracted').glob('*.zip')):
        digest = sha(path.read_bytes())
        rel = path.relative_to(root).as_posix()
        target = output / path.name
        try:
            if manifest.get(rel) != digest: raise ValueError('source_archive_hash_mismatch')
            cached = None
            if target.exists() and manifest.get(target.relative_to(root).as_posix()) == sha(target.read_bytes()):
                with zipfile.ZipFile(target) as archive: cached = json.loads(archive.read('statements.json'))
            if cached and cached.get('parser_sha256') == fingerprint and cached.get('extraction_sha256') == digest:
                packet = cached
            else:
                with zipfile.ZipFile(path) as archive: raw = json.loads(archive.read('pages.json'))
                if raw['source']['document_id'] != path.stem: raise ValueError('document_identity_mismatch')
                packet = parse(raw)
                packet.update(parser_sha256=fingerprint, extraction_sha256=digest)
                write_zip(target, packet)
                manifest[target.relative_to(root).as_posix()] = sha(target.read_bytes())
                newly_parsed += 1
            counts[packet['status']] += 1
            counts['candidate_rows'] += len(packet['rows'])
            counts['accounting_checks_passed'] += sum(c['status'] == 'pass' for c in packet['checks'])
            issues.update(packet['issues'])
            if packet['issues']: exceptions.append({'document_id': path.stem, 'issues': packet['issues']})
        except (ValueError, KeyError, zipfile.BadZipFile) as error:
            counts['source_error'] += 1
            exceptions.append({'document_id': path.stem, 'issues': [str(error)]})
    output.mkdir(parents=True, exist_ok=True)
    summary = {'parser_sha256': fingerprint, 'counts': dict(counts), 'issue_counts': dict(issues),
               'newly_parsed': newly_parsed, 'elapsed_seconds': round(time.monotonic() - started, 2),
               'analytical_verified': False, 'automatic_sample_verification_implemented': False,
               'purpose': 'Batch row extraction and accounting checks; never a frozen sample or verified label.'}
    for name, payload in [('status.json', summary), ('exceptions.json', exceptions)]:
        p = output / name
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
        manifest[p.relative_to(root).as_posix()] = sha(p.read_bytes())
    manifest_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    print(json.dumps(run(parser.parse_args().root), indent=2))
