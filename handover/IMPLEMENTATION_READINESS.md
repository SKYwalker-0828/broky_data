# 测试期实施决策与状态

此文件记录 M00–M09 的当前本地原型决定。用户已授权在测试阶段自行确定实现与模拟权限；这些选择用于打通流程，不等于生产级选型或 RelicWeave 正式契约签收。

## 实现状态

| 模块 | 当前实现 | 主要边界 |
|---|---|---|
| M00 | `contracts.py` 中的 `broky_data.*.v1` 原型字段/状态 | 不是既有 PG-Frag/MEHR canonical schema 的替代品 |
| M01 | SHA-256 文件对象；Observation、Truth 分开目录；POSIX 私有目录权限 | 本机用户级权限，不含加密、备份、对象存储或跨主机 ACL |
| M02 | SQLite 来源登记；审核独立更新授权与用途 | 本地数据库；不部署 Arches；证据引用格式正确不等于法律审核完成 |
| M03 | 标准库规则检查、资产摘要核验、用途/分区/资格门禁 | 不解析图像/3D 内容，不判断考古或物理真实性 |
| M04 | SQLite 元数据 + 内容 hash + JSON manifest；Truth 只允许 evaluation 快照 | 文件系统目录分区与应用 ACL，不构成隔离执行环境；join 不包含样本配对 |
| M05 | SQLite 追加式人工决策，R2 双向记录且无传递闭包 | 不验证完整 R2 物理证据条件或 Arches/MEHR 往返映射 |
| M06 | 调用方提供向量；SQLite 保存不可变版本的精确 cosine 索引 | 无模型推理、FAISS、性能优化或大规模负载保证 |
| M07 | SQLite 聚合；按用途呈现 assessed/not_assessed/outcomes | 指标和敏感小样本政策尚为测试口径，无看板 |
| M08 | 内部 HTML 标本卡和概览报告，输出按内容 hash 版本化 | 无批准模板、PDF、Scribus 交接或外部发布能力 |
| M09 | JSON 质量/功能收据、SQLite 哈希链审计日志 | 无签名、外部不可变日志、正式阈值或独立签署 |

## 工具和许可证

当前实现只使用本仓库代码与 Python 标准库；没有集成 Arches、OpenRefine、Frictionless、DVC、FAISS、DuckDB、Superset、WeasyPrint 或 Scribus，因此当前运行路径没有这些第三方运行依赖。候选项目的上游许可证信息仍见 [LICENSE_REGISTER.md](../LICENSE_REGISTER.md)。项目自身许可证未决定。

## 可运行性验证

当前全量测试为 24 项；包括合成端到端演练、Observation/Truth 越权检查、旧 SQLite 搜索向量迁移保留与迁移失败回滚。CLI `--help` 和 Python 字节码编译检查通过。操作入口仅为 CLI，没有图形管理界面；测试身份由调用者传入，不可作为生产认证。

## 正式启用

正式启用需要完成的不只是补 schema，还包括身份认证、Truth/GT 独立安全边界、正式领域校验、真实关系证据规则、生产存储/恢复、审计签名、模板权利、统计披露规则和验收签署。逐项改造要求见 [PRE_PRODUCTION_READINESS.md](../PRE_PRODUCTION_READINESS.md)。
