# 入口意图与 Workflow 路由

入口路由不是关键词分类器。它要识别用户希望文章替谁完成什么任务、真值来自哪里、最终如何验收，再选择 workflow。

## 四轴 route

```yaml
lifecycle_intent: create | research | shape | draft | revise | audit | humanize | train-voice | evaluate-voice | tool-select | personal-context | post-publish
article_family: not_applicable | argument | evidence-explainer | tutorial | how-to | technical-reference | technical-explanation | case-retrospective | personal-narrative | newsletter-platform | formal-report | marketing-copy
evidence_risk: low | medium | high
collaboration_modifier:
  mode: direct | coauthor
  voice: none | temporary | profile
  channel: ""
  persistence: chat-only | files
operation: "由 lifecycle_intent 映射"
depth: quick | standard | deep
```

展示 route 时使用以下 canonical route card，不省略字段或改写枚举值：

```yaml
lifecycle_intent: create
article_family: evidence-explainer
evidence_risk: high
operation: full
depth: deep
```

自然语言说明只能解释字段，不得替代字段本身。

`lifecycle_intent` 决定从哪个节点进入，`article_family` 决定主 workflow，`evidence_risk` 决定 depth，modifier 决定交互与声音。四者正交：例如「用我的声音逐节共创一篇研究解释文」是 `create × evidence-explainer × high × coauthor+profile`。

`train-voice`、`evaluate-voice`、`tool-select`、`personal-context` 和 `post-publish` 是非文章 lifecycle，必须设 `article_family: not_applicable`，直接进入其专用合同。`research`、`shape`、`audit` 只有明确服务某篇文章时才继承该文章 family；独立研究或工具审查也使用 `not_applicable`。

用户比较写作/Humanizer 工具的许可证、隐私、维护状态或写文件范围时，即使需要外部调研，也必须保留 `tool-select × not_applicable`；不得把内部研究动作升级为顶层 `research` lifecycle。

## 生命周期映射

| 用户真正要做的事 | lifecycle_intent | operation |
|---|---|---|
| 从问题到终稿 | `create` | `full` |
| 只找资料、核来源 | `research` | `research` |
| 定主张、论证或大纲 | `shape` | `shape` |
| 已有 brief/大纲，写成正文 | `draft` | `draft` |
| 改现有稿件且允许修改 | `revise` | `revise` |
| 只找问题、不修改 | `audit` | `audit` |
| 只处理模板感 | `humanize` | `humanize` |
| 建立/验证声音档案 | `train-voice/evaluate-voice` | 同名 operation |
| 选择或核验外部工具 | `tool-select` | `tool-select` |
| 建立个人说明书或宿主投射 | `personal-context` | `personal-context` |
| 复盘真实发布数据 | `post-publish` | 顶层流水线 Node 14 |

“优化、改好、看看”不足以判定写权限。给定现有稿件但没有明确允许改写时，默认 `audit`；用户说“修改、重写、直接改文件”才进入 `revise` 或 `humanize`。

## 文章类型判断

仅当 `article_family` 不为 `not_applicable` 时，优先看五项，不按单个词匹配：

1. **读者任务：**形成判断、理解机制、完成操作、复盘事件、理解作者、维持订阅关系、做决策，还是采取购买行动？
2. **真值基础：**论证与证据、来源综合、可执行步骤、时间线/记录、第一人称经历、栏目承诺、组织数据，还是产品证明？
3. **作者位置：**提出立场、解释、教练、复盘者、叙事者、主编、报告人或品牌？
4. **结构时间：**命题推进、概念解释、任务顺序、事件前后、经历弧线、期刊节奏、决策结构或转化漏斗？
5. **退出标准：**观点成立、读者理解、步骤跑通、教训可追溯、经历真实、栏目兑现、建议可决策或 CTA 清楚？

## 置信度与提问

- **高：**用户给出体裁、读者或明确结果。声明「按 X workflow 执行」并继续。
- **中：**大部分信号一致，错误可逆。声明推断及关键假设，继续执行；用户可纠正。
- **低：**至少两个 family 同样可能，且会改变证据、结构或交付物。只问一个能分叉流程的问题。

### 裸主题硬路由

当请求只有“写一篇关于 X 的文章”或同等信息，只给出主题而没有 reader job、具体体裁、目标读者、现有 brief 或交付目标时，必须判为低置信度。此规则优先于“中等置信度可声明假设并继续”。

执行合同：

1. 输出且只输出一个 workflow 分叉问题；
2. 问题应优先区分读者是要形成判断、理解机制、完成操作、复盘事件还是支持决策；
3. 问完立即停止，等待用户回答；
4. 禁止起草正文、大纲、标题、route card 或编辑说明；
5. 禁止自行填入目标读者、文章 family 和语气后继续。

好问题示例：

```text
这篇内容更希望读者形成一个判断，还是照着步骤完成一件事？
```

不要一次询问体裁、字数、平台、语气、读者和材料。先解决 workflow 分叉，进入对应 brief 后再补真正缺失的字段。

## 路由卡

内部始终生成，只有用户要求计划、路由存在假设或任务较复杂时才展示：

```text
Route: create × evidence-explainer × high × direct
Workflow: 研究解释文 / deep
关键门禁: 原始来源、冲突证据、warrant、事实回归
假设: 面向已有基础认知的业务读者
```

路由卡是执行合同，不是正文内容。不得把它写进最终文章。

## 优先级与组合

1. 用户明确类型和授权。
2. 可验证的 reader job 与完成标准。
3. 当前材料和发布场景。
4. 关键词和常见体裁印象。

一份文章交付物只能有一个主 family，但可叠加局部能力。例如研究解释文可包含个人场景，正式报告可附技术 Reference；主 workflow 不因此改变。若一份文件承担两个相互冲突的 reader job，优先拆成两份，不做混合文体。非文章 lifecycle 不适用这条规则。

## 失败与回退

- 路由后发现核心证据不可得：收窄 thesis，或从研究解释降级为带边界的观点/观察，不伪造研究。
- 教程无法运行：标记 `not_run` 并停止发布放行，不能改成“解释文”逃避验证。
- 个人叙事缺真实经历：向作者索取，或改为非第一人称观点文。
- 正式报告缺决策 owner：先补决策问题和使用者，不写泛泛综述。
- 用户纠正类型：保留可复用上游材料，重新生成 route；不要硬把旧结构继续写完。
