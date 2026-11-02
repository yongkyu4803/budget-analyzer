#!/usr/bin/env python3
"""MSIT repeated-TOC Markdown adapter, derived from workspace doc_search.py. Only the current layout has been validated."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import quote, unquote

ROOT = Path.cwd()
CONFIG = {}
DATA = ROOT / '.doc-index' / 'local'
SOURCE_DIR = ROOT / 'index' / 'source'
BUILD_DATE = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
LINE_CACHE = {}
HEADING = re.compile(r'^\((\d+)\)\s*(.+?)\s*\((\d{4}-\d{3})\)$')
TOC = re.compile(r'^\((\d+)\)\s*(.+?)\s*\((\d{4}-\d{3})\)\s+(\d+)$')
ACCOUNT_NAMES = {
    '일반회계': 'general',
    '소재·부품·장비산업경쟁력강화및공급망안정화특별회계': 'materials',
    '지역균형발전특별회계': 'balanced',
    '고등·평생교육지원특별회계': 'higher-education',
    '반도체산업경쟁력강화특별회계': 'semiconductor',
    '책임운영기관특별회계(국립중앙과학관)': 'national-science-museum',
    '책임운영기관특별회계(국립과천과학관)': 'gwacheon-science-museum',
    '우편사업특별회계': 'postal',
    '우체국예금특별회계': 'postal-deposits',
    '우체국보험특별회계': 'postal-insurance',
    '과학기술진흥기금': 'science',
    '원자력기금 원자력연구개발계정': 'atomic',
    '방송통신발전기금': 'broadcast',
    '정보통신진흥기금': 'ict',
    '기후대응기금': 'climate',
    '미래대응기금': 'future',
}
EXPANSIONS = {
    'GPUaaS': ['GPU 임차', 'GPU 임대', '클라우드 이용료', '컴퓨팅 자원 지원'],
    'NIPA': ['정보통신산업진흥원'],
    'IITP': ['정보통신기획평가원'],
    'HPC': ['초고성능컴퓨팅'],
    'AIDC': ['AI 데이터센터', '인공지능 데이터센터'],
    '피지컬AI': ['Physical AI', '피지컬 인공지능'],
}
SECTION_PATTERNS = [
    ('contact', '사업 담당자', r'^□\s*사업\s*담당자'),
    ('summary', '예산·지출계획 총괄표', r'^가\.\s*(?:예산안|지출계획안)\s*총괄표'),
    ('description', '사업설명자료', r'^나\.\s*사업설명자료'),
    ('purpose', '사업목적·내용', r'^1\)\s*사업목적'),
    ('basis', '사업개요', r'^2\)\s*사업(?:개요|근거)'),
    ('history', '추진경위', r'^[①②③④⑤]\s*(?:사업)?추진경위'),
    ('calculation', '산출 근거', r'^3\)\s*\d{4}년도.*산출'),
    ('effects', '사업효과', r'^4\)\s*사업효과'),
    ('feasibility', '타당성조사', r'^5\)\s*타당성'),
    ('total-cost', '총사업비', r'^6\)\s*총사업비'),
    ('execution-detail', '사업추진체계', r'^[①②③④⑤]\s*사업추진체계'),
    ('beneficiaries', '사업 수혜자', r'^사업\s*수혜자'),
    ('execution', '사업 집행절차', r'^7\)\s*사업\s*집행'),
    ('medium-term', '중기재정계획', r'^8\)\s*중기'),
    ('evaluation', '외부지적사항·평가', r'^9\)\s*최근'),
    ('future-plan', '향후 추진계획', r'^10\)\s*향후'),
    ('settlement', '결산내역', r'^다\.\s*'),
    ('additional', '기타 추가자료', r'^라\.\s*기타'),
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plain(raw: str) -> str:
    """Keep table cell boundaries; join line wraps only in the search key."""
    raw = re.sub(r'<!--.*?-->', '', raw, flags=re.S)
    raw = re.sub(r'!\[[^\]]*\]\([^\n]*?\)', ' [이미지] ', raw)
    raw = re.sub(r'<img\b[^>]*>', ' [이미지] ', raw, flags=re.I)
    raw = re.sub(r'\[([^\]]+)\]\([^\n]*?\)', r'\1', raw)
    raw = re.sub(r'<br\s*/?>', ' ', raw, flags=re.I)
    raw = re.sub(r'</(?:td|th)>', ' | ', raw, flags=re.I)
    raw = re.sub(r'</tr>', '\n', raw, flags=re.I)
    raw = re.sub(r'</?(?:table|thead|tbody|tfoot|tr|td|th|sup|sub|u|b|strong|em|i|a|p|div|span)\b[^>]*>', '', raw, flags=re.I)
    raw = html.unescape(raw).replace('**', '').replace('`', '')
    raw = re.sub(r'\\([*_~<>\[\]()])', r'\1', raw)
    raw = re.sub(r'(?m)^\s*#{1,6}\s+', '', raw)
    return raw.strip()


def compact(text: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text).casefold())


def identity_text(text: str) -> str:
    return ''.join(c for c in compact(plain(text)) if c.isalnum())


def account_heading(line: str):
    value = plain(line)
    m = re.match(r'^(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+\.|3-[123]\.)\s*(.+)$', value)
    if not m:
        return None
    name = m[1].strip()
    for label, key in ACCOUNT_NAMES.items():
        if compact(label) == compact(name):
            return key, label
    return None


def source_blocks(lines: list[str], start: int, end: int):
    """Paragraphs and complete (including nested) tables, with original line locations."""
    blocks = []
    i = start - 1
    while i < end:
        if not lines[i].strip():
            i += 1
            continue
        first = i
        depth = 0
        while i < end:
            line = lines[i]
            depth += len(re.findall(r'<table\b', line)) - len(re.findall(r'</table>', line))
            i += 1
            if depth <= 0 and (i == end or not lines[i].strip()):
                break
        raw = '\n'.join(lines[first:i])
        text = plain(raw)
        if text:
            blocks.append({'start_line': first + 1, 'end_line': i, 'text': text, 'section': '본문', 'table': '<table' in raw or bool(re.search(r'(?m)^\|', raw))})
    return blocks


def section_map(lines: list[str], start: int, end: int):
    found = []
    used = Counter()
    for n in range(start, end + 1):
        raw = lines[n-1]
        text = plain(raw)
        if not text or len(text) > 180 or '<tr' in raw:
            continue
        if re.match(r'^가\s*\.', text) and ('총괄표' in compact(text)):
            text = re.sub(r'\s+', '', text)
        for key, label, pattern in SECTION_PATTERNS:
            if re.search(pattern, text):
                used[key] += 1
                anchor = key if used[key] == 1 else f'{key}-{used[key]}'
                found.append({'anchor': anchor, 'title': text, 'label': label, 'heading': text, 'start_line': n})
                break
    for i, item in enumerate(found):
        item['end_line'] = found[i+1]['start_line'] - 1 if i+1 < len(found) else end
    return found


def read_notes():
    notes = {}
    for p in sorted((ROOT / 'index').glob('*.md')):
        text = p.read_text(encoding='utf-8')
        found = re.search(r'^index-id:\s*(.+)$', text, re.M)
        if not found: continue
        key = found[1]
        title = re.search(r'^title:\s*(.+)$', text, re.M)[1]
        assert key not in notes, f'Duplicate curated index ID: {key}'
        notes[key] = {'path': p.relative_to(ROOT).as_posix(), 'title': title}
    return notes


def make_record(lines, *, start, end, volume, source, file_hash, account, kind, number=None, title=None, code=None, serial=0):
    account_id, account_label = account
    if kind == 'program':
        key = f"{CONFIG['fiscal_year']}-{CONFIG['ministry_id']}-{account_id}-v{volume:02d}-n{number:03d}"
    else:
        key = f"{CONFIG['fiscal_year']}-{CONFIG['ministry_id']}-context-v{volume:02d}-{serial:03d}"
    while end > start and (not lines[end-1].strip() or plain(lines[end-1]) == '사업명'):
        end -= 1
    parts = section_map(lines, start, end) if kind == 'program' else []
    blocks = source_blocks(lines, start, end)
    for block in blocks:
        earlier = [s for s in parts if s['start_line'] <= block['start_line']]
        block['section'] = earlier[-1]['title'] if earlier else ('사업 식별·담당자' if kind == 'program' else '총괄·세입·수입 등')
    return {'id': key, 'kind': kind, 'title': title or f'{volume}권 {account_label} 총괄·세입·수입 등', 'code': code, 'year': CONFIG['fiscal_year'], 'volume': volume, 'account': account_label, 'account_id': account_id, 'number': number, 'source': source, 'source_sha256': file_hash, 'source_start_line': start, 'source_end_line': end, 'fragment': f'index/source/{key}.md', 'sections': parts, 'blocks': blocks}


def collect():
    files = sorted(ROOT.glob(CONFIG['markdown_glob']))
    files = [p for p in files if re.search(r'\(\d+권\)', unicodedata.normalize('NFC', p.name))]
    assert files, 'No budget Markdown files found'
    if CONFIG.get('expected_volumes') is not None:
        assert len(files) == CONFIG['expected_volumes'], 'Volume count changed; review configuration'
    files.sort(key=lambda p: int(re.search(r'\((\d+)권\)', unicodedata.normalize('NFC',p.name))[1]))
    records, sources, canonical_toc, toc_variants = [], [], [], []
    for p in files:
        volume = int(re.search(r'\((\d+)권\)', unicodedata.normalize('NFC', p.name))[1])
        raw = p.read_bytes()
        lines = raw.decode('utf-8').splitlines()
        toc = [(n, TOC.fullmatch(plain(line))) for n, line in enumerate(lines, 1)]
        toc = [(n, m) for n, m in toc if m]
        assert toc, f'No TOC in volume {volume}'
        if CONFIG.get('expected_programs') is not None:
            assert len(toc) == CONFIG['expected_programs'], f'Unexpected TOC count: {len(toc)}'
        toc_end = toc[-1][0]
        toc_values = [(int(m[1]), m[2], m[3], int(m[4])) for n, m in toc]
        if not canonical_toc:
            canonical_toc = toc_values
        else:
            toc_variants.append(toc_values)
        file_hash = digest(raw)
        source_path = p.relative_to(ROOT).as_posix()
        sources.append({'volume': volume, 'path': source_path, 'sha256': file_hash, 'bytes': len(raw), 'lines': len(lines), 'toc_start_line': toc[0][0], 'toc_end_line': toc_end})
        account = tuple(CONFIG.get('default_accounts', {}).get(str(volume), ['unclassified', '분류 확인 필요']))
        initial_account = account
        boundaries = []
        for n in range(toc_end+1, len(lines)+1):
            a = account_heading(lines[n-1])
            if a:
                account = a
                boundaries.append((n, 'account', account, None))
            m = HEADING.fullmatch(plain(lines[n-1]))
            if m:
                assert account[0] != 'unclassified', (volume, n, m[2])
                preceding = [plain(s) for s in lines[max(0,n-5):n-1] if plain(s)]
                assert preceding and preceding[-1] == '사업명', (volume, n, preceding)
                boundaries.append((n, 'program', account, m))
        boundaries.sort(key=lambda x:x[0])
        context_start, context_account, serial = toc_end+1, (initial_account if initial_account[0] != 'unclassified' else ('context','총괄')), 0
        for i, (start, kind, acct, match) in enumerate(boundaries):
            if context_start < start and (i == 0 or boundaries[i-1][1] == 'account'):
                if len(plain('\n'.join(lines[context_start-1:start-1]))) > 80:
                    serial += 1
                    records.append(make_record(lines, start=context_start, end=start-1, volume=volume, source=source_path, file_hash=file_hash, account=context_account, kind='context', serial=serial))
            following = boundaries[i+1][0] if i+1 < len(boundaries) else len(lines)+1
            if kind == 'program':
                records.append(make_record(lines, start=start, end=following-1, volume=volume, source=source_path, file_hash=file_hash, account=acct, kind=kind, number=int(match[1]), title=match[2], code=match[3]))
                context_start = following
            else:
                context_start, context_account = start, acct
        # All volume endings are within the last program in this edition.
    assert all(t == canonical_toc for t in toc_variants), 'Repeated TOCs differ'
    programs = [r for r in records if r['kind'] == 'program']
    assert len(programs) == len(canonical_toc), (len(programs), len(canonical_toc))
    discrepancies = []
    for r, (number, title, code, page) in zip(programs, canonical_toc):
        assert (r['number'], r['code']) == (number, code), (r, number, code)
        assert identity_text(r['title']) == identity_text(title), (r['title'], title)
        if r['title'] != title:
            discrepancies.append({'id':r['id'], 'toc_title':title, 'body_title':r['title'], 'resolution':'본문 표기 보존; 문장부호 차이'})
        r['toc_printed_page'] = page
    ids = [r['id'] for r in records]
    assert len(ids) == len(set(ids)), 'Duplicate local record IDs'
    notes = read_notes()
    lookup = {r['id']:r for r in programs}
    for key, note in notes.items():
        if key not in lookup: continue
        lookup[key]['curated_index'] = note['path']
        lookup[key]['curated_title'] = note['title']
    return records, sources, discrepancies



def parse(root, config):
    global ROOT, CONFIG
    ROOT, CONFIG = Path(root).resolve(), config
    if config.get("account_names"):
        ACCOUNT_NAMES.update(config["account_names"])
    LINE_CACHE.clear()
    return collect()
