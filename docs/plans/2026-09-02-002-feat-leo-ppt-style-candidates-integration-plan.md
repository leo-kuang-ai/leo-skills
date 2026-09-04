---
title: leo-ppt-generator 候补源残余集成与 300 硬顶退役 - Plan
type: feat
date: 2026-09-02
topic: leo-ppt-style-candidates-integration
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: spec-plan-bootstrap
execution: code
status: active
---

# leo-ppt-generator 候补源残余集成与 300 硬顶退役 - Plan

## Goal Capsule

- **Objective**：在两条新基线上收口候补矿的剩余集成面——① owner 2026-09-02 决策**退役 300 硬顶**（风格库独立可选风格不再设数量上限，防膨胀改由质量门承担）；② C1-C4 进货批（2026-09-01，净增 89）已清空主要风格条目矿，剩余净价值集中在**语料/机制层**（负面语料、容量查询词汇、构图词汇、色板池）与两笔治理债（硬顶合同文本、候补台账与 C 批实收不同步）。
- **Recommended approach**：三批推进——Batch A 治理面（硬顶合同退役 + 候补台账 C 批同步，纯文档修订，先行）；Batch B 语料/机制层（五路语料资产落盘，不占风格条目、不依赖使用信号）；Batch C 补货通道固化（信号驱动评估流程 + 金样板义务成文，余量源按点名落空信号择机执行）。
- **Decision focus**：硬顶退役后防膨胀护栏的替代构成（KTD1）；负面语料以"参考池文档"而非批量改 brief 的形态落地，与渐进补齐纪律兼容（KTD2）；台账余量真值以迁移器 `--report` 为准、文档只做登记（KTD3）；与风格库重构 plan（2026-09-02-001）的执行时序（KTD4）。
- **Verification focus**：治理 lint 全绿；`audit_style_families.py` 疑似同族簇不高于当前基线 10 且 ≤ 回退门槛 20（known-issues C 批口径：10 为当前值、>20 才触发回退）；迁移器 `--check` 幂等；新增语料/词汇资产有单测或可机检的存在性断言；候补台账与 `evals/known-issues.md` C 批口径一致。
- **Largest risk / boundary**：本方案**不动推荐算法**（归坐标系 plan）、**不做计数单一真值**（归重构 plan R4，单一 owner）、**不批量重写存量 brief 的 negative_prompt**（渐进纪律）、**不主动执行风格条目补货**（余量源按使用信号择机）；若与重构 plan Phase 0 合批执行，Batch A 文档修订需按其新元数据口径落地。

---

## Product Contract

### Summary

以"300 硬顶退役（owner 决策）+ C1-C4 已清空主矿"为基线，把候补清单（`leo-ppt-generator/references/style-candidates.md`）中仍具净价值的集成面分三批落地：治理面修订（硬顶合同退役、台账同步 C 批实收）、语料/机制层资产（huashu 审美禁区负面语料、dashi 容量选页词汇、nano-banana 构图词汇、ian-handdrawn 手绘素材语汇、OfficeMCP 色板入池）、补货通道固化（信号驱动评估流程与金样板义务成文）。全部增量不削弱既有质量门（四重去重、治理 lint、audit 簇数门、金样板与预览义务）。

### Problem Frame

