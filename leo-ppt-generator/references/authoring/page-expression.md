# 页面表达 authoring 合同

在已有 `content_model` v2 母版的每个 `page_expression` 中显式填写 `expression`。
完整可编译示例见 `page-expression-example.md`，数值是合同示例，不代表真实业务结果。
schema 唯一正式身份是 `https://leo-ppt.invalid/schemas/page-expression/v1`；内容包直接引用它，运行时离线解析。

每页六个必填字段：`reading_task`、`focus`、`reading_order`、`relation_encoding`、`fact_refs`、`uncertainty`。
focus 是引用，不能重复写结论；reading_order 必须显式包含 `claim`、全部必需 point、图和数字。
使用 `point:1`、`figure:1`、`fact:1` 引用本页各类条目的第 1 项；编译器转换为已有 item_id，不生成新事实。
也可直接使用已知 item_id。`claim` 指向当前页标题。
结构内容用本页 JSON Pointer，如 `/structures/sides/0`；数字的单位、期间等用 `/facts/fact:1/unit`。
跨页、路径穿越、悬空引用、未知字段、超长引用和重复顺序都拒绝。

| reading_task | relation_encoding 必需字段 | 约束 |
| --- | --- | --- |
| comparison | item_refs、dimension_refs、cells | 完整笛卡尔网格；每格引用 fact，或 `unknown:true` 与空 fact_ref 并显式记录 uncertainty |
| trend | samples、unit_ref、period_ref、baseline_ref | samples 含 time_ref/value_ref；严格有序时间、有限数值、同单位与期间；无基线时明确 null |
| process | nodes、edges、parallel_branches | 节点有序，依赖 from→to 不得逆序；parallel_branches 显式列出无内部依赖的节点 |
| causal | nodes、edges | 每边含 from、to、meaning_ref、support_refs；support 必须能回溯来源，不把 correlation 改成因果 |
| independent | item_refs、edges | edges 必须为空；保留引用、焦点与阅读顺序 |
| statement | item_refs、edges | 使用 independent 编码；只有 claim 的页面可以成立，不补造数据 |

最小文字页声明：

```json
{"reading_task":"statement","focus":"claim","reading_order":["claim"],"relation_encoding":{"item_refs":["claim"],"edges":[]},"fact_refs":[],"uncertainty":[]}
```

负例：focus 写成任意句子；reading_order 漏掉 point；comparison 漏格；trend 不填时间/单位；
process 逆序依赖；causal 引用无来源文字；independent 自动补边；声明 process 却提供 sides。
上述输入必须返回 `expression_incomplete` 或 `expression_declaration_conflict`，不能通过模板改写来消解。

不确定结构仍需显式声明当前能够表达的部分和 uncertainty；`semantic_structure:undecided` 只保留未定状态，
不豁免 focus/事实/阅读顺序要求。Agent 不得用默认 title/label、条目数量或关键词补齐缺失的表达合同。
