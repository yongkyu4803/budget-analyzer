import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/budget-index/scripts'))
import budget_core as b


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name).resolve()
        (self.root/'.budget-index').mkdir()
        (self.root/'md').mkdir()
        self.config={'schema_version':3,'adapter':'msit-repeated-toc','ministry_id':'test','ministry':'검증부','fiscal_year':2031,
                     'edition':{'id':'proposal-a','stage':'government_proposal','published_at':None},
                     'markdown_glob':'md/*.md','expected_volumes':1,'expected_programs':2,'default_accounts':{'1':['general','일반회계']}}
        self.config_path=self.root/'.budget-index/config.json'
        self.config_path.write_text(json.dumps(self.config))
        self.source=self.root/'md/시험(1권).md'
        self.source.write_text('''목차
(1) GPU 임차 지원 (1111-111) 1
(2) NPU 구매 지원 (1111-111) 2

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

사업명

(2) NPU 구매 지원 (1111-111)

1) 사업목적·내용

기업에 NPU를 구매하여 제공한다. 출연 지원이다.
''')
        b.build(self.root)
        self.id='2031-test-general-v01-n001'
        self.record=b.show(self.root,self.id)['record']

    def tearDown(self): self.temp.cleanup()

    def amount(self,raw='1,500',state='value',value='1500'):
        lines=self.source.read_text().splitlines()
        start=lines.index('(단위: 백만원)')+1;end=lines.index('</table>')+1
        return {'label':'program_total','year':2031,'stage':'adjusted_proposal','unit':'백만원','raw':raw,'value':value,'state':state,'verification':'source_checked','column_label':'조정안(B)','unit_raw':'(단위: 백만원)',
                'evidence':{'path':self.record['source'],'sha256':self.record['source_sha256'],'start_line':start,'end_line':end,'quote':'\n'.join(lines[start-1:end])}}

    def install_facts(self):
        f={'schema_version':3,'uid':self.record['uid'],'edition':'proposal-a','fields':{},'amounts':[self.amount()]}
        (self.root/'.budget-index/facts.json').write_text(json.dumps([f]))
        b.build(self.root)
        return f

    def test_corpus_counts_dynamic_and_duplicate_code(self):
        result=b.search(self.root,{'filters':{'code':'1111-111'}})
        self.assertEqual(result['total'],2)
        self.assertEqual(result['corpus']['programs'],2)

    def test_middle_dot_and_nfd(self):
        import unicodedata
        for term in ['산학연','산·학·연',unicodedata.normalize('NFD','산학연')]:
            self.assertEqual(b.search(self.root,{'must':[[term],['GPU']]})['results'][0]['id'],self.id)

    def test_technology_and_financing_not_synonyms(self):
        for query in [('GPU','구매'),('NPU','임차'),('출자',)]:
            self.assertEqual(b.search(self.root,{'must':[[t] for t in query]})['total'],0)

    def test_complete_table_with_unit(self):
        shown=b.show(self.root,self.id,'summary')['segments'][0]['raw']
        self.assertIn('(단위: 백만원)',shown)
        self.assertIn('2031년 조정안(B)',shown)
        self.assertIn('</table>',shown)

    def test_edition_filter_no_silent_fallback(self):
        for f in [{'year':2030},{'stage':'approved'},{'ministry':'다른부'}]:
            self.assertEqual(b.search(self.root,{'filters':f})['total'],0)

    def test_structured_groups_and_optional_terms(self):
        result=b.search(self.root,{'must':[['임대','임차']],'should':[['GPU'],['없는단어']]})
        self.assertEqual(result['total'],1)

    def test_source_staleness_detected(self):
        self.source.write_text(self.source.read_text()+'\n변경\n')
        with self.assertRaisesRegex(ValueError,'Stale'): b.search(self.root,{'must':[['GPU']]})

    def test_new_facts_requires_rebuild(self):
        (self.root/'.budget-index/facts.json').write_text('[]')
        with self.assertRaisesRegex(ValueError,'added/removed'):b.search(self.root,{'must':[['GPU']]})

    def test_config_staleness_detected(self):
        c=copy.deepcopy(self.config);c['edition']['id']='approved-b';self.config_path.write_text(json.dumps(c))
        with self.assertRaisesRegex(ValueError,'Stale'):b.show(self.root,self.id)

    def test_uid_changes_with_edition(self):
        old=self.record['uid'];c=copy.deepcopy(self.config);c['edition']['id']='approved-b';c['edition']['stage']='approved';self.config_path.write_text(json.dumps(c));b.build(self.root)
        self.assertNotEqual(old,b.show(self.root,self.id)['record']['uid'])

    def test_wrong_source_quote_and_cross_business_rejected(self):
        for change in [{'quote':'없는 원문'},{'sha256':'0'*64},{'end_line':9999},{'path':'elsewhere.md'}]:
            a=self.amount();a['evidence'].update(change)
            with self.assertRaises(ValueError):b.validate_amount(a,self.record,self.root,{})

    def test_mismatched_numeric_value_unit_and_year(self):
        for change in [{'value':'15000'},{'unit':'달러'},{'year':2030},{'stage':'approved'},{'column_label':'확정액'},{'value':'NaN'}]:
            a=self.amount();a.update(change)
            with self.assertRaises(ValueError):b.validate_amount(a,self.record,self.root,{})

    def test_zero_dash_blank_not_equivalent(self):
        for raw,state,value in [('0','zero','0'),('-','dash',None),('','blank',None)]:
            a=self.amount(raw,state,value);a['verification']='not_checked';self.assertTrue(b.validate_amount(a,self.record,self.root,{}))
        for raw,state,value in [('-','dash','0'),('0','value','0'),('','blank','0')]:
            a=self.amount(raw,state,value);a['verification']='not_checked'
            with self.assertRaises(ValueError):b.validate_amount(a,self.record,self.root,{})

    def test_amount_conversion_and_unknown_coverage(self):
        self.install_facts()
        q={'amount':{'year':2031,'stage':'adjusted_proposal','unit':'억원','min':'15','max':'15'}}
        result=b.search(self.root,q)
        self.assertEqual(result['total'],1);self.assertEqual(result['amount_unknown_count'],1)
        q['amount']['min']='16';q['amount'].pop('max');self.assertEqual(b.search(self.root,q)['total'],0)
        q['amount']['stage']='approved';self.assertEqual(b.search(self.root,q)['amount_unknown_count'],2)

    def test_stale_facts_not_carried_forward_and_atomic_build(self):
        self.install_facts();before=b.sha(self.root/'.budget-index/budget.sqlite')
        self.source.write_text(self.source.read_text()+'\n원문 변경\n')
        with self.assertRaisesRegex(ValueError,'another source version'): b.build(self.root)
        self.assertEqual(before,b.sha(self.root/'.budget-index/budget.sqlite'))

    def test_workspace_portability(self):
        import shutil
        with tempfile.TemporaryDirectory() as dest:
            other=Path(dest)/'한국어 공백 폴더';shutil.copytree(self.root,other)
            self.assertEqual(b.search(other,{'must':[['GPU']]})['total'],1)

    def test_verify_and_invalid_query(self):
        self.assertTrue(b.verify(self.root)['ok'])
        for p in [{},{'must':[[]]},{'filters':{'bogus':True}},{'amount':{'min':'100'}}]:
            with self.assertRaises(ValueError):b.search(self.root,p)


if __name__=='__main__': unittest.main(verbosity=2)
