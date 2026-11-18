"""Optional derivative rebuild from the preserved v5 source (requires Pillow)."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True, help='v5 source folder containing assets/')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
manifest_path = root / 'manifest.json'
manifest = json.loads(manifest_path.read_text())
for asset in manifest['assets']:
    data = (args.source / asset['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == asset['source_sha256'], asset['file']
    im = Image.open(args.source / asset['file']).convert('RGB')
    assert im.size == tuple(asset['source_dimensions'][k] for k in ('width', 'height'))
    im = im.resize((asset['width'], asset['height']), Image.Resampling.LANCZOS)
    dest = root / asset['file']
    im.save(dest, format='WEBP', quality=manifest['export']['quality'], method=6)
    asset['bytes'] = dest.stat().st_size
    asset['sha256'] = hashlib.sha256(dest.read_bytes()).hexdigest()
manifest['image_bytes'] = sum(a['bytes'] for a in manifest['assets'])
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print('Exported ten uncropped derivatives. Encoder versions may produce different compressed bytes.')
