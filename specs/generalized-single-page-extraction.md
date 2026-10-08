# 泛化单页抽取规范

状态：阶段 1 规范草案，待 BDD 场景全部实现后转为已验证规范。

## 目标

系统面向一个用户明确提交的单页 URL，完成以下闭环：

1. 采集并归一化该页面；
2. 判断页面是否确实是可抽取的单资源页或文章页；
3. 与 AI 协作确定抽取范围和字段；
4. 生成绑定当前页面结构的安全 `ProgramSpec`；
5. 在同站点、同结构的其他单资源页上复用该规范；
6. 对正文完整性、字段证据、复用兼容性和运行结果进行可观测记录。

MineBBS、MCMod、Wikipedia、萌娘百科只是验证样本，不是规则来源。规范不得
包含站点名称、站点专用 selector、站点专用字段模板或挑战页识别逻辑。

## 页面意图

页面采集后必须产生一个通用的 `PageIntent`：

```text
single_resource  单个资源、条目、产品或对象详情页
article          单篇文章、新闻或百科正文页
list             分类、搜索、分页或资源索引页
home             站点主页、频道首页或门户聚合页
unknown          信号不足或互相冲突
```

页面意图只使用通用结构信号：

- 主要标题是否唯一且位于主要内容区域；
- 是否存在作者、发布时间、版本或其他详情元数据；
- 是否存在连续正文块；
- 重复列表项占可见内容的比例；
- 导航、侧栏、页脚和推荐区域占主要文本的比例；
- 页面是否包含多个同级详情卡片。

页面意图不是访问控制或挑战页识别。浏览器挑战只由统一的导航等待策略处理。

### 抽取闸门

- 用户意图为 `single_resource` 时，分类结果为 `home` 或 `list` 必须阻止正文抽取，
  并返回可追踪的 `page_intent_mismatch` 原因。
- 分类结果为 `unknown` 时不得静默当作详情页；可以请求用户确认或进入一次性
  AI 规划，但必须保留低置信度观测。
- `single_resource` 和 `article` 允许继续进入 SchemaAgent、PlannerAgent 和
  ProgrammerAgent。
- 页面意图判断失败不得伪造空的成功结果，也不得改用站点专用兜底模板。

## 正文候选与完整性

正文字段不能只绑定一个“命中节点”的 selector。页面归一化必须保留若干正文候选
区域，每个候选至少包含：

- DOM 定位信息（CSS 和/或 XPath）；
- 可见文本、文本块数量、heading/block 层级；
- 候选区域的祖先和邻接结构摘要；
- 被排除的导航、侧栏、页脚、广告、相关推荐等噪声摘要；
- selector 命中数量和空值状态。

正文候选评分至少输出以下独立观测：

```text
visible_text_coverage = 候选区域可见字符 / 页面主要可见字符
block_coverage         = 被候选覆盖的正文块 / 主要正文块
continuity_score       = 正文块在文档中的连续性
noise_ratio            = 候选区域中被判定为外围噪声的字符 / 候选字符
```

评分不能用单一 selector 命中作为完整性证明。以下情况必须拒绝候选或降级为
低置信度，并触发重新规划：

- 只有摘要、简介、首段或资源关联描述；
- 正文之后存在明显连续内容但候选未覆盖；
- 候选主要由导航、页脚、推荐项或侧栏组成；
- 候选为空、只有图片占位符或只有脚本/样式文本；
- 多个候选区域之间存在可合并的连续正文却只保留首个区域。

候选合并必须保留文档顺序、段落边界、代码块和表格文本，并排除重复节点。
图片 alt、链接文字等是否进入正文由字段 Schema 和证据策略决定，不能隐式扩大
正文范围。

## Schema 与 ProgramSpec 协作

URL-only 请求的顺序固定为：

```text
collect → normalize → classify → SchemaAgent → PlannerAgent → ProgrammerAgent
```

页面采集前不得强制套用系统内置领域 Schema。用户显式提供的 Schema 可以作为
覆盖，但必须在运行 Trace 中区分：

```text
schema_generation_mode = user | inferred | benchmark
program_generation_mode = llm | deterministic_fallback | reused
```

ProgramSpec 必须绑定生成时的页面结构摘要，而不是只绑定 `SchemaSpec` 签名。
ProgramSpec 仍然只能使用受支持的 DSL 策略，禁止 `eval`、`exec` 或任意代码。

## 结构指纹与复用

每个可持久化、可复用的 ProgramSpec 必须记录 `PageStructureSignature`，至少包括：

- `signature_version`；
- `page_intent`；
- 标题、正文候选和元数据区域的结构摘要；
- heading/block 数量区间和重复项比例；
- 各字段规则在生成页面上的 selector 命中数；
- 正文候选的覆盖率、连续性和噪声比例区间。

结构摘要不得保存完整网页、完整提示词或敏感凭据。selector 的具体值可以保存为
ProgramSpec 的 DSL 内容，但必须经过当前页面的安全验证。

复用前必须返回兼容性判断：

```text
compatible | incompatible | unknown
```

兼容条件至少包括：

- 页面意图相同；
- 标题和正文候选结构落在已验证区间；
- 必填字段规则的 selector 命中状态满足要求；
- 正文覆盖率和噪声率没有越过已验证边界。

仅 Schema 名称相同、仅 hostname 相同或仅 URL 路径相似，均不能证明兼容。

- `compatible`：允许复用，并记录 `reuse_decision=accepted`；
- `incompatible`：不得复用，重新进入 PlannerAgent/ProgrammerAgent，并记录拒绝原因；
- `unknown`：默认不复用，除非用户显式确认一次性试用。

## RSI 与可观测性

每次页面抽取至少记录以下指标，并区分 `measured`、`estimated`、`unavailable`：

- 页面意图及置信度；
- 正文候选数量、选择数量和合并数量；
- 正文可见文本覆盖率；
- 正文 block 覆盖率与连续性；
- 正文噪声率；
- selector 命中数、空值数、歧义数；
- ProgramSpec 结构兼容性与复用决定；
- 复用成功、拒绝、回退和重新生成原因；
- 字段完成率、必填缺失率、证据覆盖率；
- verifier 分数和 RSI 质量代理。

这些指标是质量代理，不是假定的人工 gold accuracy。不同结构指纹、不同页面意图
或不同评估器版本的运行不能直接宣称质量提升。

## 非目标

- 不自动发现并爬取论坛主页或分类页；
- 不把主页、列表页误当成单资源页；
- 不为 MineBBS、MCMod、Wikipedia 或萌娘百科添加硬编码适配器；
- 不做验证码破解、挑战识别、代理轮换、登录绕过或反爬绕过；
- 不在运行时自动修改代码、规则或部署配置；
- 不把 DOM reference comparison 当作人工正确率。

