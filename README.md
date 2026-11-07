# broky_data

面向 RelicWeave 数据接入、治理、快照、关系审核、检索、统计、成果输出和验收的模块化本地原型。当前实现面向合成/已授权测试数据，不是生产部署。

## 当前基线

- Python 3.10+ 标准库，无第三方 Python 运行依赖。
- SQLite 保存业务登记、快照成员、关系历史、派生向量和审计记录；M01 按 SHA-256 保存文件对象。
- Observation 与 Truth/GT 使用分开的资产目录和快照目录，并由应用角色策略限制读取。该隔离不是独立主机、密钥或操作系统账户级的生产安全边界。
- M00–M09 均有本地测试期实现。字段、状态和角色是 `broky_data.*.v1` 原型契约；接入正式数据前须按 [正式启用前改造清单](PRE_PRODUCTION_READINESS.md) 复核。
- VesselForge 已废弃，不作为入口或依赖。Arches、OpenRefine、Frictionless、DVC、FAISS、DuckDB、Superset、WeasyPrint、Scribus 均未作为当前代码依赖。

## 运行

运行完整合成数据演练；它会在所给目录写入本地数据库、资产、快照、审计收据和 HTML 报告：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m broky_data \
  --root ./local-data demo --output-dir ./demo-output
```

查看所有操作命令：

```bash
PYTHONPATH=src python3 -m broky_data --help
```

从文件接入后，记录初始状态为 `unknown`；之后由 `curator` 角色记录授权和资格审核。CLI 的 `--role` 是测试期模拟身份，可由本机用户自行填写，不提供真实身份认证。不要把它用于多人或远程生产环境。

运行测试：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## 模块导航

| 模块 | 测试期实现 | 交接说明 |
|---|---|---|
| M00 | 版本化原型契约与默认未知状态 | [M00](handover/M00_contracts.md) |
| M01 | Observation/Truth 分区的 SHA-256 本地资产仓库 | [M01](handover/M01_asset_repository.md) |
| M02 | SQLite 来源登记、人工授权/资格审核 | [M02](handover/M02_registry_intake.md) |
| M03 | 引用完整性、摘要、用途、资格和分区门禁 | [M03](handover/M03_validation.md) |
| M04 | 版本化 JSON 快照、opaque member ID、受控评测 join | [M04](handover/M04_dataset_access.md) |
| M05 | SQLite 人工关系决策历史；不做传递推断 | [M05](handover/M05_relations_review.md) |
| M06 | 外部向量输入、版本化精确 cosine 索引 | [M06](handover/M06_search_index.md) |
| M07 | 按用途报告已评估/未评估/通过/失败/阻断分母 | [M07](handover/M07_analytics.md) |
| M08 | 授权校验后的内部 HTML 标本卡/统计报告 | [M08](handover/M08_outputs.md) |
| M09 | 分离质量/功能结果的 JSON 收据和哈希链日志 | [M09](handover/M09_acceptance_audit.md) |

更多说明：[总体架构](ARCHITECTURE.md)、[可行性复核](REVIEW.md)、[第三方许可证清单](LICENSE_REGISTER.md)、[正式启用前改造清单](PRE_PRODUCTION_READINESS.md)。

## 安全和范围边界

- 未审核的授权、物理资格、训练资格保持未知并阻断相应用途；`FAST GEO` 不得标作物理资格已证实。
- Truth/GT 只能以评测用途创建快照；模型角色只能读 Observation。评测 join 记录两个快照与审批证据，不自动匹配具体答案。
- 关系状态由人工传入；R2 写入双向直接记录但不校验完整 MEHR 证据闭包，不推导传递关系。
- 检索只实现小规模精确 cosine；向量由调用方提供，不含嵌入模型。
- 输出仅为内部 HTML；没有正式标本卡/图版模板、PDF 排版、字体或出版许可。
- 哈希链可检测普通改写，但有数据库写权限的管理员可重写整条链；它不是数字签名或不可篡改审计。
- `broky_data` 自身许可证仍未决定；本仓库不添加根 `LICENSE`。数据、图像、3D、字体和模板的内容权利须与软件许可证分开审核。