- **硬顶合同与 owner 决策冲突**：300 硬顶作为上限断言散在三处合同文本——`references/style-candidates.md` 表头两处（定位行"不占 300 硬顶"、补货门"300 硬顶余量检查……余量不足先家族内归并腾位，仍不足顺延"）与 `references/styles/00_索引/_INDEX.md` 顶行（"独立可选风格合计 294 ≤ 硬顶 300"）。owner 2026-09-02 决策去掉该限制，三处文本若不同步退役，治理文档自相矛盾，且补货评估会继续按"余量 6"错误决策。已核实 `scripts/lint_style_index.py` 无 300 断言，退役纯文档面，成本低。
- **候补台账滞后于 C 批实收**：`style-candidates.md` 正文停留在 2026-08-31 快照（S4b 口径），仅 C2 两源（slides-grab/OfficeCLI）回写了"已收"标注；C1/C3/C4 覆盖的源条目仍写旧状态——gpt-image2 写"本批不入"（C1 实收 12 主 + 233 池归并 7 池代表）、beautiful 写"预期 SKIP 率高"（C3 实收 14，原判被推翻）、academic/huashu 写"S3 配额 6-10 在收"（C3 实收 4/6）、xhs 写"净新 8-12"（C4 实收 4）。读者基于过期余量做补货决策是实际风险。`evals/known-issues.md` 明确"台账余量已由 C 批清空（各源吸收/跳过台账在迁移器 --report 可复现）"，但正文未兑现该同步。
- **语料型资产未被 C 批开采**：C1-C4 是纯风格条目批（+2 渲染锚），候补清单登记的五路语料/机制层资产全部未动：huashu 审美禁区（负面语料，已核实仓库内无负面语料参考池文档，且主库有约 126 份 brief negative_prompt 不足 3 条的在册渐进债）、dashi 容量选页硬条件词汇（`12_版式库/*.layouts.json` 已有静态 `content_capacity` 字段，缺按容量条件筛选版式的查询面）、nano-banana 六类视觉词汇表 + 50+ 一句构图描述（08 轴参考）、ian-handdrawn 手绘箭头/便签素材语汇、Office-PowerPoint-MCP 8 色板（`scripts/chart_palette_pool.py` 补非重叠）。
- **信号通道不完整**：候补合同的驱动信号三通道（R-30 分角色组合、R-64 推荐落盘反馈、R-55 负触发与点名落空）中，仅 R-55 基本可用（91 case 含负触发组）；R-64/R-30 归 R3 PRD 的 R3-4 择优批未落地。硬顶退役后若不把"质量门替代数字上限"的护栏成文，防膨胀失去显式依据。

### Key Decisions

- **KD-1 硬顶退役，质量门接管防膨胀**（owner 2026-09-02 决策）：独立可选风格不设数量上限；补货节制由既有质量门组合承担——四重去重（概念级 SKIP／色板指纹 family_duplicate／同板并入 variant_of／跨源同名同族合并）+ 治理 lint 全绿 + audit 疑似同族簇不恶化（现基线 10）+ 金样板与配对预览义务 + 信号驱动触发（点名落空为主通道）。
- **KD-2 语料层先行，不依赖使用信号**：语料/机制层资产（负面语料、容量词汇、构图词汇、素材语汇、色板）是对存量体系薄弱面的定向增强，不新增风格条目、不受信号纪律约束，本批直接做。
- **KD-3 风格条目补货仍按信号**：硬顶退役≠全量进货。余量源（xhs 4-8、academic 2-6、beautiful 复核等）保持"点名落空持续出现才评估"的触发纪律；本方案只固化评估流程与出口门，不预排进货执行。
- **KD-4 台账真值分层**：各源吸收/跳过明细的真值是迁移器 `--report` 输出（幂等可复现）；`style-candidates.md` 只登记快照口径的余量与状态，标注快照日期，不复制明细。

### Requirements

- **R1（硬顶合同退役）**：三处合同文本移除 300 上限断言——`style-candidates.md` 定位行与补货门、`_INDEX.md` 顶行；补货门改写为纯质量门（四重去重 + 治理 lint + audit 簇数 + 金样板义务 + 信号触发），不再含"余量检查/腾位/顺延"语义；`evals/known-issues.md` 的历史入账记录（"≤300 硬顶""硬顶 220"）作为历史账保留不改。
- **R2（候补台账 C 批同步）**：`style-candidates.md` 全部源条目刷新为 C 批后实收/余量口径（快照 2026-09-02），与 `known-issues.md` C1-C4 终局收口段、CHANGELOG C 批条目、迁移器 `--report` 三方一致；表头"19 源零遗漏"的净价值排序按 C 批后余量重排。
- **R3（负面语料参考池）**：huashu-design 审美禁区提炼为 negative_prompt 语料参考文档（思想级改写，不搬原文），按视觉家族/场景组织——**首期只覆盖该语料可派生的家族组（东方意蕴/中式载体/质感专业等三派辐射面），其余家族留扩展位不硬凑**，供两处消费：存量 brief"顺手补"渐进债（点名命中或渲染修订时补至 3-5 条，`scripts/draft_negative_prompts.py` 可引用该池派生草案）与新风格入库时的 negative_prompt 起草。**不批量重写约 126 份 brief**（渐进纪律，见 `references/style-library.md` 渐进治理债节）。
- **R4（容量查询词汇）**：dashi 容量选页硬条件词汇（title-chars/item-count 档位分布）吸收进 `12_版式库`——`content_capacity` 既有槽位字段（title/subtitle/meta 各带 chars_per_line/max_lines/max_chars）不变；**条目数（item-count）为现有 schema 没有的维度，按向后兼容的键级增量新增**（旧键不动、新键可选，旧消费者不读新键则行为不变），不是纯查询面改造；查询面按"标题字数/条目数"条件预筛版式（消费方 `references/layout-dispatch.md` 的容量预检），缺省输出不变。
- **R5（构图与素材词汇）**：nano-banana 六类视觉词汇表 + 50+ 一句构图描述以参考文档落盘（08 轴参考面，缓解生图构图同质化；不学其富提示词密度哲学——评审反面结论）；ian-handdrawn 手绘箭头/便签素材语汇进手绘家族参考（机制层已吸收，仅素材语汇）。
- **R6（色板池补非重叠）**：Office-PowerPoint-MCP 8 色板对照 `scripts/chart_palette_pool.py` 现池做色板指纹查重，非重叠者入池；重叠者登记跳过台账。
- **R7（补货通道固化）**：信号驱动的补货评估流程成文（触发信号 → 四重去重 → 精选 → 金样板三页 + 视觉风格配对预览行 → 治理 lint + audit 出口），更新进 `style-candidates.md` 表头合同与 `references/styles/00_索引/style-extension-template.md` 的合格门清单；余量源首推候选（xhs-visual-director 余量 4-8、academic 学术细分 2-6）在台账标注"信号触发首选"。
- **R8（Mck avoid_for 补缺，可选）**：Mck CATALOG Use/Don't-use 卡片结构思想级改写，补 `12_版式库` 咨询系版式的 avoid_for 字段薄弱面；仅当咨询系版式 avoid_for 稀疏度核实成立时执行，否则登记不收。

