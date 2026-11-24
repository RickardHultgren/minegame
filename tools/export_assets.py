"""Reproduce only the eight selected v7 derivatives; requires Pillow, never runtime."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NEW_KEYS = {'warning', 'giveway', 'slide', 'below'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--originals', type=Path,
                        default=ROOT.parent / 'mine_intro_v7_fall_no_light_eye_fix_art_source/originals',
                        help='Separate folder containing the eight selected 05–08 native PNGs')
    parser.add_argument('--check-only', action='store_true', help='Verify exports in memory without writing')
    args = parser.parse_args()
    manifest_bytes = (ROOT / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    baseline = json.loads((ROOT / 'production/baseline_hashes.json').read_text())
    player_hash = sha((ROOT / 'index.html').read_bytes())
    protected = baseline['protected_assets']
    selected = [a for a in manifest['assets'] if a['key'] in NEW_KEYS]
    assert len(protected) == len(selected) == 8
    for asset in protected:
        assert sha((ROOT / asset['file']).read_bytes()) == asset['sha256'], asset['file']

    # Prepare and validate every output before replacing any delivered derivative.
    # A different encoder must not silently redefine approved compressed bytes.
    prepared = []
    for asset in selected:
        assert asset['source_role'] == 'v7_fall_selected_native_png'
        original = args.originals / asset['source_file']
        assert sha(original.read_bytes()) == asset['source_sha256'], original
        with Image.open(original) as source:
            assert source.size == tuple(asset['source_dimensions'][k] for k in ('width', 'height'))
            assert asset['width'] <= source.width and asset['height'] <= source.height
            image = source.convert('RGB').resize((asset['width'], asset['height']), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format='WEBP', quality=asset['export']['quality'], method=asset['export']['method'])
        data = output.getvalue()
        assert len(data) == asset['bytes'] and sha(data) == asset['sha256'], (
            f"{asset['file']}: encoder differs from the approved export. Keep delivered bytes; "
            'inspect codec differences before any explicit new selection.'
        )
        prepared.append((ROOT / asset['file'], data))
    if not args.check_only:
        for path, data in prepared:
            path.write_bytes(data)
    for asset in protected:
        assert sha((ROOT / asset['file']).read_bytes()) == asset['sha256'], asset['file']
    assert sha((ROOT / 'index.html').read_bytes()) == player_hash
    assert (ROOT / 'manifest.json').read_bytes() == manifest_bytes
    print(json.dumps({'status': 'passed', 'selected_new_derivatives': 8,
                      'protected_old_derivatives_unchanged': 8,
                      'operation': 'verified_in_memory' if args.check_only else 'reproduced_byte_for_byte'}, indent=2))


if __name__ == '__main__':
    main()
