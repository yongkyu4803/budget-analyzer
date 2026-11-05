#!/usr/bin/env python3
"""상임위원회 예산안 검토보고서 색인·검색 (review 1.0.0). Python 표준 라이브러리만 사용.

사업설명자료 색인(budget_core.py, .budget-index/budget.sqlite)과 별도의 DB(.budget-index/review.sqlite)를 만들고
사업 코드와 제목(예: 1111-111)으로 두 문서를 연결해 보여 준다. 두 DB를 합치지 않는다.

명령: build | search | show | verify  (--root 작업 폴더)
"""
from __future__ import annotations

import argparse
import difflib
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import unicodedata
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 임베디드 Python은 스크립트 폴더를 경로에 넣지 않는다

VERSION = '1.0.0'
SCHEMA = 1
REVIEW_STAGES = {'committee_review'}
CONFIG_PATH = '.budget-index/review-config.json'
DB_PATH = '.budget-index/review.sqlite'
ALIASES = {
    'NIPA': ['정보통신산업진흥원'], 'IITP': ['정보통신기획평가원'], 'HPC': ['초고성능컴퓨팅'],
    'AIDC': ['AI 데이터센터', '인공지능 데이터센터'], 'GPUaaS': ['GPU 임차', 'GPU 임대', '클라우드 이용료', '컴퓨팅 자원 지원'],
    '피지컬AI': ['Physical AI', '피지컬 인공지능'],
}
CODE_RE = re.compile(r'\d{2,4}-\d{3}')


def fail(message):
    raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def norm(text):
    """검색용 접기: 원문은 바꾸지 않는다. 가운뎃점 변형(･ ・ ㆍ)을 같은 글자로 본다."""
    text = unicodedata.normalize('NFKC', text).translate(str.maketrans({'･': '·', '・': '·', 'ㆍ': '·'}))
    return ''.join(c for c in text.casefold() if c.isalnum())


def local(root, path):
    p = Path(path)
    if p.is_absolute() or '..' in p.parts:
        fail(f'Workspace-relative path required: {path}')
    result = (root / p).resolve()
    if not result.is_relative_to(root.resolve()):
        fail(f'Path escapes workspace: {path}')
    return result


def config_at(root):
    path = root / CONFIG_PATH
    if not path.is_file():
        fail(f'설정이 없습니다: {CONFIG_PATH} (references/review-config-example.json을 복사해 자료에 맞게 고치세요)')
    c = read_json(path)
    if c.get('schema_version') != SCHEMA:
        fail('Unsupported review config schema')
    if c.get('adapter') != 'committee-review-report':
        fail('adapter는 committee-review-report여야 합니다')
    for key in ('ministry', 'ministry_id', 'fiscal_year', 'edition', 'committee', 'markdown_glob'):
        if not c.get(key):
            fail(f'Missing configuration: {key}')
    if not isinstance(c['fiscal_year'], int):
        fail('fiscal_year must be integer')
    if c['edition'].get('stage') not in REVIEW_STAGES:
        fail('edition.stage는 committee_review여야 합니다')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', c['edition'].get('id', '')):
        fail('Invalid edition ID')
    if not c['committee'].get('name'):
        fail('committee.name 필요 (예: 과학기술정보방송통신위원회)')
    return c


def record_uid(r, config):
    return f"{r['id']}@{config['edition']['id']}@{r['source_sha256'][:16]}"


def block_weight(section, kind):
    if kind == 'context':
        return 1.0
    if section == '검토요지':
        return 3.0
    if section == '사업 머리글':
        return 0.5
    if '개요' in section:
        return 1.0
    return 2.2  # 쟁점(나)·다)…) 본문: 국회가 지적한 내용