### Success Criteria

- **合同一致**：`rg -n "硬顶 300|300 硬顶|≤ 硬顶" leo-ppt-generator/references/` 仅剩历史记录（known-issues/CHANGELOG 历史条目），活合同零残留。
- **台账同步**：`style-candidates.md` 每源条目含 C 批实收数与快照日期；gpt-image2/beautiful/academic/huashu/xhs/frontend-slides/awesome-ppt-skills/dashi/awesome-gpt-image-2 九源状态与 `known-issues.md` C1-C4 段数字一致。
- **语料资产存在且可机检**：负面语料参考池、构图词汇参考、容量查询词汇各自有存在性断言（单测或 lint）与来源登记（许可口径：huashu 思想级、nano-banana MIT、dashi 已授权、OfficeMCP 色板指纹非重叠直引）。
- **质量门零回归**：治理 lint 六条全绿（`lint_style_briefs`、`lint_style_index`、`lint_style_governance`、`lint_layout_grid`、`lint_render_templates`、`lint_skill_structure`，全集=`scripts/lint_*.py`）；`audit_style_families.py` 疑似同族簇不高于当前基线 10 且 ≤ 回退门槛 20（known-issues C 批口径：10 为当前值、>20 才触发回退）；全量单测零新增失败（基线 1120 tests OK）；迁移器 `--check` 幂等（全集=`scripts/intake_*.py`，现 7 个）。
- **行为面零变化**：本批为语料/文档/参考层增量，`style render` 缺省输出逐字节不变（若 R4 触碰 `style layouts` 查询输出，仅新增旗标/字段、缺省输出不变）。

### Scope Boundaries

**In scope**：`references/style-candidates.md`（表头合同 + 19 源台账）、`references/styles/00_索引/_INDEX.md`（顶行硬顶断言移除）、`references/styles/00_索引/style-extension-template.md`（合格门清单增补货流程引用）、负面语料/构图词汇/容量词汇/手绘素材语汇参考文档（落位见 Interface Contracts）、`scripts/chart_palette_pool.py` 池数据增量、`12_版式库` 容量查询面（layouts sidecar 消费路径）、`scripts/draft_negative_prompts.py` 语料池引用接线、根 `CHANGELOG.md`。

**Out of scope（非目标）**：
- 推荐算法（MMR/tier/硬规则）——归坐标系 plan（`2026-09-01-001`）。
- 计数单一真值与三处文档计数派生——归重构 plan R4（单一 owner）；本方案只移除硬顶断言，不重定义计数口径。
- 风格条目补货的**执行**（任何源的新风格入库）——按信号择机另行立项；本方案只固化通道。
- 存量约 126 份 brief negative_prompt 的批量补齐——渐进纪律（点名命中/渲染修订时顺手补）。
- R-64/R-30 信号通道建设——归 R3 PRD R3-4 择优批。
- brief `source`/`taxonomy` 元数据、目录分层——归重构 plan Phase 0-2。

