#!/usr/bin/env python3
"""Attach the verified release and original source bytes to a GitHub release."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = 'sumrian/swarm'


def release(version):
    catalog = json.loads((ROOT / 'releases/sources.json').read_text())
    item = next(x for x in catalog['versions'] if x['version'] == version)
    result = json.loads((ROOT / 'dist' / version / 'release.json').read_text())
    verified = json.loads((ROOT / 'verification' / f'{version}.json').read_text())
    tarball = ROOT / result['tarball']
    assert hashlib.sha256(tarball.read_bytes()).hexdigest() == result['sha256'] == verified['tarballSha256']
    source = ROOT / 'cache' / f"{item['sourceName']}-{item['sourceVersion']}.tgz"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == item['sourceSha256']
    assets = ROOT / 'dist' / version / 'github'
    assets.mkdir(exist_ok=True)
    shutil.copyfile(source, assets / ('source-' + source.name))
    shutil.copyfile(tarball, assets / tarball.name)
    shutil.copyfile(ROOT / 'verification' / f'{version}.json', assets / 'verification.json')
    shutil.copyfile(ROOT / 'dist' / version / 'release.json', assets / 'release.json')
    files = sorted(p for p in assets.iterdir() if p.is_file() and p.name != 'SHA256SUMS')
    (assets / 'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in files))
    tag = 'v' + version
    subprocess.run(['git', 'rev-parse', '--verify', 'refs/tags/' + tag], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    notes = ROOT / 'dist' / version / 'release-notes.md'
    notes.write_text(f'''Swarm `{version}` — independent repack of `{item['sourceName']}@{item['sourceVersion']}`.

npm: `@sumrian/swarm@{version}`; command: `swarm`.

Native daemon bytes are unchanged from the source artifact. Only package metadata, CLI display text and documentation are renamed; runtime protocols and installation paths retain upstream behavior. Set `AUTOWONDER_AUTO_UPDATE=false` to disable upstream automatic polling updates.

Included: Swarm package, byte-original source package, checksums, build result and local packaging verification. Verification covers macOS ARM64 offline installation, CLI help and daemon self-check, not live provider/server workflows or all platforms. Historical known issues remain documented in the repository README.

Source SHA-256: `{item['sourceSha256']}`.
Swarm SHA-256: `{result['sha256']}`.

Default npm latest is deliberately 0.2.150. This release is not an official Alibaba Cloud release.
''')
    existing = json.loads(subprocess.check_output(['gh', 'api', f'repos/{REPO}/releases?per_page=100'], text=True))
    current = next((r for r in existing if r['tag_name'] == tag), None)
    if current:
        remote_assets = {a['name']: a for a in current['assets']}
        local_assets = {p.name: p for p in assets.iterdir() if p.is_file()}
        assert set(remote_assets) <= set(local_assets), 'Unexpected remote assets; manual review required'
        for name, asset in remote_assets.items():
            expected = 'sha256:' + hashlib.sha256(local_assets[name].read_bytes()).hexdigest()
            assert asset['state'] == 'uploaded' and asset.get('digest') == expected, f'Existing asset differs: {tag}/{name}'
        missing = [str(p) for name, p in local_assets.items() if name not in remote_assets]
        if missing:
            assert current['draft'], 'Published release is incomplete; manual review required'
            subprocess.run(['gh', 'release', 'upload', tag, '--repo', REPO] + missing, check=True)
        if current['draft']:
            subprocess.run(['gh', 'release', 'edit', tag, '--repo', REPO, '--draft=false', '--latest=true' if version == '0.2.150' else '--latest=false'], check=True)
        print(f'{version}: existing GitHub release assets verified', flush=True)
        return
    cmd = ['gh', 'release', 'create', tag, '--repo', REPO, '--verify-tag', '--title', 'Swarm ' + version, '--notes-file', str(notes), '--latest=true' if version == '0.2.150' else '--latest=false']
    if '-sy.' in version:
        cmd.append('--prerelease')
    cmd += [str(p) for p in sorted(assets.iterdir()) if p.is_file()]
    subprocess.run(cmd, check=True)
    print(f'{version}: GitHub release uploaded', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('versions', nargs='+')
    args = parser.parse_args()
    for version in args.versions:
        lock = ROOT / 'dist' / version / '.github-release.lock'
        with lock.open('w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            release(version)
