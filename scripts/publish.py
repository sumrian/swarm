#!/usr/bin/env python3
"""Publish verified immutable tarballs with explicit tags; download to verify."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = 'https://registry.npmjs.org'
CATALOG = json.loads((ROOT / 'releases/sources.json').read_text())


def remote_version(version):
    try:
        with urllib.request.urlopen(f'{REGISTRY}/@sumrian%2fswarm/{version}', timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def publish(version):
    item = next(i for i in CATALOG['versions'] if i['version'] == version)
    release = json.loads((ROOT / 'dist' / version / 'release.json').read_text())
    verification = json.loads((ROOT / 'verification' / f'{version}.json').read_text())
    tgz = ROOT / release['tarball']
    assert hashlib.sha256(tgz.read_bytes()).hexdigest() == verification['tarballSha256'] == release['sha256']
    remote = remote_version(version)
    if remote is None:
        subprocess.run(['npm', 'publish', str(tgz), '--access=public', '--tag=' + item['defaultTag'], '--registry=' + REGISTRY, '--ignore-scripts'], check=True)
        remote = remote_version(version)
    assert remote and remote['dist']['integrity'] == release['integrity'], 'Remote version differs; do not overwrite'
    with urllib.request.urlopen(remote['dist']['tarball'], timeout=120) as response:
        data = response.read()
    assert hashlib.sha256(data).hexdigest() == release['sha256'], 'Remote tarball differs'
    receipt = {'package': CATALOG['package'], 'version': version, 'sha256': release['sha256'], 'integrity': remote['dist']['integrity'], 'remoteTarball': remote['dist']['tarball'], 'downloadVerified': True}
    out = ROOT / 'verification' / f'{version}-published.json'
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'{version}: npm tarball downloaded and verified', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('versions', nargs='+')
    args = parser.parse_args()
    identity = subprocess.check_output(['npm', 'whoami', '--registry=' + REGISTRY], text=True).strip()
    assert identity == 'sumrian', f'Expected npm user sumrian, got {identity}'
    for version in args.versions:
        publish(version)
