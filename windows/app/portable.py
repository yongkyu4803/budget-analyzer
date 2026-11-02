"""Portable kordoc + budget tools. Python standard library only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

KIT = Path(__file__).resolve().parent.parent
SUPPORTED = {'.hwp', '.hwpx', '.hml', '.docx', '.xls', '.xlsx'}
NODE_VERSION = 'v24.22.0'
PYTHON_VERSION = (3, 14, 8)
KIT_VERSION = '1.1.0'
# kordoc 4.22.13 은 HWP 구역 100개·구역당 레코드 50만 개를 넘는 부분을 경고 없이 버린다.
# 1.1.0 은 동봉 dist 의 상한을 올려 두었다(developer/patch-limits.cjs).
OLD_LIMITS = ('var MAX_SECTIONS = 100;', 'var MAX_RECORDS = 5e5;')
NEW_LIMITS = ('var MAX_SECTIONS = 2000;', 'var MAX_RECORDS = 5e6;')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def node_command(host_node=None):
    if host_node:
        return str(Path(host_node).resolve())
    if os.name != 'nt':
        raise ValueError('Windows x64용 패키지입니다. 개발 시험은 --host-node PATH로 구분합니다.')
    return str(KIT / 'runtime/node/node.exe')


def run_kordoc(args, host_node=None, max_unzip_mb=256):
    env = dict(os.environ, KORDOC_OFFLINE='1', ORT_DISABLE_TELEMETRY='1',
               KORDOC_MAX_UNZIP_MB=str(max_unzip_mb), NO_COLOR='1')
    cmd = [node_command(host_node), str(KIT / 'app/node_modules/kordoc/dist/cli.js'), *map(str, args)]
    result = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            encoding='utf-8', errors='replace', timeout=900, shell=False)
    if result.returncode:
        raise ValueError(f'kordoc 실패 ({result.returncode}):\n{result.stderr[-6000:]}\n{result.stdout[-1000:]}')
    return result


def zip_plan(path, images, max_unzip_mb):
    if not zipfile.is_zipfile(path):
        return None
    text_only = path.suffix.lower() == '.hwpx' and not images
    with zipfile.ZipFile(path) as z:
        kept, omitted, size = [], [], 0
        for i in z.infolist():
            name = i.filename.replace('\\', '/')
            if name.startswith('/') or '..' in name.split('/') or ':' in name.split('/')[0]:
                raise ValueError('안전하지 않은 ZIP 내부 경로: ' + name)
            if text_only and name.casefold().startswith('bindata/'):
                omitted.append(i.filename)
            else:
                kept.append(i.filename)
                size += i.file_size
    if size > max_unzip_mb * 1024 * 1024:
        raise ValueError(f'{path.name}: 읽을 부분의 압축 해제 크기 {size/1024/1024:.1f} MiB. '
                         '신뢰하는 대용량 문서는 --max-unzip-mb 1024를 명시하세요.')
    if path.suffix.lower() == '.hwpx' and len(kept) > 500:
        raise ValueError(f'{path.name}: 읽을 ZIP 항목 {len(kept)}개, kordoc 한도 500개. '
                         '그림이 많으면 --images 없이 본문·표를 변환하세요.')
    return {'kept': kept, 'omitted_bindata': len(omitted), 'read_uncompressed_bytes': size}


def make_text_copy(source, target, plan, max_unzip_mb):
    """Keep HWPX XML/layout intact; omit only the explicitly unrequested BinData."""
    written = 0
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, 'w') as dst:
        keep = set(plan['kept'])
        for info in src.infolist():
            if info.filename not in keep:
                continue
            with src.open(info) as reader, dst.open(info, 'w') as writer:
                for block in iter(lambda: reader.read(1024 * 1024), b''):
                    written += len(block)
                    if written > max_unzip_mb * 1024 * 1024:
                        raise ValueError('HWPX 읽기용 사본 크기가 설정 한도를 초과했습니다.')
                    writer.write(block)


def convert(source, output=None, images=False, max_unzip_mb=256, host_node=None):
    source = Path(source).resolve()
    if not source.exists():
        raise ValueError(f'입력 경로가 없습니다: {source}')
    files = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED) if source.is_dir() else [source]
    if not files or any(p.suffix.lower() not in SUPPORTED for p in files):
        raise ValueError('지원 입력: HWP, HWPX, HML, DOCX, XLS, XLSX. 폴더의 바로 아래 파일을 처리합니다.')
    stems = [p.stem.casefold() for p in files]
    if len(stems) != len(set(stems)):
        raise ValueError('동일 이름의 서로 다른 형식 파일이 있습니다. 출력 이름 충돌을 먼저 해결하세요.')
    if not 16 <= max_unzip_mb <= 2048:
        raise ValueError('--max-unzip-mb는 16~2048 범위입니다. 큰 문서는 충분한 메모리가 필요합니다.')
    output = Path(output).resolve() if output else (source if source.is_dir() else source.parent) / 'markdown'
    if output.exists():
        raise ValueError(f'출력 폴더가 이미 있습니다. --output으로 새 폴더를 지정하세요: {output}')
    plans = {p: zip_plan(p, images, max_unzip_mb) for p in files}
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.kordoc-convert-', dir=output.parent))
    records = []
    try:
        for p in files:
            print(f'변환: {p.name}', file=sys.stderr, flush=True)
            with tempfile.TemporaryDirectory(prefix='kordoc-text-input-') as temp:
                plan = plans[p]
                parse_input = p
                if plan and plan['omitted_bindata']:
                    parse_input = Path(temp) / p.name
                    make_text_copy(p, parse_input, plan, max_unzip_mb)
                args = [str(parse_input), '-o', str(staging / (p.stem + '.md')), '--html-tables']
                if not images:
                    args.append('--no-images')
                result = run_kordoc(args, host_node, max_unzip_mb)
            md = staging / (p.stem + '.md')
            if not md.is_file() or not md.stat().st_size:
                raise ValueError(f'Markdown 생성 실패: {p.name}')
            records.append({'input': p.name, 'input_sha256': sha(p), 'markdown': md.name,
                            'markdown_sha256': sha(md), 'stderr': result.stderr[-4000:],
                            'omitted_bindata': plans[p]['omitted_bindata'] if plans[p] else 0})
        report = {'kordoc': '4.22.13', 'images': images, 'max_unzip_mb': max_unzip_mb,
                  'time_utc': datetime.now(timezone.utc).isoformat(), 'files': records}
        write_json(staging / 'conversion-report.json', report)
        # Publish a complete batch only; failures leave the prior corpus untouched.
        staging.rename(output)
        return {'output': str(output), 'files': len(files), 'images': images}
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def budget_module():
    sys.path.insert(0, str(KIT / 'skills/budget-index/scripts'))
    import budget_core
    return budget_core


def check_manifest():
    manifest = json.loads((KIT / 'MANIFEST.json').read_text(encoding='utf-8'))
    errors = []
    for name, expected in manifest['files'].items():
        p = (KIT / name).resolve()
        if not p.is_relative_to(KIT) or not p.is_file() or sha(p) != expected:
            errors.append(name)
    if errors:
        raise ValueError('패키지 파일 누락/변경: ' + ', '.join(errors[:20]))
    return len(manifest['files'])


def check_kordoc_limits():
    dist = KIT / 'app/node_modules/kordoc/dist'
    text = ''.join(p.read_text(encoding='utf-8', errors='replace') for p in dist.glob('*.js'))
    left = [s for s in OLD_LIMITS if s in text]
    missing = [s for s in NEW_LIMITS if s not in text]
    if left or missing:
        raise ValueError('kordoc HWP 읽기 상한이 올려져 있지 않습니다: ' + ', '.join(left + missing))
    return 'sections 2000, records 5e6'


def check(host_node=None):
    count = check_manifest()
    limits = check_kordoc_limits()
    node = subprocess.check_output([node_command(host_node), '--version'], encoding='utf-8').strip()
    if not host_node and (node != NODE_VERSION or sys.version_info[:3] != PYTHON_VERSION):
        raise ValueError(f'번들 런타임 버전 불일치: Node {node}, Python {sys.version}')
    version = run_kordoc(['--version'], host_node).stdout.strip()
    if version != '4.22.13':
        raise ValueError('kordoc 버전 불일치: ' + version)
    with tempfile.TemporaryDirectory(prefix='kordoc-check-') as temp:
        root = Path(temp) / '한국어 공백 예제'
        root.mkdir()
        source = KIT / 'samples/input/가상예산(1권).hwpx'
        shutil.copy2(source, root / source.name)
        convert(root, host_node=host_node)
        (root / '.budget-index').mkdir()
        shutil.copy2(KIT / 'samples/config.json', root / '.budget-index/config.json')
        b = budget_module()
        b.build(root)
        verified = b.verify(root, originals=True)
        hit = b.search(root, {'must': [['GPU'], ['임차']]})
        if verified['programs'] != 2 or hit['total'] != 1:
            raise ValueError('예제 검색 결과가 기대와 다릅니다.')
        shown = b.show(root, hit['results'][0]['uid'], 'summary')
        raw = '\n'.join(s['raw'] for s in shown['segments'])
        if not all(token in raw for token in ['백만원', '2031', '1,500']):
            raise ValueError('예제의 금액·연도·단위가 보존되지 않았습니다.')
    report = {'ok': True, 'kit_version': KIT_VERSION, 'test_mode': 'host-code-test' if host_node else 'windows-bundled-runtime',
              'node': node, 'python': sys.version.split()[0], 'sqlite': sqlite3.sqlite_version,
              'kordoc': version, 'kordoc_hwp_limits': limits, 'manifest_files_checked': count,
              'pipeline': 'HWPX -> Markdown -> budget index -> search -> source table',
              'programs': 2, 'gpu_rental_matches': 1,
              'time_utc': datetime.now(timezone.utc).isoformat()}
    write_json(KIT / 'diagnostics/last-check.json', report)
    return report


def init_workspace(root, config):
    root = Path(root).resolve()
    config = Path(config).resolve()
    value = json.loads(config.read_text(encoding='utf-8-sig'))
    target = root / '.budget-index/config.json'
    if target.exists():
        raise ValueError('설정이 이미 있습니다. 기존 파일을 직접 검토·수정하세요: ' + str(target))
    # Validate the supplied configuration before publishing it.
    with tempfile.TemporaryDirectory() as temp:
        trial = Path(temp)
        write_json(trial / '.budget-index/config.json', value)
        budget_module().config_at(trial)
    write_json(target, value)
    return {'config': str(target), 'next': 'budget.cmd --root "WORKSPACE" build'}


def install_skills(target):
    target = Path(target).expanduser().resolve()
    names = ['kordoc', 'budget-index', 'budget-search']
    collisions = [str(target / n) for n in names if (target / n).exists()]
    if collisions:
        raise ValueError('기존 스킬을 보존하기 위해 중단합니다: ' + ', '.join(collisions))
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copytree(KIT / 'skills' / name, target / name)
        write_json(target / name / 'portable-kit.json', {'kit_root': str(KIT)})
    return {'installed': [str(target / n) for n in names],
            'note': '이 ZIP 폴더를 유지하세요. 이동했다면 portable-kit.json 경로를 갱신하세요.'}


def menu(host_node=None):
    print(f'kordoc + 예산 인덱스·검색 / Windows x64 / {KIT_VERSION}\n')
    print('1. 패키지·예제 동작 확인\n2. 문서 폴더를 Markdown으로 변환\n3. 사용 안내서 열기\n0. 종료')
    choice = input('\n선택: ').strip()
    if choice == '1':
        print(json.dumps(check(host_node), ensure_ascii=False, indent=2))
    elif choice == '2':
        source = input('문서 폴더 경로: ').strip().strip('"')
        # Large document limit remains explicit in the CLI; menu keeps the default.
        print(json.dumps(convert(source, host_node=host_node), ensure_ascii=False, indent=2))
    elif choice == '3':
        if os.name == 'nt':
            os.startfile(str(KIT / 'START-HERE.txt'))
        else:
            print((KIT / 'START-HERE.txt').read_text(encoding='utf-8-sig'))


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    argv = list(sys.argv[1:] if argv is None else argv)
    host_node = None
    if argv[:1] == ['--host-node']:
        if len(argv) < 2:
            raise ValueError('--host-node PATH 필요')
        host_node, argv = argv[1], argv[2:]
    if argv[:1] == ['budget']:
        sys.path.insert(0, str(KIT / 'skills/budget-index/scripts'))
        sys.argv = [str(KIT / 'skills/budget-index/scripts/budget_core.py'), *argv[1:]]
        runpy.run_path(sys.argv[0], run_name='__main__')
        return
    if argv[:1] == ['kordoc']:
        result = run_kordoc(argv[1:] or ['--help'], host_node)
        print(result.stdout, end='')
        print(result.stderr, end='', file=sys.stderr)
        return
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command')
    sub.add_parser('check')
    c = sub.add_parser('convert')
    c.add_argument('source', type=Path)
    c.add_argument('--output', type=Path)
    c.add_argument('--images', action='store_true')
    c.add_argument('--max-unzip-mb', type=int, default=256)
    c = sub.add_parser('init')
    c.add_argument('--root', type=Path, required=True)
    c.add_argument('--config', type=Path, required=True)
    c = sub.add_parser('install-skills')
    c.add_argument('--target', type=Path, required=True)
    a = p.parse_args(argv)
    if not a.command:
        return menu(host_node)
    if a.command == 'check':
        result = check(host_node)
    elif a.command == 'convert':
        result = convert(a.source, a.output, a.images, a.max_unzip_mb, host_node)
    elif a.command == 'init':
        result = init_workspace(a.root, a.config)
    else:
        result = install_skills(a.target)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, AssertionError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        sys.exit(1)
