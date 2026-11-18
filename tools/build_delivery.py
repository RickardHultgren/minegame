"""Check and package the editable lightweight folder; no runtime dependency."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=ROOT.parent / 'mine_game_intro_v6_lite.zip')
args = parser.parse_args()
subprocess.run([sys.executable, str(ROOT / 'checks/validate.py')], check=True)
with tempfile.TemporaryDirectory() as temporary:
    html = (ROOT / 'index.html').read_text()
    js = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', html, re.S)[-1]
    script = Path(temporary) / 'runtime.js'
    script.write_text(js)
    subprocess.run(['node', '--check', str(script)], check=True)
subprocess.run(['node', str(ROOT / 'checks/runtime_checks.mjs')], check=True)
files = sorted(p for p in ROOT.rglob('*') if p.is_file()
               and not set(p.parts).intersection({'__pycache__', '.git'})
               and p.suffix not in {'.zip', '.pyc'})
args.output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for p in files:
        info = zipfile.ZipInfo(p.relative_to(ROOT).as_posix(), date_time=(2026, 11, 18, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, p.read_bytes(), compresslevel=9)
with zipfile.ZipFile(args.output) as archive:
    assert archive.testzip() is None
    assert len([n for n in archive.namelist() if n.startswith('assets/')]) == 10
    assert not any(n.endswith('.png') or 'backup' in n.lower() for n in archive.namelist())
report = {'file': str(args.output), 'bytes': args.output.stat().st_size,
          'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(), 'files': len(files), 'integrity': 'passed'}
print(json.dumps(report, indent=2))
