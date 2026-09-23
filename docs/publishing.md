# 发布流程

发布身份：GitHub `sumrian/swarm`（public）；npm `@sumrian/swarm`（public）。

## 前提

在自己的终端完成 `gh auth login`、`npm login` 和 npm 要求的 2FA。不要把 Token、登录配置、测试工作区或私有日志提交到 Git。

## 构建与验证

1. `python3 scripts/build.py <version>`：根据 sources.json 校验源包，重命名元数据和命令展示，保留 native 字节并打包。
2. `python3 scripts/verify.py <version>`：检查实际 tgz、来源哈希、文件白名单、离线安装、swarm help 和 macOS ARM64 native self-check。此步骤不连接业务服务。
3. 查看 `dist/<version>/release.json` 与 `verification/<version>.json`。不得将这些检查称为业务端到端验收。
4. 将本次构建脚本、来源清单与发行记录提交，再为该提交打 `v<version>` 标签。多个历史版本可以共享同一构建清单提交。

## npm 发布

从 root 运行以下脚本，只发布经验证的 tgz，不重打包：

```bash
python3 scripts/publish.py 0.2.150
# 多个版本先提交，再逐一下载验证，减少等待 registry 处理时认证过期的次数：
python3 scripts/publish.py --batch 0.2.151 0.2.152
```

脚本要求 npm 当前身份为 sumrian；固定写入 public registry；已存在同名版本时核对 registry integrity，发现不一致立即停止。需要 OTP 时由 npm 交互流程处理，不记录凭证。

发布标签由清单指定：仅 0.2.150 使用 latest；其他官方派生版本使用 archive；-sy.N 使用 custom。发布不可覆盖，发现内容错误必须另发新版本，不复用旧版本号。

发布后重新下载 registry tarball，与本地 SHA-256 对比。仅 npm publish 退出成功不算最终验收。

npm 接受发布后，脚本在本地 verification/ 保存 submitted 记录。中断后重跑会等待该版本可读，避免重复提交；最终以 published 记录中的下载校验结果为准。这些本地状态文件不进入 Git。

## GitHub Releases

每个版本的 Release 对应 `v<version>` 标签，附带：

- Swarm tgz、SHA256SUMS 和 release.json；
- 原始源包，命名为 `source-<sourceName>-<sourceVersion>.tgz`；
- 本次发行包 verification.json。

源包必须保持原始字节；GitHub Release 的 SHA256SUMS 同时覆盖重新分发包和源包。

0.2.152-sy.1 使用 `--prerelease`。其他历史发布使用 `--latest=false`，只有 v0.2.150 作为选定默认版本。GitHub latest 与 npm latest 分别管理。

正式使用安装后的包之前，固定版本并关闭上游自动更新；不要与原 AutoWonder 共用运行进程。已安装实例、业务任务及服务端版本迁移不由本发布流程自动操作。
