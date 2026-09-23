#!/usr/bin/env python3
"""Check published release assets against locally verified bytes."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
remote = json.loads(subprocess.check_output(['gh', 'api', 'repos/sumrian/swarm/releases?per_page=100'], text=True))
by_tag = {r['tag_name']: r for r in remote}
results = []
for item in json.loads((ROOT / 'releases/sources.json').read_text())['versions']:
    version = item['version']
    release = by_tag.get('v' + version)
    assert release and not release['draft'], f'{version}: missing or still draft'
    assert release['prerelease'] == ('-sy.' in version)
    assets = {a['name']: a for a in release['assets']}
    local = ROOT / 'dist' / version / 'github'
    assert len(assets) == len(list(local.iterdir())), f'{version}: unexpected asset count'
    for file in local.iterdir():
        asset = assets[file.name]
        expected = 'sha256:' + hashlib.sha256(file.read_bytes()).hexdigest()
        assert asset['state'] == 'uploaded' and asset['size'] == file.stat().st_size
        assert asset.get('digest') == expected, f'{version}/{file.name}: digest mismatch or unavailable'
    results.append({'version': version, 'url': release['html_url'], 'assetsSha256Verified': True})
latest = json.loads(subprocess.check_output(['gh', 'api', 'repos/sumrian/swarm/releases/latest'], text=True))
assert latest['tag_name'] == 'v0.2.150', latest['tag_name']
(ROOT / 'verification/github-published.json').write_text(json.dumps(results, indent=2) + '\n')
print(f'PASS: {len(results)} published GitHub releases and all asset digests; latest=v0.2.150')
