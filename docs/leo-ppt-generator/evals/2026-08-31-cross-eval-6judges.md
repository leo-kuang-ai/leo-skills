# leo-ppt-generator 交叉测评报告（darwin-skill × skill-upper，6 judge × 2 轮，2026-08-31）

- **方法**：三轴交叉——行为轴（skill-up：既有 13 轮行为数据 + M1 78-case 轮在跑）、结构轴（darwin 9 维，6 个相互独立的评审 agent）、paired 版本轴（同 judge 同上下文内比较，within-judge cancellation）。方案全文：`leo-ppt-workspace/cross-eval-0831/PLAN.md`
- **对象版本**：C = pre-fusion（31ef61b，271 行）/ A = M0.1（HEAD 1369db1，284 行）/ B = M1（工作树，302 行）
- **runtime 中立性 gate**：红灯扫描 0 命中（darwin gate 通过）

## 一、Paired 多数决（keep/revert 级证据）

| 比较 | 第 1 轮（J1/J2/J3） | 第 2 轮（J4/J5/J6） | 合计 |
|---|---|---|---|
| **A→B（M0.1 vs M1）** | better/clear ×2 + better/slight ×1 | better/clear ×2 + better/slight ×1 | **6-0 better**（4 clear + 2 slight） |
| **C→B（pre-fusion vs M1）** | better/clear ×3 | better/clear ×3 | **6-0 better**（6 clear） |

**跨轮零翻转**——两轮独立评审团方向完全一致。多位 judge 给出了用例级实证链：C 版缺失条款 ↔ stability 10 轮 0/10 FAIL ↔ iteration-85 全数转绿（如收据门、学术三字段、样张反演），B 增量中的成本预估/同回合确认有 iteration-86→88 两轮收敛证据。**结论：融合弧（M0+M0.1+M1）与 M1 增量均为无回退面的净增益，无需任何 revert。**

## 二、9 维绝对分（仅 triage——darwin 实证换 judge 可摆 ±8）

| 维度 | J1 | J2 | J3 | J4 | J5 | J6 | 均值 | 共识 |
|---|---|---|---|---|---|---|---|---|
| dim1 Frontmatter | 9 | 9 | 9 | 9 | 9 | 9 | 9.0 | 稳定强 |
| dim2 工作流清晰度 | 8 | 8 | 8 | 8 | 8 | 9 | 8.2 | 「不变边界」巨节 + ⑥⑦不在主文件 |
| dim3 失败模式编码 | 9 | 9 | 9 | 8 | 9 | 9 | 8.8 | 强；跨会话恢复与 registry 记账两缺口 |
| dim4 检查点设计 | 10 | 9 | 9 | 10 | 9 | 9 | 9.3 | 四显性 GATE 全票认可 |
| dim5 可执行具体性 | 9 | 8 | 9 | 9 | 9 | 9 | 8.8 | 强；指针化口径（词表下沉）注意 |
| dim6 资源整合度 | 8 | 8 | 9 | 10 | 10 | 10 | 9.2 | 抽查全可达（累计 70+ 路径） |
| dim7 整体架构 | 8 | 8 | 8 | 8 | 8 | 8 | 8.0 | **全票 8**：防御性重复 + 长条目 |
| dim8 实测表现 | 8 | 7 | 8 | 8 | 7 | 7 | 7.5 | **最弱维度**（见归因） |
| dim9 反例黑名单 | 10 | 9 | 9 | 9 | 10 | 9 | 9.3 | 红灯清单被两 judge 称"范本形态" |
| **加权总分** | 86.1 | 80.8 | 85.3 | 85.1 | 84.0 | 84.6 | **84.3** | 极差 5.3 < ±8 噪声带 |

## 三、结构弱点 ↔ 行为失败交叉归因（本报告核心增量）

| # | 结构缺口（6 judge 共识度） | 行为证据 | 修复建议 |
|---|---|---|---|
| 1 | **prompts/registry.yaml 记账规则在 SKILL.md 入口零提及**（6/6 judge 独立点名） | gamma-m6-prompt-registry 持续 FAIL（stability 2/10、iteration-85 FAIL），实测答"不用走流程" | P0：SKILL.md 按需读取表或不变边界加一行（"prompts/ 任何 .md 变更须先在 registry.yaml 记账，governance lint 无条目即 FAIL"）——与 M0.1 教训同型（横切规则不上入口即失效） |
| 2 | **跨会话恢复场景无条款编码**（J4 dim3、J1/J2 dim8） | post-confirm-revision-doc-gate 10 轮 1 过、master-doc 全量轮超时/失败（沙箱无前次工件时行为正确但措辞不被判分器认） | P1：编码"继续上次任务而工件不可寻址/多候选命中"分支（找不到→列候选求指认，禁凭空声称存在） |
| 3 | **「不变边界」巨节可扫读性**（6/6 在 dim2/dim7/dim5 提及） | 密度/预算类 case 历史波动（M0.1 已用入口锚点治愈同类问题） | P1：CONFIRM-GATE/模版推荐两条超长条目 TL;DR 化拆分；"按需读取表"与"执行导航"两处清单去重；Gate 0/worker 固定块"一处定义+一处速查引用" |
| 4 | **M1 新条款行为验证缺口**（J3/J4：TF-1/TF-2、sources-strict、rst-paging 专项 case） | M1 78-case 轮运行中（alpha-m1 四 case 正是这些条款的行为验证） | 已在补：本轮完成后回填 |

## 四、诚实记录

- iteration-85 记录态为 **15/18**（J1/J3 独立复核纠正；我先前 16/18 误计入了判官修复后的重放补正）
- stability CSV 首统 CRLF 误读为 0%，J6 修正为 92/180=51.1%（低通过率大半为修复前校准缺口，round-11 修复后 15/18）
- 绝对分极差 5.3 恰在 darwin 实证 ±8 judge 噪声带内——本轮再次验证"绝对分只做 triage"教义；若按绝对分 delta 决策会出现 J1(+86.1) vs J2(80.8) 的假分歧，而 paired 比较 6 位全数一致

## 五、结论与建议

1. **融合方向被 6/6 独立 judge 双轮一致确认为净增益**（M1 增量 6-0 better、全程弧 6-0 clear better），无任何 revert 依据
2. triage 均值 84.3，结构面 dim4/dim9/dim6 是全票强项（治理设计是全技能的差异化资产）
3. 唯一持续弱项 dim8 的两大根因均有明确 P0/P1 修复路径（registry 入口行、恢复分支编码），成本低
4. darwin 成果记录：`cross-eval-0831/results.tsv`（paired 4 行 + triage 2 行，eval_mode 标注）
