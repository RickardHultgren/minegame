"""Check the complete player, optionally package its lightweight editable folder."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import re
import runpy
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)


def delivery_files():
    # Explicit scope: native originals, previews, backups and historical projects
    # live outside this root and cannot inflate the runtime delivery.
    files = [ROOT / name for name in ('index.html', 'manifest.json', 'README.md',
                                     'verification.md', 'file_checks.json', 'runtime_checks.json')]
    rules = {'assets': {'.webp'}, 'docs': {'.md'}, 'production': {'.json', '.md'},
             'checks': {'.py', '.mjs'}, 'tools': {'.py'}}
    forbidden = {'__pycache__', '.git', 'backups', 'history', 'originals', 'rejected', 'qa', 'previews'}
    for directory, extensions in rules.items():
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and path.suffix in extensions and not set(path.relative_to(ROOT).parts) & forbidden:
                files.append(path)
    return sorted(files)


def check_art_source(source):
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    selected = [a for a in manifest['assets'] if a['key'] in {'warning', 'giveway', 'slide', 'below'}]
    art_manifest = json.loads((source / 'asset_manifest.json').read_text())
    assert art_manifest['runtime_exports'] == selected
    native = runpy.run_path(str(ROOT / 'checks/validate.py'))['validate_originals'](source / 'originals')
    assert {p.name for p in (source / 'originals').iterdir()} == {a['source_file'] for a in selected}
    return native


def package_art_source(source, output):
    native = check_art_source(source)
    # Native files occur once; no WebPs, contact sheets, old ZIPs or rejected art.
    names = ['README.md', 'asset_manifest.json',
             'production/art_review.json', 'production/file_checks.json',
             'production/generation_requests.json', 'production/selected_images.json',
             'production/export_selected.py']
    names += ['originals/' + a['file'] for a in native['files']]
    for name in ('production/dark_world_revision.json', 'production/eye_fix_revision.json', 'production/no_light_eye_fix_revision.json'):
        if (source / name).is_file():
            names.append(name)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(names):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (source / name).read_bytes(), compresslevel=9)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert len([n for n in archive.namelist() if n.endswith('.png')]) == 8
        assert not any(n.endswith(('.zip', '.webp', '.pyc')) for n in archive.namelist())
        for a in native['files']:
            assert hashlib.sha256(archive.read('originals/' + a['file'])).hexdigest() == a['sha256']
    return dict(file=str(output), bytes=output.stat().st_size, files=len(names),
                sha256=hashlib.sha256(output.read_bytes()).hexdigest(), integrity='passed', selected_native_pngs=8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT.parent / 'mine_game_intro_v7_fall_lite_no_light_eye_fix.zip')
    parser.add_argument('--check-only', action='store_true', help='Run checks without creating a release ZIP')
    parser.add_argument('--art-source', type=Path, help='Optionally verify/package the separate selected PNG source root')
    parser.add_argument('--art-output', type=Path, default=ROOT.parent / 'mine_game_intro_v7_fall_lite_no_light_eye_fix_art_source.zip')
    args = parser.parse_args()
    for directory in ('tools', 'checks'):
        for path in (ROOT / directory).glob('*.py'):
            ast.parse(path.read_text(), filename=str(path))
    run([sys.executable, str(ROOT / 'checks/validate.py')])
    with tempfile.TemporaryDirectory() as temporary:
        html = (ROOT / 'index.html').read_text()
        js = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', html, re.S)[-1]
        script = Path(temporary) / 'runtime.js'
        script.write_text(js)
        run(['node', '--check', str(script)])
    run(['node', '--check', str(ROOT / 'checks/runtime_checks.mjs')])
    run(['node', str(ROOT / 'checks/runtime_checks.mjs')])
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    file_report = json.loads((ROOT / 'file_checks.json').read_text())
    runtime_report = json.loads((ROOT / 'runtime_checks.json').read_text())
    report = {'status': 'passed', 'release': manifest['release'], 'total_ms': manifest['total_ms'],
              'active_images': len(manifest['assets']), 'runtime_cases': len(runtime_report['cases']),
              'html_bytes': file_report['html_bytes'], 'runtime_file_bytes': file_report['runtime_file_bytes'],
              'max_owned_images_simulated': runtime_report['max_owned_images']}
    if args.check_only:
        report['packaging'] = 'not_performed_check_only'
        if args.art_source:
            report['selected_native_pngs_verified'] = check_art_source(args.art_source)['selected_native_png_hashes_verified']
    else:
        files = delivery_files()
        assert args.output.resolve() not in {p.resolve() for p in files}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), date_time=(2026, 11, 22, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes(), compresslevel=9)
        with zipfile.ZipFile(args.output) as archive:
            assert archive.testzip() is None
            assert {n for n in archive.namelist() if n.startswith('assets/')} == {a['file'] for a in manifest['assets']}
            assert not any(n.endswith('.png') or 'backup' in n.lower() for n in archive.namelist())
        report.update(file=str(args.output), bytes=args.output.stat().st_size,
                      sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(), files=len(files), integrity='passed')
        if args.art_source:
            assert args.art_output.resolve() != args.output.resolve()
            report['art_source'] = package_art_source(args.art_source, args.art_output)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
