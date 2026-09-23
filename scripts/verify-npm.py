#!/usr/bin/env python3
"""Verify registry versions, tags, and receipts from downloaded npm tarballs."""
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
with urllib.request.urlopen('https://registry.npmjs.org/@sumrian%2fswarm', timeout=30) as response:
    remote = json.load(response)
expected_tags = {'latest': '0.2.150', 'archive': '0.2.163', 'custom': '0.2.152-sy.1'}
for tag, version in expected_tags.items():
    assert remote['dist-tags'].get(tag) == version, f'{tag}: unexpected version'
results = []
for release in json.loads((ROOT / 'releases/artifacts.json').read_text())['releases']:
    version = release['version']
    metadata = remote['versions'].get(version)
    assert metadata, f'{version}: registry version unavailable'
    assert metadata['dist']['integrity'] == release['integrity'], f'{version}: integrity mismatch'
    receipt = json.loads((ROOT / 'verification' / f'{version}-published.json').read_text())
    assert receipt['downloadVerified'] and receipt['sha256'] == release['sha256']
    assert receipt['integrity'] == metadata['dist']['integrity']
    assert receipt['remoteTarball'] == metadata['dist']['tarball']
    results.append(receipt)
(ROOT / 'verification/npm-published.json').write_text(json.dumps({'tags': expected_tags, 'versions': results}, indent=2) + '\n')
print(f'PASS: {len(results)} npm versions, downloaded tarball hashes, and all release tags')
