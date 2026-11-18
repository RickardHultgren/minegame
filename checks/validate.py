"""Offline structural and asset checks; Python standard library only."""
from pathlib import Path
import hashlib
import json
import re
import struct

ROOT = Path(__file__).resolve().parents[1]


def dimensions(data):
    assert data[:4] == b'RIFF' and data[8:12] == b'WEBP'
    offset = 12
    while offset + 8 <= len(data):
        kind = data[offset:offset + 4]
        size = int.from_bytes(data[offset + 4:offset + 8], 'little')
        chunk = data[offset + 8:offset + 8 + size]
        if kind == b'VP8X':
            return (1 + int.from_bytes(chunk[4:7], 'little'),
                    1 + int.from_bytes(chunk[7:10], 'little'))
        if kind == b'VP8 ':
            assert chunk[3:6] == b'\x9d\x01\x2a'
            return tuple(n & 0x3fff for n in struct.unpack('<HH', chunk[6:10]))
        offset += 8 + size + (size & 1)
    raise AssertionError('Unsupported WebP dimensions')


def validate():
    html = (ROOT / 'index.html').read_text()
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    art = json.loads(re.search(r'<script id="art-data"[^>]*>(.*?)</script>', html, re.S)[1])
    cards = re.findall(r'<p class="story">(.*?)</p>', html)
    assert cards == [
        'They came for the views.',
        '“They say this mine was dug for goblin treasure.”',
        'A good story. A better livestream.',
        'Nobody wanted to turn back first.',
        'The camera kept rolling.',
    ]
    durations = [int(v) for v in re.findall(r'data-duration="(\d+)"', html)]
    assert durations == [3000, 5000, 5000, 4000, 3000, 4000, 3000, 4000, 3000, 6000]
    assert sum(durations) == manifest['total_ms'] == 40000
    assert list(art) == ['live', 'legend', 'cut', 'gap', 'descent']
    assert len(manifest['assets']) == 10
    assert not manifest['audio_enabled']
    assert not re.search(r'AudioContext|Oscillator|<audio|data:image|https?://|fetch\(|@import|setInterval|setTimeout', html)
    assert 'object-fit:contain' in html and 'overflow:hidden' in html
    assert 'min-height:44px' in html and 'min-width:44px' in html
    assert 'prefers-reduced-motion' in html and 'safe-area-inset' in html
    assert "new CustomEvent('minegame:start'" in html
    assert 'scene-status' in html and 'aria-hidden' in html
    assert len(re.findall(r'\.addEventListener\(', html)) < 25
    total = 0
    for asset in manifest['assets']:
        p = ROOT / asset['file']
        data = p.read_bytes()
        assert hashlib.sha256(data).hexdigest() == asset['sha256'], p
        assert len(data) == asset['bytes']
        assert dimensions(data) == (asset['width'], asset['height'])
        assert art[asset['key']][asset['orientation']] == asset['file']
        assert len(asset['source_sha256']) == 64
        total += len(data)
    assert set(p.name for p in (ROOT / 'assets').iterdir()) == {Path(a['file']).name for a in manifest['assets']}
    assert total == manifest['image_bytes']
    managed_pixels = sorted(a['width'] * a['height'] for a in manifest['assets'])
    original_pixels = sum(a['source_dimensions']['width'] * a['source_dimensions']['height'] for a in manifest['assets'])
    report = {
        'status': 'passed', 'release': 'v6_lite', 'total_ms': sum(durations),
        'image_count': 10, 'image_bytes': total, 'html_bytes': (ROOT / 'index.html').stat().st_size,
        'runtime_file_bytes': total + (ROOT / 'index.html').stat().st_size,
        'max_owned_rgba_pixel_bytes_estimate': sum(managed_pixels[-2:]) * 4,
        'previous_ten_image_rgba_pixel_bytes_estimate': original_pixels * 4,
        'memory_limit': 'Pixel arithmetic only; excludes browser caches, GPU copies, JS/DOM and decoder working buffers. Not measured native RAM.',
        'html_sha256': hashlib.sha256((ROOT / 'index.html').read_bytes()).hexdigest(),
    }
    (ROOT / 'file_checks.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
