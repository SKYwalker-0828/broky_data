# AGENTS.md

本文件为在此仓库中工作的自动化代理（含 AI agent）提供操作规范。人类贡献者也可参考。

## 仓库性质

- M00–M09 已有本地测试期原型，入口为 `python3 -m broky_data`；它不是生产系统。
- 原型 schema、SQLite、角色策略、精确 cosine、HTML 模板和验收阈值均为本仓库 `v1` 测试期决定，不得描述为 RelicWeave 正式契约或业务签收。
- 命令行 `--role` 是可伪造的模拟身份；不得用于真实多人或远程环境。Truth/GT 与 Observation 目录分开，但不构成独立主机/密钥级隔离。
- 项目自身许可证未决定；不要添加 `LICENSE`，不要宣称本项目采用某一许可证。
- 不得把本地文件、SQLite、哈希链或应用 ACL 当作生产级权限、加密、备份或不可篡改保证。

## 代码与测试

- 当前代码位于 `src/broky_data/`，测试位于 `tests/`；应用目标为 Python 3.10+ 标准库，不添加未登记的第三方运行依赖。
- Python 使用四空格缩进、类型标注和 `snake_case`；测试文件命名为 `test_<area>.py`，测试方法以 `test_` 开头。
- 修改前先读对应模块交接文档。新增测试期字段要升级/版本化原型契约并同步 [正式启用前改造清单](PRE_PRODUCTION_READINESS.md)；不要从 PG-Frag 等项目导入其内部实现，也不要把原型 schema 写成上游 canonical schema。
- 运行全套测试：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v`。
- 运行合成端到端演练：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m broky_data --root ./local-data demo --output-dir ./demo-output`。

## 分支与合并

- `main` 应配置为受保护分支：禁止直接 push、force push 和删除；在保护生效前也应遵守同样约束。
- 当前私有仓库受 GitHub Free 计划限制，服务端分支保护/rulesets 不可用（API 403）；在升级 Pro 或转公开前，必须自觉走分支 + PR，不直接推 `main`。
- 所有改动走短生命周期分支 + Pull Request。
- 分支命名：`docs/<topic>`、`feat/<topic>`、`fix/<topic>`、`chore/<topic>`。
- PR 合并前至少完成：本地自查、链接检查、与现有文档术语一致。
- 合并方式优先 squash；保持 `main` 线性历史。

## 提交信息

使用 Conventional Commits 风格：

```
<type>(<scope>): <summary>
```

常用 type：`docs`、`feat`、`fix`、`chore`、`refactor`。
示例：`docs(handover): clarify M04 snapshot boundary`

- 一次提交只做一件事。
- 不提交生成物、缓存、密钥或本地路径。

## 敏感信息

- 严禁把 token、私钥、`.env`、凭据写入仓库、提交信息或 PR 描述。
- 本机凭据存放在 `~/.config/broky_data/gh_token`（权限 600），通过 `GH_TOKEN` 注入命令。
- 发现凭据泄露：立即在 GitHub 撤销，并清理历史/日志。

## 文档约定

- 文档使用中文；代码、命令、字段名保留英文。
- 新增架构判断时，注明依据与不确定性；不要把候选工具写成选型结论。
- 修改 `ARCHITECTURE.md`、`REVIEW.md`、`LICENSE_REGISTER.md` 时同步检查 README 的文件导航和模块表。
- 许可证相关表述必须区分“工程边界”与“法律结论”。

## 代理操作边界

- 未经明确指示，不执行：删除仓库、转移所有权、修改可见性、强制推送、重写 `main` 历史。
- 执行破坏性操作前必须在对话中说明影响并取得确认。
- 每次操作后报告：改动的文件、提交、推送结果、遗留问题。

## 验证

提交前至少执行：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
git diff --check
git status --short
```
