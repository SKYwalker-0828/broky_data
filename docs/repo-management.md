# 仓库管理与访问控制

本文记录 `broky_data` 的仓库管理方式、token 权限、轮换与审计流程。**不要在本文件中存放任何密钥。**

## 1. 角色与权限

| 角色 | GitHub 权限 | 用途 |
|---|---|---|
| Owner | Admin | 最终控制、计费、转移/删除 |
| 维护者 | Maintain | 日常设置、Issue/PR 管理 |
| 开发者 | Write | 推送分支、开 PR |
| 审阅者 | Read / Triage | 查看、Issue 分诊 |

添加协作者：Settings → Collaborators → Add people；对方接受邀请后生效。

## 2. 自动化 token（完整版）

使用 fine-grained PAT，限定到本仓库：

- Resource owner：`SKYwalker-0828`
- Repository access：Only select repositories → `broky_data`
- Expiration：90 天（到期轮换）

| 权限 | 级别 | 用途 |
|---|---|---|
| Metadata | Read | 必选（GitHub 自动勾选） |
| Contents | Read and write | 代码、分支、tag、release |
| Issues | Read and write | Issue |
| Pull requests | Read and write | PR |
| Actions | Read and write | CI |
| Workflows | Read and write | 修改 workflow 文件 |
| Commit statuses | Read and write | 提交状态 |
| Administration | Read and write | 协作者、分支保护、仓库设置 |
| Secrets | Read and write | Actions secrets |
| Webhooks | Read and write | Webhook |
| Environments | Read and write | 部署环境 |
| Deployments | Read and write | 部署记录 |
| Pages | Read and write | Pages（如启用） |
| Packages | Read and write | Packages（如启用） |
| Projects | Read and write | Projects（如启用） |
| Discussions | Read and write | Discussions（如启用） |

账户级权限一律不授予；不要授予 `delete_repo`、`admin:org`。

## 3. 本机存放

```bash
mkdir -p ~/.config/broky_data && chmod 700 ~/.config/broky_data
# 手动创建 token 后：
printf '%s' 'github_pat_xxx' > ~/.config/broky_data/gh_token
chmod 600 ~/.config/broky_data/gh_token
```

使用：

```bash
export GH_TOKEN="$(cat ~/.config/broky_data/gh_token)"
gh auth status   # 可能提示 scope 缺失，但 gh api / git 仍可用
```

不要：
- 写入仓库或 `.git/config`
- 贴在 Issue/PR/聊天记录
- 提交到 shell 历史（使用 `read -s` 或编辑器写文件）

## 4. 轮换与撤销

- 每 90 天轮换：GitHub → Settings → Developer settings → Fine-grained tokens → 重新生成，更新本机文件，撤销旧 token。
- 泄露时立即撤销，并检查 `git log`、Actions 日志、最近的 push。
- 离职/交接：撤销 token，移除 collaborator，审计最近 30 天操作。

## 5. 分支保护

`main` 建议配置：

- Require a pull request before merging（solo 仓库审批数可设 0）
- Dismiss stale approvals
- Require conversation resolution
- Block force pushes
- Prevent branch deletion
- Enforce for administrators
- 有 CI 后再加 required status checks

脚本：`scripts/protect-main.sh`（使用 `GH_TOKEN` 调用 GitHub API）。

> **当前状态（2026-11-07）：** 本仓库是 GitHub Free 账户下的私有仓库，分支保护与 repository rulesets 的 API 均返回 403（"Upgrade to GitHub Pro or make this repository public"）。在升级 GitHub Pro 或转为公开仓库之前，服务端无法强制 PR/禁 force push；只能依靠 `AGENTS.md` 的流程约定与代理自律。转公开前必须先决定项目许可证。

## 6. 审计

```bash
git log --oneline --decorate -20
gh api repos/SKYwalker-0828/broky_data/commits --paginate
gh api repos/SKYwalker-0828/broky_data/collaborators
```

## 7. 备选：GitHub App

若需要更长期的无人值守管理，改用 GitHub App：

- 安装到仅 `broky_data`
- 权限与上表一致
- 保存 App ID + 私钥（600，仓库外）
- 每次会话用私钥换 1 小时 installation token

私钥比 PAT 更敏感，需放入系统密钥环或受控文件。
