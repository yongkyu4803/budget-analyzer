#!/usr/bin/env python3
"""상임위원회 예산안 검토보고서 Markdown 어댑터 (adapter: committee-review-report).

검증 기준 자료: 2027년도 과학기술정보통신부 소관 예산안·기금운용계획안 검토보고서(과학기술정보방송통신위원회, 과방위, 2026.11).
다른 상임위 보고서도 같은 편집 관례(목차 + Ⅰ 개관 + Ⅱ 검토의견, 소관과 → 【회계】 → (번호) 사업(코드) → 가)·나)·다) 쟁점)를 따를 것으로 보고
설정으로 패턴을 바꿀 수 있게 했으나, 과방위 보고서 외에는 실물로 검증하지 않았다. 반드시 build 출력의 toc_check를 확인한다.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from pathlib import Path

from msit_adapter import ACCOUNT_NAMES, plain, source_blocks

TOC_LINE = re.compile(r'^(.+?)\t\s*(\d{1,4})\s*$')
ISSUE_LABELS = '가나다라마바사아자차카타파하'
CODE = re.compile(r'\((\d{2,4}-\d{3})\)')
CODE_END = re.compile(r'\(\d{2,4}-\d{3}\)\s*(?:\d+\)\s*)?$')
DEFAULTS = {
    # 검토의견 부분이 시작되는 본문 줄 (목차 줄은 쪽번호가 붙어 제외된다)
    'review_start_pattern': r'^Ⅱ\.\s*검토의견\s*$',
    # 개관 부분이 시작되는 본문 줄
    'overview_start_pattern': r'^Ⅰ\.\s',
    # 소관과 머리글 바로 뒤에 오는 표지 낱말
    'dept_marker': '소관',
    'general_dept_names': ['총괄'],
}
MIDDLE_DOTS = str.maketrans({'･': '·', '・': '·', 'ㆍ': '·', '∙': '·', '•': '·'})


def key(text: str) -> str:
    """제목 비교용 키. 원문은 바꾸지 않는다."""
    text = unicodedata.normalize('NFKC', plain(text)).translate(MIDDLE_DOTS)
    return ''.join(c for c in text.casefold() if c.isalnum())


def clean(text: str) -> str:
    return re.sub(r'\s+', ' ', plain(text)).strip()


def account_id(label: str, extra: dict | None = None) -> str:
    names = {key(k): v for k, v in {**ACCOUNT_NAMES, **(extra or {})}.items()}
    k = key(label)
    if k in names:
        return names[k]
    for name_key, value in names.items():  # '원자력기금(원자력연구개발계정)' ↔ '원자력기금 원자력연구개발계정'
        if name_key == k:
            return value
    return 'other-' + (k[:24] or 'unknown')


def parse_toc(lines: list[str], cfg: dict):
    """목차 영역과 항목을 읽는다. 쪽번호가 붙은 줄만 목차로 본다."""
    start = next((i for i, l in enumerate(lines) if TOC_LINE.match(plain(l)) and re.match(r'^[ⅠⅡⅢ]\.', plain(l))), None)
    if start is None:
        raise ValueError('목차를 찾지 못했습니다 (쪽번호가 탭으로 붙은 "Ⅰ." 줄이 없음). 보고서 편집 형식을 확인하세요.')
    overview = re.compile(cfg['overview_start_pattern'])
    body_start = next((i for i in range(start + 1, len(lines)) if overview.match(plain(lines[i])) and not TOC_LINE.match(plain(lines[i]))), None)
    if body_start is None:
        raise ValueError('본문 시작(Ⅰ.)을 찾지 못했습니다.')
    entries = []
    for i in range(start, body_start):
        m = TOC_LINE.match(plain(lines[i]))
        if m:
            entries.append({'line': i + 1, 'text': clean(m[1]), 'page': int(m[2])})
    return entries, start + 1, body_start + 1


def classify_toc(entries: list[dict]):
    """목차 항목을 부(Ⅰ/Ⅱ) 구분과 종류로 분류한다."""
    part, out = None, []
    for e in entries:
        t = e['text']
        item = None
        if m := re.match(r'^([ⅠⅡⅢⅣ])\.\s*(.+)$', t):
            part = m[1]
            item = ('part', m[2])
        elif m := re.match(r'^(<참고\s*\d*>\s*)?【\s*(.+?)\s*】$', t):
            item = ('account', m[2])
        elif m := re.match(r'^\((\d+)\)\s*(.+)$', t):
            item = ('unit', m[2])
        elif m := re.match(r'^([가-하])\)\s*(.+)$', t):
            item = ('issue', m[2], m[1])
        elif m := re.match(r'^(?:<참고\s*\d*>\s*)?(\d+)\.\s*(.+)$', t) or re.match(r'^(<참고\s*\d*>)\s*(.+)$', t):
            item = ('section', m[2])
        if item:
            out.append({**e, 'part': part, 'type': item[0], 'title': item[1], 'label': item[2] if len(item) > 2 else None})
        else:
            out.append({**e, 'part': part, 'type': 'other', 'title': t, 'label': None})
    return out


def split_unit_header(text: str):
    """'(1) 사업명(1234-567)27) (주: …)' → (번호, 제목, [코드])."""
    m = re.match(r'^\(?(\d+)\)\s*(.+)$', text)
    number, rest = int(m[1]), m[2]
    rest = re.sub(r'(\(\d{2,4}-\d{3}\))\s*\d+\)\s*$', r'\1', rest.split('(주:')[0].strip())
    codes = CODE.findall(rest)
    if not codes:
        return number, rest, []
    if len(codes) == 1:
        return number, rest[:CODE.search(rest).start()].strip(), codes
    last = list(CODE.finditer(rest))[-1]
    return number, rest[:last.end()].strip(), codes  # 여러 사업이 한 항목: 원문 표기를 그대로 둔다


def next_nonblank(lines: list[str], i: int, limit: int = 6):
    for j in range(i + 1, min(len(lines), i + 1 + limit)):
        if plain(lines[j]):
            return j, plain(lines[j])
    return None, ''


def find_review_start(lines: list[str], body_start: int, cfg: dict):
    pat = re.compile(cfg['review_start_pattern'])
    for i in range(body_start, len(lines)):
        if pat.match(plain(lines[i])) and not TOC_LINE.match(plain(lines[i])):
            return i + 1
    raise ValueError('검토의견 시작 줄을 찾지 못했습니다: review_start_pattern 설정을 확인하세요.')


def dept_name_at(lines: list[str], i: int, dept_keys: set):
    """소관과 이름이 두 줄로 갈라진 경우('연구성과' + '혁신관')를 목차의 소관과 이름과 맞춰 합친다."""
    prev = []
    j = i - 1
    while j >= 0 and len(prev) < 2:
        t = plain(lines[j])
        if t:
            prev.append((j, t))
        j -= 1
    here = plain(lines[i])
    candidates = []
    if len(prev) >= 2:
        candidates.append((prev[1][0], prev[1][1] + prev[0][1] + here))
    if prev:
        candidates.append((prev[0][0], prev[0][1] + here))
    for start, joined in candidates:
        if key(joined) in dept_keys and len(joined) <= 40:
            return start, joined
    return i, here


def parse_review(lines: list[str], review_start: int, cfg: dict, dept_keys: set | None = None):
    """검토의견 부분을 소관과·회계·사업·쟁점 경계로 나눈다 (줄 번호는 1부터)."""
    marker = cfg['dept_marker']
    generals = {key(n) for n in cfg['general_dept_names']}
    events = []  # (line, kind, payload)
    n_lines = len(lines)
    in_table = 0
    unit_open, expected = False, 0
    dept_is_general = False
    for i in range(review_start, n_lines):  # review_start는 1부터 센 Ⅱ 줄 → 0부터 센 다음 줄
        raw = lines[i]
        in_table += len(re.findall(r'<table\b', raw)) - len(re.findall(r'</table>', raw))
        if in_table > 0 or '</table>' in raw:
            continue
        text = plain(raw)
        if not text:
            continue
        ln = i + 1
        # 소관과: 이름 줄 뒤 두 줄 안에 '소관' 한 단어만 있는 줄
        j, nxt = next_nonblank(lines, i, 2)
        if nxt == marker and len(text) <= 40 and not text.startswith(('○', '◦', '-', '(', '【')):
            start_i, name = dept_name_at(lines, i, dept_keys or set())
            events.append((start_i + 1, 'dept', {'name': name}))
            unit_open, expected, dept_is_general = False, 0, False
            continue
        if key(text) in generals and len(text) <= 8:
            events.append((ln, 'dept', {'name': text}))
            unit_open, expected, dept_is_general = False, 0, True
            continue
        if m := re.match(r'^(?:<참고\s*\d*>\s*)?【\s*(.+?)\s*】\s*$', text):
            events.append((ln, 'account', {'label': clean(m[1]), 'reference': text.startswith('<참고')}))
            unit_open, expected = False, 0
            continue
        # 변환 과정에서 '(2)'가 '2)'로 나오는 경우가 있어 번호 괄호는 선택으로 받는다. 코드로 끝나는 줄만 사업 머리글로 인정한다.
        if re.match(r'^\(?\d+\)\s', text) and len(text) <= 600:
            number, title, codes = split_unit_header(text)
            if codes and CODE_END.search(text.split('(주:')[0].strip()):
                events.append((ln, 'unit', {'number': number, 'title': title, 'codes': codes, 'header': text}))
                unit_open, expected = True, 0
                continue
            if not codes and re.match(r'^\(\d+\)', text) and dept_is_general and next_nonblank(lines, i)[1][:1] in ('◦', '○', '가'):
                events.append((ln, 'unit', {'number': number, 'title': title, 'codes': [], 'header': text}))
                unit_open, expected = True, 0
                continue
        if unit_open and (m := re.match(r'^([가-하])\)\s+(.+)$', text)) and len(text) <= 260:
            if m[1] == ISSUE_LABELS[expected]:
                events.append((ln, 'issue', {'label': m[1], 'title': clean(m[2])}))
                expected += 1
    events.sort(key=lambda e: e[0])
    return events


def build_records(lines, events, review_start, toc_end_line, cfg, source, file_hash, fiscal_year, ministry_id):
    """이벤트를 사업·쟁점·블록 레코드로 만든다."""
    total = len(lines)
    boundaries = [e[0] for e in events] + [total + 1]
    extra_accounts = cfg.get('account_names')
    units, depts, accounts = [], [], []
    dept = None
    account = None
    account_fresh = False  # 이 사업 바로 앞(직전 사업 이후)에 【회계】 머리글이 있었는가
    current = None
    seq = 0
    for idx, (ln, kind, data) in enumerate(events):
        end = boundaries[idx + 1] - 1
        if kind == 'dept':
            dept = data['name']
            depts.append({'name': dept, 'line': ln})
            account = None
            account_fresh = False
            current = None
        elif kind == 'account':
            account_fresh = True
            account = data['label']
            accounts.append({'label': account, 'dept': dept, 'line': ln, 'reference': data['reference']})
            current = None
        elif kind == 'unit':
            seq += 1
            current = {'seq': seq, 'number': data['number'], 'title': data['title'], 'codes': data['codes'], 'code': data['codes'][0] if data['codes'] else None,
                       'header': data['header'], 'dept': dept, 'account': account, 'account_id': account_id(account, extra_accounts) if account else None,
                       'reference_account': bool(accounts and accounts[-1]['reference'] and accounts[-1]['label'] == account),
                       'account_carried': not account_fresh,
                       'start_line': ln, 'end_line': end, 'issues': []}
            account_fresh = False
            units.append(current)
        elif kind == 'issue' and current is not None:
            current['issues'].append({'label': data['label'], 'title': data['title'], 'start_line': ln, 'end_line': end})
        if current is not None and kind in ('unit', 'issue'):
            current['end_line'] = end
        elif current is not None and kind in ('dept', 'account'):
            pass
    # 마지막 사업의 끝: 다음 소관과/회계 경계 직전 (위 루프에서 end로 이미 반영됨)
    for u in units:
        _finish_unit(lines, u, source, file_hash, fiscal_year, ministry_id)
    return units, depts, accounts


def _caption_info(blocks, k):
    """표 블록 앞뒤에서 표 제목, (단위: …), 자료 출처를 찾는다."""
    caption = unit_raw = note = None
    for j in range(k - 1, max(-1, k - 4), -1):
        b = blocks[j]
        if b['table']:
            break
        t = b['text'].strip()
        if unit_raw is None and (m := re.match(r'^\(\s*단위\s*[:：]\s*(.+?)\s*\)$', t)):
            unit_raw = m[1]
        elif caption is None and re.match(r'^<.+>$', t):
            caption = t
    for j in range(k + 1, min(len(blocks), k + 3)):
        b = blocks[j]
        if b['table']:
            break
        t = b['text'].strip()
        if t.startswith(('자료', '주:', '주 :')):
            note = t
            break
    return caption, unit_raw, note


def _finish_unit(lines, u, source, file_hash, fiscal_year, ministry_id):
    start, end = u['start_line'], u['end_line']
    while end > start and not plain(lines[end - 1]):
        end -= 1
    u['end_line'] = end
    blocks = source_blocks(lines, start, end)
    issues = u['issues']
    for n, issue in enumerate(issues):
        issue['end_line'] = (issues[n + 1]['start_line'] - 1) if n + 1 < len(issues) else end
    for k, block in enumerate(blocks):
        owner = None
        for issue in issues:
            if issue['start_line'] <= block['start_line']:
                owner = issue
        if block['start_line'] == start:
            block['section'] = '사업 머리글'
        elif owner is None:
            block['section'] = '검토요지'
        else:
            block['section'] = f"{owner['label']}) {owner['title']}"
        block['issue_label'] = owner['label'] if owner else None
        block['caption'], block['unit_raw'], block['source_note'] = _caption_info(blocks, k) if block['table'] else (None, None, None)
    u['blocks'] = blocks
    u['source'] = source
    u['source_sha256'] = file_hash
    u['id'] = f"{fiscal_year}-{ministry_id}-review-u{u['seq']:03d}"


def build_contexts(lines, toc, overview_start, review_start, cfg, source, file_hash, fiscal_year, ministry_id):
    """Ⅰ 개관 부분을 목차의 '번호. 제목' 순서대로 맞춰 구간으로 나눈다 (사업 단위가 아닌 총괄표·회계별 현황)."""
    wanted = [t for t in toc if t['part'] == 'Ⅰ' and t['type'] == 'section']
    positions, cursor = [], overview_start
    for t in wanted:
        target = key(t['title'])
        depth = 0
        for i in range(cursor, review_start - 1):
            depth += len(re.findall(r'<table\b', lines[i])) - len(re.findall(r'</table>', lines[i]))
            if depth > 0 or '</table>' in lines[i]:
                continue
            text = plain(lines[i])
            if text and len(text) <= 120 and (m := re.match(r'^(?:<참고\s*\d*>|\d+\.)\s*(.+)$', text)):
                if key(m[1]) == target:
                    positions.append((i + 1, t))
                    cursor = i + 1
                    break
    contexts = []
    for n, (ln, t) in enumerate(positions):
        end = (positions[n + 1][0] - 1) if n + 1 < len(positions) else review_start - 1
        while end > ln and not plain(lines[end - 1]):
            end -= 1
        blocks = source_blocks(lines, ln, end)
        for k, b in enumerate(blocks):
            b['section'] = t['title']
            b['issue_label'] = None
            b['caption'], b['unit_raw'], b['source_note'] = _caption_info(blocks, k) if b['table'] else (None, None, None)
        contexts.append({'seq': n + 1, 'title': t['title'], 'toc_page': t['page'], 'start_line': ln, 'end_line': end, 'blocks': blocks,
                         'source': source, 'source_sha256': file_hash, 'id': f"{fiscal_year}-{ministry_id}-review-c{n + 1:03d}"})
    return contexts, len(wanted)


def check_against_toc(toc, units, depts, accounts, overview_found, overview_expected):
    """목차와 본문 경계를 대조한다. 사업·소관과는 어긋나면 실패, 쟁점은 경고로 보고한다."""
    part2 = [t for t in toc if t['part'] == 'Ⅱ']
    report = {'toc_depts': 0, 'body_depts': len(depts), 'toc_units': 0, 'body_units': len(units), 'toc_issues': 0,
              'body_issues': sum(len(u['issues']) for u in units), 'toc_accounts': 0, 'body_accounts': len(accounts),
              'overview_sections_expected': overview_expected, 'overview_sections_found': overview_found,
              'errors': [], 'warnings': [], 'minor_title_differences': []}
    toc_depts = [t for t in part2 if t['type'] == 'section']
    toc_units = [t for t in part2 if t['type'] == 'unit']
    toc_issues = [t for t in part2 if t['type'] == 'issue']
    report['toc_depts'], report['toc_units'], report['toc_issues'] = len(toc_depts), len(toc_units), len(toc_issues)
    report['toc_accounts'] = sum(t['type'] == 'account' for t in part2)

    def compare(label, toc_items, body_items, strict):
        a = [key(x) for x in toc_items]
        b = [key(x) for x in body_items]
        if a == b:
            return
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == 'equal':
                continue
            if op == 'replace' and i2 - i1 == j2 - j1:
                for x, y in zip(range(i1, i2), range(j1, j2)):
                    ratio = difflib.SequenceMatcher(None, a[x], b[y]).ratio()
                    row = {'level': label, 'toc': toc_items[x], 'body': body_items[y], 'similarity': round(ratio, 3)}
                    if ratio >= 0.85:
                        report['minor_title_differences'].append(row)
                    else:
                        (report['errors'] if strict else report['warnings']).append({**row, 'problem': 'title differs'})
            else:
                (report['errors'] if strict else report['warnings']).append(
                    {'level': label, 'problem': op, 'toc': toc_items[i1:i2], 'body': body_items[j1:j2]})

    compare('회계', [t['title'] for t in part2 if t['type'] == 'account'], [a['label'] for a in accounts], False)
    compare('소관과', [re.sub(r'\s*소관$', '', t['title']) for t in toc_depts], [d['name'] for d in depts], True)
    # 사업은 코드가 있으면 코드로, 없으면 제목으로 비교한다.
    toc_ids = [(CODE.findall(t['title']) or [t['title']])[0] if CODE.search(t['title']) else t['title'] for t in toc_units]
    body_ids = [u['code'] if u['code'] else u['title'] for u in units]
    compare('사업', toc_ids, body_ids, True)
    compare('쟁점', [t['label'] + ') ' + t['title'] for t in toc_issues],
            [i['label'] + ') ' + i['title'] for u in units for i in u['issues']], False)
    return report


def fill_accounts_from_toc(toc, units, config, report):
    """본문에 【회계】 머리글이 빠진 사업은 목차의 회계 구분으로 채운다 (출처를 account_source에 남긴다)."""
    toc_units, account = [], None
    for t in toc:
        if t['part'] != 'Ⅱ':
            continue
        if t['type'] == 'section':
            account = None
        elif t['type'] == 'account':
            account = t['title']
        elif t['type'] == 'unit':
            toc_units.append(account)
    for u in units:
        u['account_source'] = 'body' if u['account'] else None
    if len(toc_units) != len(units):
        return
    for u, toc_account in zip(units, toc_units):
        if not toc_account:
            continue
        missing = u['account'] is None
        # 앞 사업의 회계를 이어받았을 뿐인데 목차와 다르면 머리글이 빠진 것으로 보고 목차를 따른다.
        carried_wrong = u['account'] is not None and u.get('account_carried') and key(u['account']) != key(toc_account)
        if missing or carried_wrong:
            before = u['account']
            u['account'] = toc_account
            u['account_id'] = account_id(toc_account, config.get('account_names'))
            u['account_source'] = 'toc'
            report['warnings'].append({'level': '회계', 'problem': '본문에 회계 머리글이 없어 목차 기준으로 채움' if missing else '앞 사업의 회계를 이어받았으나 목차와 달라 목차 기준으로 바꿈',
                                       'unit': u['id'], 'code': u['code'], 'account': toc_account, 'body_inherited': before})


def parse(root, config):
    """config의 markdown_glob 파일(보고서 1개)을 읽어 구조를 만든다."""
    cfg = {**DEFAULTS, **config.get('patterns', {})}
    root = Path(root).resolve()
    files = sorted(root.glob(config['markdown_glob']))
    if len(files) != 1:
        raise ValueError(f"markdown_glob는 보고서 파일 1개와 일치해야 합니다 (현재 {len(files)}개): {config['markdown_glob']}")
    p = files[0]
    raw = p.read_bytes()
    import hashlib
    file_hash = hashlib.sha256(raw).hexdigest()
    lines = raw.decode('utf-8').splitlines()
    source = p.relative_to(root).as_posix()
    fy, mid = config['fiscal_year'], config['ministry_id']
    entries, toc_start, overview_start = parse_toc(lines, cfg)
    toc = classify_toc(entries)
    review_start = find_review_start(lines, overview_start, cfg)
    dept_keys = {key(re.sub(r'\s*소관$', '', t['title'])) for t in toc if t['part'] == 'Ⅱ' and t['type'] == 'section'}
    events = parse_review(lines, review_start, cfg, dept_keys)
    units, depts, accounts = build_records(lines, events, review_start, entries[-1]['line'], cfg, source, file_hash, fy, mid)
    contexts, expected_overview = build_contexts(lines, toc, overview_start, review_start, cfg, source, file_hash, fy, mid)
    report = check_against_toc(toc, units, depts, accounts, len(contexts), expected_overview)
    if len(contexts) != expected_overview:
        report['warnings'].append({'level': '개관', 'problem': f'목차 {expected_overview}개 중 본문에서 {len(contexts)}개만 찾음'})
    if config.get('expected_units') is not None and len(units) != config['expected_units']:
        report['errors'].append({'level': '사업', 'problem': f"expected_units {config['expected_units']} ≠ 본문 {len(units)}"})
    fill_accounts_from_toc(toc, units, config, report)
    source_info = {'path': source, 'sha256': file_hash, 'bytes': len(raw), 'lines': len(lines), 'toc_start_line': toc_start,
                   'toc_end_line': entries[-1]['line'], 'overview_start_line': overview_start, 'review_start_line': review_start}
    return {'units': units, 'contexts': contexts, 'depts': depts, 'accounts': accounts, 'toc': toc, 'toc_check': report, 'source': source_info}
