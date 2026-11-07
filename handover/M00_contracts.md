# M00 共享数据契约交接

**状态：** `broky_data.*.v1` 测试期原型契约已实现；RelicWeave/MEHR canonical schema 适配未实现。

## 当前测试期实现

- `src/broky_data/contracts.py` 定义接入、授权、记录和校验对象，并提供规范化 JSON 与 SHA-256 辅助函数；其他模块使用显式版本字符串标识本地数据。
- 该契约只用于打通本地流程，不复制或替代 RelicWeave/MEHR 的权威字段。当前无第三方 schema/序列化依赖，仅使用 Python 标准库。

## 模块职责

为各存储模块提供稳定的交换边界，优先复用项目公共对象：`Asset`、`Material`、`Event`、`Job`、`Result`、`Truth`、`Observation`、`Dataset`、`Validation` 及 `FragmentSet`、`SurfaceSet` 等辅助对象。具体字段以现行主计划、MEHR 契约交叉表和实际 schema 文件为准。

## 候选项目/数据库

- 无第三方项目或数据库选型。
- 建议以仓库已有、版本控制的 schema/fixture 为唯一权威，不在此复制一套字段定义。格式、schema 版本和文件位置应在项目启动时确认。
- JSON/Parquet 是候选交换/快照格式，不是数据库，也不自动规定业务语义。

## 正式接入前的目标实现

1. 建立契约版本目录和数据包适配器；只允许显式声明版本，未知主版本或关键字段拒绝处理。
2. 保留项目要求中的单位、frame、dtype/shape、引用闭包、缺失原因、版本与 hash 信息；旧 pack 的字节/哈希语义不能被静默重算。
3. 各模块只消费经过适配层解析的包；不得从 PG-Frag core 导入其他项目源码实现。
4. 用现行 fixture 覆盖 Observation/Truth 隔离、stable ID、多 region/subpatch、多对手、双向 R2 和 legacy 兼容边界。

## 隐私与领域边界

Truth 与 Observation 使用分离引用，不设 Truth 自动投影为 Observation 的 API。观察输入不能携带母体身份、group/split、历史事件、答案距离或隐藏来源路径。实际字段清单必须逐条引用现行 schema，未找到时记为待确认，不凭经验添加。

## 许可证

本模块没有选定第三方代码或数据库；JSON、Parquet 等格式名不是软件许可证。后续如果引入 JSON Schema 验证器、序列化库或代码生成器，需登记其准确包名、版本及许可证。`broky_data` 自身许可证未决定。

## 交接验收

- 新契约不会覆盖或改写上游已冻结 pack。
- 未知主版本、缺必需引用、错误单位/frame、非法缺失表达均有负例。
- Observation/Truth 的字段和权限边界由静态与运行时测试覆盖。
- 所有新增字段均有数据所有者、版本变更记录和兼容策略。

## 待确认

- 目标代码仓库中的 schema 权威路径及适用分支/版本。
- `broky_data` 首期是否只读既有格式，还是需要写入新的版本化包装层。
- 兼容/弃用策略由哪个项目维护者签收。
