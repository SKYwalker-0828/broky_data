# 第三方许可证与来源清单

**核对日期：2026-11-07。** 此表记录设计推荐或候选的上游许可证入口，不是 SBOM，也不是法律兼容结论。除 Arches 试点推荐外，第三方工具仍未在生产采用。接入时须固定版本/镜像 digest，读取实际发行物的全部 license/notice 文件并逐项复核。

## 当前实现的许可证范围

- M00–M09 当前原型由本仓库 Python 代码实现，仅调用 Python 标准库；当前没有集成第三方运行时依赖，也没有复制候选项目源代码/数据。此项说明不替代未来构建发行物、Python 解释器、系统包或外部资源的许可证清单。
- `broky_data` 自身许可证仍未决定；不要因此推断当前或未来代码已获开源授权，也不要添加根目录 `LICENSE`。

| 项目/组件 | 草案用途 | 许可证标识/来源 | 当前是否采用 | 审查备注 |
|---|---|---|---|---|
| [Arches](https://github.com/archesproject/arches) | 可选的 M02 登记与 M05 人工审核工作流 | 官方指南要求 `AGPL-3.0-only`；PyPI 8.1.6 元数据为 `AGPL-3.0-or-later` | 当前未采用；本地原型使用 SQLite | 上游表述存在版本级差异；如未来采用，须核对实际源码/发行包并复核服务和分发义务。 |
| [Elasticsearch](https://www.elastic.co/pricing/faq/licensing) | Arches 搜索依赖（仅当未来采用 Arches 时） | 默认发行物为 `ELv2`；部分源代码可选 `AGPLv3` 等许可 | 当前未采用 | 固定准确发行物和许可证路径；源代码选项不自动改变所用发行物的许可证。 |
| [OpenRefine](https://github.com/OpenRefine/OpenRefine) | 可选的人工表格清洗 | BSD-3-Clause | 否，可选 | 如打包分发，应保留上游版权、条件和免责声明。 |
| [frictionless-py](https://github.com/frictionlessdata/frictionless-py) | 结构校验候选 | MIT | 否，候选 | 此项只对应该 Python 仓库，不代表整个 Frictionless 生态的每个包同许可证。 |
| [DVC](https://github.com/treeverse/dvc) | 可选数据版本追踪 | Apache-2.0 | 否，可选 | DVC 不替代底层 remote 的授权系统；DVC 插件、remote 与发行包需另审。 |
| [FAISS](https://github.com/facebookresearch/faiss) | 可选向量索引 | MIT | 否，可选 | Python wheel、CUDA/BLAS 运行时及传递依赖需按实际构建另审。 |
| [DuckDB](https://github.com/duckdb/duckdb) | 本地/离线分析 | MIT | 否，候选 | DuckDB 核心许可证不替代扩展、第三方组件或具体发行包的许可证清单。 |
| [Apache Superset](https://github.com/apache/superset) | 可选统计看板 | Apache-2.0 | 否，可选 | 上游列出单独许可的子组件/字体；若部署或分发，依镜像与功能范围复核。 |
| [WeasyPrint](https://github.com/Kozea/WeasyPrint) | 可选模板 PDF | BSD-3-Clause | 否，可选 | PDF 输出所用字体、模板、图像资源另行许可；运行依赖按锁定版本复核。 |
| [Scribus](https://github.com/scribusproject/scribus) | M08 可选的独立桌面人工排版 | GPL version 2 or later（项目 COPYING） | 当前未采用；M08 输出 HTML | 部分代码及文档、词典、色彩配置、模板等资源有各自条款；按实际使用内容审查。 |

## 接入许可证门禁

1. 先记录软件的上游 URL、版本/commit、来源发行包和实际功能范围；使用 SBOM 工具扫描直接与传递依赖，再用上游发布包内容复核。
2. 记录 SPDX 标识、版权人、许可证文本路径、NOTICE、例外条款、字体/模板/样例/模型/数据的单独许可。缺许可证或许可不清的组件先隔离，不进入交付物。
3. 分别判断开发依赖、运行时依赖、独立服务、容器镜像、安装包和整体分发物；“独立模块/API”不自动决定法律上的组合关系。
4. 当前没有 Arches/Scribus 组合或文件交接实现。若未来同时采用，工程上仍建议服务端工作流与桌面排版分开部署；这不是许可证冲突/兼容结论。按准确版本、代码、资源和发布形式完成法律审查。Arches 指南对 `GPL-2.0-only` 等许可证另有组合限制；Scribus 的主程序许可不能替代对实际使用文件和发行物的逐项审查。
5. 依许可证履行保留声明、提供文本/源码、变更标注等适用义务。不要给第三方程序加上与其许可证相冲突的附加限制。
6. 数据本身另建授权台账：项目代码许可证不授予考古照片、标本、3D、论文图表、模型权重、字体或模板的复制、训练、展示和再发布权。
7. `broky_data` 自身许可证未由用户指定，本目录不添加 `LICENSE`，也不暗示默认许可。

## 上游核验入口

- Arches：[许可证合规指南](https://www.archesproject.org/license-compliance/)、[依赖要求](https://arches.readthedocs.io/en/stable/installing/requirements-and-dependencies/)、[路线图](https://www.archesproject.org/roadmap-2/)、[GitHub 项目](https://github.com/archesproject/arches)
- Arches 8.1.6：[PyPI 发行元数据](https://pypi.org/project/arches/8.1.6/)
- Elasticsearch：[许可证 FAQ](https://www.elastic.co/pricing/faq/licensing)
- OpenRefine：[LICENSE.txt](https://github.com/OpenRefine/OpenRefine/blob/master/LICENSE.txt)
- Frictionless：[frictionless-py LICENSE.md](https://github.com/frictionlessdata/frictionless-py/blob/main/LICENSE.md)
- DVC：[LICENSE](https://github.com/treeverse/dvc/blob/main/LICENSE)
- FAISS：[LICENSE](https://github.com/facebookresearch/faiss/blob/main/LICENSE)
- DuckDB：[LICENSE](https://github.com/duckdb/duckdb/blob/main/LICENSE)
- Superset：[LICENSE.txt](https://github.com/apache/superset/blob/master/LICENSE.txt)
- WeasyPrint：[LICENSE](https://github.com/Kozea/WeasyPrint/blob/main/LICENSE)
- Scribus：[COPYING](https://github.com/scribusproject/scribus/blob/master/COPYING)

本清单用于工程交接，不构成法律意见。许可证文本和合规建议会变化；合并代码、构建镜像或发布软件前重新核查。
