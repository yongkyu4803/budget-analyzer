#!/usr/bin/env python3
"""Budget corpus v3: local, edition-aware indexing and retrieval; Python stdlib."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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

VERSION = '1.0.0'
SCHEMA = 3
STAGES = {'government_proposal', 'approved', 'supplementary', 'request', 'adjusted_proposal', 'settlement', 'unknown'}
UNITS = {'원': Decimal(1), '천원': Decimal(1000), '백만원': Decimal(1000000), '억원': Decimal(100000000)}
STATES = {'value', 'zero', 'dash', 'blank', 'not_checked', 'not_reported', 'not_applicable'}
ROLES = ('beneficiaries', 'eligibility', 'implementer', 'buyer', 'funding_method', 'subprograms')
ALIASES = {
    'NIPA': ['정보통신산업진흥원'], 'IITP': ['정보통신기획평가원'],
    'HPC': ['초고성능컴퓨팅'], 'AIDC': ['AI 데이터센터', '인공지능 데이터센터'],
    'GPUaaS': ['GPU 임차', 'GPU 임대', '클라우드 이용료', '컴퓨팅 자원 지원'],
    '피지컬AI': ['Physical AI', '피지컬 인공지능'],
}


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
    return json.loads(Path(path).read_text(encoding='utf-8'))


def norm(text):
    # Original text is never rewritten. Search-only folding handles NFD and middle dots.
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def local(root, path):
    p = Path(path)
    if p.is_absolute() or '..' in p.parts:
        fail(f'Workspace-relative path required: {path}')
    result = (root / p).resolve()
    if not result.is_relative_to(root.resolve()):
        fail(f'Path escapes workspace: {path}')
    return result


def config_at(root):
    c = read_json(root / '.budget-index/config.json')
    if c.get('schema_version') != SCHEMA:
        fail('Unsupported config schema')
    for key in ('ministry', 'ministry_id', 'fiscal_year', 'edition'):
        if not c.get(key): fail(f'Missing configuration: {key}')
    if not isinstance(c['fiscal_year'], int): fail('fiscal_year must be integer')
    if c['edition'].get('stage') not in STAGES: fail('Unknown edition stage')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', c['edition'].get('id', '')): fail('Invalid edition ID')
    return c


def record_uid(record, config):
    return f"{record['id']}@{config['edition']['id']}@{record['source_sha256'][:16]}"


def verify_evidence(e, r, root, lines_cache):
    for k in ('path', 'sha256', 'start_line', 'end_line', 'quote'):
        if k not in e: fail(f'Missing evidence {k}')
    if e['path'] != r['source'] or e['sha256'] != r['source_sha256']:
        fail('Evidence source/hash differs from record')
    start, end = e['start_line'], e['end_line']
    if type(start) is not int or type(end) is not int or not r['source_start_line'] <= start <= end <= r['source_end_line']:
        fail('Evidence lines outside business boundary')
    if e['path'] not in lines_cache:
        lines_cache[e['path']] = local(root, e['path']).read_text(encoding='utf-8').splitlines()
    raw = '\n'.join(lines_cache[e['path']][start-1:end])
    if not e['quote'] or e['quote'] not in raw:
        fail('Evidence quote does not occur verbatim at stated lines')
    return raw


def validate_amount(a, r, root, cache):
    state = a.get('state')
    if state not in STATES: fail('Unknown amount state')
    if a.get('stage') not in STAGES: fail('Unknown amount stage')
    if type(a.get('year')) is not int: fail('Amount year missing')
    if a.get('verification') not in {'not_checked', 'source_checked'}: fail('Unknown verification')
    raw = a.get('raw')
    value = a.get('value')
    if state in {'value', 'zero'}:
        if a.get('unit') not in UNITS: fail('Amount unit unsupported')
        if not isinstance(raw, str) or not re.fullmatch(r'[+-]?\d[\d,]*(?:\.\d+)?', raw.strip()): fail('Non-numeric raw amount')
        if not isinstance(value, str): fail('Decimal value must be a string')
        try:
            parsed = Decimal(raw.replace(',', '').strip())
            numeric = Decimal(value)
        except InvalidOperation:
            fail('Invalid decimal')
        if not numeric.is_finite() or parsed != numeric: fail('Raw/parsed amount disagree')
        if (state == 'zero') != (numeric == 0): fail('Zero must have its own state')
    elif value is not None:
        fail('Missing/dash amount cannot have a numeric value')
    if state == 'dash' and raw not in {'-', '–', '—', '―'}: fail('Dash state differs from raw')
    if state == 'blank' and raw != '': fail('Blank state differs from raw')
    if a['verification'] == 'source_checked':
        if state in {'not_checked', 'not_reported'}: fail('Absence cannot be proved by a quoted number')
        raw_evidence = verify_evidence(a['evidence'], r, root, cache)
        for k in ('column_label', 'unit_raw'):
            if not a.get(k) or a[k] not in raw_evidence: fail(f'Missing budget header evidence: {k}')
        if raw and raw not in raw_evidence: fail('Amount missing from evidence')
        if str(a['year']) not in raw_evidence: fail('Amount year missing from table')
        label = norm(a['column_label'])
        expected_stage = next((stage for key,stage in [('조정안','adjusted_proposal'),('요구안','request'),('본예산','approved'),('당초','approved'),('추경','supplementary'),('결산','settlement')] if key in label), None)
        if expected_stage and a['stage'] != expected_stage:
            fail('Column label and amount stage disagree')
    return True


def validate_facts(facts, records, config, root):
    lookup = {record_uid(r, config): r for r in records}
    cache, seen = {}, set()
    for f in facts:
        if f.get('schema_version') != SCHEMA: fail('Unsupported facts schema')
        uid = f.get('uid')
        if uid in seen: fail('Duplicate facts UID')
        seen.add(uid)
        if uid not in lookup: fail('Facts belong to another source version; recheck before carrying forward')
        r = lookup[uid]
        if f.get('edition') != config['edition']['id']: fail('Facts edition mismatch')
        for a in f.get('amounts', []): validate_amount(a, r, root, cache)
        for name, field in f.get('fields', {}).items():
            if name not in ROLES + ('purpose',): fail(f'Unknown structured field: {name}')
            if field.get('state') not in STATES: fail('Unknown field state')
            if field['state'] == 'value':
                if not field.get('raw'): fail('Empty value field')
                raw = verify_evidence(field['evidence'], r, root, cache)
                if field['raw'] not in raw: fail('Field raw text not in evidence')
    return {f['uid']: f for f in facts}


def section_weight(section):
    if '사업목적' in section: return 3.0
    if '산출' in section: return 2.2
    if '사업개요' in section or '수혜자' in section: return 1.8
    if '담당자' in section or '식별' in section: return 0.2
    if '결산' in section or '지적' in section: return 0.6
    return 1.0


def build(root):
    from msit_adapter import parse
    config = config_at(root)
    if config.get('adapter') != 'msit-repeated-toc': fail('No validated adapter for this layout')
    records, sources, differences = parse(root, config)
    # Source is parsed afresh; never consume the previous search cache as authority.
    facts_path = root / '.budget-index/facts.json'
    facts = read_json(facts_path) if facts_path.exists() else []
    by_uid = validate_facts(facts, records, config, root)
    inputs = [{ 'path': '.budget-index/config.json', 'sha256': sha(root / '.budget-index/config.json')}]
    if facts_path.exists(): inputs.append({'path': '.budget-index/facts.json', 'sha256': sha(facts_path)})
    notes = set()
    originals = {}
    for source in sources:
        p = local(root, source['path'])
        candidate = root / p.with_suffix('.hwpx').name
        if candidate.is_file(): originals[source['path']] = {'path': candidate.name, 'sha256': sha(candidate)}
    data = root / '.budget-index'
    data.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=data, suffix='.sqlite', delete=False) as tmp: temp_path = Path(tmp.name)
    try:
        con = sqlite3.connect(temp_path)
        con.executescript('''
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE programs(uid TEXT PRIMARY KEY, legacy_id TEXT, kind TEXT, code TEXT, volume INTEGER, account TEXT, title_key TEXT, body_key TEXT, payload TEXT);
            CREATE INDEX lookup_id ON programs(legacy_id);
            CREATE INDEX lookup_code ON programs(code);
            CREATE TABLE blocks(uid TEXT, start_line INTEGER, end_line INTEGER, section TEXT, weight REAL, is_table INTEGER, key TEXT, text TEXT);
            CREATE INDEX block_uid ON blocks(uid);
        ''')
        for r in records:
            uid = record_uid(r, config)
            blocks = r['blocks']
            metadata = {k:v for k,v in r.items() if k != 'blocks'}
            if not local(root, r['fragment']).exists(): metadata['fragment'] = None
            metadata.update(uid=uid, schema_version=SCHEMA, ministry=config['ministry'], ministry_id=config['ministry_id'],
                            fiscal_year=config['fiscal_year'], edition=config['edition'], original=originals.get(r['source']),
                            review_status='source_location_checked', facts=by_uid.get(uid))
            if r.get('curated_index'):
                path = r['curated_index']; notes.add(path)
                text = local(root,path).read_text(encoding='utf-8')
                m = re.search(r'^source-reverified-at:\s*(\S+)',text,re.M)
                metadata['curated_source_reverified_at'] = None if not m or m[1]=='null' else m[1]
            title_key = norm(r['title'])
            body_key = '\n'.join(norm(b['text']) for b in blocks)
            con.execute('INSERT INTO programs VALUES(?,?,?,?,?,?,?,?,?)', (uid,r['id'],r['kind'],r['code'],r['volume'],norm(r['account']),title_key,body_key,dumps(metadata)))
            con.executemany('INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?)', [(uid,b['start_line'],b['end_line'],b['section'],section_weight(b['section']),int(b['table']),norm(b['text']),b['text']) for b in blocks])
        inputs += [{'path':p, 'sha256':sha(local(root,p))} for p in sorted(notes)]
        manifest = {'runtime_version':VERSION,'schema_version':SCHEMA,'built_at':datetime.now(timezone.utc).isoformat(),
                    'config':config,'sources':sources,'inputs':inputs,'originals':list(originals.values()),
                    'program_count':sum(r['kind']=='program' for r in records),'context_count':sum(r['kind']=='context' for r in records),
                    'curated_count':len(notes),'structured_count':len(facts),'toc_differences':differences}
        con.execute('INSERT INTO meta VALUES(?,?)',('manifest',dumps(manifest)))
        con.commit(); con.close()
        # Single-file commit prevents mixing a new manifest with an old database.
        temp_path.replace(data/'budget.sqlite')
    finally:
        temp_path.unlink(missing_ok=True)
    catalog = ['# 예산사업 전체 목록', '', f"{config['ministry']} · {config['fiscal_year']} · {config['edition']['stage']} · {config['edition']['id']}", '', '| 사업명 | 코드 | 회계·기금 | 권 | 원문 |', '|---|---|---|---|---|']
    for r in records:
        if r['kind']=='program': catalog.append(f"| {r['title']} | {r['code']} | {r['account']} | {r['volume']} | [{r['source_start_line']}행](../{quote(r['source'])}) |")
    (data/'CATALOG.md').write_text('\n'.join(catalog)+'\n',encoding='utf-8')
    return {k:manifest[k] for k in ('program_count','context_count','curated_count','structured_count','built_at')}


def connect(root, check=True):
    db = root / '.budget-index/budget.sqlite'
    if not db.exists(): fail('Run build first; .budget-index/budget.sqlite missing')
    con = sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    manifest = json.loads(con.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()[0])
    if manifest['schema_version'] != SCHEMA or manifest['runtime_version'] != VERSION:
        con.close(); fail('Cache/runtime version mismatch; rebuild')
    if check:
        facts_present = any(s['path']=='.budget-index/facts.json' for s in manifest['inputs'])
        if (root/'.budget-index/facts.json').exists() != facts_present:
            con.close(); fail('Facts file added/removed; rebuild')
        for source in manifest['sources'] + manifest['inputs']:
            p = local(root,source['path'])
            if not p.is_file() or sha(p) != source['sha256']:
                con.close(); fail(f"Stale or missing input: {source['path']}; recheck facts and rebuild")
    return con, manifest


def groups_for(query, phrase=False, expand=False):
    groups=[]
    for term in ([query] if phrase else query.split()):
        terms=[term]
        if expand:
            for key, values in ALIASES.items():
                if norm(term)==norm(key): terms+=values
        groups.append(terms)
    return groups


def validate_plan(plan):
    allowed={'question','must','should','exclude','filters','amount','expand'}
    if set(plan)-allowed: fail('Unknown query plan keys')
    for name in ('must','should','exclude'):
        for group in plan.get(name,[]):
            if not isinstance(group,list) or not group or any(not isinstance(t,str) or not norm(t) for t in group): fail('Each term group needs nonempty strings')
    f=plan.get('filters',{})
    if set(f)-{'code','id','volume','account','year','stage','ministry','scope'}: fail('Unsupported query filter')
    if f.get('scope','programs') not in {'programs','context','all'}: fail('Invalid scope')
    if f.get('stage') and f['stage'] not in STAGES: fail('Invalid stage')
    if not plan.get('must') and not plan.get('should') and not f and not plan.get('amount'): fail('Empty query')
    amount=plan.get('amount')
    if amount:
        if set(amount)-{'year','stage','unit','min','max','label'}: fail('Unsupported amount filter')
        if type(amount.get('year')) is not int or amount.get('stage') not in STAGES or amount.get('unit') not in UNITS: fail('Numeric filter requires year, stage, unit')
        if not ('min' in amount or 'max' in amount): fail('Amount min/max required')
        try:
            if any(not Decimal(str(amount[k])).is_finite() for k in ('min','max') if k in amount): fail('Non-finite threshold')
        except InvalidOperation: fail('Invalid threshold')
    return plan


def amount_matches(record, condition):
    amounts=(record.get('facts') or {}).get('amounts',[])
    comparable=[a for a in amounts if a['year']==condition['year'] and a['stage']==condition['stage'] and a['state'] in {'value','zero'} and a['verification']=='source_checked' and (not condition.get('label') or a.get('label')==condition['label'])]
    if not comparable: return None
    for a in comparable:
        value=Decimal(a['value'])*UNITS[a['unit']]/UNITS[condition['unit']]
        if all(value >= Decimal(str(condition[k])) if k=='min' else value <= Decimal(str(condition[k])) for k in ('min','max') if k in condition): return True
    return False


def search(root, plan, limit=20):
    validate_plan(plan)
    if limit < 0: fail('limit must be nonnegative')
    con,m=connect(root)
    try:
        f=plan.get('filters',{})
        if (f.get('year') and f['year']!=m['config']['fiscal_year']) or (f.get('stage') and f['stage']!=m['config']['edition']['stage']) or (f.get('ministry') and norm(f['ministry']) not in {norm(m['config']['ministry']),norm(m['config']['ministry_id'])}):
            return {'total':0,'results':[],'reason':'Requested edition outside selected corpus','corpus':m['config']}
        terms={name:[[norm(t) for t in group] for group in plan.get(name,[])] for name in ('must','should','exclude')}
        if plan.get('expand'):
            for groups in terms.values():
                for group in groups:
                    for key,values in ALIASES.items():
                        if norm(key) in group: group.extend(norm(v) for v in values)
        clauses,params=[],[]
        scope=f.get('scope','programs')
        if scope!='all': clauses.append('kind=?');params.append('program' if scope=='programs' else 'context')
        for name in ('code','volume'):
            if f.get(name) is not None: clauses.append(name+'=?');params.append(f[name])
        if f.get('id'): clauses.append('(uid=? OR legacy_id=?)');params.extend([f['id'],f['id']])
        if f.get('account'): clauses.append('instr(account,?)>0');params.append(norm(f['account']))
        for group in terms['must']:
            clauses.append('('+' OR '.join('(instr(title_key,?)>0 OR instr(body_key,?)>0)' for t in group)+')')
            params.extend(t for term in group for t in (term,term))
        for group in terms['exclude']:
            clauses.append('NOT ('+' OR '.join('(instr(title_key,?)>0 OR instr(body_key,?)>0)' for t in group)+')')
            params.extend(t for term in group for t in (term,term))
        rows=con.execute('SELECT uid,title_key,payload FROM programs'+(' WHERE '+' AND '.join(clauses) if clauses else ''),params).fetchall()
        groups=terms['must']+terms['should']
        # Corpus-level rarity avoids repeating generic administrative words dominating rank.
        idfs=[]
        for group in groups:
            sql='SELECT count(*) FROM programs WHERE kind="program" AND ('+' OR '.join('instr(body_key,?)>0 OR instr(title_key,?)>0' for t in group)+')'
            count=con.execute(sql,[t for term in group for t in (term,term)]).fetchone()[0]
            idfs.append(1+math.log((1+m['program_count'])/(1+count)))
        hits,unknown=[],[]
        for row in rows:
            r=json.loads(row['payload'])
            if plan.get('amount'):
                match=amount_matches(r,plan['amount'])
                if match is None: unknown.append({'id':r['id'],'uid':r['uid'],'title':r['title']});continue
                if not match: continue
            bs=con.execute('SELECT * FROM blocks WHERE uid=?',(row['uid'],)).fetchall()
            scored=[]
            for b in bs:
                matched=[i for i,g in enumerate(groups) if any(t in b['key'] for t in g)]
                if matched or not groups:
                    value=sum(idfs[i] for i in matched)*b['weight']
                    # Prefer compact evidence which covers the whole request.
                    if groups and len(matched)==len(groups): value+=sum(idfs)*2
                    scored.append((value,b,len(matched)))
            if not scored:
                if terms['should'] and not any(any(t in row['title_key'] for t in g) for g in groups): continue
                scored=[(0,bs[0],0)]
            scored.sort(key=lambda b:(-b[0], b[1]['start_line']))
            best,block,_=scored[0]
            score=best+sum(idfs[i]*4 for i,g in enumerate(groups) if any(t in row['title_key'] for t in g))
            if len(groups)==1 and row['title_key'] in groups[0]: score+=10000
            if f.get('code') or f.get('id'): score+=10000
            pos=0
            for g in groups:
                found=False
                for term in g:
                    mt=re.search(r'[\W_]*'.join(re.escape(c) for c in term),unicodedata.normalize('NFKC',block['text']),re.I)
                    if mt: pos=max(0,mt.start()-80);found=True;break
                if found: break
            excerpt=re.sub(r'\s+',' ',block['text'][pos:pos+480])
            keys=('uid','id','title','code','volume','account','fiscal_year','ministry','edition','source','source_sha256','toc_printed_page','curated_index','curated_source_reverified_at')
            hit={k:r.get(k) for k in keys}
            hit.update(score=round(score,4),section=block['section'],match_start_line=block['start_line'],match_end_line=block['end_line'],excerpt=excerpt,is_table=bool(block['is_table']),excerpt_is_complete=len(block['text'])<=480 and pos==0)
            hits.append(hit)
        hits.sort(key=lambda h:(-h['score'],h['volume'],h['match_start_line'],h['uid']))
        return {'total':len(hits),'shown':len(hits if limit==0 else hits[:limit]),'results':hits if limit==0 else hits[:limit],
                'amount_unknown_count':len(unknown),'amount_unknown':unknown,'query_plan':plan,
                'corpus':{'programs':m['program_count'],'structured':m['structured_count'],'edition':m['config']['edition']}}
    finally:
        con.close()


def show(root, identity, section=None):
    con,m=connect(root)
    try:
        rows=con.execute('SELECT payload FROM programs WHERE uid=? OR legacy_id=?',(identity,identity)).fetchall()
        if len(rows)!=1: fail('Unknown or ambiguous identity; supply UID with edition and hash')
        r=json.loads(rows[0][0])
        segments=[{'start_line':r['source_start_line'],'end_line':r['source_end_line'],'title':'본문'}]
        if section:
            segments=[s for s in r['sections'] if norm(section) in norm(s['anchor']+' '+s['title']+' '+s['label'])]
            if not segments: fail('No such section; available: '+', '.join(s['anchor'] for s in r['sections']))
        lines=local(root,r['source']).read_text(encoding='utf-8').splitlines()
        return {'record':r,'segments':[dict(s,raw='\n'.join(lines[s['start_line']-1:s['end_line']])) for s in segments]}
    finally: con.close()


def verify(root, originals=False):
    con,m=connect(root)
    try:
        if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok': fail('SQLite integrity failure')
        if originals:
            for src in m['originals']:
                p=local(root,src['path'])
                if not p.is_file() or sha(p)!=src['sha256']: fail('Original file changed/missing: '+src['path'])
        records=[json.loads(row[0]) for row in con.execute('SELECT payload FROM programs')]
        validate_facts([r['facts'] for r in records if r.get('facts')], records, m['config'], root)
        return {'ok':True,'runtime_version':VERSION,'programs':m['program_count'],'structured':m['structured_count'],'originals_checked':originals,'original_count':len(m['originals'])}
    finally: con.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path.cwd())
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('build')
    q=sub.add_parser('search');q.add_argument('query',nargs='*');q.add_argument('--phrase',action='store_true');q.add_argument('--expand',action='store_true');q.add_argument('--plan',type=Path);q.add_argument('--limit',type=int,default=20)
    for name in ('code','id','account','stage','ministry'):q.add_argument('--'+name)
    for name in ('volume','year'):q.add_argument('--'+name,type=int)
    q.add_argument('--scope',choices=['programs','context','all'],default='programs')
    q=sub.add_parser('show');q.add_argument('id');q.add_argument('--section')
    q=sub.add_parser('verify');q.add_argument('--originals',action='store_true')
    a=p.parse_args();root=a.root.resolve()
    try:
        if a.command=='build': result=build(root)
        elif a.command=='verify': result=verify(root,a.originals)
        elif a.command=='show': result=show(root,a.id,a.section)
        else:
            query=' '.join(a.query).strip()
            if a.plan: plan=read_json(a.plan)
            else:
                filters={k:getattr(a,k) for k in ('code','id','account','stage','ministry','volume','year') if getattr(a,k) is not None}
                if a.scope!='programs': filters['scope']=a.scope
                if re.fullmatch(r'\d{4}-\d{3}',query): filters['code']=query;query=''
                plan={'must':groups_for(query,a.phrase,a.expand),'filters':filters}
            result=search(root,plan,a.limit)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,AssertionError,sqlite3.Error,KeyError) as exc:
        print(f'오류: {exc}',file=sys.stderr);sys.exit(1)


if __name__=='__main__': main()
