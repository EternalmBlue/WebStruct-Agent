# Specs：WebStruct-Agent 的规范层（Spec-First）

本目录是项目的**唯一事实来源（SSOT）**。任何功能变更都遵循「先写规范 → 再写行为测试 → 最后写实现」的顺序，
不允许出现「实现先落地、事后补文档」的情况。

## 目录约定

```
specs/
├── README.md                   本文件：spec-first 工作流约定
├── feature-centers.md          能力索引（中心 ↔ 规范 ↔ 实现 ↔ 测试 的映射）
├── module-boundaries.md        可复用能力的模块归属与依赖边界
├── decisions.md                已确认决策与旧约束的替代关系
├── runtime-contract.md         任务、节点、查询和恢复的统一语义
├── benchmark-protocol.md       五方法定义与指标计算口径
├── acceptance-plan.md          实现阶段的 BDD 验收设计
└── features/                   Gherkin 行为契约（每类能力一个 .feature）
    ├── ops-center.feature
    ├── schema-center.feature
    ├── page-center.feature
    ├── program-center.feature
    ├── extraction-center.feature
    ├── evaluation-center.feature
    ├── review-center.feature
    ├── spec-assistant-center.feature
    ├── observability-center.feature
    ├── configuration-center.feature
    ├── generalized-extraction.feature
    └── ui-workbench.feature
```

## 工作流（Spec-First + BDD）

```
① 需求澄清        ② 编写规范          ③ 编写失败测试      ④ 实现           ⑤ 回归
 需求讨论   →   specs/features/*.feature  →   tests/bdd/*.py  →   features/*/  →   全绿收尾
                （中文 Gherkin，面向行为）   （pytest-bdd 步骤）   （功能中心实现）
```

四条硬约束：

1. **新增/修改功能必须先有 `.feature` 场景**。没有对应场景的代码不允许合入。
2. **`.feature` 描述可观测行为**，不描述内部结构。步骤句子写「用户能看到的」，不写「调用了哪个函数」。
3. **步骤定义与 feature 文件一一绑定**。pytest-bdd 中 `scenarios()` 显式指向 Feature 名称与 `specs/features` 目录，
   禁止出现游离的、没有 scenario 的步骤。
4. **规范变更必须同步更新 `feature-centers.md` 或对应的能力索引**，保持索引与实际实现一致。

## 当前变更约束

当前规范包含已实现契约与阶段性待实现契约。后续新增或修改能力仍必须先更新
`.feature`、行为测试与能力索引，再修改 `backend/`、`frontend/` 或平台代码。
`generalized-extraction.feature` 是泛化单页抽取的阶段 1 红灯契约，进入实现前
必须先补齐其步骤绑定。

## 统一设计原则

- 系统不提供领域内置中文 Schema。Schema 必须来自用户输入、当前页面推断或评测数据集。
- 抽取与评测共享统一的运行状态、任务关联标识和节点事件结构；终态统一使用 `completed` 或 `failed`。
- 非敏感配置与敏感凭据统一由本地 `config.toml` 管理，不独立加载 `.env` 或接受环境变量覆盖。
- 本地 `config.toml` 不提交、不进入镜像和前端产物；可提交示例不包含真实凭据。
- URL 渲染采集使用 CloakBrowser；HTTP 降级必须由配置允许且留下事件，不静默换回普通 Playwright 浏览器。
- 流程 `completed` 与验证通过分开；节点状态不与任务状态混用。
- 已验证规则默认仅确定性执行与验证，字段级 LLM 修复需要显式启用，且不改写原规则。
- 历史任务和规则不因模板移除被删除，浏览器刷新不重新提交任务，后端重启不自动续跑中断任务。
- 评测指标区分实际测量、估算与不可用，方法定义和公式见 `benchmark-protocol.md`。
- 可复用的生命周期管理、追踪、监测、配置加载能力归属平台模块，由功能中心复用。
- 前端优先呈现抽取主流程，诊断信息按需展开，状态必须可动态刷新并适配小屏。

## Feature 文件约定

- 使用中文 Gherkin 关键字，文件首行必须是 `# language: zh-CN`。
- 关键字：**功能**（Feature）/ **场景**（Scenario）/ **假如**（Given）/ **当**（When）/ **那么**（Then）/ **并且**（And/But）。
- 一个「功能」对应**一个后端领域中心、平台能力或前端能力**；一个「场景」对应**一条验收标准**。
- 实现阶段将场景步骤绑定到能力索引对应的测试模块，句子文案即为步骤标识。
- 当前实现已与新规范同步；后端 BDD/单元测试与前端构建是回归验收入口。
- LangGraph 节点拓扑属于必须保留的架构契约，允许用图节点场景检查；其他场景优先描述用户可观察行为。

## 目录 ↔ 规范 ↔ 实现 的映射

| 层 | 位置 | 职责 |
| --- | --- | --- |
| 规范层 | `specs/features/*.feature` | 行为契约（人可读、机器可执行） |
| 契约对象 | `backend/app/contracts/` | 类型化输入输出（Pydantic / TypedDict） |
| 功能中心 | `backend/app/features/<center>/` | 每个中心自带 router / service / workflow / repository |
| 平台能力 | `backend/app/platform/` | 跨中心复用：配置、持久化、LLM、追踪、文本处理 |
| 行为测试 | `backend/tests/bdd/test_<center>.py` 或能力索引中的前端测试目录 | Gherkin 步骤定义绑定 feature 文件 |
| 单元测试 | `backend/tests/unit/<center>/` | 不直接对应场景的细粒度断言 |

## 执行命令

```bash
# 全部测试（BDD + 单元）
cd backend && pytest

# 只跑某个功能中心的行为测试
cd backend && pytest tests/bdd/test_extraction_center.py

# 只跑评测行为场景
cd backend && pytest tests/bdd/test_evaluation_center.py
```

## 验证边界

默认回归会 mock CloakBrowser 下载，不调用真实模型、不执行业务数据迁移；CloakBrowser
真实二进制下载与供应商调用需在网络和许可条件满足后单独烟测。离线验收执行：
`backend/.venv/Scripts/python.exe -m pytest -q` 与 `frontend/npm run build`。
