# 兼容性与可行性复核

**复核日期：** 2026-11-07
**结论：** M00–M09 的本地测试期原型已可通过合成演练运行；尚不具备生产上线条件。当前运行实现不含 Arches/Scribus 或其他第三方项目。以下是工程复核，不是数据真实有效、法律兼容或生产安全结论。

## 当前运行基线

- M00–M09 由单一 Python 应用提供独立逻辑模块。SQLite 保存业务元数据；M01 使用 SHA-256 内容寻址文件仓库，并将 Observation/Truth 分开存储。
- M02 使用本地登记/审核表，不部署 Arches；M03 使用标准库校验规则；M04 使用 SQLite + JSON 快照；M05 使用人工关系事件；M06 使用可版本化精确 cosine 索引；M07 使用 SQLite 聚合；M08 输出内部 HTML；M09 输出 JSON 收据并记录本地哈希链。
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v` 当前通过 23 项测试；`python3 -m broky_data ... demo` 完成合成端到端演练。
- 应用角色由调用方提供，不具备真实认证。Truth 目录 ACL 和数据库角色检查不构成独立物理安全边界；哈希链不是签名或不可篡改日志。
- 逐模块限制和正式启用门槛见 [PRE_PRODUCTION_READINESS.md](PRE_PRODUCTION_READINESS.md)。

## 候选生产架构（未采用）

- M00–M09 保持一个模块化应用/代码库中的逻辑模块，不拆成十个微服务。各模块通过版本化数据包和适配层隔离实现。
- Arches 作为 M02 来源登记、M05 人工关系审核的共用业务工作流，试点只部署一套独立服务。它不与 `broky_data` 打包为同一安装包/镜像，不作为其进程内运行时依赖，也不存放原始 Truth/GT。审核记录经项目规则校验后导出为符合 RelicWeave/MEHR 契约的版本化记录；未经转换的 Arches 工作流数据不作为唯一关系真值。
- Scribus 仅用于独立桌面排版，通过经审核的文件交接接收 M08 内容/素材并返回成果件；不嵌入、不链接、不打包为运行时依赖。交换格式和人工复核步骤须在原型中确定。
- Arches 与 Scribus 的分开部署是降低工程耦合的决定，**不代表**两者许可证必然冲突或已获法律兼容结论。若以后要合并发行、共用容器或复用代码，重新做版本级审查。

## 模块兼容性

| 模块 | 当前原型适配结论 | 正式启用门槛 |
|---|---|---|
| M00 | 本地 `broky_data.*.v1` 原型契约 | 与权威 RelicWeave/MEHR schema 对照并建立迁移 |
| M01 | POSIX 私有目录 + SHA-256 本地资产存储 | 生产对象存储/文件服务、备份、加密、恢复和可用性 |
| M02 | SQLite 登记和独立清权更新 | 正式来源字段、授权凭据、身份认证和审批流程 |
| M03 | 标准库规则、哈希和用途门禁 | 图像/3D 解析、领域规则、资格证据和正式负例 |
| M04 | JSON 冻结快照、Opaque ID、应用层双区 | Truth 独立安全边界、split 规则、恢复与保留策略 |
| M05 | SQLite 人工关系历史、双向记录、无传递推断 | MEHR 证据闭包和 R0/R1/R2/TINY/UNKNOWN 规则校验 |
| M06 | 调用方特征 + 精确 cosine + 保留旧索引 | 真实模型/向量规格、规模基准、索引产品决策 |
| M07 | SQLite 用途级分母与聚合 | 签收指标公式、披露控制和 dashboard 访问方案 |
| M08 | 仅内部 HTML 标本卡/统计报告 | 正式模板、PDF/图版工作流、字体/图像权利和视觉 QA |
| M09 | 分离质量/功能 JSON 收据 + 本地哈希链 | 正式阈值、签署、可信身份、签名和外部不可变存储 |

## M01 原型可用性复核

截至 2026-11-07，M01 支持流式写入、按内容 SHA-256 寻址、去重、读取、存在检查和重算摘要；Observation/Truth 使用不同根目录，POSIX 管理目录权限为 700、数据库为 600。M01 原有 9 项测试覆盖写入、完整性和路径边界；整体 23 项测试另覆盖模块权限和合成端到端流程。上述是本地适配行为，不覆盖生产规模、加密密钥、独立 Truth 主机、备份恢复或多用户身份。

## Arches 版本与运维影响

截至复核日，上游路线图列出的最新稳定版为 **8.1.6（2026-10-29 发布）**；8.1 主支持计划于 **2026-12** 结束，延长支持计划于 **2027-06** 结束。8.2 LTS 计划于 **2026-12-31** 发布，并包含 Django、Elasticsearch、PostgreSQL 升级。建议 8.1.6 只用于短期、隔离的原型；生产选版等 8.2 LTS 实际发布后再做迁移和验收，不提前视其为已发布版本。

Arches 官方稳定依赖页标注为 8.1.0，列出 PostgreSQL 14+、PostGIS 3.5+、Elasticsearch 8.19+、GDAL、GEOS、Python 3.11+、Node 20.14.x；长耗时任务需要 Celery broker。该清单不能代替 8.1.6 原型的精确依赖锁定和集成测试。Arches 不是轻量的单库接入，需单独评估部署、升级、监控、备份、索引重建和运维责任。官方开发/测试最低资源不能替代本项目生产容量评估；数据量、并发量和可用性目标仍未知。

## 许可证与内容权利门禁

- Arches 上游合规指南要求包清单使用 `AGPL-3.0-only`，但 PyPI 上 Arches 8.1.6 元数据列为 `AGPL-3.0-or-later`。这是需要版本级核实的上游表述差异，本设计不自行择一认定；任何修改、对外提供服务或发行前须核实实际源码、发行包许可证文本和维护者说明。Arches 依赖文档列出 Elasticsearch；Elastic 默认发行物适用 ELv2，而部分源代码有其他许可选项。不能把“有 AGPLv3 源代码选项”误当成 Arches 所用 Elasticsearch 发行物自动采用 AGPL。须先固定准确版本、发行包和 SBOM，再判断发布条件。
- Scribus `COPYING` 标注主程序 GPL version 2 or later，且部分代码和资源有独立许可。独立桌面使用和文件交接是本设计的工程边界；如进入同一分发物，须针对实际代码、资源、模板、字体和发行包重新审查。
- 数据、图像、3D、模型、字体、色彩配置和模板的授权与软件许可证分开记录。`broky_data` 自身许可证尚未决定，不由本设计代选。

## 生产上线门槛

1. 用合成/已授权样本完成 Arches 模型映射和往返导出测试，关系边、状态、证据引用及版本信息无损；验证 Arches 停用后仍可独立读取项目数据包。
2. 确认 Observation 与 Truth/GT 的物理/逻辑隔离、角色矩阵、评测审批、审计记录和备份恢复；未授权账号与模型路径均不得读取 Truth。
3. 选定资产后端，完成容量、完整性、备份恢复、权限和数据保留验证；当前资料不足以指定供应商或生产规格。
4. 在目标数据规模上测试导入、检索、统计和并发；FAISS、Superset、DVC 按实测需求决定，不作为首期必选项。
5. 锁定所有第三方版本/镜像 digest，复核 Arches/Elasticsearch 发行物、传递依赖、字体/模板及数据授权，完成项目自身许可证决策。
6. 由业务负责人签收关系规则、输出模板、质量/功能阈值和发布流程；本设计不替业务方填造这些内容。

## 上游依据

- [Arches 依赖要求](https://arches.readthedocs.io/en/stable/installing/requirements-and-dependencies/)
- [Arches 版本路线图](https://www.archesproject.org/roadmap-2/)
- [Arches 开源许可证合规指南](https://www.archesproject.org/license-compliance/)
- [Arches 8.1.6 PyPI 元数据](https://pypi.org/project/arches/8.1.6/)
- [Elastic 软件许可证 FAQ](https://www.elastic.co/pricing/faq/licensing)
- [Scribus COPYING](https://github.com/scribusproject/scribus/blob/master/COPYING)
