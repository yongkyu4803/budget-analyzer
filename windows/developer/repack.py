"""Recreate the integrity manifest and a distributable ZIP from this kit."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {'diagnostics', 'workspace', '__pycache__', '.git', '.DS_Store'}


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error('Output must be outside the kit.')
    if output.exists():
        parser.error('Output already exists; choose a new filename.')
    files = sorted(p for p in ROOT.rglob('*') if p.is_file() and
                   not EXCLUDE.intersection(p.relative_to(ROOT).parts) and p.name != 'MANIFEST.json')
    if any(p.is_symlink() for p in files):
        parser.error('Distribution must not contain symlinks.')
    manifest = {'algorithm': 'sha256', 'files': {p.relative_to(ROOT).as_posix(): digest(p) for p in files}}
    path = ROOT / 'MANIFEST.json'
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in [*files, path]:
            z.write(p, (Path(ROOT.name) / p.relative_to(ROOT)).as_posix())
        z.writestr(ROOT.name + '/workspace/', '')
    checksum = digest(output)
    output.with_suffix('.zip.sha256').write_text(checksum + '  ' + output.name + '\n', encoding='ascii')
    print(json.dumps({'zip': str(output), 'bytes': output.stat().st_size,
                      'sha256': checksum, 'files': len(files) + 1}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