def build(root):
    from review_adapter import parse
    config = config_at(root)
    parsed = parse(root, config)
    check = parsed['toc_check']
    if check['errors']:
        fail('목차와 본문 경계가 맞지 않아 게시하지 않습니다 (기존 색인은 보존): ' + json.dumps(check['errors'][:5], ensure_ascii=False))
    data = root / '.budget-index'
    data.mkdir(exist_ok=True)
    records = []
    for u in parsed['units']:
        records.append(('unit', u))
    for c in parsed['contexts']:
        records.append(('context', c))
    with tempfile.NamedTemporaryFile(dir=data, suffix='.sqlite', delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        con = sqlite3.connect(temp_path)
        con.executescript('''
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE units(uid TEXT PRIMARY KEY, legacy_id TEXT, kind TEXT, code TEXT, codes TEXT, seq INTEGER, dept_key TEXT, account_key TEXT, title_key TEXT, body_key TEXT, payload TEXT);
            CREATE INDEX unit_code ON units(code);
            CREATE INDEX unit_legacy ON units(legacy_id);
            CREATE TABLE blocks(uid TEXT, start_line INTEGER, end_line INTEGER, section TEXT, issue_label TEXT, weight REAL, is_table INTEGER, caption TEXT, unit_raw TEXT, key TEXT, text TEXT);
            CREATE INDEX block_uid ON blocks(uid);
        ''')
        for kind, r in records:
            uid = record_uid(r, config)
            blocks = r['blocks']
            payload = {k: v for k, v in r.items() if k != 'blocks'}
            payload.update(uid=uid, kind=kind, schema_version=SCHEMA, ministry=config['ministry'], ministry_id=config['ministry_id'],
                           fiscal_year=config['fiscal_year'], committee=config['committee'], edition=config['edition'],
                           review_status='source_location_checked', source_toc_checked=True)
            if kind == 'context':
                payload.update(code=None, codes=[], dept=None, account=r['title'], account_id=None, issues=[])
            title_key = norm(payload['title'])
            codes = payload.get('codes') or []
            body_key = '\n'.join(norm(b['text']) for b in blocks)
            con.execute('INSERT INTO units VALUES(?,?,?,?,?,?,?,?,?,?,?)', (
                uid, r['id'], kind, payload.get('code'), dumps(codes), r['seq'], norm(payload.get('dept') or ''), norm(payload.get('account') or ''),
                title_key, body_key, dumps(payload)))
            con.executemany('INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?,?,?,?)', [(
                uid, b['start_line'], b['end_line'], b['section'], b.get('issue_label'), block_weight(b['section'], kind), int(b['table']),
                b.get('caption'), b.get('unit_raw'), norm(b['text']), b['text']) for b in blocks])
        inputs = [{'path': CONFIG_PATH, 'sha256': sha(root / CONFIG_PATH)}]
        manifest = {'runtime_version': VERSION, 'schema_version': SCHEMA, 'built_at': datetime.now(timezone.utc).isoformat(),
                    'config': config, 'source': parsed['source'], 'inputs': inputs,
                    'unit_count': len(parsed['units']), 'context_count': len(parsed['contexts']),
                    'issue_count': sum(len(u['issues']) for u in parsed['units']),
                    'dept_count': len(parsed['depts']), 'toc_check': check}
        con.execute('INSERT INTO meta VALUES(?,?)', ('manifest', dumps(manifest)))
        con.commit()
        con.close()
        temp_path.replace(data / 'review.sqlite')  # 단일 파일 교체: 새 manifest와 옛 DB가 섞이지 않는다
    finally:
        temp_path.unlink(missing_ok=True)
    write_catalog(root, config, parsed)
    return {k: manifest[k] for k in ('unit_count', 'issue_count', 'dept_count', 'context_count', 'built_at')} | {
        'warnings': len(check['warnings']), 'minor_title_differences': len(check['minor_title_differences'])}


def write_catalog(root, config, parsed):
    c = config
    lines = ['# 검토보고서 사업·쟁점 목록', '',
             f"{c['ministry']} · {c['fiscal_year']} · {c['committee']['name']} · {c['edition']['id']}", '',
             '| 소관과 | 회계·기금 | 사업명 | 코드 | 쟁점 | 원문 |', '|---|---|---|---|---|---|']
    src = quote(parsed['source']['path'])
    for u in parsed['units']:
        issues = '<br>'.join(f"{i['label']}) {i['title']}" for i in u['issues'] if '개요' not in i['title']) or '-'
        lines.append(f"| {u['dept']} | {u.get('account') or '-'} | {u['title']} | {u['code'] or '-'} | {issues} | [{u['start_line']}행](../{src}) |")
    (root / '.budget-index/REVIEW_CATALOG.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def connect(root, check=True):
    db = root / DB_PATH
    if not db.exists():
        fail(f'Run review build first; {DB_PATH} missing')
    con = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    manifest = json.loads(con.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()[0])
    if manifest['schema_version'] != SCHEMA or manifest['runtime_version'] != VERSION:
        con.close()
        fail('Cache/runtime version mismatch; rebuild')
    if check:
        for item in [manifest['source'], *manifest['inputs']]:
            p = local(root, item['path'])
            if not p.is_file() or sha(p) != item['sha256']:
                con.close()
                fail(f"Stale or missing input: {item['path']}; rebuild")
    return con, manifest


def _title_match(review_title, program_title):
    a, b = norm(review_title), norm(program_title)
    if not a or not b:
        return None
    if a == b:
        return 'title_exact'
    if a in b or b in a:  # 여러 사업이 한 머리글에 묶인 경우 포함
        return 'title_contains'
    if difflib.SequenceMatcher(None, a, b).ratio() >= 0.85:
        return 'title_similar'
    return None


def program_link(root, code, fiscal_year, title=None, account=None):
    """사업설명자료 색인(budget.sqlite)에서 같은 코드의 사업을 읽기 전용으로 찾는다.

    사업 코드는 회계가 다르면 중복된다(2027년 과기정통부 자료에서 36개 코드가 서로 다른 사업에 쓰임).
    그래서 코드가 같아도 제목이 맞는 사업만 연결하고, 맞지 않으면 연결하지 않은 채 후보를 따로 보여 준다.
    """
    if not code:
        return {'linked': False, 'reason': '코드 없는 항목(총괄 주제 등)'}
    db = root / '.budget-index/budget.sqlite'
    if not db.exists():
        return {'linked': False, 'reason': '사업설명자료 색인(budget.sqlite)이 없음: budget_core.py build를 먼저 실행'}
    try:
        con = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
        con.row_factory = sqlite3.Row
        manifest = json.loads(con.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()[0])
        rows = [json.loads(r[0]) for r in con.execute("SELECT payload FROM programs WHERE kind='program' AND code=?", (code,))]
        con.close()
    except (sqlite3.Error, KeyError, ValueError) as exc:
        return {'linked': False, 'reason': f'사업설명자료 색인을 읽지 못함: {exc}'}
    year = manifest.get('config', {}).get('fiscal_year')
    if year != fiscal_year:
        return {'linked': False, 'reason': f'회계연도가 다름 (사업설명자료 {year}, 검토보고서 {fiscal_year})'}
    if not rows:
        return {'linked': False, 'reason': '사업설명자료 색인에 같은 코드가 없음 (세입 항목이거나 다른 판본일 수 있음)'}
    keys = ('uid', 'id', 'title', 'code', 'volume', 'account', 'source', 'source_start_line', 'source_end_line', 'toc_printed_page')
    candidates = []
    for r in rows:
        item = {k: r.get(k) for k in keys}
        item['match'] = _title_match(title, r.get('title', '')) if title else None
        item['account_agrees'] = None if not account else (norm(account) in norm(r.get('account', '')) or norm(r.get('account', '')) in norm(account))
        candidates.append(item)
    if title:
        matched = [c for c in candidates if c['match']]
        order = {'title_exact': 0, 'title_contains': 1, 'title_similar': 2}
        matched.sort(key=lambda c: (order[c['match']], c['account_agrees'] is False))
        others = [c for c in candidates if not c['match']]
        if not matched:
            return {'linked': False, 'reason': '같은 코드의 사업은 있으나 제목이 맞지 않음 (회계가 다른 사업이 같은 코드를 쓰는 경우가 있어 연결하지 않음)',
                    'code_only_candidates': candidates, 'edition': manifest['config']['edition']}
        out = {'linked': True, 'edition': manifest['config']['edition'], 'programs': matched}
        if others:
            out['same_code_other_programs'] = others  # 코드만 같은 다른 사업: 연결 대상이 아님
        if any(c['account_agrees'] is False for c in matched):
            out['note'] = '제목은 맞으나 회계 표기가 다름: 원문으로 확인'
        return out
    return {'linked': True, 'edition': manifest['config']['edition'], 'programs': candidates,
            'note': '제목 없이 코드로만 찾음: 코드가 같은 다른 사업이 섞여 있을 수 있음'}


def unit_link(root, r):
    """검토보고서 사업 1개(여러 코드가 한 머리글에 묶인 경우 포함)를 사업설명자료와 연결한다."""
    codes = r.get('codes') or ([r['code']] if r.get('code') else [])
    if not codes:
        return {'linked': False, 'reason': '코드 없는 항목(총괄 주제 등)'}
    links = [program_link(root, c, r['fiscal_year'], r['title'], r.get('account')) for c in codes]
    if len(links) == 1:
        return links[0]
    ok = [l for l in links if l['linked']]
    if not ok:
        return links[0]
    programs = [p for l in ok for p in l['programs']]
    out = {'linked': True, 'edition': ok[0]['edition'], 'programs': programs}
    unmatched = [c for c, l in zip(codes, links) if not l['linked']]
    if unmatched:
        out['unmatched_codes'] = unmatched
    return out


def groups_for(query, phrase=False, expand=False):
    groups = []
    for term in ([query] if phrase else query.split()):
        terms = [term]
        if expand:
            for key, values in ALIASES.items():
                if norm(term) == norm(key):
                    terms += values
        groups.append(terms)
    return groups


def validate_plan(plan):
    allowed = {'question', 'must', 'should', 'exclude', 'filters', 'expand'}
    if set(plan) - allowed:
        fail('Unknown query plan keys')
    for name in ('must', 'should', 'exclude'):
        for group in plan.get(name, []):
            if not isinstance(group, list) or not group or any(not isinstance(t, str) or not norm(t) for t in group):
                fail('Each term group needs nonempty strings')
    f = plan.get('filters', {})
    if set(f) - {'code', 'id', 'dept', 'account', 'scope', 'issue'}:
        fail('Unsupported query filter')
    if f.get('scope', 'units') not in {'units', 'contexts', 'all'}:
        fail('Invalid scope')
    if not plan.get('must') and not plan.get('should') and not f:
        fail('Empty query')
    return plan


def search(root, plan, limit=20):
    validate_plan(plan)
    if limit < 0:
        fail('limit must be nonnegative')
    con, m = connect(root)
    try:
        f = plan.get('filters', {})
        terms = {name: [[norm(t) for t in group] for group in plan.get(name, [])] for name in ('must', 'should', 'exclude')}
        if plan.get('expand'):
            for groups in terms.values():
                for group in groups:
                    for key, values in ALIASES.items():
                        if norm(key) in group:
                            group.extend(norm(v) for v in values)
        clauses, params = [], []
        scope = f.get('scope', 'units')
        if scope != 'all':
            clauses.append('kind=?')
            params.append('unit' if scope == 'units' else 'context')
        if f.get('code'):
            clauses.append('(code=? OR instr(codes,?)>0)')
            params.extend([f['code'], f['code']])
        if f.get('id'):
            clauses.append('(uid=? OR legacy_id=?)')
            params.extend([f['id'], f['id']])
        if f.get('dept'):
            clauses.append('instr(dept_key,?)>0')
            params.append(norm(f['dept']))
        if f.get('account'):
            clauses.append('instr(account_key,?)>0')
            params.append(norm(f['account']))
        for group in terms['must']:
            clauses.append('(' + ' OR '.join('(instr(title_key,?)>0 OR instr(body_key,?)>0)' for _ in group) + ')')
            params.extend(t for term in group for t in (term, term))
        for group in terms['exclude']:
            clauses.append('NOT (' + ' OR '.join('(instr(title_key,?)>0 OR instr(body_key,?)>0)' for _ in group) + ')')
            params.extend(t for term in group for t in (term, term))
        rows = con.execute('SELECT uid,title_key,payload FROM units' + (' WHERE ' + ' AND '.join(clauses) if clauses else ''), params).fetchall()
        groups = terms['must'] + terms['should']
        total_units = m['unit_count'] + m['context_count']
        idfs = []
        for group in groups:
            sql = 'SELECT count(*) FROM units WHERE ' + ' OR '.join('instr(body_key,?)>0 OR instr(title_key,?)>0' for _ in group)
            count = con.execute(sql, [t for term in group for t in (term, term)]).fetchone()[0]
            idfs.append(1 + math.log((1 + total_units) / (1 + count)))
        hits = []
        for row in rows:
            r = json.loads(row['payload'])
            bs = con.execute('SELECT * FROM blocks WHERE uid=?', (row['uid'],)).fetchall()
            if f.get('issue'):
                bs = [b for b in bs if norm(f['issue']) in norm(b['section']) or f['issue'] == b['issue_label']]
            scored = []
            for b in bs:
                matched = [i for i, g in enumerate(groups) if any(t in b['key'] for t in g)]
                if matched or not groups:
                    value = sum(idfs[i] for i in matched) * b['weight']
                    if groups and len(matched) == len(groups):
                        value += sum(idfs) * 2
                    scored.append((value, b))
            if not scored:
                if terms['should'] and not any(any(t in row['title_key'] for t in g) for g in groups):
                    continue
                if not bs:
                    continue
                scored = [(0, bs[0])]
            scored.sort(key=lambda x: (-x[0], x[1]['start_line']))
            best, block = scored[0]
            score = best + sum(idfs[i] * 4 for i, g in enumerate(groups) if any(t in row['title_key'] for t in g))
            if len(groups) == 1 and row['title_key'] in groups[0]:
                score += 10000
            if f.get('code') or f.get('id'):
                score += 10000
            pos = 0
            for g in groups:
                found = False
                for term in g:
                    mt = re.search(r'[\W_]*'.join(re.escape(c) for c in term), unicodedata.normalize('NFKC', block['text']), re.I)
                    if mt:
                        pos = max(0, mt.start() - 80)
                        found = True
                        break
                if found:
                    break
            excerpt = re.sub(r'\s+', ' ', block['text'][pos:pos + 480])
            matched_sections = []
            seen = set()
            for value, b in scored:
                if b['section'] not in seen and value > 0:
                    seen.add(b['section'])
                    matched_sections.append({'section': b['section'], 'start_line': b['start_line']})
                if len(matched_sections) == 4:
                    break
            hit = {k: r.get(k) for k in ('uid', 'id', 'kind', 'title', 'code', 'codes', 'dept', 'account', 'fiscal_year', 'committee', 'edition', 'source', 'source_sha256')}
            hit.update(score=round(score, 4), section=block['section'], match_start_line=block['start_line'], match_end_line=block['end_line'],
                       excerpt=excerpt, is_table=bool(block['is_table']), table_caption=block['caption'], table_unit=block['unit_raw'],
                       excerpt_is_complete=len(block['text']) <= 480 and pos == 0, matched_sections=matched_sections,
                       issue_titles=[f"{i['label']}) {i['title']}" for i in r.get('issues', [])])
            hits.append(hit)
        hits.sort(key=lambda h: (-h['score'], h['match_start_line'], h['uid']))
        shown = hits if limit == 0 else hits[:limit]
        for h in shown:
            h['program_link'] = unit_link(root, h) if h['kind'] == 'unit' else None
        return {'total': len(hits), 'shown': len(shown), 'results': shown, 'query_plan': plan,
                'corpus': {'units': m['unit_count'], 'issues': m['issue_count'], 'edition': m['config']['edition'], 'committee': m['config']['committee']}}
    finally:
        con.close()


def show(root, identity, issue=None):
    con, m = connect(root)
    try:
        rows = con.execute('SELECT payload FROM units WHERE uid=? OR legacy_id=?', (identity, identity)).fetchall()
        if not rows and CODE_RE.fullmatch(identity):
            rows = con.execute('SELECT payload FROM units WHERE kind="unit" AND (code=? OR instr(codes,?)>0)', (identity, identity)).fetchall()
        if not rows:
            fail('Unknown identity')
        if len(rows) > 1:
            fail('Ambiguous identity; use UID/ID: ' + ', '.join(json.loads(r[0])['id'] for r in rows))
        r = json.loads(rows[0][0])
        lines = local(root, r['source']).read_text(encoding='utf-8').splitlines()
        segments = [{'title': '전체', 'start_line': r['start_line'], 'end_line': r['end_line']}]
        if issue:
            wanted = [i for i in r.get('issues', []) if issue == i['label'] or norm(issue) in norm(i['title'])]
            if not wanted:
                fail('No such issue; available: ' + ', '.join(f"{i['label']}) {i['title']}" for i in r.get('issues', [])))
            segments = [{'title': f"{i['label']}) {i['title']}", 'start_line': i['start_line'], 'end_line': i['end_line']} for i in wanted]
        tables = [dict(caption=b['caption'], unit=b['unit_raw'], section=b['section'], start_line=b['start_line'], end_line=b['end_line'])
                  for b in con.execute('SELECT * FROM blocks WHERE uid=? AND is_table=1 ORDER BY start_line', (r['uid'],))
                  if any(s['start_line'] <= b['start_line'] <= s['end_line'] for s in segments)]
        link = unit_link(root, r) if r['kind'] == 'unit' else None
        return {'record': r, 'segments': [dict(s, raw='\n'.join(lines[s['start_line'] - 1:s['end_line']])) for s in segments],
                'tables': tables, 'program_link': link}
    finally:
        con.close()


def verify(root):
    con, m = connect(root)
    try:
        if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            fail('SQLite integrity failure')
        if m['toc_check']['errors']:
            fail('manifest에 목차 대조 오류가 남아 있음')
        lines = local(root, m['source']['path']).read_text(encoding='utf-8').splitlines()
        total = len(lines)
        seen_ids = set()
        problems = []
        for row in con.execute('SELECT payload FROM units'):
            r = json.loads(row[0])
            if r['id'] in seen_ids:
                problems.append(f"중복 ID {r['id']}")
            seen_ids.add(r['id'])
            if not 1 <= r['start_line'] <= r['end_line'] <= total:
                problems.append(f"{r['id']}: 행 범위 밖")
            prev_end = r['start_line'] - 1
            for i in r.get('issues', []):
                if not r['start_line'] <= i['start_line'] <= i['end_line'] <= r['end_line'] or i['start_line'] <= prev_end:
                    problems.append(f"{r['id']} {i['label']}): 쟁점 범위 이상")
                prev_end = i['end_line']
        for b in con.execute('SELECT b.uid, b.start_line, b.end_line, u.payload FROM blocks b JOIN units u ON u.uid=b.uid'):
            r = json.loads(b['payload'])
            if not r['start_line'] <= b['start_line'] <= b['end_line'] <= r['end_line']:
                problems.append(f"{r['id']}: 블록 {b['start_line']}-{b['end_line']} 범위 밖")
        if problems:
            fail('검증 실패: ' + '; '.join(problems[:10]))
        return {'ok': True, 'runtime_version': VERSION, 'units': m['unit_count'], 'issues': m['issue_count'], 'contexts': m['context_count'],
                'source_sha256': m['source']['sha256'], 'toc_warnings': len(m['toc_check']['warnings']),
                'scope': '색인 경계·해시·행 범위 검사. 쟁점·표의 의미나 금액의 정확성은 원문 표와 대조해야 한다.'}
    finally:
        con.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path.cwd())
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('build')
    q = sub.add_parser('search')
    q.add_argument('query', nargs='*')
    q.add_argument('--phrase', action='store_true')
    q.add_argument('--expand', action='store_true')
    q.add_argument('--plan', type=Path)
    q.add_argument('--limit', type=int, default=20)
    for name in ('code', 'id', 'dept', 'account', 'issue'):
        q.add_argument('--' + name)
    q.add_argument('--scope', choices=['units', 'contexts', 'all'], default='units')
    q = sub.add_parser('show')
    q.add_argument('id', help='UID, ID 또는 사업 코드')
    q.add_argument('--issue', help='쟁점 라벨(나) 또는 제목 일부')
    sub.add_parser('verify')
    a = p.parse_args()
    root = a.root.resolve()
    try:
        if a.command == 'build':
            result = build(root)
        elif a.command == 'verify':
            result = verify(root)
        elif a.command == 'show':
            result = show(root, a.id, a.issue)
        else:
            query = ' '.join(a.query).strip()
            if a.plan:
                plan = read_json(a.plan)
            else:
                filters = {k: getattr(a, k) for k in ('code', 'id', 'dept', 'account', 'issue') if getattr(a, k)}
                if a.scope != 'units':
                    filters['scope'] = a.scope
                if CODE_RE.fullmatch(query):
                    filters['code'] = query
                    query = ''
                plan = {'must': groups_for(query, a.phrase, a.expand) if query else [], 'filters': filters}
            result = search(root, plan, a.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, AssertionError, sqlite3.Error, KeyError) as exc:
        print(f'오류: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
