# M04 数据集快照与访问边界交接

**状态：** SQLite 元数据与 JSON manifest 的本地快照已实现；Parquet、DVC 未集成。Truth/GT 生产存储与独立权限边界未确定。

## 当前测试期实现

- `DatasetService` 逐条运行 M03 门禁，通过后生成不可变快照、随机 opaque member ID、规范化 JSON manifest 及 SHA-256，并将成员与资产摘要登记在 SQLite。
- Truth/GT 仅允许 evaluation 快照；受控 join 保存 Observation/Truth 快照引用及审批证据，不包含样本级答案配对，也不构成隔离评测环境。
- 当前无 Parquet/DVC 依赖；只使用 Python 标准库、SQLite 与本地文件系统。DVC 的 Apache-2.0 许可只在未来实际采用时才适用。

## 模块职责

从已登记且通过适用门禁的数据构建可复现的训练、开发、确认及其他获准快照；维持 Observation 与 Truth/GT 物理/逻辑分离，控制评测时的受控关联。它不负责资产原件的底层存储产品选择。

## 项目/数据库/许可证

- **manifest + Parquet/JSON：** 建议的数据快照/序列化格式；格式本身不是特定数据库或软件许可。
- **DVC：** 数据版本追踪候选，上游 [`LICENSE`](https://github.com/treeverse/dvc/blob/main/LICENSE) 为 Apache-2.0。是否使用未决定。
- **真实访问控制：** 由对象存储、文件权限、密钥/身份或服务层提供，但产品/实现尚未选；DVC 本身不得当作 Truth 权限边界。

## 正式接入前的目标实现

1. 每次冻结快照生成独立 manifest，引用准确 schema、数据包、资产 hash、用途、split 和校验收据；字段以批准的契约为准。
2. Observation 快照只包含模型合法可见字段及 opaque ID；不携带母体 ID、GT、隐藏来源路径或会泄漏答案的分组字段。
3. Truth/GT 使用单独目录/仓库/访问角色，具体物理隔离程度取决于待选后端；原始 Truth/GT 不存入 Arches。禁止把 Truth 指针或缓存默认纳入普通工作区。
4. 首期不要求引入 DVC。若后续启用，只做内容/版本追踪；remote ACL、身份认证、加密、备份由底层设施负责。Truth/GT 不进入普通 DVC remote，除非专门的权限/隔离方案通过负向访问测试。
5. split 由已确认的来源簇、母体/孪生、物理角色和 ML 角色规则生成；不得在模型确认集上调阈值。更改 snapshot 必须形成新版本，不能静默改写旧确认快照。
6. 评测配对在授权的隔离执行边界发生，记录谁授权、使用哪个快照和评测版本；具体执行服务尚未选。

## 许可证与权利

DVC Apache-2.0 的使用/分发义务按实际安装包确认；插件、云 remote、第三方存储或 SaaS 服务需单独核查。manifest 中记录的数据授权不等于软件许可证。项目数据的许可必须逐来源建账。

## 交接验收

- 同一版本 manifest 可以重建相同的 Observation 成员集合和 hash。
- GT 不出现在模型工作区、向量索引输入、公开分析或一般用户下载中。
- 无权账户不能因知道路径、revision 或 hash 读取 GT；若采用 DVC，其 pull/checkout 必须通过同等负向访问测试。
- split 与资格状态可回溯到经确认的来源/实体分组，不按路径、排序或随机临时分配。
- 验收分母保留采集、导入、QA、闭包等失败个案。

## 待确认

- Snapshot schema、Parquet/JSON 各自承载的对象类型和分区粒度。
- Truth/GT 是否也用现有 pack bytes；保护等级、访问角色、评测审批和备份恢复办法。
- DVC 启用条件、remote 后端、密钥管理和同步/离线流程。
- 数据集版本保留、删除和确认集复用规则。
