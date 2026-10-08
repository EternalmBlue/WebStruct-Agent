# 能力索引（Feature Centers / Platform / UI）

相似能力按「功能中心、平台能力、前端能力」收敛：领域中心包含自己的 API 路由、领域服务、LangGraph 节点/工作流与持久化仓储；
平台能力负责跨中心复用；前端能力负责工作台交互。每类能力都通过**一份 Gherkin 规范**与**一组行为测试**约束。

> 维护规则：新增或移动实现代码必须同步更新本表；`.feature` 文件必须在实现之前修改。

| 功能中心 | 对外 API | 实现位置 | 规范文件 | 行为测试 |
| --- | --- | --- | --- | --- |
| 运行保障中心 ops | `GET /api/health` 与公开配置摘要 | `app/features/ops_center/` | [ops-center.feature](./features/ops-center.feature) | `tests/bdd/test_ops_center.py` |
| 模式中心 schema | `GET /api/schemas`、`GET /api/schemas/versions`、`POST /api/schemas/validate` | `app/features/schema_center/` | [schema-center.feature](./features/schema-center.feature) | `tests/bdd/test_schema_center.py` |
| 页面采集与多视图中心 page | 无独立端点（由抽取中心编排），CloakBrowser 渲染采集 | `app/features/page_center/` | [page-center.feature](./features/page-center.feature) | `tests/bdd/test_page_center.py` |
| ProgramSpec 中心 program | `GET /api/program-specs/verified` | `app/features/program_center/` | [program-center.feature](./features/program-center.feature) | `tests/bdd/test_program_center.py` |
| 抽取编排中心 extraction | `POST /api/extract`（202 回执）、`GET /api/extract/{task_id}`（结果） | `app/features/extraction_center/` | [extraction-center.feature](./features/extraction-center.feature) | `tests/bdd/test_extraction_center.py` |
| 评测中心 evaluation | `POST /api/benchmark/run`（202 回执）、`GET /api/benchmark/reports/{task_id}`（结果） | `app/features/evaluation_center/` | [evaluation-center.feature](./features/evaluation-center.feature) | `tests/bdd/test_evaluation_center.py` |
| 人工复核中心 review | `POST /api/reviews/manual` | `app/features/review_center/` | [review-center.feature](./features/review-center.feature) | `tests/bdd/test_review_center.py` |
| 对话式规格助手 spec-assistant | `POST /api/spec-assistant/revise` | `app/features/spec_assistant_center/` | [spec-assistant-center.feature](./features/spec-assistant-center.feature) | `tests/bdd/test_spec_assistant_center.py` |

## 平台能力规范

| 能力 | 对外接口或入口 | 实现位置 | 规范文件 | 行为测试 |
| --- | --- | --- | --- | --- |
| 链路追踪与运行监测 | `GET /api/runs/{task_id}`、`GET /api/runs/{task_id}/events`、`POST /api/runs/{task_id}/retry`、`GET /api/observability/summary` | `app/platform/observability/` 提供协议，ops 路由暴露查询 | [observability-center.feature](./features/observability-center.feature) | `tests/bdd/test_observability_center.py` |
| 统一配置 | `config.toml` 与 ops 健康检查、公开配置摘要 | `app/platform/configuration/` | [configuration-center.feature](./features/configuration-center.feature) | `tests/bdd/test_configuration_center.py` |

## 前端能力规范

| 能力 | 作用 | 实现位置 | 规范文件 | 行为测试 |
| --- | --- | --- | --- | --- |
| 响应式工作台 | 响应式布局、动态状态刷新、极简交互 | `frontend/src/features/`、`frontend/src/pages/` | [ui-workbench.feature](./features/ui-workbench.feature) | `frontend/src/pages/Dashboard.tsx` 与 `frontend/src/styles.css` |

## 平台层（platform，被功能中心共享）

| 模块 | 职责 |
| --- | --- |
| `app/platform/configuration/` | 本地 TOML 配置和凭据加载、校验、服务端设置与白名单公开摘要 |
| `app/platform/browser/` | CloakBrowser 启动适配、版本识别、准备状态与资源释放 |
| `app/platform/persistence/` | 数据库引擎、自动迁移、ORM 模型、JSON 载荷读写 |
| `app/platform/llm/` | 模型适配协议、可用的 OpenAI 兼容适配器、未配置时的显式失败适配器 |
| `app/platform/observability/` | 任务关联标识、节点事件、运行状态、指标聚合与统一监测查询 |
| `app/platform/text_processing.py` | HTML→文本、空白/日期归一化、证据片段截取 |

## 契约层（contracts）

`app/contracts/` 集中所有跨模块传递的类型化对象：`SchemaSpec`、`ProgramSpec`、`EvidenceBundle`、
`VerificationReport`、`AgentRunTrace`、`GraphRunState` 等，以及 LangGraph 图的共享状态定义。

## LangGraph 工作流

| 图 | 节点 | 所属中心 |
| --- | --- | --- |
| 抽取工作流 | `page_collector_node` → `view_normalizer_node` → `schema_agent_node` → `planner_agent_node` → `programmer_agent_node` → `extractor_agent_node` → `verifier_agent_node` → `repair_agent_node` → `result_persist_node` | `features/extraction_center/workflow.py` |
| 评测工作流 | `dataset_loader_node` → `baseline_runner_node` → `ours_runner_node` → `metric_agent_node` → `report_agent_node` | `features/evaluation_center/workflow.py` |

## 统一运行状态

所有抽取和评测任务使用同一组生命周期状态：

```text
queued → running → completed
                 ↘ failed
```

`task_id` 唯一标识一次工作流运行；`correlation_id` 关联同一请求链路产生的相关操作。
节点状态为 `pending/running/success/failed/skipped`，验证结果单独保存，不以 `completed` 表示节点成功。
节点嵌套、重试、HTTP 回执和恢复语义详见 [runtime-contract.md](./runtime-contract.md)。

## 模块归属原则

1. 一个可复用能力只能有一个权威归属模块，其他功能中心通过契约调用。
2. 任务生命周期、Trace、状态快照和指标聚合统一归属 `platform/observability/`。
3. 配置加载、校验和脱敏摘要统一归属 `platform/configuration/`。
4. 抽取、评测、人工复核和规格助手只保留领域编排，不复制配置、追踪和监测逻辑。
5. 前端按用户任务组织界面：输入与运行、结果与质量、诊断与评测；可复用展示组件归属 `frontend/src/features/common/`。

本表描述当前已落地的模块边界、平台路径和接口；新增能力必须先更新对应
`.feature` 与本索引，再修改实现。跨中心只通过明确公共服务接口调用，
由组合入口注入依赖，不禁止合法的领域协作。
