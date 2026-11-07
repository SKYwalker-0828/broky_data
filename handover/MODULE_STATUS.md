# 项目模块状态交接说明

**更新日期：** 2026-11-07

**交接范围：** `broky_data` 当前仓库中的 M00–M09 本地测试期原型。本文汇总实现状态，不替代模块交接文件、业务规则签收或正式上线审批。

## 1. 总体状态

项目已具备可运行的模块化 CLI 演练链路：Python 3.10+ 标准库负责应用逻辑，SQLite 保存登记、校验、快照、关系、检索、验收和审计元数据，本地文件保存资产及输出。`src/broky_data/workflow.py` 中的 `BrokyData` 是模块组合入口；数据库 schema 当前为版本 2。命令行支持初始化、合成演练、登记、审核、校验、快照、关系、检索、统计、标本卡、评测关联、验收收据和审计操作。

当前状态应理解为“测试原型可用，生产启用未就绪”。项目没有图形界面、可信身份系统、生产存储或独立 Truth/GT 安全域。`--role` 是调用者提供的模拟角色；Observation 与 Truth 分区及应用权限只适用于本地演练。合成演练通过不代表数据真实、权利有效、领域规则获签或生产安全已达标。

## 2. 模块状态

| 模块 | 当前实现与代码位置 | 状态、限制及交接重点 |
|---|---|---|
| **M00 契约** | `contracts.py`：`broky_data.*.v1` 原型对象、规范化 JSON、SHA-256 辅助函数。 | 原型契约已供模块使用；不是 RelicWeave/MEHR canonical schema。待确认权威 schema、字段映射、版本兼容和迁移责任人。详见 [M00](M00_contracts.md)。 |
| **M01 资产** | `asset_store.py`：`AssetStore` 协议及 `LocalAssetStore`；按 SHA-256 内容寻址，支持流式写入、去重、读取与完整性校验，Observation/Truth 使用不同目录。 | 本地适配器可用于测试；不提供生产对象存储、加密、备份、跨账户 ACL、保留/删除或恢复保证。发布依赖同一文件系统硬链接能力。待按容量、并发和恢复目标选定后端并演练。详见 [M01](M01_asset_repository.md)。 |
| **M02 登记** | `registry.py`：`RegistryService` 将资产及原型记录写入 SQLite；人工审核更新授权/资格字段。 | 初始状态为 `unknown`；证据只记 opaque 引用，不核实文件内容或法律效力。Arches、OpenRefine 均未集成。待签收登记字段、状态词表、授权流程和导入规则。详见 [M02](M02_registry_intake.md)。 |
| **M03 校验** | `validation.py`：`ValidationService` 检查原型字段、资产/hash、用途、分区及部分资格状态，并保存校验收据。 | 未知授权/资格可阻断；PASS 仅表示通过当前原型规则，不判断图像/3D 可读性、考古或物理真实性。Frictionless 未集成。待以权威 schema、格式解析器、领域规则和真实负例补齐。详见 [M03](M03_validation.md)。 |
| **M04 快照与访问** | `dataset.py`：`DatasetService` 生成 SQLite 元数据、JSON manifest、hash 和 opaque member ID 的快照。 | Truth/GT 只允许 evaluation 快照；join 仅记 Observation/Truth 快照引用与审批证据，不含样本级答案配对，也不是隔离评测环境。Parquet、DVC 未集成。待确定正式 split、保留策略及 Truth/GT 独立安全域。详见 [M04](M04_dataset_access.md)。 |
| **M05 关系** | `relations.py`：`RelationService` 追加人工关系决策事件；R2 双向直接记录，不做传递推断。 | 证据引用和决策历史已记录，但不验证完整 MEHR 证据闭包、最终叶或所有反向一致性条件。Arches 未集成。待签收 R0/R1/R2/TINY_CONTACT/UNKNOWN 语义、证据规则及往返映射。详见 [M05](M05_relations_review.md)。 |
| **M06 检索** | `search.py`：`SearchService` 接收调用方向量，在 SQLite 建立版本化索引并执行精确 cosine 查询。 | 仅面向 Observation、小规模数据；无嵌入模型推理、FAISS 或规模性能保证。检索命中只是人工候选，不能成为关系真值。待确认向量规格、模型版本绑定、负载和是否需要近似索引。详见 [M06](M06_search_index.md)。 |
| **M07 统计** | `analytics.py`：`AnalyticsService` 汇总登记、校验、用途、评估状态和关系事件计数。 | 统计口径仍为测试期定义；没有看板、已签收公式、置信区间或敏感小样本控制。DuckDB、Superset 未集成。待明确指标、分母、披露规则和看板访问边界。详见 [M07](M07_analytics.md)。 |
| **M08 输出** | `outputs.py`：`OutputService` 生成内部 HTML 标本卡与统计概览；输出做字段转义并使用内容 hash 标识。 | 当前不是正式标本卡、图版或出版报告；无 PDF、正式模板、字体/图像权利核验或视觉签收。WeasyPrint、Scribus 未集成。待获取并批准模板、字段、版式及人工排版/复核流程。详见 [M08](M08_outputs.md)。 |
| **M09 验收与审计** | `acceptance.py`、`audit.py`：记录调用方提交的质量/功能检查 JSON 收据；本地 SQLite 事件按 hash 链接并可校验/导出。 | 可保留 PASS/FAIL/BLOCKED 与审计线索，但检查结论由调用方提供；哈希链可被有数据库写权限者整体重写。无数字签名、独立不可变存储、正式阈值或签署流程。详见 [M09](M09_acceptance_audit.md)。 |

