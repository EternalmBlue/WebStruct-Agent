# 模块边界与复用归属

本文是 `specs/features/*.feature` 的补充设计规范，用于约束“可复用功能归属到一起”
的模块化方向。它不替代 Gherkin 行为场景；所有可观察行为仍必须落在对应的
`.feature` 文件中。

## 目标结构

```text
backend/app/
  contracts/                     跨模块类型契约
  platform/
    configuration/               config.toml 加载、校验、脱敏摘要
    browser/                     CloakBrowser 启动与资源生命周期适配
    observability/               任务生命周期、事件、Trace、运行指标
    persistence/                 数据库和通用载荷存储
    llm/                         ModelAdapter 与模型提供商实现
    text_processing.py           文本和日期归一化
  features/
    schema_center/               Schema 输入、校验、版本
    page_center/                 页面采集和多视图
    program_center/              ProgramSpec 生成、净化、复用
    extraction_center/           抽取领域编排
    evaluation_center/           评测领域编排
    review_center/               人工复核领域编排
    spec_assistant_center/       Schema/ProgramSpec 协作编排
    ops_center/                  健康、公开配置、任务监测的 HTTP 入口
frontend/src/
  features/common/               跨页面展示组件和状态组件
  features/<domain>/             领域工作台组件
  pages/                         页面级组合
```

## 归属规则

### 配置

- 所有运行配置及敏感凭据只由 `platform/configuration/` 读取。
- 配置文件为项目根目录的 `config.toml`。
- 本地从明确定位的项目根配置加载，容器加载其挂载的同名配置；数据库和缓存相对路径以配置目录为基准。
- 业务模块不得直接读取 `.env`、环境变量或自行解析 TOML。
- 模型密钥、数据库密码和可选浏览器授权凭据直接写在本地 TOML 中，仅生成服务端配置对象。
- 本地 TOML 不提交、不烘焙进镜像，以运行时只读挂载提供；可提交示例不得包含真实凭据。
- 前端的公开设置由白名单投影提供，开发工具可复用 TOML 解析适配但不得把服务端凭据带入产物。
- 不自动加载 `.env` 或采用环境变量覆盖。第三方 SDK 必需的内部参数映射只能由已加载的 TOML 派生。
- 配置修改重启相关服务生效；配置快照与哈希不保存或计算公开可见的密钥内容。

### 浏览器

- 浏览器生命周期与启动细节归属 `platform/browser/`，页面采集及 HTTP 降级策略归属 `page_center/`。
- 渲染提供方为 CloakBrowser，普通 Playwright Chromium 不再是项目的采集默认或隐式 fallback。
- 不承诺删除 CloakBrowser SDK 自身需要的 Playwright 依赖；领域模块不得直接创建具体浏览器。
- 支持性验收包括当前 Windows x64 工作区与现有 Linux Docker 目标，版本在实施时验证并固定。
- 浏览器二进制、缓存与可选许可由配置控制；缺失时可在首次 URL 采集前自动下载
  固定版本，不静默升级已固定版本。
- 采集记录实际提供方、版本、耗时与失败原因；所有成功、失败和超时路径释放浏览器资源。

### 可观测性

- 所有 LangGraph 工作流使用同一套任务生命周期、关联标识和节点事件协议。
- 抽取、评测和后续工作流不得各自实现独立 Trace 格式。
- 状态查询、事件回查和监测摘要统一由 `platform/observability/` 提供。
- 领域节点只负责提供节点上下文和结果，不负责保存监测数据。
- ops 路由通过公开协议暴露状态和事件；平台包不依赖 FastAPI 路由或具体领域工作流。
- 本地任务提交调度通过注入的工作流调用对象启动，不让平台反向导入抽取或评测中心。
- 持久化任务状态和事件，先提交可追踪元数据再启动执行；不引入分布式队列或自动断点续跑。

### 持久化

- 领域仓储负责领域对象的读写语义。
- 通用数据库连接、迁移、JSON 载荷和事务边界归属 `platform/persistence/`。
- 领域模块不得复制数据库初始化和通用序列化逻辑。

### 前端复用

- 状态徽标、加载骨架、错误提示、运行进度、空状态等通用控件归属
  `frontend/src/features/common/`。
- 抽取、评测、复核等领域组件只负责领域数据和交互。
- 页面级组件负责布局组合，不重复实现领域规则。
- 任务恢复、轮询与连接异常状态由可复用客户端逻辑管理，领域页面不各自实现刷新计时器。

## 依赖方向

允许的依赖方向为：

```text
backend composition root -> feature public services -> platform
backend features -> contracts
backend platform -> contracts
frontend pages -> feature components / common
frontend features -> api clients / shared types
```

禁止以下情况：

- `platform` 反向依赖具体业务功能中心。
- 一个功能中心直接读取另一个功能中心的内部模块或绕过其公开服务契约。
- 多个功能中心复制同一套状态、Trace、配置或数据库工具。
- 前端页面直接拼装后端内部数据库结构。

合法的评测调用抽取服务、复核登记规则和抽取调用页面服务不受禁止；它们通过公开服务接口或组合入口注入协作。
上述结构为目标规范，不表示当前仓库已完成迁移。
