# broky_data

> 面向 RelicWeave 考古数字化工作流的模块化数据管理系统（规划中）。

**GitHub 项目简介：** 为 RelicWeave 提供可追溯的数据接入、质量治理、权限隔离、版本管理、关系台账、分类统计与成果交付能力。

## 项目定位

`broky_data` 计划作为 RelicWeave 的数据管理层，管理实采与授权资料、合成数据、图像和 3D 资产，以及与之关联的来源、许可、质量、关系和版本记录。目标是让数据从接入、审核、使用到交付都能追溯，而不是替代 PG-Frag 等数据生成组件、RelicWeave 的检索算法或考古专业判断。

## 规划能力

- **资产接入：** 以受控文件或对象仓库保存原始图像、3D 和合成资产；记录 manifest、来源与 SHA-256。具体存储后端尚未选定。
- **登记与清理：** 管理来源、许可、样本和处理记录；Arches 可作为业务登记与审核工作流候选，OpenRefine 可用于导入前表格清理。
- **质量与资格：** 以 Frictionless Framework 做结构检查，并由项目规则检查媒体、单位、引用闭包、物理资格和训练用途；失败记录进入隔离或补采流程。
- **数据集与权限：** 以 manifest 和 Parquet/JSON 规划可复现快照，DVC 为可选版本工具。Observation 与 Truth/GT 分开管理；Truth/GT 不进入模型可见数据集，具体格式及后端待确认。
- **检索与统计：** FAISS 可选地保存可重建的派生向量索引；Parquet 与 DuckDB 用于统计分析，Superset 可选用于看板。索引不作为关系真值来源。
- **成果输出：** WeasyPrint 可用于模板化 PDF，Scribus 可作为图版人工精修工具；模板、自动化范围和实际采用情况待确认。

## 模块化原则

各能力通过明确的数据契约和接口协作；存储后端、校验器、检索索引、统计工具和输出工具应可独立替换。候选工具不等于已选型或已部署；Arches 的通用关系能力也不能替代 RelicWeave 对 R0、R1、R2、TINY_CONTACT 和 UNKNOWN 的项目规则。

## 第三方许可证

下表记录当前候选上游项目的主许可证，供初步规划使用。实际接入和发布时，必须按选定版本、发行包、传递依赖和所用资源逐项复核，不能仅凭项目名称推定兼容。

| 候选项目 | 规划用途 | 上游主许可证 |
|---|---|---|
| [Arches](https://github.com/archesproject/arches) | 登记、业务记录与审核流程 | [AGPL-3.0-only](https://www.archesproject.org/license-compliance/) |
| [OpenRefine](https://github.com/OpenRefine/OpenRefine) | 导入前表格清理 | [BSD-3-Clause](https://github.com/OpenRefine/OpenRefine/blob/master/LICENSE.txt) |
| [Frictionless Framework](https://github.com/frictionlessdata/frictionless-py) | 数据结构与资源校验 | [MIT](https://github.com/frictionlessdata/frictionless-py/blob/main/LICENSE.md) |
| [DVC](https://github.com/treeverse/dvc) | 可选数据集版本追踪 | [Apache-2.0](https://github.com/treeverse/dvc/blob/main/LICENSE) |
| [FAISS](https://github.com/facebookresearch/faiss) | 可选向量检索索引 | [MIT](https://github.com/facebookresearch/faiss/blob/main/LICENSE) |
| [DuckDB](https://github.com/duckdb/duckdb) | 本地/离线统计分析 | [MIT](https://github.com/duckdb/duckdb/blob/main/LICENSE) |
| [Apache Superset](https://github.com/apache/superset) | 可选统计看板 | [Apache-2.0](https://github.com/apache/superset/blob/master/LICENSE.txt) |
| [WeasyPrint](https://github.com/Kozea/WeasyPrint) | 可选模板 PDF 生成 | [BSD-3-Clause](https://github.com/Kozea/WeasyPrint/blob/main/LICENSE) |
| [Scribus](https://github.com/scribusproject/scribus) | 可选桌面图版精修 | [GPL-2.0-or-later](https://github.com/scribusproject/scribus/blob/master/COPYING)；部分代码与资源另有许可 |

接入时应保留适用的版权声明和许可证文本；若上游提供 `NOTICE`，也应按其条款保留，并生成依赖清单或 SBOM。Arches 官方合规指南指出，其 AGPL-3.0-only 代码与若干许可证存在组合限制；Scribus 的主程序为 GPL-2.0-or-later，但部分代码、随附程序和资源另有许可。若将 Arches 与 Scribus 或其组件放入同一安装包、镜像或组合发行物，须按具体版本和依赖逐项审查；仅采用独立进程或 API 集成，不能自动证明组合或分发方式合规。部署或修改 Arches 前，还须核查其源代码提供、许可证文本和版权声明义务。软件许可证不授予考古图像、标本资料或其他项目数据的使用权，这些内容必须另行记录来源、授权和使用范围。

**本项目自身的许可证尚未决定。** 在维护者选定许可证并加入根目录 `LICENSE` 前，不应在 README、包元数据或发行物中宣称 `broky_data` 代码采用某一开源许可证。本文仅作项目规划与许可证审查提示，不构成法律意见。

## 当前状态

本仓库目前提供项目介绍和候选架构说明，不代表已有可运行系统。对象存储产品、数据库/元数据模型、接口、部署方式、具体依赖版本和项目自身许可证均待确认。
