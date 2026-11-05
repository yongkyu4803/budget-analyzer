"""검토보고서 색인(review_core) 시험. 합성 자료만 쓴다.

기본은 이 키트의 windows/skills/budget-index/scripts. 다른 위치를 시험하려면 환경변수 BUDGET_SCRIPTS에 폴더를 지정한다.
  python -X utf8 -B developer/test_review.py
  BUDGET_SCRIPTS=/path/to/mac/budget-index/scripts python3 windows/developer/test_review.py
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

SCRIPTS = Path(os.environ.get('BUDGET_SCRIPTS') or Path(__file__).resolve().parents[1] / 'skills/budget-index/scripts')
sys.path.insert(0, str(SCRIPTS))
import budget_core as b  # noqa: E402
import review_core as rc  # noqa: E402

REVIEW = '''표지

## 목 차

Ⅰ. 시험부 소관 예산안 개관\t 1

1. 총 괄\t 1

2. 일반회계\t 3

Ⅱ. 검토의견\t 5

1. 총 괄\t 5

(1) 연구개발 예산 과다 편성\t 6

가) 사업 및 예산안 개요\t 6

2. 가상정책관 소관\t 9

【일반회계】\t 11

(1) GPU 임차 지원(1111-111)\t 11

가) 사업 및 예산안 개요\t 11

나) 임차 단가 적정성 검토 필요\t 12

【방송통신발전기금】\t 14

(2) NPU 구매 지원(2222-222)\t 14

가) 사업 및 계획안 개요\t 14

Ⅰ. 2031년도 시험부 소관 예산안 개관

1. 총 괄

총괄 설명이다.

2. 일반회계

일반회계 설명이다.

Ⅱ. 검토의견

총 괄

![image](image_002.jpg)

문의처

1234

(1) 연구개발 예산 과다 편성

◦ 시험부는 지원개월 수를 반영할 필요가 있음.

가) 사업 및 예산안 개요

○ 연구개발 예산 개요이다.

가
상정책관

소관

![image](image_002.jpg)

문의처

5678

【 일반회계 】

(1) GPU 임차 지원(1111-111)

◦ 시험부는 GPU 임차 단가를 재검토할 필요가 있음.

가) 사업 및 예산안 개요

○ GPU를 임차하는 사업이다.

나) 임차 단가 적정성 검토 필요

○ 임차 단가가 높다.

<2031년도 GPU 임차 예산안 현황>

(단위: 백만원)

<table>
<tr><th>구 분</th><th>2030예산</th><th>2031예산안(B)</th></tr>
<tr><td>GPU 임차</td><td>1,000</td><td>1,500</td></tr>
</table>

자료: 시험부

○ 따라서 시험부는 단가를 낮출 필요가 있음.

2) NPU 구매 지원(2222-222)

◦ 시험부는 구매 방식을 검토할 필요가 있음.

가) 사업 및 계획안 개요

○ NPU를 구매하는 사업이다.
'''.replace('가\n상정책관', '가상\n정책관')

BUDGET = '''목차
(1) GPU 임차 지원 (1111-111) 1

Ⅰ. 일반회계

사업명

(1) GPU 임차 지원 (1111-111)

가. 예산안 총괄표

(단위: 백만원)

<table>
<tr><th>사업명</th><th>2031년 조정안(B)</th></tr>
<tr><td>GPU 임차 지원</td><td>1,500</td></tr>
</table>

1) 사업목적·내용

산·학·연에 GPU를 임차하여 제공한다.
'''


BUDGET_DUP = '''목차
(1) GPU 임차 지원 (1111-111) 1
(2) 지역 AI 실증 (1111-111) 2

Ⅰ. 일반회계

사업명

(1) GPU 임차 지원 (1111-111)

1) 사업목적·내용

산·학·연에 GPU를 임차하여 제공한다.

Ⅱ. 지역균형발전특별회계

사업명

(2) 지역 AI 실증 (1111-111)

1) 사업목적·내용

지역에서 AI를 실증한다.
'''


def write_config(root, **changes):
    value = {'schema_version': 1, 'adapter': 'committee-review-report', 'ministry_id': 'test', 'ministry': '시험부', 'fiscal_year': 2031,
             'committee': {'id': 'test', 'name': '시험위원회', 'short': '시험위'},
             'edition': {'id': 'review-a', 'stage': 'committee_review', 'published_at': '2031-11'},
             'markdown_glob': 'md/*.md', 'expected_units': 3}
    value.update(changes)
    (root / '.budget-index/review-config.json').write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root / '.budget-index').mkdir()
        (self.root / 'md').mkdir()
        self.source = self.root / 'md/검토보고서.md'
        self.source.write_text(REVIEW, encoding='utf-8')
        write_config(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_build_verify_and_boundaries(self):
        result = rc.build(self.root)
        self.assertEqual((result['unit_count'], result['issue_count'], result['dept_count'], result['context_count']), (3, 4, 2, 2))
        self.assertTrue(rc.verify(self.root)['ok'])
        gpu = rc.show(self.root, '1111-111')['record']
        self.assertEqual(gpu['dept'], '가상정책관')  # 두 줄로 갈라진 소관과 이름
        self.assertEqual([i['label'] for i in gpu['issues']], ['가', '나'])
        npu = rc.show(self.root, '2222-222')['record']  # '2)' 형태의 머리글
        self.assertEqual(npu['title'], 'NPU 구매 지원')
        self.assertEqual((npu['account'], npu['account_source']), ('방송통신발전기금', 'toc'))  # 본문에 회계 머리글이 없어 목차로 채움
        self.assertEqual(gpu['account_source'], 'body')
        theme = rc.search(self.root, {'must': [['연구개발']]})['results'][0]
        self.assertIsNone(theme['code'])  # 총괄 주제는 코드가 없다

    def test_table_caption_unit_and_issue_filter(self):
        rc.build(self.root)
        shown = rc.show(self.root, '1111-111', issue='나')
        self.assertEqual(shown['tables'][0]['caption'], '<2031년도 GPU 임차 예산안 현황>')
        self.assertEqual(shown['tables'][0]['unit'], '백만원')
        raw = shown['segments'][0]['raw']
        self.assertIn('1,500', raw)
        self.assertNotIn('NPU를 구매', raw)
        with self.assertRaises(ValueError):
            rc.show(self.root, '1111-111', issue='라')

    def test_search_filters_and_scope(self):
        rc.build(self.root)
        self.assertEqual(rc.search(self.root, {'must': [['GPU']]})['total'], 1)
        self.assertEqual(rc.search(self.root, {'must': [['임차']], 'exclude': [['NPU']]})['total'], 1)
        self.assertEqual(rc.search(self.root, {'filters': {'dept': '가상정책관'}})['total'], 2)
        self.assertEqual(rc.search(self.root, {'filters': {'code': '2222-222'}})['total'], 1)
        self.assertEqual(rc.search(self.root, {'must': [['일반회계']], 'filters': {'scope': 'contexts'}})['total'], 1)
        with self.assertRaises(ValueError):
            rc.search(self.root, {})

    def test_link_to_program_index_by_code(self):
        rc.build(self.root)
        before = rc.show(self.root, '1111-111')['program_link']
        self.assertFalse(before['linked'])  # 사업설명자료 색인이 아직 없다
        (self.root / 'md2').mkdir()
        (self.root / 'md2/시험(1권).md').write_text(BUDGET, encoding='utf-8')
        (self.root / '.budget-index/config.json').write_text(json.dumps({
            'schema_version': 3, 'adapter': 'msit-repeated-toc', 'ministry_id': 'test', 'ministry': '시험부', 'fiscal_year': 2031,
            'edition': {'id': 'proposal-a', 'stage': 'government_proposal', 'published_at': None},
            'markdown_glob': 'md2/*.md', 'expected_volumes': 1, 'expected_programs': 1, 'default_accounts': {'1': ['general', '일반회계']}}))
        b.build(self.root)
        linked = rc.show(self.root, '1111-111')['program_link']
        self.assertTrue(linked['linked'])
        self.assertEqual(linked['programs'][0]['title'], 'GPU 임차 지원')
        hit = rc.search(self.root, {'must': [['GPU']]})['results'][0]
        self.assertTrue(hit['program_link']['linked'])
        missing = rc.show(self.root, '2222-222')['program_link']
        self.assertFalse(missing['linked'])
        self.assertIn('같은 코드가 없음', missing['reason'])
        write_year = json.loads((self.root / '.budget-index/config.json').read_text())
        write_year['fiscal_year'] = 2030
        (self.root / '.budget-index/config.json').write_text(json.dumps(write_year))
        b.build(self.root)
        self.assertIn('회계연도가 다름', rc.show(self.root, '1111-111')['program_link']['reason'])

    def test_toc_mismatch_blocks_publish_and_keeps_old_index(self):
        rc.build(self.root)
        db = self.root / '.budget-index/review.sqlite'
        before = hashlib.sha256(db.read_bytes()).hexdigest()
        self.source.write_text(REVIEW.replace('2) NPU 구매 지원(2222-222)', '다음 문단'), encoding='utf-8')
        with self.assertRaises(ValueError) as caught:
            rc.build(self.root)
        self.assertIn('목차와 본문 경계가 맞지 않아', str(caught.exception))
        self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(), before)

    def test_stale_source_is_rejected(self):
        rc.build(self.root)
        self.source.write_text(REVIEW + '\n추가 문장\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            rc.search(self.root, {'must': [['GPU']]})
        with self.assertRaises(ValueError):
            rc.verify(self.root)

    def test_config_validation(self):
        write_config(self.root, adapter='msit-repeated-toc')
        with self.assertRaises(ValueError):
            rc.build(self.root)
        write_config(self.root, edition={'id': 'review-a', 'stage': 'government_proposal'})
        with self.assertRaises(ValueError):
            rc.build(self.root)
        write_config(self.root, expected_units=5)
        with self.assertRaises(ValueError):
            rc.build(self.root)

    def test_independent_databases(self):
        rc.build(self.root)
        self.assertTrue((self.root / '.budget-index/review.sqlite').is_file())
        self.assertFalse((self.root / '.budget-index/budget.sqlite').exists())  # 사업설명자료 색인을 만들거나 바꾸지 않는다
        con = sqlite3.connect((self.root / '.budget-index/review.sqlite').as_uri() + '?mode=ro', uri=True)
        self.assertEqual(con.execute('SELECT count(*) FROM units').fetchone()[0], 5)
        con.close()

    def test_same_code_in_two_accounts_links_only_matching_program(self):
        """회계가 다르면 사업 코드가 중복된다(2027년 과기정통부 자료에서 36개). 제목이 맞는 사업만 연결해야 한다."""
        rc.build(self.root)
        (self.root / 'md2').mkdir()
        (self.root / 'md2/시험(1권).md').write_text(BUDGET_DUP, encoding='utf-8')
        (self.root / '.budget-index/config.json').write_text(json.dumps({
            'schema_version': 3, 'adapter': 'msit-repeated-toc', 'ministry_id': 'test', 'ministry': '시험부', 'fiscal_year': 2031,
            'edition': {'id': 'proposal-a', 'stage': 'government_proposal', 'published_at': None},
            'markdown_glob': 'md2/*.md', 'expected_volumes': 1, 'expected_programs': 2, 'default_accounts': {'1': ['general', '일반회계']}}))
        b.build(self.root)
        link = rc.show(self.root, '1111-111')['program_link']
        self.assertTrue(link['linked'])
        self.assertEqual([p['title'] for p in link['programs']], ['GPU 임차 지원'])  # 같은 코드의 다른 사업은 연결하지 않는다
        self.assertEqual(link['programs'][0]['match'], 'title_exact')
        self.assertEqual([p['title'] for p in link['same_code_other_programs']], ['지역 AI 실증'])
        direct = rc.program_link(self.root, '1111-111', 2031, title='지역 AI 실증', account='지역균형발전특별회계')
        self.assertEqual([p['title'] for p in direct['programs']], ['지역 AI 실증'])
        self.assertTrue(direct['programs'][0]['account_agrees'])
        none = rc.program_link(self.root, '1111-111', 2031, title='전혀 다른 사업', account='일반회계')
        self.assertFalse(none['linked'])  # 코드만 같고 제목이 맞는 사업이 없으면 연결하지 않는다
        self.assertEqual(len(none['code_only_candidates']), 2)
        loose = rc.program_link(self.root, '1111-111', 2031)
        self.assertIn('섞여 있을 수 있음', loose['note'])


if __name__ == '__main__':
    unittest.main()