**Deferred to Follow-Up Work**：
- beautiful-html-templates 余量二次复核（C3 推翻"零净新"原判实收 14，是否还有净新需专门评估）——按可编辑路线 HTML token 主题点名信号触发。
- Mck 版式骨架（R8）与 scholar-ppt-cn/MultiAgentPPT/AI-PPT-Slides 小额杂项——维持候补登记，按各自触发条件评估。

### Dependencies / Assumptions

- **依赖**：重构 plan（`2026-09-02-001`）若先行落地 Phase 0，`style-candidates.md`/`_INDEX.md` 的修订需按新元数据口径写（`source` 字段、`briefs/` 单树）；建议 Batch A 与重构 Phase 0 合批或紧邻，避免同一文档两轮重写。
- **依赖**：R4 容量查询面的消费方 `layout-dispatch.md` 容量预检为既有合同，扩展不得破坏其缺省行为。
- **A1**：`lint_style_index.py` 无 300 硬顶断言（已核实，2026-09-02），硬顶退役纯文档面。
- **A2**：C 批终验数字（312 briefs / 295 主风格 + 17 变体 / 净增 89 / 六 lint 全绿 / 1120 tests OK）以 `known-issues.md` 2026-09-01 段为准；`style-library.md`（311/294）与 `_INDEX.md` 顶行的计数差是重构 plan R4 要收敛的既有债，本方案不修数、只移除断言。
- **A3**：huashu 审美禁区语料的许可口径为思想级改写（无授权源合同），负面语料参考池文档不复制上游文本。
- **A4**：dashi 线下授权（2026-09）的明示范围为 theme01-12 色板直引；**容量词汇默认按"档位数值=事实数据可引用、表述=思想级改写"的保守口径处理**，若 owner 后续确认授权覆盖容量词汇文本则可升级直引；nano-banana MIT；OfficeMCP 无 LICENSE 从严——色板仅指纹非重叠直引（数值事实不受版权保护），文本描述思想级改写。

### Outstanding Questions

**Deferred to Planning / 执行期核实**：
- 容量查询面的承载形态：`style layouts` 子命令加 `--capacity` 过滤旗标，还是 layouts.json 增独立索引文件（执行期按 CLI 合同改动面最小化原则定）。
- 负面语料参考池的落位：`references/styles/00_索引/`（随重构 Phase 1 迁 `_meta/`）还是独立 references 文档——若重构先行则直接落 `_meta/`。
- R8 咨询系版式 avoid_for 稀疏度是否成立（执行期 audit 后决定做或不做）。

### Sources / Research

- 仓内（快照 2026-09-02，工作树实测）：`references/style-candidates.md`（S4b 快照口径 19 源台账）、`evals/known-issues.md`（2026-09-01 C1-C4 终局收口段：净增 89、295+17、台账清空声明）、根 `CHANGELOG.md`（C1/C2/C3/C4 四批入账明细）、`references/style-library.md`（渐进治理债：126 份 negative_prompt 不足 3 条；311/294 计数口径）、`references/styles/00_索引/_INDEX.md` 顶行（"≤ 硬顶 300"断言）、`references/styles/12_版式库/01_Cover.layouts.json`（`content_capacity` 现有结构实测：title/subtitle/meta 各带 chars_per_line/max_lines/max_chars）、`scripts/draft_negative_prompts.py`（存在，dry-run 默认）、`scripts/chart_palette_pool.py`（AST 提取型池）、`samples/reference-golden/`（gorden/officecli 金样板先例）、`scripts/lint_style_index.py`（无 300 断言，实测）。
- 关联 plan：`docs/plans/2026-09-02-001-refactor-leo-ppt-style-library-restructure-plan.md`（重构 plan：R4 计数真值、U2.3 进货流程、Phase 0 元数据化时序）、`docs/plans/2026-09-01-001-feat-leo-ppt-style-recommendation-coordinate-plan.md`（坐标系 plan：推荐算法 owner）、`docs/plans/2026-08-31-006-feat-leo-ppt-style-intake-plan.md`（S/C 进货批先例）。
- 上游需求语境：`docs/brainstorms/2026-08-31-005-leo-ppt-oss-fusion-r3-requirements.md`（R3 PRD：R-55/R-64 信号通道、R-65 金样板回归、R3-2.5 风格体系批边界——本方案不与其重叠立项）。
- 失效条件：若重构 plan 先行完成 Phase 2（briefs/ 单树），本方案文档路径需按新树重投影；若 owner 恢复数量上限约束，R1 逆转为补货门增设计上限断言。

