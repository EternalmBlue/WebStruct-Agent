# language: zh-CN
功能: ProgramSpec 中心（Program Center）
  作为抽取策略的生成与治理者
  我希望 ProgramSpec 既能从 Schema 确定性生成，也能吸纳 LLM 候选并做安全净化、人工复用
  以便抽取过程不执行任意代码且可沉淀可复用规则

  场景: Schema 可以确定性地生成 ProgramSpec
    假如 一个合法的用户自定义 Schema
    当 ProgramSpec 中心为该 Schema 生成抽取程序
    那么 生成的 ProgramSpec 为每个字段都提供了至少一条抽取程序
    并且 所有抽取程序只允许使用受支持的策略

  场景: LLM 候选程序中的不安全策略会被净化
    假如 一个合法的用户自定义 Schema
    并且 一个含不支持策略的候选 ProgramSpec
    当 ProgramSpec 中心净化该候选 ProgramSpec
    那么 净化后的 ProgramSpec 不包含不支持的策略
    并且 净化过程至少上报一条问题

  场景: 已人工验证的 ProgramSpec 可被列表接口列出
    假如 一个合法的用户自定义 Schema
    并且 一条被标记为人工验证通过的 ProgramSpec 记录
    当 我请求已验证 ProgramSpec 列表
    那么 列表中至少包含该条记录
    并且 列表项包含 Schema 名称与抽取程序数量

  场景: 未配置模型凭据时仍能确定性生成 ProgramSpec
    假如 config.toml 未配置模型密钥
    并且 一个合法的用户自定义 Schema
    当 ProgramSpec 中心为该 Schema 生成抽取程序
    那么 生成的 ProgramSpec 仍然覆盖全部必填字段
