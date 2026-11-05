import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

KIT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('portable', KIT/'app/portable.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root/'input'
        self.source.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_no_overwrite(self):
        (self.source/'a.hwp').write_bytes(b'fake')
        out = self.root/'existing'
        out.mkdir()
        (out/'old.md').write_text('preserve')
        with self.assertRaisesRegex(ValueError, '이미 있습니다'):
            p.convert(self.source, out)
        self.assertEqual((out/'old.md').read_text(), 'preserve')

    def test_same_stem_rejected(self):
        for name in ['A.hwp', 'a.hwpx']:
            (self.source/name).write_bytes(b'fake')
        with self.assertRaisesRegex(ValueError, '충돌'):
            p.convert(self.source)

    def test_failure_does_not_publish_partial_batch(self):
        (self.source/'a.hwp').write_bytes(b'fake')
        with patch.object(p, 'run_kordoc', side_effect=ValueError('conversion failed')):
            with self.assertRaisesRegex(ValueError, 'conversion failed'):
                p.convert(self.source)
        self.assertFalse((self.source/'markdown').exists())
        self.assertFalse(list(self.source.glob('.kordoc-convert-*')))

    def test_large_document_requires_explicit_limit(self):
        with zipfile.ZipFile(self.source/'a.hwpx', 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('large.xml', b'0' * (17 * 1024 * 1024))
        with self.assertRaisesRegex(ValueError, '압축 해제'):
            p.convert(self.source, max_unzip_mb=16)
        self.assertFalse((self.source/'markdown').exists())

    def test_text_copy_preserves_xml_and_omits_only_bindata(self):
        source = self.source/'images.hwpx'
        body = '<section>본문·표·한글</section>'.encode('utf-8')
        with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('mimetype', 'application/hwp+zip')
            z.writestr('Contents/section0.xml', body)
            for n in range(501):
                z.writestr(f'BinData/image{n}.bmp', b'fake-image')
        before = p.sha(source)
        plan = p.zip_plan(source, False, 256)
        self.assertEqual(plan['omitted_bindata'], 501)
        target = self.root/'text.hwpx'
        p.make_text_copy(source, target, plan, 256)
        with zipfile.ZipFile(target) as z:
            self.assertEqual(z.read('Contents/section0.xml'), body)
            self.assertEqual(len(z.namelist()), 2)
        self.assertEqual(p.sha(source), before)
        with self.assertRaisesRegex(ValueError, '한도 500'):
            p.zip_plan(source, True, 256)

    def test_install_collision_preserves_all_existing_skills(self):
        target = self.root/'skills'
        (target/'budget-search').mkdir(parents=True)
        (target/'budget-search/SKILL.md').write_text('existing')
        with self.assertRaisesRegex(ValueError, '보존'):
            p.install_skills(target)
        self.assertEqual((target/'budget-search/SKILL.md').read_text(), 'existing')
        self.assertFalse((target/'kordoc').exists())

    def test_skill_location_can_be_resolved_after_install(self):
        target = self.root/'agent skills'
        p.install_skills(target)
        for name in ['kordoc', 'budget-index', 'budget-search']:
            path = json.loads((target/name/'portable-kit.json').read_text())['kit_root']
            self.assertEqual(Path(path), KIT)
            self.assertTrue((Path(path)/'budget.cmd').is_file())

    def test_init_does_not_overwrite_existing_config(self):
        target = self.root/'work'
        config = KIT/'samples/config.json'
        p.init_workspace(target, config)
        before = (target/'.budget-index/config.json').read_bytes()
        with self.assertRaisesRegex(ValueError, '이미 있습니다'):
            p.init_workspace(target, config)
        self.assertEqual((target/'.budget-index/config.json').read_bytes(), before)

    def test_review_selftest_and_init(self):
        result = p.review_selftest()
        self.assertEqual((result['review_units'], result['review_issues'], result['review_gpu_matches']), (3, 4, 1))
        target = self.root/'ws'
        out = p.init_workspace(target, KIT/'samples/review-config.json', review=True)
        self.assertTrue(out['config'].endswith('review-config.json'))
        before = (target/'.budget-index/review-config.json').read_bytes()
        with self.assertRaisesRegex(ValueError, '이미 있습니다'):
            p.init_workspace(target, KIT/'samples/review-config.json', review=True)
        self.assertEqual((target/'.budget-index/review-config.json').read_bytes(), before)
        self.assertFalse((target/'.budget-index/config.json').exists())  # 사업설명자료 설정과 섞이지 않는다


if __name__ == '__main__':
    unittest.main(verbosity=2)