---

## Planning Contract

Product Contract 由本次 spec-plan-bootstrap 会话撰写（无独立上游 Product Contract；WHAT 来源为当前用户三轮会话决策——候补集成评估、300 硬顶退役、语料层优先）。R1 承接"硬顶退役"，R2 承接"台账不同步"，R3-R6 承接"语料层未开采"，R7 承接"护栏成文"，R8 为可选项。

### Key Technical Decisions

- **KTD1 · 防膨胀护栏 = 质量门组合，无数字上限**。硬顶退役后，防膨胀由四层承担：入库前（四重去重 + 信号触发纪律）、入库时（金样板三页 + 配对预览义务 + 治理 lint）、入库后（audit 疑似同族簇门：10 是当前值不是门槛，判据为"相对基线不恶化"且 ≤ 回退门槛 20）、检索面（variant_of 家族归并 + 别名检索，数量增长不直接放大推荐选择面）。备选"提高上限至 500"被否决：owner 明确不要限制，且数字上限本质是代理指标，簇数门才是质量的直接判据。
- **KTD2 · 负面语料以"参考池文档"落地，不批量改 brief**。渐进治理债的既有纪律是"点名命中或渲染修订时顺手补，不专项批量重写（避免无真实风险的模板化填充）"。因此 R3 的形态是**新建语料参考池文档**（按家族/场景组织的负面词条 + 选用指引），消费路径两条：人工/agent 顺手补时查池取词；`draft_negative_prompts.py` 以池为输入源派生草案（现工具只从 brief 自身 avoid/constraints 派生，实测产出少，池化后产出面扩大）。批量改写 126 份 brief 被明确排除。
- **KTD3 · 台账真值分层：有迁移器的源以 --report 为准，无迁移器的源以 CHANGELOG/known-issues 为数字来源**。`scripts/intake_*.py`（现 7 个）幂等可复现，其 `--report` 是所覆盖源（gpt-image2/slides-grab/OfficeCLI/beautiful 等进货主力）吸收/跳过明细的真值；**C4 杂项五源（xhs/awesome-ppt-skills/frontend-slides/dashi 思想级/awesome-gpt-image-2 余量）无专属迁移器**，数字以 CHANGELOG C 批条目与 known-issues 终局段为准并声明该局限；`style-candidates.md` 只登记"实收数 + 余量区间 + 快照日期"，表头声明真值分层，终结"文档余量与实收漂移"的复发面。
- **KTD4 · 与重构 plan 的时序协调**。Batch A 触碰的 `_INDEX.md` 顶行与 `style-candidates.md` 也是重构 plan Phase 0/U0.2 的触碰面。协调规则：硬顶断言移除（本方案 R1）独立可先行——它只删断言不碰计数定义；计数真值函数（重构 R4）后落地时直接按"无上限"口径实现。若两 plan 批次相邻执行，文档修订合并为一次提交。
- **KTD5 · 语料资产的机检化**。每份新增语料/词汇参考文档配存在性断言（`tests/` 单测或 lint 规则：文档存在、含最低条目数、来源与许可登记行在场），防"参考文档写完即腐烂"；词汇类资产（构图词汇、容量词汇）如被运行时消费，消费路径加确定性单测。

### Interface Contracts

- **负面语料参考池**（新文档，建议 `references/styles/00_索引/负面语料参考池.md`，重构后随 `_meta/` 迁移）：frontmatter 登记来源（huashu-design 审美禁区，思想级改写，快照日期）与许可口径；正文按视觉家族/场景分组（首期覆盖范围见 R3 修订：仅 huashu 语料可派生的家族组，全家族覆盖为后续扩展位），每个**已登记组** 3-8 条负面词条（一句话一条，可执行、非口号）；文末"选用指引"节声明与渐进补齐纪律的衔接（点名命中/渲染修订时取用，不批量应用）。
- **构图词汇参考**（新文档，`references/styles/08_图片渲染/` 同级或 `00_索引/` 附录）：六类视觉词汇表 + 构图描述条目，标注 MIT 来源与"富提示词密度哲学不学"边界声明。
- **容量查询词汇**（`12_版式库` 扩展）：`content_capacity` 既有槽位字段不变，**条目数为键级增量**（可选键，如 `items.max_count` 形态，执行期定）；查询能力走 `style layouts` 只读查询面（如 `--capacity title<=8,items<=6`——items 过滤依赖上述新键），缺省输出逐字节不变；dashi 容量档位词汇以参考节登记（许可口径见 Dependencies A4 修订：数值档位按事实数据引用、表述思想级改写）。
- **色板池增量**（`scripts/chart_palette_pool.py` 数据面）：新色板条目带来源登记（OfficeMCP，色板指纹非重叠直引）；入池幂等（重跑不重复入）。
- **手绘素材语汇**（手绘系 brief 视觉语汇段增量）：箭头/便签类素材词条以 MIT 来源登记，定向补 `01_通用母版/` 手绘白板/手绘技术解释家族（0-2 条），形态为 brief 内语料增量或家族级参考节，不新建独立文件。
- **补货流程合同**（`style-candidates.md` 表头 + `style-extension-template.md` 合格门清单）：五步流程（信号确认 → 四重去重 → 精选与许可核验 → 金样板三页 + 配对预览行 → 治理 lint + audit 出口）成文；金样板落位沿用 `samples/reference-golden/<源名>/` 先例。

