#!/usr/bin/env python3
"""Repackage pinned upstream artifacts; never builds or changes native daemons."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'releases/sources.json').read_text())
PACKAGE = CATALOG['package']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rename_commands(text, version):
    text = re.sub(r'npx -y --package=/[^\s]+\.tgz\s*\\\n\s*autowonder connect', f'npx -y {PACKAGE}@{version} connect', text)
    text = re.sub(r'\bnpx\s+(?:-y\s+)?autowonder(?:@[\w.\-]+)?(?=\s)', f'npx -y {PACKAGE}@{version}', text)
    text = re.sub(r'\bautowonder(?=\s+(?:connect|start|stop|status|dispatch|install|workitem|scheduled-task|help)\b)', 'swarm', text)
    text = text.replace('autowonder —', 'swarm —')
    return text


def source_archive(item, archive_root):
    cache = ROOT / 'cache' / f"{item['sourceName']}-{item['sourceVersion']}.tgz"
    cache.parent.mkdir(exist_ok=True)
    if not cache.exists():
        local = None
        if archive_root:
            if item['kind'] == 'upstream-repack':
                local = archive_root / item['sourceVersion'] / 'package.tgz'
            else:
                local = archive_root / 'codex-patch/dist' / f"{item['sourceName']}-{item['sourceVersion']}.tgz"
        temporary = cache.with_suffix('.partial')
        if local and local.is_file():
            shutil.copyfile(local, temporary)
        else:
            with urllib.request.urlopen(item['sourceUrl'], timeout=120) as response:
                temporary.write_bytes(response.read())
        if digest(temporary) != item['sourceSha256']:
            temporary.unlink()
            raise ValueError(f"Source digest mismatch: {item['version']}")
        temporary.replace(cache)
    assert digest(cache) == item['sourceSha256'], 'Cached source changed'
    if item.get('sourceIntegrity'):
        sri = 'sha512-' + base64.b64encode(hashlib.sha512(cache.read_bytes()).digest()).decode()
        assert sri in item['sourceIntegrity'].split(), 'Source npm integrity mismatch'
    return cache


def build(item, archive_root):
    version = item['version']
    archive = source_archive(item, archive_root)
    stage = ROOT / 'build' / version
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    with tarfile.open(archive) as source:
        members = source.getmembers()
        for member in members:
            p = Path(member.name)
            assert not p.is_absolute() and '..' not in p.parts and p.parts[0] == 'package'
            assert member.isfile() or member.isdir(), f'Unexpected archive entry: {member.name}'
        source.extractall(stage, filter='data')
    package = stage / 'package'
    original = json.loads((package / 'package.json').read_text())
    assert original['name'] == item['sourceName'] and original['version'] == item['sourceVersion']
    assert original['license'] == 'Apache-2.0'
    original_files = {str(p.relative_to(package)): digest(p) for p in package.rglob('*') if p.is_file()}
    # These upstream build scripts require the unavailable upstream Go source tree.
    # Our own build recipe lives in GitHub; the runtime package includes no lifecycle scripts.
    shutil.rmtree(package / 'scripts', ignore_errors=True)
    for p in (package / 'bin').glob('*.js'):
        content = p.read_text()
        changed = rename_commands(content, version)
        if p.name == 'shared.js':
            changed = changed.replace('[autowonder]', '[swarm]')
        if changed != content:
            notice = '// Modified by sumrian: npm package/CLI display names only; runtime protocol unchanged.\n'
            if changed.startswith('#!'):
                line, rest = changed.split('\n', 1)
                changed = line + '\n' + notice + rest
            else:
                changed = notice + changed
            p.write_text(changed)
    upstream_readme = package / 'README.md'
    if upstream_readme.exists():
        (package / 'UPSTREAM_README.md').write_text('<!-- Modified by sumrian: command examples use @sumrian/swarm; other upstream behavior retained. -->\n' + rename_commands(upstream_readme.read_text(), version))
    metadata = {k: v for k, v in original.items() if k in ('engines', 'os', 'cpu', 'dependencies', 'optionalDependencies', 'license', 'author')}
    metadata.update({'name': PACKAGE, 'version': version, 'description': f'Swarm: independent repack of {item["sourceName"]}@{item["sourceVersion"]}', 'bin': {'swarm': 'bin/cli.js'}, 'files': ['bin/', 'lib/', 'vendor/', 'README.md', 'UPSTREAM_README.md', 'LICENSE', 'NOTICE', 'ORIGIN.json', 'PATCH-MANIFEST.json'], 'repository': {'type': 'git', 'url': 'git+https://github.com/sumrian/swarm.git'}, 'homepage': 'https://github.com/sumrian/swarm#readme', 'bugs': {'url': 'https://github.com/sumrian/swarm/issues'}, 'publishConfig': {'access': 'public', 'registry': 'https://registry.npmjs.org/', 'tag': item['defaultTag']}, 'x-swarm-modifications': 'Package metadata, command examples and display names changed by sumrian. Native daemon unchanged from source artifact.'})
    (package / 'package.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n')
    shutil.copyfile(ROOT / 'LICENSE', package / 'LICENSE')
    existing_notice = (package / 'NOTICE').read_text() if (package / 'NOTICE').exists() else ''
    (package / 'NOTICE').write_text(existing_notice + '\nSwarm distribution maintained by sumrian.\nUpstream AutoWonder package author: Alibaba Cloud.\nUpstream npm metadata declares Apache-2.0.\nThis is an independent redistribution, not an official Alibaba Cloud release.\nModified files and byte-preserved native binaries are recorded in ORIGIN.json.\nThe upstream Go source is not included; this repository reproduces the npm repack, not a native source build.\n' + ('Codex ACP adapter license is preserved at lib/codex-acp/LICENSE.\n' if item['kind'] == 'custom-repack' else ''))
    (package / 'README.md').write_text(readme(item))
    current_files = {str(p.relative_to(package)): digest(p) for p in package.rglob('*') if p.is_file()}
    native = {p: h for p, h in original_files.items() if p.startswith('vendor/')}
    assert native and all(current_files.get(p) == h for p, h in native.items()), 'Native binary changed'
    provenance = dict(item)
    provenance.update({'package': PACKAGE, 'nativeFilesSha256': native, 'modifiedFiles': sorted(p for p, h in current_files.items() if original_files.get(p) != h), 'removedFiles': sorted(set(original_files) - set(current_files)), 'unchangedFilesSha256': {p: h for p, h in original_files.items() if current_files.get(p) == h}})
    (package / 'ORIGIN.json').write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + '\n')
    dest = ROOT / 'dist' / version
    dest.mkdir(parents=True, exist_ok=True)
    packed = json.loads(subprocess.check_output(['npm', 'pack', '--ignore-scripts', '--json', '--pack-destination', str(dest)], cwd=package, text=True))
    tarball = dest / packed[0]['filename']
    result = {'version': version, 'sourceSha256': item['sourceSha256'], 'tarball': str(tarball.relative_to(ROOT)), 'sha256': digest(tarball), 'integrity': packed[0]['integrity'], 'fileCount': len(packed[0]['files']), 'bytes': tarball.stat().st_size}
    (dest / 'SHA256SUMS').write_text(f"{result['sha256']}  {tarball.name}\n")
    (dest / 'release.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f"{version}: packed {result['fileCount']} files; native hashes unchanged", flush=True)
    return result


def readme(item):
    v = item['version']
    custom = item['kind'] == 'custom-repack'
    extra = '\n定制版来自本地 0.2.152-codex.3，发布版本映射为 0.2.152-sy.1。仅 macOS ARM64；Node.js ≥22。历史测试使用 Codex CLI 0.153.4 和 codex-acp 1.10.0，包含同步/异步提问。它保留上游 152 的 lazy checkout 已知限制；本次重新打包不等于重新验证所有模型或服务端组合。\n' if custom else '\n上游派生版本保留原版本号。包名、命令及帮助示例经过改名，daemon 二进制逐文件哈希与原包一致。\n'
    return f'''# @sumrian/swarm {v}

独立发行的 AutoWonder 本地运行时；上游来源：`{item['sourceName']}@{item['sourceVersion']}`。不是阿里云官方发行或稳定性认证。
{extra}
## 安装与运行

```bash
AUTOWONDER_AUTO_UPDATE=false npx -y @sumrian/swarm@{v} connect --ws-url '<服务端地址>' --token '<执行器令牌>' --executor-id '<执行器ID>' --provider {'codex' if custom else 'qoder'}
```

也可 `npm install -g @sumrian/swarm@{v}` 后使用 `swarm help`。首次使用请固定版本。`latest` 的发布目标为 0.2.150；`archive` 和 `custom` 是可移动标签，不能用于精确锁定。

Windows PowerShell（官方派生版本）：

```powershell
$env:AUTOWONDER_AUTO_UPDATE = "false"
npx -y @sumrian/swarm@{v} help
```

## 行为与限制

- 仅将 npm 包名和对外 CLI 命令改为 Swarm。协议字段、MCP 工具名、环境变量 `AUTOWONDER_*`、二进制文件名与内置版本保持上游值。
- 官方派生版沿用 `~/.autowonder` 安装路径、默认 API 端口与工作区；定制版沿用自身安装路径。改包名不实现并行隔离，切换前先处理运行中的任务并停止对应旧进程。
- 官方 daemon 自动更新仍可能查询官方 autowonder 渠道；启动时显式设置 `AUTOWONDER_AUTO_UPDATE=false`。该变量不保证阻止服务端发起的远程升级。此发行版没有新增 Swarm 自动更新器。
- 所需 Node/provider CLI 与登录前提见 UPSTREAM_README.md；某些上游包 engines 声明 Node ≥16，但 Qoder 启动要求 Node ≥20，以实际 provider 要求为准。
- 156～158 在允许 push 且无分支白名单时有已知 pre-push 空循环缺陷；150/152 有 lazy checkout 权限问题记录。升级还须考虑服务端协议及 checkpoint 兼容性。
- 官方派生版包含六个平台产物，但此次只做本机发行包验证，不承诺全平台业务验证。定制版仅支持其 package.json 指定平台。

## 来源与校验

源包 SHA-256：`{item['sourceSha256']}`。
`ORIGIN.json` 记录来源、修改清单和逐文件哈希；LICENSE/NOTICE 保留归属。完整发行材料及发布说明：[sumrian/swarm](https://github.com/sumrian/swarm)。
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('versions', nargs='*', help='Default: all catalog versions')
    parser.add_argument('--archive-root', type=Path, help='Optional existing local archive; no files there are changed')
    args = parser.parse_args()
    selected = [i for i in CATALOG['versions'] if not args.versions or i['version'] in args.versions]
    assert selected and (not args.versions or len(selected) == len(set(args.versions))), 'Unknown/duplicate version'
    results = [build(item, args.archive_root) for item in selected]
    (ROOT / 'dist/build-results.json').write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    main()
