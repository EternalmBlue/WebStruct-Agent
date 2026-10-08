# 已确认决策

确认日期：2026-10-07。状态：已实施；用户已授权“开始实现代码”。

本文记录用户已确认的产品决策。行为验收由 `features/*.feature` 描述，生命周期和评测口径
分别由 `runtime-contract.md`、`benchmark-protocol.md` 细化。

## 决策清单

| 编号 | 确认内容 | 对应规范 |
| --- | --- | --- |
| D1 | 取消三个领域预置模板及自动 Schema 兜底，不删除历史任务、Schema 版本和用户验证规则；样例与模板库隔离 | schema、extraction、evaluation |
| D2 | 任务完成不等于质量通过；验证结论和字段错误独立保留 | extraction、UI、runtime |
| D3 | 已验证规则默认确定性执行与验证；字段级 LLM 修复需显式启用，不改写规则 | extraction、program、UI |
| D4 | 刷新恢复查询；后端重启将中断任务标为失败；重试创建关联新任务，不自动断点续跑 | observability、UI、runtime |
| D5 | 追踪采集降级、规则复用、模型调用与字段修复；默认不向日志写入完整网页或提示词 | observability、page |
| D6 | 极简工作台常驻输入、模式、连接、当前节点、结果与质量；详细诊断按需展开；刷新错误不改任务真值 | UI |
| D7 | 所有应用配置及敏感凭据直接写入本地 config.toml；不依赖 .env 或环境变量提供凭据 | configuration、ops |
| D8 | 五种方法边界和指标定义明确；实际测量、估算与不可用分开，禁止固定值伪造指标 | evaluation、benchmark |
| D9 | 渲染采集浏览器从普通 Playwright Chromium 切换为 CloakBrowser | page、configuration、module |

## 配置安全边界

- TOML 是配置格式，不是加密方案。本地文件可能包含明文凭据，只应由本机维护者及运行进程访问。
- `config.toml` 必须被 Git 与 Docker 构建上下文排除，不进入前端包或镜像层。
- 共享时只分发没有真实凭据的示例，容器运行时只读挂载配置，不能把完整配置交给浏览器。
- 日志、Trace、配置校验异常、连接字符串及公开配置摘要必须脱敏。
- 配置缺失或格式错误阻止启动；模型密钥为空不阻止显式 Schema 的确定性执行。
- 配置变更重启生效；不会在规范阶段读取、迁移或复制现有 `.env` 中的真实凭据。

## CloakBrowser 替换边界

- 替换页面采集的渲染浏览器与启动入口，业务层依赖统一浏览器适配接口。
- 保留直接 HTML 路径；HTTP 降级可配置并留下原因，禁止静默使用旧浏览器。
- 不新增验证码处理、登录绕过、代理轮换、反爬业务或收费功能。
- 不自动注册上游账号或购买许可；允许按 `config.toml` 在首次 URL 采集时自动下载
  配置指定版本的 CloakBrowser binary，不自动升级到其他版本。
- 可选浏览器授权凭据也从本地 TOML 读取；许可未配置时是否可用取决于选定构建，不能假装可用。
- 使用的 SDK 和二进制版本须固定并记录，不自动追随上游最新版本。
- CloakBrowser SDK 的底层 Playwright 依赖不等于继续使用原采集浏览器，不能为追求删除包而破坏 SDK。

核实来源（2026-10-07）：

- [上游仓库 README](https://github.com/CloakHQ/CloakBrowser)
- [Python 包元数据](https://pypi.org/pypi/cloakbrowser/json)

上述来源用于确认 Python 接入、SDK 依赖与准备流程，不代表已在本工作区完成浏览器运行验证。

## 旧约束替代与实施闸门

现有 `AGENTS.md`、README 和实现仍有“必须提供三个内置 Schema”“凭据只从环境变量读取”
以及“Playwright Python 作为采集浏览器”的旧描述。D1、D7、D9 是用户后续明确确认的替代要求；
不得在实施时依据旧描述恢复模板或继续使用环境变量凭据。

本轮已同步旧项目说明、依赖、配置示例、忽略规则、部署方式和 BDD 步骤。
LangGraph、ModelAdapter、ProgramSpec 白名单和禁止任意代码执行等约束不变。

仍属于实施细节的版本号、刷新周期、超时、并发上限和选择性准确率阈值必须以显式配置记录，
不作为当前已经测量或验证的事实。