### Assumptions

> 本 plan 为 bootstrap 撰写，以下 WHAT 级选择待 owner 执行前确认；不确认即维持现状的部分已标注。

- **A1（硬顶退役为无条件下限）**：owner 指令"去掉，不需要限制"理解为**不设任何数量上限**（不是提高上限）；质量门替代护栏是 HOW 层设计，不改变该决策本身。
- **A2（C 批数字基线）**：以 `known-issues.md` 2026-09-01 段为准（312 briefs / 295+17 / 净增 89）；`style-library.md` 的 311/294 为待收敛旧口径，不在本方案修数。
- **A3（语料层不依赖信号即可做）**：五路语料资产均为存量薄弱面的定向增强（在册渐进债、既有查询面扩展），非新增风格条目，不适用候补合同的信号触发纪律。
- **A4（R8 为可选项）**：Mck avoid_for 补缺以执行期稀疏度 audit 为前置，不成立则登记不收。

---

## Implementation Units

### Batch A — 治理面（纯文档，先行）

#### UA1 硬顶合同退役（R1）

- **Goal**：三处活合同移除 300 上限断言（最小删除，不新增替代表述——补货门的完整质量门成文统一归 UC1，避免同一条目两批两改）。
- **Requirements**：R1。
- **Dependencies**：无（与重构 plan 合批规则见 KTD4）。
- **Files**：`leo-ppt-generator/references/style-candidates.md`（表头定位行 + 补货门第四条）、`leo-ppt-generator/references/styles/00_索引/_INDEX.md`（顶行"≤ 硬顶 300"短语）、根 `CHANGELOG.md`（user-visible 条目：风格库取消数量硬顶）。
- **Approach**：定位行"不占 300 硬顶"改为"不进主库、不进 style list"；补货门列表删除"300 硬顶余量检查（……腾位/顺延）"一项（删后补货门仍含四重去重 + 治理 lint + audit 簇数三项，自洽；完整五步质量门表述由 UC1 统一成文，本单元不写替代表述）；`_INDEX.md` 顶行删"≤ 硬顶 300"断言、计数行其余不动。known-issues 与 CHANGELOG 历史条目不改（历史账）。
- **Test scenarios**：`rg "硬顶" leo-ppt-generator/references/` 结果仅剩历史语境词或零命中；既有测试（`test_style_candidates_doc.py` 等）若断言了硬顶措辞则同步改。
- **Verification**：文档合同测试全绿；`rg` 断言通过。

#### UA2 候补台账 C 批同步（R2）

