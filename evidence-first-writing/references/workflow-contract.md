# 写作流程合同

调研、分析、列纲和起草时读取本文件。流程允许递归：后续阶段发现问题时，返回拥有该问题的阶段。

## 1. 写作 brief

写作前必须确认以下五项。信息不足且无法从材料可靠推断时，宁可收窄范围和结论，也不要用常见模板补全：

1. **体裁：**短帖、长文、教程、复盘、评论、正式报告或其他明确类型。
2. **作者意图：**解释、说服、复盘、吐槽、记录、建立判断或其他明确目的。
3. **目标读者：**读者已经知道什么、真正卡在哪里；不得虚构一个低智读者或并不存在的误解。
4. **语气：**如冷静判断、现场复盘、亲身吐槽、轻微讽刺、克制说明；允许用户自定义。
5. **素材来源：**区分真实经历、已核实数据、有来源转述、作者推测和待核实信息。

只记录会改变编辑决策的字段：

```yaml
topic: ""
article_family: not_applicable | argument | evidence-explainer | tutorial | how-to | technical-reference | technical-explanation | case-retrospective | personal-narrative | newsletter-platform | formal-report | marketing-copy
genre: "该 family 下的具体体裁"
channel: ""
audience:
  identity: ""
  knows: ""
  needs: ""
reader_outcome: ""
author_intent: explain | persuade | analyze | reflect | document
author_position: ""
tone: ""
scope_in: []
scope_out: []
constraints: []
source_policy: supplied-only | research-allowed | primary-required
material_classes:
  verified_facts: []
  attributed_reports: []
  author_inferences: []
  author_experiences: []
voice_samples: []
```

当读者任务、作者意图和范围边界可以验证时退出。不要被可选元数据阻塞。

## 2. 调研问题与证据账本

把主题拆成可能改变主张的研究问题，而不是宽泛地搜集资料。按需要查定义、机制、规模、时间线、反证和边界条件。

用账本追踪主张：

| Claim ID | 待证主张 | 类别 | 来源 | 来源日期 | 证据摘录/位置 | 质量 | 状态 |
|---|---|---|---|---|---|---|---|
| C01 | ... | fact/judgment/experience | URL 或文件 | YYYY-MM-DD | 页码/章节 | primary/secondary | verified/disputed/unsupported/stale |

规则：

- 打开并阅读来源；搜索摘要不能当证据。
- 优先原始研究、官方记录、源码、逐字稿和第一方文档。
- 区分发布日期、事件发生日期和访问日期。
- 记录相互冲突的证据，不要静默取平均值。
- 引用必须支持相邻主张，而不只是讨论同一主题。
- 对时效性主张，在交付前再次核实。

当所有支撑核心论点的事实都被核实、收窄、归因或显式标记为未解决时退出。

## 3. 论证图

使用紧凑的 Toulmin 式结构：

```yaml
thesis: ""
reader_tension: ""
reasons:
  - claim: ""
    evidence_ids: [C01]
    warrant: "为什么这些证据能支持该主张"
qualifiers: []
strongest_counterargument: ""
response: concede | bound | rebut | investigate
excluded_angles: []
```

主论点必须表达一个选择或解释模型，而不是只复述主题。删除不能改变结论的理由。不得虚构弱小的读者误解来制造戏剧性反转。

当主论点能在既定范围内承受最强、且有证据的反方时退出。

## 4. 大纲

每节明确：

- 读者问题或任务；
- 本节主张；
- 所需 evidence ID；
- 与上一节的依赖关系；
- 可用的具体例子；
- 不应重复的内容。

执行交换测试：如果正文段落或章节可以随意换位，文章很可能只是平行摘要集合，而不是逐步推进的论证。

当每节都推动主论点，且开头没有承诺正文无法支持的内容时退出。

## 5. 起草

依据已确认的论证图和证据账本起草。对未解决内容保留显式标记，例如 `[需要来源：采用率]`；不得凭记忆静默补齐。按用户指定格式引用，并逐字保护直接引语。

段落结构可以变化，但每段通常应完成一个可辨认的动作：提出主张、给出证据、解释证据、限定范围、承接过渡或说明后果。因为思想需要而改变节奏，不要为了绕过 AI 检测器而改变节奏。

协作写作时，先起草不确定性最高的章节。局部应用用户反馈；只有当反馈揭示稳定偏好时，才更新声音说明。

当全文已完整到足以进行实质审查时退出，此时无需完成句子级润色。

## 6. Hook 优化

先分析现有开头承担的任务、有效信息、读者进入成本和与正文的承诺关系，再决定是否需要改。需要候选时至少提供 3 个结构真正不同的方向，例如直接判断、具体事实/数据、真实场景、问题或反常识冲突；不得为制造吸引力而编造故事或数据，也不得默认套用「钩子、痛点、承诺」。

每个候选说明适用读者和代价，并推荐一个。Hook 承诺必须在正文得到兑现；正式报告和技术参考通常优先直接说明目的，不强求戏剧化开头。

## 7. 逐节共创

`coauthor` 使用三个阶段：

1. **上下文倾倒：**让用户用任意形式提供背景、限制、既有讨论和隐含知识；再提出 5-10 个只针对真实缺口的问题。用户可以跳过或要求自由写作。
2. **逐节精修：**优先处理不确定性最高的章节。每节依次执行针对性提问、提出 5-20 个可选内容点、让用户保留/删除/合并、检查遗漏、起草、局部迭代。用户不想逐项筛选时，根据其自由反馈继续，不机械阻塞。
3. **读者测试：**预测 5-10 个目标读者问题，检查歧义、隐含前提和矛盾。只有真正隔离的新审查者收到正文且没有写作上下文，才称为独立读者测试；否则标记为作者侧模拟。

章节修改优先局部编辑，不因一处反馈重写全文。连续多轮没有实质变化时，询问还能否删除内容，然后进入下一节。

## 建议产物

只有用户要求落盘，或项目确实复杂时才创建：

```text
writing-brief.md
evidence-ledger.md
argument-map.md
outline.md
draft.md
review-report.md
final.md
```

短任务在工作上下文中维护这些结构，只返回用户要求的产物。
