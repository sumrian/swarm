# Swarm

`@sumrian/swarm` 是由 sumrian 维护的 AutoWonder 运行时独立发行。命令名为 `swarm`。它不是阿里云官方发行，也不代表对所有历史版本的稳定性认证。

## 使用

默认发布目标：`latest` → **0.2.150**。建议始终固定具体版本：

```bash
AUTOWONDER_AUTO_UPDATE=false npx -y @sumrian/swarm@0.2.150 connect \
  --ws-url '<服务端地址>' --token '<执行器令牌>' --executor-id '<执行器 ID>' --provider qoder

npx -y @sumrian/swarm@0.2.150 help
```

需要全局安装时运行 `npm install -g @sumrian/swarm@0.2.150`，再使用 `swarm` 命令。Windows PowerShell 先设置 `$env:AUTOWONDER_AUTO_UPDATE = "false"`，然后执行上述 npx 命令。

## 版本与标签

| 类型 | 版本 | npm 标签 |
|---|---|---|
| 上游历史包重新分发 | 0.2.138～0.2.163，版本号与上游对应 | `archive` 指向最近一次发布的历史版本 |
| 默认上游派生版本 | 0.2.150 | `latest` 固定选择此版本，不按最大版本号自动推进 |
| 本地定制版本 | 0.2.152-sy.1，来源 0.2.152-codex.3 | `custom` |

`-sy.N` 表示同一上游基底的第 N 次定制发布，在 SemVer 中属于预发布版本。标签可移动；只有完整版本号用于精确选择。每个版本有对应 Git 标签 `v<版本>` 和 GitHub Release。

[来源版本清单](releases/sources.json) 保存每个源包的 URL、SHA-256 和上游版本。本文列的是准备发布的版本集合，实际远端发布状态以 npm 版本列表和 GitHub Releases 为准。

## 与上游的差异

- npm 包名改为 `@sumrian/swarm`，命令改为 `swarm`，帮助示例改为新的固定版本命令。
- 增加来源记录、许可证与独立发行声明；移除依赖未提供 Go 源码的上游构建脚本。
- 上游派生版的 daemon 二进制与官方源包逐字节相同，其他未修改文件的哈希记录在每包 `ORIGIN.json` 中。
- 不机械替换内部协议、MCP 工具名、环境变量、二进制文件名或内置版本。原生 daemon 自检和心跳仍报告上游版本。
- 官方派生版沿用 `~/.autowonder`、默认端口及工作区。改 npm 包名不等于运行隔离。不要同时启动两个会争用相同安装目录或端口的实例。
- 自动更新机制仍属于上游：显式设置 `AUTOWONDER_AUTO_UPDATE=false`，并控制服务端远程升级。Swarm 未实现自己的自动更新源。

原始官方归档保持不变，重新分发包不宣称与原始 `.tgz` 哈希相同。

## 已知限制

- 150/152 的 lazy checkout 有权限传递问题记录；归档不等于业务验收。
- 156～158 在允许 push 且没有分支白名单的场景存在 pre-push 空循环缺陷。没有将此结论外推到后续版本。
- 151 起官方客户端入口限制为 Qoder 系列；定制版的 Codex 支持属于本地修改。
- 160 的 checkpoint v2、162 派单清单协议、163 启动环境变量接口存在服务端配套要求，不能只依据 npm 版本号随意升级或回退。
- `0.2.152-sy.1` 只面向 macOS ARM64、Node ≥22；历史适配器版本为 codex-acp 1.10.0，历史实测 Codex CLI 为 0.153.4。它仍有上游 152 的 lazy checkout 限制。

每个 npm 包附带对应上游说明 `UPSTREAM_README.md`。本次发行验证覆盖本机安装、CLI 和原生自检，不等于真实模型、业务任务或所有平台的验证。

## 从归档重建发布包

需要 Python ≥3.12、Node/npm。原生二进制直接使用锁定哈希的已有产物，不从源码编译。

```bash
python3 scripts/build.py 0.2.150
python3 scripts/verify.py 0.2.150
```

也可读取已有本地归档（路径自行指定），无需再次下载：

```bash
python3 scripts/build.py --archive-root /path/to/autowonder-runtime-comparison
python3 scripts/verify.py
```

产物位于 `dist/<version>/`。`cache/` 和 `build/` 为可再生成目录，不进入 Git。上游源包可从每版 GitHub Release 获取；定制版源包也作为 Release 附件保存。

## 发布

见 [发布流程](docs/publishing.md)。根目录 package.json 设置为 private，防止把整个发布仓库误发到 npm；真正发布的是 `dist/` 中经过验证的版本包。

## 许可证与来源

上游 npm 元数据标注 Apache-2.0，原作者为 Alibaba Cloud。本仓库保留上游署名，提供 [Apache-2.0 许可证](LICENSE)。定制包内另保留 Codex ACP 的许可证。上游 Go 源码未包含在本仓库，因此此处提供的是可重复的 npm 重新打包流程，不是完整的原生源码构建。