- **Goal**：19 源条目全部刷新为 C 批后实收/余量口径，终结台账漂移。
- **Requirements**：R2。
- **Dependencies**：UA1（同文件，合并提交）。
- **Files**：`leo-ppt-generator/references/style-candidates.md`（表头快照日期 + 全部源条目）、根 `CHANGELOG.md`。
- **Approach**：数字来源按 KTD3 分层（有迁移器源跑 `--report` 核对；无迁移器的 C4 五源以 CHANGELOG/known-issues 为准），执行时先核实五源台账可复现性，不可复现者在表头声明局限。逐源更新（全量清单核对——实测大型矿 9 + 择优杂项 11 = 20 条，表头"19 源零遗漏"计数需一并修正）：gpt-image2（C1 实收 12 主 + 233 池→7 池代表，余量≈0-8 同族变体）、slides-grab/OfficeCLI（已标注，余量口径复核）、beautiful（C3 实收 14，原判推翻，余量待复核）、academic（C3 实收 4，余量 2-6 + 调色板 token 直引）、huashu（C3 实收 6，余量 0-3 + 审美禁区语料→本方案 R3）、frontend-slides（C4 实收 2）、dashi（C4 思想级 2，容量词汇→本方案 R4）、xhs（C4 实收 4，余量 4-8，信号触发首选）、awesome-gpt-image-2（累计 3+2 锚，余量 0-3）、awesome-ppt-skills（转轴 6，按 02 轴外行业点名）；nano-banana/ian-handdrawn/Mck/OfficeMCP/scholar/MultiAgentPPT/AI-PPT-Slides 标注"未开采，语料/机制层归本方案 Batch B 或维持候补"；**open-kimi-ppt-skill（44 套全量评估完毕、余量 0，维持关闭登记）与 gitee-mirrors/deckjs（已判不收，维持）两源同样刷新快照日期与状态，不留遗漏**。表头补一行真值声明（分层口径见 KTD3）。
- **Test scenarios**：`test_style_candidates_doc.py` 合同测试适配新快照（存在性/结构断言）；文档内 9 源实收数与 known-issues 逐一对得上。
- **Verification**：包级测试绿；人工抽查 3 源数字与迁移器 `--report` 输出一致。

### Batch B — 语料/机制层（五路资产，不占风格条目）

#### UB1 负面语料参考池（R3）

- **Goal**：huashu 审美禁区提炼为按家族/场景组织的 negative_prompt 语料池文档，接通渐进补齐与工具派生两条消费路径。
- **Requirements**：R3。
- **Dependencies**：无。
- **Files**：`leo-ppt-generator/references/styles/00_索引/负面语料参考池.md`（新建）、`leo-ppt-generator/scripts/draft_negative_prompts.py`（语料池输入源接线）、`leo-ppt-generator/tests/`（存在性与结构单测）、根 `CHANGELOG.md`。
- **Approach**：按 Interface Contracts 的文档契约撰写（来源/许可登记、家族分组词条、选用指引）；工具接线为可选输入参数（如 `--pool <path>`），不改变缺省行为（从 brief 自身派生）。词条撰写遵循"可执行、一句话、针对视觉系统"（如"禁用高饱和撞色破坏莫兰迪低饱和基调"式），不复制上游文本。
- **Test scenarios**：文档存在、含来源登记行、每个已登记组 ≥3 条（断言范围为已登记组，不要求全家族覆盖）；`draft_negative_prompts.py --pool` 对样例 brief 产出含池词条的草案。
- **Verification**：单测绿；缺省路径工具行为不变（既有测试零改动通过）。

#### UB2 容量查询词汇与查询面（R4）

- **Goal**：dashi 容量选页硬条件词汇进 `12_版式库`，版式选择获得按容量条件预筛的查询能力。
- **Requirements**：R4。
- **Dependencies**：`layout-dispatch.md` 容量预检既有合同（扩展不破坏缺省）。
- **Files**：`leo-ppt-generator/references/styles/12_版式库/`（容量词汇参考节 + 查询面）、`leo-ppt-generator/references/layout-dispatch.md`（消费说明一行）、`leo-ppt-generator/scripts/`（`style layouts` 查询扩展，执行期定形态）、`leo-ppt-generator/tests/`、根 `CHANGELOG.md`。
- **Approach**：先盘点 36 版式骨架 `content_capacity` 字段的覆盖完整度（是否每版式每槽位都有数值）；dashi 档位词汇（标题字数档/条目数档）作参考节登记（许可口径按 Dependencies A4 修订：数值档位可引、表述思想级）；查询面按 Outstanding Question 的两个候选形态中改动面最小者实现，缺省输出逐字节不变。
- **Test scenarios**：容量过滤查询对固定输入返回确定性子集；缺省 `style layouts` 输出与扩展前逐字节一致；字段缺失的版式在查询中如实报缺而非静默通过。
- **Verification**：单测绿；缺省输出快照 diff 为空。

#### UB3 构图词汇参考（R5 前半）

- **Goal**：nano-banana 六类视觉词汇表 + 构图描述落盘为 08 轴参考资产。
- **Requirements**：R5。
- **Dependencies**：无。
- **Files**：构图词汇参考文档（新建，落位见 Outstanding Question）、`leo-ppt-generator/tests/`（存在性断言）、根 `CHANGELOG.md`。
- **Approach**：词汇按六类组织、构图描述逐条映射到 08 轴既有渲染锚可配的构图场景；文档头登记 MIT 来源与"不学富提示词密度"边界。
- **Test scenarios**：文档存在、分类完整、含边界声明行。
- **Verification**：单测绿。

