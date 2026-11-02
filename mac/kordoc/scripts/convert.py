"""폴더의 HWP/HWPX/HML/DOCX/XLS/XLSX를 Markdown으로 일괄 변환한다. 표준 라이브러리만 사용."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

SUPPORTED = {'.hwp', '.hwpx', '.hml', '.docx', '.xls', '.xlsx'}
KORDOC_VERSION = '4.22.13'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


ENGINE = Path(__file__).resolve().parent.parent / 'engine'


def kordoc_command():
    """ensure-env.sh이 자체 시험을 통과시킨 Node만 쓴다. env.json이 없으면 변환을 거부한다."""
    env_file = ENGINE / 'env.json'
    if not env_file.is_file():
        raise ValueError('환경 검사 기록(engine/env.json)이 없습니다. 먼저 scripts/ensure-env.sh을 실행하세요.')
    env = json.loads(env_file.read_text(encoding='utf-8-sig'))
    node, cli = env.get('node'), ENGINE / 'node_modules/kordoc/dist/cli.js'
    if not env.get('ok') or not node or not Path(node).is_file():
        raise ValueError('env.json이 유효하지 않습니다. scripts/ensure-env.sh을 다시 실행하세요.')
    if not cli.is_file():
        raise ValueError('동봉된 kordoc이 없습니다: ' + str(cli))
    return [node, str(cli)]


def run_kordoc(args, max_unzip_mb):
    env = dict(os.environ, KORDOC_OFFLINE='1', ORT_DISABLE_TELEMETRY='1', KORDOC_MAX_UNZIP_MB=str(max_unzip_mb), NO_COLOR='1')
    result = subprocess.run([*kordoc_command(), *map(str, args)], env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, encoding='utf-8', errors='replace', timeout=900)
    if result.returncode:
        raise ValueError(f'kordoc 실패 ({result.returncode}):\n{result.stderr[-6000:]}\n{result.stdout[-1000:]}')
    return result


def zip_plan(path, images, max_unzip_mb):
    if not zipfile.is_zipfile(path):
        return None
    text_only = path.suffix.lower() == '.hwpx' and not images
    kept, omitted, size = [], [], 0
    with zipfile.ZipFile(path) as z:
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
    return {'kept': kept, 'omitted_bindata': len(omitted)}


def make_text_copy(source, target, plan, max_unzip_mb):
    """HWPX의 XML·서식은 그대로 두고 BinData만 뺀 읽기용 사본을 만든다."""
    written = 0
    keep = set(plan['kept'])
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, 'w') as dst:
        for info in src.infolist():
            if info.filename not in keep:
                continue
            with src.open(info) as reader, dst.open(info, 'w') as writer:
                for block in iter(lambda: reader.read(1024 * 1024), b''):
                    written += len(block)
                    if written > max_unzip_mb * 1024 * 1024:
                        raise ValueError('HWPX 읽기용 사본 크기가 설정 한도를 초과했습니다.')
                    writer.write(block)


def convert(source, output=None, images=False, max_unzip_mb=256):
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
        raise ValueError('--max-unzip-mb는 16~2048 범위입니다.')
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
                args = [parse_input, '-o', staging / (p.stem + '.md'), '--html-tables']
                if not images:
                    args.append('--no-images')
                result = run_kordoc(args, max_unzip_mb)
            md = staging / (p.stem + '.md')
            if not md.is_file() or not md.stat().st_size:
                raise ValueError(f'Markdown 생성 실패: {p.name}')
            records.append({'input': p.name, 'input_sha256': sha(p), 'markdown': md.name,
                            'markdown_sha256': sha(md), 'stderr': result.stderr[-4000:],
                            'omitted_bindata': plans[p]['omitted_bindata'] if plans[p] else 0})
        report = {'kordoc': KORDOC_VERSION, 'images': images, 'max_unzip_mb': max_unzip_mb,
                  'time_utc': datetime.now(timezone.utc).isoformat(), 'files': records}
        (staging / 'conversion-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        staging.rename(output)  # 전체가 성공했을 때만 게시한다.
        return {'output': str(output), 'files': len(files), 'images': images}
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--images', action='store_true')
    p.add_argument('--max-unzip-mb', type=int, default=256)
    a = p.parse_args()
    print(json.dumps(convert(a.source, a.output, a.images, a.max_unzip_mb), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('오류: ' + str(exc), file=sys.stderr)
        sys.exit(1)
