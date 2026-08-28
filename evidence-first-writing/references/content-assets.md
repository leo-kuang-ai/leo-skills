# 内容资产层

流程保证单篇质量，资产保证稳定产出。本文件定义三类可复用资产与一条测试-放大回路，全部与因果红线兼容。维护动作挂在 `shape`（选题池、系列规划）与 `post-publish`（配方候选、观察回流）之下，不新增 operation。

## 1. 选题池

`shape` / `research` 产出的待写 backlog，每条记录：

```yaml
question: ""            # 读者问题
momentum: {}            # topic-momentum 四问的预填（可部分为空）
priority: high | medium | low
source: ""              # 选题来源：讨论观察、读者提问、系列规划
```

纯规划资产，不涉红线。重跑选题价值验证时优先消费池内条目，避免临场找题。

## 2. 配方候选区（gated）

标题模式、开头模式、论点压缩句的沉淀库。因果红线禁止把单篇表现升格为规则；本库把红线显式化为**分级沉淀**：

```yaml
pattern: ""
tier: hypothesis | promoted
replications: 0         # 可比项目独立复现次数
comparable_runs: 0      # 满足可比控制的项目数
counterexamples_checked: false
notes: ""
```

- 单篇表现只能以 `hypothesis` 入库：可被下一篇引用尝试，但条目永久携带未验证语义，引用时编辑说明必须声明其为未验证假设；
- 升格 `promoted` 的条件与 `editorial-pipeline.md` Node 14 的 `stable_rule_update` 完全一致：`replications >= 2`、`comparable_runs >= 2`、`counterexamples_checked: true`；三个条件缺一个，只能停留在 hypothesis 层。

条目示例（来自 2026 年微信科技圈样本，证据等级见标注）：

```yaml
pattern: "职业威胁型标题：「XX，危！」+ 新能力实证"
tier: hypothesis
replications: 0
comparable_runs: 0
counterexamples_checked: false
notes: 量子位「视频后期，危！MiniMax H3手绘即特效」样本（inferred）；情绪为
  anxiety，正文必须给出口（新岗位/新工作流），否则违反情绪曲线三段合同
```

```yaml
pattern: "场景下沉型：成熟技术 × 非技术人群的具体场景指南"
tier: hypothesis
replications: 1        # 台账 verified 双例（同属一母题，计 1 次独立复现）
comparable_runs: 1
counterexamples_checked: false
notes: 「DeepSeek 中老年人使用指南」等 verified 样本；母题轮换后该形态
  可迁移到下一个国民级工具；升级仍差反例检查与第二次可比复现
```

## 3. 系列规划

母题-问题矩阵：一个母题下拆出一组读者问题，按 [topic-momentum.md](topic-momentum.md) 四问排序成选题序列。系列文章共享 [reader-profile.md](reader-profile.md) 的更新；系列不是拆水文，每个成员必须独立通过选题价值验证。

## 4. 测试-放大循环

选题四问中时机或情绪证据不足时，不直接写长文：

1. 用低成本形态探测（短帖、单条论点压缩句、投票），面向目标圈层发布；
2. 探测结果记录为 observation（点开、回复、引用情况），只作四问的证据输入；
3. 证据补齐再展开长文；探测失败则回选题池，不写。

探测数据不得当作因果证据，不得据此外推「读者喜欢 X」的结论。

## 持久化

三类资产默认只在当前会话维护；落盘需要用户明确授权和目标路径（沿用 `personal-context` 机制），未授权时停在 `persistence: not_run`。