#### UB4 手绘素材语汇 + 色板池补非重叠（R5 后半、R6，小额合并 Unit）

- **Goal**：ian-handdrawn 箭头/便签素材语汇进手绘家族参考；OfficeMCP 8 色板指纹查重后非重叠入池。
- **Requirements**：R5、R6。
- **Dependencies**：无。
- **Files**：手绘家族参考（`01_通用母版/` 手绘系 brief 的 avoid/notes 增量或独立参考节）、`leo-ppt-generator/scripts/chart_palette_pool.py`（池数据）、`leo-ppt-generator/tests/`、根 `CHANGELOG.md`。
- **Approach**：素材语汇 0-2 条定向补手绘白板/手绘技术解释家族的视觉语汇段（MIT）；色板以主色 HEX 集合近似指纹对照现池，重叠者登记跳过、非重叠者带来源入池。
- **Test scenarios**：入池幂等（重跑零重复）；色板指纹撞池时跳过并记录。
- **Verification**：单测绿；池快照计数与登记一致。

### Batch C — 补货通道固化（流程成文，不执行进货）

#### UC1 补货评估流程成文 + 台账信号标注（R7）

- **Goal**：五步补货流程成文进表头合同与扩展模板合格门，余量源标注信号触发首选。
- **Requirements**：R7。
- **Dependencies**：UA1/UA2（同文件，可合并提交）。
- **Files**：`leo-ppt-generator/references/style-candidates.md`（表头）、`leo-ppt-generator/references/styles/00_索引/style-extension-template.md`（合格门清单引用）、根 `CHANGELOG.md`。
- **Approach**：五步流程（信号确认 → 四重去重 → 精选与许可核验 → 金样板三页 + 配对预览 → lint + audit 出口）写入表头"补货门"条目，一次成文为完整质量门表述（UA1 已删除硬顶余量项，本单元是补货门的唯一改写点，无中间态口径分叉）；xhs/academic 条目加"信号触发首选"标注；金样板落位声明沿用 `samples/reference-golden/` 先例。
- **Test scenarios**：`test_style_candidates_doc.py` 断言五步流程关键词在场。
- **Verification**：合同测试绿。

#### UC2（可选）Mck avoid_for 补缺（R8）

- **Goal**：咨询系版式 avoid_for 薄弱面补缺（思想级）。
- **Requirements**：R8。
- **Dependencies**：前置 audit：`12_版式库` 咨询系版式 avoid_for 稀疏度核实。
- **Files**：`leo-ppt-generator/references/styles/12_版式库/`（涉及版式 md）、根 `CHANGELOG.md`。
- **Approach**：audit 成立才执行——Use/Don't-use 卡结构思想级改写为 avoid_for 条目（不搬文本）；不成立则在候补台账登记"audit 不成立，不收"。
- **Test scenarios**：改动版式过 `lint_layout_grid`；avoid_for 新条目与既有语义不冲突。
- **Verification**：lint 绿；audit 结论留痕。

---

## Verification / Definition of Done

- **每批独立出口**：Batch A/B/C 各自 Unit Verification 全绿；Batch A 与 B 无相互依赖，可并行；UC1 依赖 UA1/UA2。
- **质量门零回归**：治理 lint 六条全绿（清单与全集口径见 Success Criteria 同名条）；`audit_style_families.py` 疑似同族簇不高于当前基线 10 且 ≤ 回退门槛 20（known-issues C 批口径：10 为当前值、>20 才触发回退）；全量单测零新增失败（基线 1120 tests OK）；迁移器 `--check` 幂等（全集=`scripts/intake_*.py`，现 7 个）。
- **行为面零变化**：`style render` 与 `style layouts` 缺省输出逐字节不变（新增查询/旗标不改缺省路径）。
- **合同一致性**：活合同零硬顶断言残留（`rg` 断言）；候补台账 9 源实收数与 `known-issues.md`/迁移器 `--report` 三方一致；新增语料资产各有存在性断言与来源许可登记。
- **变更记录**：硬顶退役与语料资产在根 `CHANGELOG.md` 按 Keep a Changelog 记录；`style list` 可见面无变化（本批不新增风格条目，无 user-visible 风格增减；硬顶退役本身记 user-visible 治理变更）。
- **与关联 plan 的边界复核**：不触碰坐标系 plan（推荐算法）与重构 plan（计数真值/元数据）的 owner 项；若重构 plan 先行落地，按 KTD4 重投影文档路径后复验。
