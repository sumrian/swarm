#!/usr/bin/env python3
"""Verify packed bytes and exercise the installed CLI in a temporary HOME."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def verify(version):
    release = json.loads((ROOT / 'dist' / version / 'release.json').read_text())
    tarball = ROOT / release['tarball']
    assert hashlib.sha256(tarball.read_bytes()).hexdigest() == release['sha256']
    assert 'sha512-' + base64.b64encode(hashlib.sha512(tarball.read_bytes()).digest()).decode() == release['integrity']
    with tarfile.open(tarball) as archive:
        names = archive.getnames()
        assert all(n.startswith('package/') and '..' not in Path(n).parts for n in names)
        forbidden = [n for n in names if Path(n).name in ('.npmrc', '.env', '.DS_Store') or n.endswith(('.log', '.tgz')) or n.startswith(('package/scripts/', 'package/node_modules/'))]
        assert not forbidden, forbidden
        meta = json.load(archive.extractfile('package/package.json'))
        origin = json.load(archive.extractfile('package/ORIGIN.json'))
        assert meta['name'] == '@sumrian/swarm' and meta['version'] == version
        assert meta['bin'] == {'swarm': 'bin/cli.js'} and 'scripts' not in meta and 'private' not in meta
        assert meta['publishConfig']['access'] == 'public'
        for name, expected in origin['unchangedFilesSha256'].items():
            assert hashlib.sha256(archive.extractfile('package/' + name).read()).hexdigest() == expected, name
        allowed = {'package.json', 'README.md', 'UPSTREAM_README.md', 'LICENSE', 'NOTICE', 'bin/cli.js', 'bin/shared.js', 'bin/qoder-bootstrap.js', 'bin/token-proxy.js'}
        assert set(origin['modifiedFiles']) <= allowed, origin['modifiedFiles']
        for member in archive.getmembers():
            if member.isfile() and member.name.endswith(('.js', '.md', '.json', '.mjs')):
                text = archive.extractfile(member).read().decode()
                assert '/Users/sumrian/' not in text, f'Local user path in {member.name}'
                assert not re.search(r'\bnpm_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----', text), f'Credential pattern in {member.name}'
        cli = archive.extractfile('package/bin/cli.js').read().decode()
        assert 'swarm connect' in cli and 'npx -y @sumrian/swarm@' + version in cli
        assert not re.search(r'\bnpx\s+(?:-y\s+)?autowonder(?:@[^\s]+)?\s', cli)
    with tempfile.TemporaryDirectory(prefix='swarm-verify-') as temp:
        temp = Path(temp)
        env = dict(os.environ, HOME=str(temp / 'home'), AUTOWONDER_AUTO_UPDATE='false', npm_config_cache=str(temp / 'npm-cache'))
        (temp / 'home').mkdir()
        result = subprocess.run(['npm', 'install', '--prefix', str(temp / 'install'), '--ignore-scripts', '--no-audit', '--no-fund', '--offline', str(tarball)], env=env, text=True, capture_output=True, timeout=120)
        assert result.returncode == 0, result.stderr
        entry = temp / 'install/node_modules/.bin/swarm'
        help_result = subprocess.run([str(entry), 'help'], env=env, text=True, capture_output=True, timeout=20)
        assert help_result.returncode == 0 and 'swarm connect' in help_result.stdout, help_result.stderr
        assert not (temp / 'home/.autowonder/bin').exists(), 'Help unexpectedly installed daemon'
        native_check = None
        if platform.system() == 'Darwin' and platform.machine() == 'arm64':
            binary = temp / 'install/node_modules/@sumrian/swarm/vendor/autowonder-daemon-darwin-arm64'
            check = subprocess.run([str(binary), '--self-check'], env=env, capture_output=True, text=True, timeout=20)
            assert check.returncode == 0, check.stderr
            native_check = json.loads(check.stdout)
            assert native_check['version'] == origin['upstreamVersion'], native_check
        result = {'version': version, 'tarballSha256': release['sha256'], 'archiveAndNativeHashes': 'passed', 'offlineLocalInstall': 'passed', 'installedSwarmHelp': 'passed', 'nativeSelfCheck': native_check, 'platform': platform.platform(), 'node': subprocess.check_output(['node', '--version'], text=True).strip(), 'npm': subprocess.check_output(['npm', '--version'], text=True).strip(), 'scope': 'Packaging, unchanged-file hashes, offline install, CLI help, local native self-check. No provider login, real model calls or live server/task execution.'}
    out = ROOT / 'verification'
    out.mkdir(exist_ok=True)
    (out / f'{version}.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'{version}: PASS packed hashes + offline install + swarm help + native self-check', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('versions', nargs='*')
    args = parser.parse_args()
    versions = args.versions or [x['version'] for x in json.loads((ROOT / 'releases/sources.json').read_text())['versions']]
    for v in versions:
        verify(v)