## 3. 数据流与模块依赖

当前主链路为：资产与来源进入 M01/M02，M03 执行校验；通过后由 M04 冻结 Observation 或 evaluation 用途的 Truth/GT 快照。Observation 可进入 M05 人工关系审核、M06 候选检索和 M07 统计；M07 与授权记录可供 M08 生成内部 HTML。M09 汇集相关质量/功能检查和本地审计线索。失败或阻断需要操作人员处置后重跑，不自动修改 Truth/GT 或关系真值。

`workflow.py` 负责组合服务，`database.py` 管理 SQLite schema/迁移和本地资产存储入口；实际模块 API 和约束以各自代码及上方链接的交接文档为准。

## 4. 依赖与许可证状态

当前 M00–M09 没有第三方 Python 运行时依赖，使用本仓库代码、Python 标准库、SQLite 和本地文件。Arches、OpenRefine、Frictionless、DVC、FAISS、DuckDB、Superset、WeasyPrint、Scribus 均未集成，不应作为当前运行前提。其候选用途及许可证来源见 [第三方许可证清单](../LICENSE_REGISTER.md)；许可证只针对具体项目/发行物，采用前需锁定版本并复核依赖与声明。`broky_data` 自身许可证尚未决定。软件许可证不替代文物图像、3D、模型、字体、模板等内容的授权。

## 5. 验证基线与启用前事项

2026-11-07 本次全量测试运行结果为 **24 项通过**；覆盖资产存储、合成端到端工作流、权限与未知状态阻断、评测快照、关系非传递、检索输入边界、HTML 转义和 SQLite 向量迁移/失败回滚。CLI 帮助命令可运行。该结果是测试原型的可用性证据，不是生产验收。

复测命令：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m broky_data --root ./local-data demo --output-dir ./demo-output
```

正式启用前的关键工作包括：签收权威契约与关系规则；落实真实来源授权和内容权利台账；引入可信身份及 Truth/GT 独立隔离；确定并演练生产存储、备份恢复和保留删除；补齐媒体/领域校验；批准统计口径、输出模板和验收阈值；完成软件许可证、数据授权、部署与运维审查。完整责任项与门槛见 [正式启用前改造清单](../PRE_PRODUCTION_READINESS.md)。

## 6. 建议交接顺序

先由数据/领域负责人签收 M00、M02、M03、M05 的字段、权利和关系规则；安全与运维负责人确认身份、Truth/GT 边界及 M01/M04 存储恢复方案；随后按真实工作量验证 M06/M07；最后签收 M08 模板和 M09 验收流程。上述是待办排序建议，不表示相关方已承诺或任何工具已选定。
