#!/usr/bin/env python3
"""Publish verified immutable tarballs with explicit tags; download to verify."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
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


def publish(version, defer_verification=False):
    item = next(i for i in CATALOG['versions'] if i['version'] == version)
    release = json.loads((ROOT / 'dist' / version / 'release.json').read_text())
    verification = json.loads((ROOT / 'verification' / f'{version}.json').read_text())
    tgz = ROOT / release['tarball']
    assert hashlib.sha256(tgz.read_bytes()).hexdigest() == verification['tarballSha256'] == release['sha256']
    remote = remote_version(version)
    submitted = ROOT / 'verification' / f'{version}-submitted.json'
    if submitted.exists():
        assert json.loads(submitted.read_text())['sha256'] == release['sha256']
    if remote is None and not submitted.exists():
        subprocess.run(['npm', 'publish', str(tgz), '--access=public', '--tag=' + item['defaultTag'], '--registry=' + REGISTRY, '--ignore-scripts'], check=True)
        submitted.write_text(json.dumps({'version': version, 'sha256': release['sha256'], 'accepted': True}) + '\n')
    if remote is None:
        if defer_verification:
            print(f'{version}: accepted; final download verification pending', flush=True)
            return
        # npm may accept a publish before the registry exposes its metadata.
        for attempt in range(60):
            remote = remote_version(version)
            if remote is not None:
                break
            if attempt % 6 == 0:
                print(f'{version}: npm accepted publication; waiting for registry availability', flush=True)
            time.sleep(10)
    assert remote is not None, 'npm accepted publication but metadata is still unavailable; check before retrying'
    assert remote['dist']['integrity'] == release['integrity'], 'Remote version differs; do not overwrite'
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
    parser.add_argument('--batch', action='store_true', help='Submit versions first, then verify every remote tarball')
    args = parser.parse_args()
    identity = subprocess.check_output(['npm', 'whoami', '--registry=' + REGISTRY], text=True).strip()
    assert identity == 'sumrian', f'Expected npm user sumrian, got {identity}'
    for version in args.versions:
        publish(version, defer_verification=args.batch)
    if args.batch:
        for version in args.versions:
            publish(version)
