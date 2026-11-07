# M03 接入校验与数据资格门交接

**状态：** 基于 Python 标准库的测试期结构、摘要、用途和部分资格校验已实现；Frictionless 未集成，图像/3D 与领域真实性检查未实现。

## 当前测试期实现

- `ValidationService` 检查原型字段约束、非空资产、SHA-256 完整性、用途授权、Observation/Truth 分区及部分训练/物理资格状态，并将结果写入 SQLite 校验收据。
- 未知授权或资格会阻断相关用途；校验 PASS 只表示本原型规则通过，不证明媒体内容可解析、考古/物理结论成立或权利有效。
- 当前无 Frictionless 依赖；实现仅使用 Python 标准库和 SQLite。Frictionless 的 MIT 许可说明仅适用于未来采用该候选项目。

## 模块职责

在数据进入正式 Observation、Truth/GT 或分析快照前，检查包结构和引用；将“文件可解析”“来源许可可用”“物理资格成立”“训练资格通过”分成不同结论。失败时保存原因并隔离，不把异常样本静默丢弃。

## 项目/数据库/许可证

- **frictionless-py：** Frictionless Framework 的 Python 实现候选，仓库 [`LICENSE.md`](https://github.com/frictionlessdata/frictionless-py/blob/main/LICENSE.md) 为 MIT。此许可只核对该具体仓库，不代表 Frictionless 生态所有组件一致。
- 项目规则校验器：自研业务代码，不指定实现语言/数据库；项目自身许可证未决定。
- 输出计划为 JSON 验收/校验收据；收据 schema 与持久化后端待定。

## 正式接入前的目标实现

1. 使用 Frictionless 做资源/表格结构与描述校验，输出原始校验报告或稳定摘要。
2. 用项目校验层补充：manifest 引用闭包、文件/hash、frame/unit/dtype/shape、图像/3D 可读性、缺失原因、split/用途字段、合成来源、MEHR 关系约束等。详细规则逐项从当前契约和已接受测试迁移，不根据图像外观猜物理有效性。
3. 每项门独立输出：schema 是否通过、来源/许可状态、物理证据状态、ML 资格与 split；未知状态保持未知，不自动转为 PASS。
4. 失败的原始输入保留引用、失败原因和处置状态；补采/重跑生成新 receipt，不重写历史失败记录。
5. 将 `FAST GEO` 标为 fast-geometry 来源且 `physics_claim=false` 的语义按 MEHR 契约传递，禁止因共用 schema 升格为 PHYS。

## 输入与输出

- 输入：带版本的资产/数据包、上游 source/provenance、适用规则集版本。
- 输出：结构化校验结果、规则集版本、输入 manifest/hash、失败项和后续路由；准确 JSON 字段待 schema 所有者签收。

## 隐私与许可

校验日志不要复制敏感 Truth、隐藏路径或可识别个人信息。MIT 组件按其许可证保留版权和许可文本；其依赖与分发包仍需 SBOM 复核。数据授权不因通过校验而自动获得。

## 交接验收

- 负例覆盖未知 schema、错误单位/frame、断裂引用、摘要不一致、未知授权/资格、FAST GEO 误标物理数据、MEHR 非法关系。
- 每个失败样本可进入隔离并保留失败分母；PASS 不能被解释为整体物理/考古真实性证明。
- 同一输入和规则版本能复现相同校验结果，或明确记录非确定性因素。
- 收据可以关联输入和规则 hash，但不暴露 Truth 内容给模型可见包。

## 待确认

- 首批正式 schema 版本及每种资产/包类型的规则责任人。
- 资格状态词汇、UNKNOWN 行为、审批人与补采路线。
- JSON receipt 是否已有正式 schema；如有，必须沿用。
