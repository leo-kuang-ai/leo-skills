---
title: leo-ppt-generator 风格库结构分层重构 - Plan
type: refactor
date: 2026-09-02
topic: leo-ppt-style-library-restructure
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: spec-plan-bootstrap
execution: code
status: superseded
superseded_by: docs/plans/2026-09-05-002-feat-leo-ppt-engineering-optimization-plan.md
superseded_on: 2026-09-05
alignment: needs-rewrite
alignment_source: docs/leo-ppt-generator/architecture/style-library-target-architecture.md
alignment_checked: 2026-09-03
---

# leo-ppt-generator 风格库结构分层重构 - Plan

> **已合并，停止作为实施入口（2026-09-05）。** 根据用户“合并一份”的要求，有效治理、索引和验证内容已纳入 [PPT 风格模板治理、索引与执行接入统一方案](2026-09-05-002-feat-leo-ppt-engineering-optimization-plan.md)。当前实施与后续路线均以该文件为准。
>
> 本文件保留历史正文供溯源，以下 Phase 0–3、目录目标和旧状态表述均不再生效。frontmatter 的 `implementation-ready` 仅保留历史文档形态，不覆盖 `status: superseded`，不得据此启动开发。

> ## ⚠ 对齐标注：本方案的默认交付与目标架构互斥，实施前必须重写
>
> **标注日期**：2026-09-03 ｜ **对齐源**：目标架构 v4.5
> [`docs/leo-ppt-generator/architecture/style-library-target-architecture.md`](../leo-ppt-generator/architecture/style-library-target-architecture.md)（见其 §0.4）
>
> 本方案成文于 2026-09-02，早于目标架构 v4.2–v4.5 的目录与字段决策。经五 Agent 对抗式评审确认：
> **默认交付路径（Phase 0 + Phase 2）会产出目标架构原则层明令禁止的结构**，据此实施的成果需要在
> 架构 L1/L3 阶段被回滚重做。frontmatter 仍为 `active` / `implementation-ready`，**但不得据此直接
> 进入实施**；请先按下表重写，或由 owner 显式决定废弃。
>
> ### 编号警告
>
> 本方案的 **Phase 0–3 与目标架构的 L0–L3 没有对应关系**，编号相似纯属巧合。不得把「Phase 1/3 可选
> 后置」读成「架构 L1/L3 可选后置」——本方案**完全没有** ID 铸造与 resolver 条目，而那正是架构 L1
> 的全部内容，也是本方案最大的覆盖缺口。
>
> ### 失效条目（逐条，均已核对本文原文）
>
> | 本文条目 | 冲突点 | 架构依据 |
> |---|---|---|
> | **KD-1** 四分区 `_meta/ briefs/ axes/ overlays/` | `overlays/` 已在架构 v4.2 被**显式删除**（不是"尚未做到"，是"已被否决"）；`_meta/` 无对应物，其职责由 `_contracts/` + `_generated/` 分担 | §3 四区 `canonical/ _contracts/ _evidence/ _generated/` |
> | **R1 / KD-3 / KTD1** 默认交付「35 份 brief 归入 `01_通用母版` 对应家族子目录」「`01/02/03` 分类树保留」 | 把 `visual_family` **编码进新建路径**，方向是加深而非退役 | §3.1「family/domain/scenario/source ⋯ **绝不复制成物理分类树**」 |
> | **R3 / KTD3** `taxonomy` 形状 `{visual_family: string[], industry: string[], scenario: string[]}` | 四处形状级冲突：`visual_family` 应为**单值**；缺 `families[]` 键（而架构 L0 的地基字段名恰是 `taxonomy.families`）；键名应为复数 `industries`/`scenarios`；值应带命名空间（`family:` / `domain:` / `scenario:`）。**这是最贵的一条——Phase 0 会把该形状写进全库 300+ brief，L1 切 v2 时需二次改写** | §4.4 |
> | **R2 / KTD3** `source` 字段 `{origin, batch, upstream_ref, license_note?}` | **缺 `license` 键**，无法承载许可门的唯一判定输入，也无法表达自研（`native-owned`）与已核验（`cleared-no-restriction`） | §4.3 |
> | **KD-4 / KTD2**「重排成本集中在文档/lint 层，运行时几乎不动」 | 架构要求 L1b 把 composer、loader、pack/gallery、preview/golden、generator、lint/docs 全部切到 resolver，并收口「风格库根」定位 | §7.3、§15 L1b |
> | **R5 / KTD4** 把 stem 全库唯一当作**长期去重键**与 Phase 2 前置门 | 架构要求 stem-based 定位与身份推导在 L1 整批退役。**唯一性 lint 本身不冲突**（架构 L0 也要求它），冲突在于把它当长期机制而非过渡守护 | §15 stem 退役 |
> | **R6** 「sidecar `.layouts.json` 始终与其 brief **同名同目录**」列为验证判据 | 架构的 sidecar 在实体包内，以 `style_id` 回指，不靠同名关联 | §4.5、§3.1 |
> | **R6** 零回归口径＝`style list`/`load`/`render` 缺省 stdout 逐字节一致 | 该口径**更弱**：漏掉 stdout 之后的逐页 prompt 组装层、只验缺省路径（不覆盖 `--brand`/`--anchor`/`--materialize`/`--layout-lock`）、且无「收据字段不进 prompt」断言 | §15 退出证据③④ |
>
> ### 方向一致、可直接保留的部分
>
> 以下与架构同向，重写时应保留：**KD-2**（来源/分类从路径降为元数据的方向）、**R4**（单一计数真值
> 与 `--check`；架构 §15.1 进一步要求**退役既有多份并存口径**而非新增第七份）、**R5 的 stem 唯一性
> lint 本身**、**KTD3a**（`compose_style()` 白名单不 passthrough 的论证，架构 §13.1 已确认成立）、
> **KTD5**（md 交叉引用批改与链接检查）、**KTD6**（与坐标系 plan 的单一 owner 纪律）。
>
> ### 重写指引
>
> 1. 字段形状先对齐 §4.3 / §4.4，**这一步必须在任何回填开始前完成**；
> 2. 默认交付去掉「归入家族子目录」，改为落到无分类语义的父目录，与架构 L1c 叶子成包、L3 父目录搬迁同向；
> 3. 补齐架构 L1 的身份层条目（铸 ID、resolver、双读等价、lint 翻门），或明确声明本方案只覆盖 L0；
> 4. 零回归口径升级为逐页 prompt 字节比对 + 覆盖旗标矩阵；
> 5. 若涉及 stem 改名，须排在 prompt 基线冻结**之前**，且 L1a–L1c 全程不得改动 `style_name`（§15）。

## Goal Capsule

- **Objective**：消除 `references/styles/` 把「载体类型 / 分类归属 / 来源出处」三个正交维度压进一维 `NN_` 目录路径的结构病，改为**类型进路径、分类进元数据 + 派生索引、来源进字段**，做到运行时零回归、逐阶段可回退、lint 可守护。
- **Recommended approach**：默认交付 Phase 0（元数据化，零文件迁移，可与风格坐标系 plan 合批）→ Phase 2（来源文件夹归位，dissolve 进现有 01/02/03 分类树，跟齐 S1a/S2a 先例——即本方案用户所求的核心产出）；Phase 1（类型分区重命名）与 Phase 3（briefs/ 单树拍平）**均为可选、后置**，二者收益均为纯可读性/运行时遍历面优化，成本明显更高（Phase 1 是全方案最大迁移风险，见 KTD5）。**排序理由（spec-doc-review 2026-09-02 定案）**：Phase 2 不要求先完成 Phase 1（见 Phase 2 说明），故价值优先顺序是 Phase 0 → Phase 2→ 可选 Phase 1/3，而非按编号线性推进。每阶段独立提交、独立出口门、可单独回退。
- **Decision focus**：来源/分类从路径降为元数据的字段设计（KTD3）；派生索引先并行校验后替换的降险时序（KTD3）；stem 全库唯一作为 Phase 2 前置门（KTD4）；md 交叉引用不受 `smart_relocate` 保护的迁移风险（KTD5，限 Phase 1/3）；与坐标系 plan 的计数真值/明度档单一 owner 协调（KTD6）。
- **Verification focus**：`style render` 缺省调用重排前后**逐字节一致**（零回归硬证据）；计数真值 lint 绿且三处文档一致；stem 唯一性 lint 绿；`check_references` 悬空引用归零；`generate_style_gallery --check` 金样板无漂移。
- **Largest risk / boundary**：本计划只动**风格库结构与元数据**（目录分层、brief 元数据字段、lint、派生索引生成器、文档计数派生），**不动推荐算法**（MMR/tier 分池属坐标系 plan）、**不动风格内容与 palette 值**、**不改 CLI 命令语义**；明度档字段与色相桶派生本体归坐标系 plan（R1/R3），本方案只消费不重定。

---

## Product Contract

### Summary

以「三维压进一维路径」为唯一需求来源，把风格库结构从「进货编年史式扁平数字目录」重构为「类型分层 + 元数据驱动分类/来源 + 确定性派生索引」。产出形态为目录分层、brief JSON 元数据增量（`source`/`taxonomy`）、治理 lint（stem 唯一性、单一计数真值）、派生索引生成器与文档计数派生，不改变四条硬约束（Gate 0 阻断、样张门、真实派发、completed≠闭环）、控制面五字段合同、推荐算法与 `style render` 缺省输出。

### Problem Frame

`references/styles/` 下 `00–16` 平级编号目录 + 顶层 11 套内置 `.md`，实证混装了五种性质完全不同的东西，且这三个正交维度被目录路径这一维度强行合并：

- **来源被当成一等目录，本该是元数据**。`04_来源_guizang`(7) / `05_来源_awesome`(3) / `14_参考池_gpt-image2`(7 池代表) / `15_来源_officecli`(7) / `16_来源_slides-grab`(25) 全是「哪来的」，却散落在 04/05/14/15/16——数字编码的是进货批次时间顺序，不是语义。一个 `16_来源_slides-grab/韩式精密网格/` 的风格本质上既是视觉风格（该进 01）又是咨询身份（该挂 02），但被出处占了路径就对 01/02 分类与 `风格路由.md` 隐身——这是「进货面与推荐面脱节」的结构性成因。
- **分类是单继承，本该是多标签**。`风格路由.md §6` 明说行业×场景正交叠加，但每个风格物理上只能存进 `01_通用母版`(155) / `02_行业内容域`(70) / `03_场景用途结构`(40) 之一，其余归属只能靠散文交叉引用。
- **散文轴与可加载 brief 同树**。`06_论证模式`(19)/`07_信息图`(11)/`08_图片渲染`(43)/`09_结构布局`(8)/`11_图表语法`(18)/`13_页面语义`(25) 不是风格而是「组合用」词表，却与 01/02/03 的 brief 住同一棵树——迫使运行时 `styles.py._is_style_md()` 打开每个 `.md` 找 json 块来区分「是不是风格」，而非按目录判定。
- **计数真值三处漂移**。`_INDEX.md` 顶行同时维护 279（lint BRIEF_DIRS 口径）/ 311（含 15/16 JSON）/ 294（独立可选）/ 300（硬顶），并注明「15/16 暂未计入 BRIEF_DIRS」「14 不计入」——根因是来源目录游离在主分类树之外、计数逻辑被迫特判。
- **设计文档与文件系统已分叉**。`设计体系.md §四` 已写着 `02_行业内容域`「待与品牌 VI 合并为身份轴」、`03_场景用途结构`「是论证模式轴的用途场景细化」——即设计意图是干净六轴模型，但目录仍停在旧的「一个风格一个文件夹」认知结构。

### Key Decisions

- **KD-1 长期理想是顶层按载体类型四分**（agent 最佳判断，**落地降级为可选 Phase 3**）：`_meta/`（原 00_索引）、`briefs/`（全部可加载 brief）、`axes/`（06/07/08/09/11/13 组合用词表）、`overlays/`（10 品牌 + 12 版式库）。类型是最稳定的维度，理想上应进路径；分类与来源降为元数据——但本方案默认交付只做到「分类与来源降为元数据」，不要求先做类型四分（见 KD-3 排序）。
- **KD-2 来源升 `source` 字段、分类升 `taxonomy` 多标签**：目录不再承载来源与分类，`_INDEX`/`风格路由` 从 brief 元数据确定性派生；进货新增按分类落 `01/02/03`（或 `pools/`）并写 `source` 字段，不再新增 `NN_来源_*` 目录。
- **KD-3 价值优先排序、每阶段独立可回退**：Phase 0 元数据化（零迁移，默认）→ **Phase 2 来源文件夹归位**（dissolve 进现有 01/02/03 分类树，跟齐 S1a/S2a 既有先例，owner 2026-09-02 确认走 dissolve、不做来源 UPSTREAM 化；默认，且**不要求先完成 Phase 1**）→ 可选 Phase 1（类型分区，只动散文轴/覆盖层，不动 265 份 brief；纯可读性优化，收益低于其迁移风险，故降为可选后置）→ 可选 Phase 3（briefs/ 单树拍平，即 KD-1 长期理想的落地）。**排序依据**：Phase 2 是用户所求的核心价值且无 Phase 1 前置依赖；Phase 1 是全方案最大迁移风险（KTD5）而收益仅纯可读性，不足以证成挡在 Phase 2 之前。派生索引先并行校验（生成 vs 手工 diff 为空）后才替换手工表。
- **KD-4 利用运行时路径解耦**（已核实）：`list_styles`/`load_style` 用 `rglob` + 按文件名 stem 去重 + 内容判定，家族归属用风格名不用路径——重排成本集中在文档/lint 层，运行时几乎不动。`style render` 逐字节回归是零回归的硬证据。
- **KD-5 与坐标系 plan 的重叠项单一 owner**：计数真值（本方案 R4 = 坐标系 plan R7）、明度档字段与色相桶派生（坐标系 plan R1/R3）由单一批次负责落地，避免双写；本方案 Phase 0 与坐标系 plan 合批或紧邻，`taxonomy`/`source` 两字段归本方案。

### Requirements

- **R1（来源文件夹归位，默认交付；类型分层降级为可选 Phase 3）**：默认交付出口是消除 `04/05/14/15/16` 来源目录——35 个视觉风格 brief（05/15/16）归入 `01_通用母版` 对应家族子目录，非 brief 的组件模板（04）与参考池（14）另置（见 R2/Phase 2 Units）；`01/02/03` 分类树在默认交付中保留。**可选 Phase 3**：顶层进一步收敛为 `_meta/ briefs/ axes/ overlays/` 四分区（散文轴 06/07/08/09/11/13 归 `axes/`、品牌与版式库 10/12 归 `overlays/`、索引与规则文档 00_索引归 `_meta/`），分区后运行时判定「是不是风格」可从内容嗅探退化为「只扫 `briefs/`」——此项收益为纯可读性/遍历面优化，不在默认交付范围。
- **R2（来源元数据化）**：来源从目录降为 brief `source` 字段（`origin`/`batch`/`upstream_ref`/可选 `license_note`）；`04/05/14/15/16` 来源目录的语义完全由字段承载；进货流程改为「按分类落 `01/02/03`（或 `pools/`）+ 写 `source`」，不再新增顶层来源目录。
- **R3（分类元数据化，主轴机械回填 + 多标签渐进）**：分类归属升为 brief `taxonomy` 多标签（`visual_family`/`industry`/`scenario`，可空可多），取代目录单继承；`_INDEX.md` 与 `风格路由.md` 的分类/来源段由生成器从元数据**确定性派生**，进货新风格自动进路由（消解「进货不进推荐」）。**范围澄清**：现状目录本身是单继承（一个风格只在 01/02/03 之一），故 Phase 0 的机械回填只能确定性填充该风格当前所在目录对应的**一个主轴**，另外两轴留空；R3 的默认交付判据是「字段结构存在且主轴正确」，「多归属」的人工/半自动富化为未预算的渐进工作，不在本方案 Success Criteria 内（见 U0.1）。
- **R4（单一计数真值）**：全库风格计数收敛为单一函数口径（定义：可加载=有 json brief / 独立可选=排除 `variant_of` / 分类轴 vs 来源），`_INDEX.md`、`style-library.md`、`style-recommendation.md` 三处计数从其派生，漂移即 lint ERROR。**本项与坐标系 plan R7 同源，声明单一 owner。**
- **R5（stem 唯一性守护）**：全库 brief 文件名 stem 唯一由新增 lint 守护，把 rglob 去重的隐性前提显式化，为 Phase 2 来源归位（跨目录移动 brief）铺路。
- **R6（零回归 + 引用完整性）**：重排前后 `style list`/`style load`/`style render` 缺省调用输出逐字节一致；风格库内 md 交叉引用无悬空（`check_references` 归零）；sidecar `.layouts.json` 始终与其 brief 同名同目录。**零回归的代码级证据**：已核实 `compose_style()`（`runtime/src/leo_ppt_generator/templates.py`）返回值是显式白名单 dict literal，只取 `visual_direction`/`color_palette`/`typography`/`layout_patterns`/`token_sidecar`/`brand`/`guardrail`/`layout_lock` 等声明字段，不存在把 brief 顶层未声明键 passthrough 进 render 输出的路径；`style-brief-v1.schema.json` 顶层未设 `additionalProperties: false`，新增 `source`/`taxonomy` 键合法且不影响既有 lint 必需键校验——U0.1 的新字段对 render 输出面构造性安全，不依赖运行时验证兜底。

### Success Criteria

- **结构（默认交付，Phase 0+2 出口）**：`ls references/styles/` 顶层不再有 `04/05/14/15/16` 来源目录；05/15/16 的 35 个视觉风格 brief 已归入 `01_通用母版` 对应家族子目录，04/14 另置（组件/规则区、`pools/`）；`01/02/03` 分类树保留。
- **结构（可选 Phase 1/3 出口，非默认交付判据）**：Phase 1 出口——散文轴与覆盖层归入 `axes/`/`overlays/`；Phase 3 出口——顶层仅 `_meta/ briefs/ axes/ overlays/`。
- **零回归**：对一组固定 `style render <风格> --mode --layout` 调用，重排前后 stdout **逐字节 diff 为空**（缺省路径，不传覆盖旗标）。
- **计数真值**：`python3 scripts/lint_style_index.py` 退出码 0，三处文档计数与单一函数输出一致（不一致即 ERROR）。
- **stem 唯一性**：新增 stem 唯一性 lint 退出码 0。
- **引用完整性**：`python3 scripts/check_references.py`（或等价机检）在风格库内悬空引用归零。
- **金样板**：`python3 scripts/generate_style_gallery.py --check` 无漂移（exit 0）。
- **对账**：`python3 scripts/capability_manifest.py --compare` 的 styles/briefs/scripts/references 文件级 diff 可逐条解释。

### Scope Boundaries

**In scope**：`references/styles/**` 的目录分层与文件位置、brief JSON 的 `source`/`taxonomy` 元数据增量、`scripts/` 新 lint（stem 唯一性、单一计数函数）与派生索引生成器、`runtime/src/leo_ppt_generator/styles.py` 的扫描范围（可选收窄，行为不变）、`_INDEX.md`/`风格路由.md`/`style-library.md`/`style-recommendation.md` 的计数与分类段派生、根 `CHANGELOG.md`、根 `AGENTS.md`/`CLAUDE.md`（仅 lint 命令登记一行）。

**Out of scope（非目标）**：

- 推荐算法（MMR 重排、tier 分池降权、家族配额语义）——归坐标系 plan（`2026-09-01-001-feat-leo-ppt-style-recommendation-coordinate-plan.md`）。
- 明度档字段本体与色相桶派生的定义与回填——归坐标系 plan R1/R3，本方案只消费其字段用于 `taxonomy` 派生，不重定其口径。
- 风格内容、`color_palette` 值、`visual_direction` 正文的任何修改。
- `style render` 输出格式、CLI 命令面语义（要求逐字节向后兼容）。
- `style_hard_rules.FAMILIES` 家族词表（用风格名不用路径，对迁移免疫，无需改）。

**Deferred to Follow-Up Work**：

- **可选 Phase 1（类型分区）与可选 Phase 3（briefs/ 单树拍平）**：坐标系 plan Scope Boundaries 曾把「目录本体重排」列为另批立项；本方案已核实 styles 无 live 上游同步（不在 `upstreams.yaml`/`vendor-lock.json`），**owner 2026-09-02 确认走 dissolve、不做「来源轴 UPSTREAM 化」**（该选项已否决，非 deferred）。Phase 1/3 本身作为纯可读性优化保留为可选、后置，待 Phase 0+2 默认交付完成后视需要再议。
- 派生索引正式替换手工 `_INDEX`/`风格路由`（Phase 0 只并行校验、不替换；正式替换随 Phase 2 U2.2 重投影）。
- 存量 stem 冲突改名（若 R5 audit 发现）——属 `style list` user-visible 变更，随 Phase 2 前置处理并记 CHANGELOG。

### Dependencies / Assumptions

- **依赖**：坐标系 plan 的明度档字段与色相桶派生（R1/R3）——`taxonomy` 派生若纳入明度/色相需消费其字段；坐标系 plan 的计数真值（R7）与本方案 R4 同源，须协调单一 owner。
- **A1**：运行时路径解耦已核实（`styles.py` 用 `rglob` + stem 去重 + `_is_style_md` 内容判定；`style_hard_rules.FAMILIES` 用风格名），故重排不动运行时——这是零回归与低迁移成本的前提。
- **A2**：全库 brief 文件名 stem 唯一的**当前状态未知**，Phase 0（U0.3）先 audit；可能存在存量冲突需改名（user-visible）。
- **A3**：明度档「背景 HEX 机械可推导 58%」被高估（承接坐标系 plan 评审发现——六分组含饱和/色温，背景 HEX 仅可靠给 dark/light）；本方案不重定该口径，只在依赖里引用其字段。
- **A4**：`smart_relocate` 只更新代码 import、**不更新 md 相对链接**——md 交叉引用漂移是 Phase 1 最大迁移风险，须以 `check_references` 作为出口门。

### Outstanding Questions

**Deferred to Planning / 执行期核实**：

- `check_references.py` 现有能力是否覆盖风格库内相对 md 链接的全量校验，还是需扩断言。
- 派生索引生成器的承载形态（独立脚本 vs 并入 `lint_style_index` 的生成模式）。
- `taxonomy` 是否纳入明度档/色相桶两轴（取决于坐标系 plan 落地节奏），还是先只做视觉族/行业/场景三标签。
- Phase 1 运行时扫描范围收窄（`_is_style_md` 只扫 `briefs/`）是否本批做，还是留作纯优化后置。

### Sources / Research

- 仓内（快照 2026-09-02，工作树实测）：`references/styles/`（目录树 00–16 + 顶层 11 内置）、`references/styles/00_索引/_INDEX.md`（计数口径行 279/311/294/300）、`00_索引/设计体系.md`（六轴模型 + §四 现有库→六轴映射的分叉声明）、`00_索引/风格路由.md`（多轴正交叠加规则 §6）、`runtime/src/leo_ppt_generator/styles.py`（`rglob`+stem 去重+`_is_style_md` 路径解耦证据）、`scripts/style_hard_rules.py`（FAMILIES 用风格名）、`scripts/audit_style_families.py`（axis/subfamily 由 `rel.parts` 派生）、真实 brief `清爽专业风.md`（现有 json 字段：`style_name/aliases/best_for/visual_direction/canvas/color_palette/typography/layout_blueprints/variant_of`，无 `source`/`taxonomy`/`tone`）。
- 关联 plan：`docs/plans/2026-09-01-001-feat-leo-ppt-style-recommendation-coordinate-plan.md`（坐标系 plan，R1/R3/R7 与本方案重叠）、`docs/plans/2026-08-29-001-feat-leo-ppt-style-system-optimization-plan.md`（token 三层化与 brief schema 化先例，本方案契约结构参照）、`docs/ideation/2026-09-01-style-template-hierarchy-ideation.html`（层级 ideation，Phase 2 目录重排的方向来源）。
- 失效条件：若坐标系 plan 将 `taxonomy` 明度/色相两轴一并落地，本方案 R3 的该部分降为消费；若库封库不再进货，R2 进货流程改造优先级下调。

---

## Planning Contract

Product Contract 由本次 spec-plan-bootstrap 会话撰写（无独立上游 Product Contract），WHAT 全覆盖映射 Problem Frame 五类结构病——R1 承接「散文轴同树」、R2 承接「来源当目录」、R3 承接「分类单继承」、R4 承接「计数漂移」、R5/R6 为迁移安全的机器可验出口。

### Key Technical Decisions

- **KTD1 · 价值优先分批，每阶段独立出口门与回退**。默认交付 Phase 0（元数据化，零文件迁移）→ Phase 2（来源文件夹归位，`smart_relocate` 迁 05/15/16 视觉风格 brief 进 01、04/14 另置）；可选后置 Phase 1（类型分区，迁散文轴/覆盖层）→ Phase 3（briefs/ 单树拍平）。**排序理由**：Phase 2 不依赖 Phase 1（见 Phase 2 说明），且是用户所求核心价值；Phase 1 收益仅纯可读性但是全方案最大迁移风险（KTD5），不足以证成挡在 Phase 2 之前，故降为可选后置。Phase 间无强耦合，可只做 Phase 0；每阶段 git 单独可回退。备选「一次性重排」被否决：md 引用漂移面与 stem 冲突面同时爆发，不可控。
- **KTD2 · 重排目标是文档/lint 层，运行时仅可选收窄扫描范围**。已核实 `styles.py._find_builtin_style`/`list_styles` 递归 `rglob` + 按 `path.stem` 去重 + `_is_style_md` 内容判定，`load_style` 按 stem 解析——目录位置对运行时透明。故 `style render` 缺省调用输出重排前后逐字节一致，作为零回归硬证据（快照断言）；`_is_style_md` 扫描范围收窄到 `briefs/` 是可选优化（Phase 3 达成后），非零回归前提。
- **KTD3 · 来源/分类进元数据 + 派生索引先并行校验后替换**。`source`/`taxonomy` 落 brief json（KTD 落点，安全性证据见 KTD3a）；`_INDEX`/`风格路由` 由生成器从元数据确定性重建；Phase 0 生成器只跑 `--check`（生成结果 vs 手工表 diff 为空）不替换，正式替换留到 Phase 2 U2.2 有 stem 唯一树的地基。降险理由：手工表与元数据在过渡期并存，任一侧错误立即被 diff 捕获。
  - **KTD3a · 新增顶层键对 render 输出面构造性安全（代码证据，非假设）**：`templates.compose_style()` 的返回值是显式白名单 dict literal（`name/visual_direction/color_palette/typography/layout_patterns` + 条件键 `token_sidecar/brand/guardrail/layout_lock/image_rendering/mode/style_anchor`），不存在把 brief 顶层未声明键 passthrough 进输出的路径；`style-brief-v1.schema.json` 顶层未设 `additionalProperties: false`。故 `source`/`taxonomy` 落 brief json 顶层不会被 render 回显，零回归无需依赖运行时验证兜底，也无需改用 frontmatter/sidecar 承载（已考虑并否决该备选：brief 单文件承载比拆两个物理位置更符合既有 `aliases`/`token_sidecar` 先例）。
- **KTD4 · stem 全库唯一作为 Phase 2 前置门**。新增 stem 唯一性 lint（Phase 0 U0.3），Phase 0 先对存量 audit；Phase 2 来源归位（跨目录移动 05/15/16 brief）前该 lint 必须全绿。存量冲突改名属 `style list` user-visible 变更（记 CHANGELOG，改名同步 brief 内 `style_name` 与 `aliases` 检索）。
- **KTD5 · md 交叉引用不受 `smart_relocate` 保护，可选 Phase 1 用专用批改脚本 + `check_references` 出口门**。`smart_relocate` 只更新代码 import；风格库内是 md 相对链接（`_INDEX`/`风格路由`/`style-library` 大量硬编码路径 + brief 间引用）。**此风险集中在可选 Phase 1**（迁移散文轴/覆盖层涉及的引用面远大于 Phase 2 的 05/15/16 单向归位）；Phase 1 若执行需用批量改写脚本更新相对链接，`check_references` 悬空归零作为 Unit 出口。Phase 2 引用面较小但同样过 `check_references` 出口门（见 U2.1a Verification）。
- **KTD6 · 与坐标系 plan 的重叠项单一 owner，避免双写**。R4（计数真值）= 坐标系 plan R7；明度档字段与色相桶（坐标系 plan R1/R3）本方案只消费。建议本方案 Phase 0 与坐标系 plan 合批或紧邻执行，计数函数与明度/色相字段由单一 Unit 落地、另一方引用。

### Interface Contracts

- **brief JSON 元数据增量**（`references/styles/**/*.md` 内嵌 json）：
  - `source`：对象，`{origin: "builtin"|"reference", batch: string, upstream_ref: string|null, license_note?: string}`；
  - `taxonomy`：对象，`{visual_family: string[], industry: string[], scenario: string[]}`（可空数组）；
  - 既有字段（`style_name/aliases/best_for/visual_direction/canvas/color_palette/typography/layout_blueprints/variant_of`）**一律不变**；
  - 缺失策略沿用既有「内置必填、参考渐进白名单」（`scripts/style-lint-baseline.txt` 只缩不涨）。
- **派生索引生成器**（`scripts/` 新增或并入 `lint_style_index`）：输入 `briefs/` 全量 brief 元数据，输出 `_INDEX.md` 分类/来源段与 `风格路由.md` 的可派生行；确定性（纯聚合 + 排序，无时间戳）；`--check` 模式只 diff 不写。
- **lint 口径**：`lint_style_index` 的 `BRIEF_DIRS` 随分层更新；新增 stem 唯一性 lint；单一计数函数为三处文档计数的唯一真值源（文档从其派生）。
- **运行时（可选，Phase 3 达成后）**：`_is_style_md` 扫描范围可从 `styles/` 全树收窄到 `styles/briefs/`；行为不变（仍按内容判定），仅缩小遍历面。

### Assumptions

> 本 plan 为 bootstrap 撰写，以下 WHAT 级选择待 owner 在执行前确认；不确认即维持现状的部分已标注。

- **A1（路径解耦已核实）**：见 Dependencies A1，重排不动运行时。
- **A2（stem 唯一性状态未知）**：Phase 0 U0.3 先 audit，冲突改名列为必须显式确认项。
- **A3（明度档机械可推导被高估）**：承接坐标系 plan 评审发现，本方案不重定口径。
- **A4（md 引用漂移为最大迁移风险）**：`check_references` 为 Phase 1 出口门；若其现有能力不足需扩断言（Outstanding Question）。

---

## Implementation Units

### Phase 0 — 元数据化（零文件迁移）

#### U0.1 brief 元数据 schema 扩展（R2、R3）

- **Goal**：在既有 brief json 内追加 `source` 与 `taxonomy` 字段，把来源与分类从「路径」搬到「字段」，不动任何既有字段与文件位置。
- **Requirements**：R2、R3。
- **Dependencies**：无。
- **Files**：`references/styles/**/*.md`（brief 内 json 增字段，内置必填、参考渐进）、`runtime/src/leo_ppt_generator/schemas/`（若存在 brief schema 则同步；否则在 `scripts/` lint 内声明必需键）、`scripts/style-lint-baseline.txt`（白名单登记）、根 `CHANGELOG.md`。
- **Approach**：先定义 `source`/`taxonomy` 字段口径（见 Interface Contracts）；11 顶层内置必填两字段（`source.origin=builtin`、`taxonomy` 按现分类回填）；参考风格渐进迁移进白名单。`taxonomy` 回填口径（**R3 范围澄清**）：因现状目录是单继承，机械回填只能确定性填入该风格当前所在目录对应的**一个主轴**（如 01 子族 brief 只填 `visual_family`，02 子族 brief 只填 `industry`），另外两轴留空数组，不臆造；`visual_family/industry/scenario` 三键结构必须齐备，但「多归属」的人工/半自动富化不在本 Unit 预算内，作为渐进工作登记（不阻断 Phase 0 出口）。来源目录（04/05/14/15/16）的风格 `source.upstream_ref` 记原目录。
- **Test scenarios**：`lint_style_briefs` 校验新字段结构；内置缺字段 ERROR、参考进白名单。
- **Verification**：`python3 scripts/lint_style_briefs.py` 退出码 0；11 内置两字段齐备；`style render` 缺省输出逐字节不变（字段不进 render 输出面）。

#### U0.2 单一计数真值函数 + 三处文档派生（R4，坐标系 plan R7 协调）

- **Goal**：建立全库计数的单一函数口径，三处文档从其派生，终结 279/311/294/300 并存。
- **Requirements**：R4。
- **Dependencies**：U0.1（口径依赖 `source`/`variant_of` 字段）。
- **Files**：`scripts/lint_style_index.py`（计数函数 + 派生断言）、`references/styles/00_索引/_INDEX.md`、`references/style-library.md`、`references/style-recommendation.md`（计数改为派生/被校验）。
- **Approach**：在 `lint_style_index` 内定义 canonical 计数（可加载 / 独立可选 / 分类轴 / 来源，口径见 Interface Contracts）；扩断言——三处文档声明的计数与函数输出不一致即 ERROR。**与坐标系 plan R7 单一 owner**：若坐标系 plan 先落此函数，本 Unit 只做三处文档派生接线。
- **Test scenarios**：故意改 `_INDEX` 顶行某计数 → lint ERROR；改回 → 绿。
- **Verification**：`python3 scripts/lint_style_index.py` 退出码 0；三处文档计数一致。

#### U0.3 stem 唯一性 lint + 存量 audit（R5）

- **Goal**：把「文件名 stem 全库唯一」这一 rglob 去重隐性前提显式化为 lint，并对存量 audit。
- **Requirements**：R5。
- **Dependencies**：无。
- **Files**：`scripts/`（新增 stem 唯一性 lint，或并入既有 lint）、根 `AGENTS.md`/`CLAUDE.md`（仓库级检查清单登记一行）。
- **Approach**：递归扫描 `references/styles/**/*.md` 中含 json brief 的文件，收集 `path.stem`，重复即 ERROR 并列出冲突路径；对当前库跑一次 audit，冲突项登记（改名留 Phase 2 前置处理）。
- **Test scenarios**：构造同 stem 两文件 → ERROR；无冲突 → 绿。
- **Verification**：新 lint 存量运行退出码 0，或如实列出待改名冲突清单并登记 owner/批次。

#### U0.4 派生索引生成器（--check 并行校验）（R3）

- **Goal**：从 brief 元数据确定性生成 `_INDEX`/`风格路由` 的分类/来源段，Phase 0 只并行校验不替换。
- **Requirements**：R3。
- **Dependencies**：U0.1（消费 `source`/`taxonomy`）。
- **Files**：`scripts/`（生成器，或 `lint_style_index` 生成模式）。
- **Approach**：遍历 `briefs` 元数据聚合分类/来源段，`--check` 输出生成结果与手工 `_INDEX`/`风格路由` 的 diff；确定性（纯聚合 + 排序）。此步验证「元数据足以重建索引」，为 Phase 2 正式替换铺路，也让进货新风格自动可见于派生路由。
- **Test scenarios**：新增一个带完整 `taxonomy` 的 brief → 生成器输出含其分类行。
- **Verification**：`--check` 对当前库 diff 为空（或差异可逐条解释为「手工表待补的进货缺口」）。

### Phase 1（可选，后置）— 类型分区（低风险重命名）

> 收益为纯可读性/运行时遍历面优化，成本是全方案最大迁移风险（KTD5）；默认不随本方案交付，待 Phase 0+2 完成后视需要单独立项执行。

#### U1.1 迁移散文轴与覆盖层 + 引用批改（原子单元，含 R1、R6）

- **Goal**：把散文轴（06/07/08/09/11/13）迁入 `axes/`、品牌与版式库（10/12）迁入 `overlays/`、索引规则文档（00_索引）迁入 `_meta/`，并在同一单元内修复全部 md 相对链接，**不动 01/02/03 的 265 份 brief**。文件移动与引用批改声明为**同一原子单元**（而非前后两个互相依赖的 Unit），避免任务图出现「移动依赖批改、批改依赖移动」的循环依赖。
- **Requirements**：R1、R6。
- **Dependencies**：无。
- **Files**：`references/styles/{06,07,08,09,11,13}/` → `axes/`；`{10,12}/` → `overlays/`；`00_索引/` → `_meta/`（含 sidecar `.layouts.json` 随 `12_版式库` 同移）；`references/styles/**/*.md`（相对链接）、`references/style-library.md`、`references/*.md`（引用 styles 路径处）、`scripts/check_references.py`（如需扩断言）。
- **Approach**：① 用 `smart_relocate` 逐目录迁移（保代码 import，sidecar 与其 brief/版式文件同名同目录约束保持）；② `smart_relocate` 不改 md 链接，紧接着用批量改写脚本更新旧路径前缀（`06_论证模式/`→`axes/argument-mode/` 等）；③ `check_references` 作为出口门，若其不覆盖风格库内相对链接则先扩断言（Outstanding Question）。①②③ 在同一提交内完成，不拆成可独立推进又互相等待的两个 Unit。
- **Test scenarios**：迁移后 `style list` 计数不变（散文轴本非 brief）；迁移前后 `check_references` 对比，迁移后悬空引用应为 0。
- **Verification**：`style list`/`style load`/`style render` 缺省输出逐字节不变；目录树顶层出现 `axes/`/`overlays/`/`_meta/`；`python3 scripts/check_references.py` 风格库内悬空引用归零。

#### U1.2 lint BRIEF_DIRS 口径更新 + 运行时扫描范围可选收窄（R1）

- **Goal**：让 lint 与运行时的目录假设与新分层一致。
- **Requirements**：R1。
- **Dependencies**：U1.1。
- **Files**：`scripts/lint_style_index.py`（BRIEF_DIRS）、`scripts/lint_layout_grid.py`（若含路径假设）、`runtime/src/leo_ppt_generator/styles.py`（可选：`_is_style_md` 扫描范围收窄到 `briefs/`）。
- **Approach**：BRIEF_DIRS 更新为新分层；运行时收窄扫描范围为可选优化，若做则加逐字节回归断言（行为不变，仅缩遍历面）。
- **Test scenarios**：`lint_style_index` 通过；若收窄扫描范围，`style list` 结果集不变。
- **Verification**：`python3 scripts/lint_style_index.py` 退出码 0；`capability_manifest --compare` 计数一致。

### Phase 2（默认交付，紧接 Phase 0）— 来源文件夹归位（dissolve 进分类树，跟齐 S1a/S2a 先例）

> **决策（2026-09-02，owner 确认走 dissolve、不做来源 UPSTREAM 化）**：已核实 styles 不在 `upstreams.yaml`/`vendor-lock.json`，无 live 上游同步；且存量 brief 已本地改造（进 `FAMILIES` 家族、加 `aliases`、palette 三层 token 化），整目录覆盖会 clobber 本地改造，干净 re-sync 对存量不现实。故来源纯属历史标签 → dissolve。**跟齐既有先例**：`style_hard_rules.FAMILIES` 记载 S1a 批（oh-my-ppt）已把 6 个新家族落成 `01_通用母版` 子目录、S2a 批（LandPPT）落 2 个；`04/05/14/15/16` 是 C1/C2 未跟齐的 holdout，本阶段消除该不一致。此路径比原「拍平 briefs/ 单树」风险低、有先例——**拍平单树降级为可选 Phase 3**。
>
> **审计结论（2026-09-02，35 brief 实测）**：05/15/16 几乎全是**视觉风格** → 归 `01_通用母版`；finance/gov 类（投行IR/集团IR/韩式政府等）行业只是各 brief 的 `best_for` 元数据，不构成进 02/03 的理由。04（组件模板）、14（参考池）非 brief，另置。
>
> **依赖关系澄清（修正版）**：本阶段依赖 Phase 0（元数据），**不要求先完成可选 Phase 1**（类型分区）——01/02/03 在 Phase 1 不动。但 U2.1b/U2.2 的目标路径含 `_meta/`（Phase 1 的产物），故两种前置状态下的落点已在对应 Unit 显式给出回落路径（若 Phase 1 未做则落 `00_索引/` 现路径），确保「不要求先做 Phase 1」在两种状态下都有明确、非空的执行路径，而不是悬空声明。
>
> **排序**：由于 Phase 2 不要求 Phase 1 前置且是本方案核心价值，**推荐执行顺序为 Phase 0 → Phase 2 → （可选）Phase 1 → （可选）Phase 3**，而非按章节编号顺序推进（见 Goal Capsule / KD-3 / KTD1）。

#### U2.1a 05/15/16 视觉风格归位 `01_通用母版`（R1、R2）

- **Goal**：把 05/15/16 的 35 个视觉风格 brief（+sidecar）迁入 `01_通用母版` 对应子族，消除来源文件夹。
- **Requirements**：R1、R2。
- **Dependencies**：U0.3（stem 唯一性全绿）前置门；U0.1（`source`/`taxonomy` 齐备）。**不依赖 Phase 1。**
- **Files（按审计映射）**：
  - `05_来源_awesome-gpt-image-2/`(3) → `01_通用母版/艺术表现/`（写实摄影风 / 历史古风题材风 / 场景叙事分镜风）；
  - `15_来源_officecli/`(7) → `01_通用母版/精密网格/`（family 已是「精密网格」）；
  - `16_来源_slides-grab/`(25) → `01_通用母版/精密网格/` 与 `01_通用母版/韩式咨询/`（按 `FAMILIES` 既有两族，含 finance/gov 视觉风格）。
- **Approach**：新建 `01_通用母版/精密网格/`、`01_通用母版/韩式咨询/` 两个子目录（家族名已在 `FAMILIES`，落目录=跟齐 S1a/S2a）；`smart_relocate` 迁移、sidecar 同名同移；每个 brief 的 `source.upstream_ref` 记原来源目录。
- **Test scenarios**：迁移后 `style list`/`style load` 结果集逐一对应；`风格路由.md` 派生段含新子族。
- **金样板画廊重生成（代码级核实，非假设）**：`generate_style_gallery.axis_counts()` 对含子目录的 axis（含 01/05/16）用**非递归** `*.md` glob 统计，迁移会改变其计数并使 `--check` 的 markdown 文本 diff 报 STALE——这是**已知的预期变化**，处理方式是迁移后运行一次 `python3 scripts/generate_style_gallery.py`（不带 `--check`）重生成并提交新 `samples/style-gallery.md`，而非把 STALE 当异常排查。金样板 thumbnail 回归（`check_golden()`）覆盖 `golden_style_names()`——11 顶层内置 + 8 个 S5 family representatives，05/15/16 内的风格从不在该名单内，故 thumbnail 回归**不受本迁移影响**，只需处理文本表格 diff。
- **Verification**：`style render` 逐字节回归；重生成后 `generate_style_gallery --check` 通过（无 thumbnail 漂移，文本表格已随重生成更新）；`check_references` 悬空归零；`lint_style_index` BRIEF_DIRS 计数一致。

#### U2.1b 04 组件模板归位、14 参考池独立（R1）

- **Goal**：把非 brief 的两类各归其位，不塞进 01/02/03。
- **Requirements**：R1。
- **Dependencies**：U2.1a。
- **Files**：
  - `04_来源_guizang/`（README + `组件模板/`，跨风格上位规则，`风格路由.md §5`）→ **落点按 Phase 1 完成状态二择一**：已完成可选 Phase 1 则落 `_meta/组件模板/`；未做 Phase 1（本方案默认交付路径）则落 `styles/组件模板/`（当前 `00_索引/` 同级新目录，不悬空等待 Phase 1）；
  - `14_参考池_gpt-image2/`（7 池代表 + `.清单.md` sidecar，不计入 brief 口径）→ 独立 `pools/`（保留清单 sidecar，同一层级，不受 Phase 1 是否完成影响）。
- **Approach**：`smart_relocate` 迁移 + md 引用批改；确认 lint 的 brief 口径仍不计入 14。
- **Test scenarios**：`04`/`14` 迁移后引用可达；brief 计数不变（14 本不计）。
- **Verification**：`check_references` 归零；`lint_style_index` brief 计数与迁移前一致。

#### U2.2 派生索引正式替换手工表（R3）

- **Goal**：`_INDEX`/`风格路由` 改由生成器产出，退役手工维护。
- **Requirements**：R3。
- **Dependencies**：U2.1a、U2.1b、U0.4。
- **Files**：`_meta/_INDEX.md`、`_meta/风格路由.md`（若已完成可选 Phase 1）或 `00_索引/_INDEX.md`、`00_索引/风格路由.md`（未做 Phase 1 时的当前路径，改为生成产物）、生成器脚本。
- **Approach**：仿确定性重投影从元数据重建，正式替换手工表；替换前最后一次 `--check` diff 语义等价。
- **Test scenarios**：重建结果与迁移前语义等价 diff。
- **Verification**：生成器输出 = 提交态；进货新风格无需手工加路由行即可见。

#### U2.3 空来源目录退役 + 进货流程更新（R2）

- **Goal**：删空 `04/05/14/15/16`，进货流程改为「按分类落 `01/02/03`（或 `pools/`）+ 写 `source` 字段」，不再开 `NN_来源_*` 目录。
- **Requirements**：R2。
- **Dependencies**：U2.1a、U2.1b、U2.2。
- **Files**：删空来源目录；`_meta/style-extension-template.md`（进货模板改为写 `source`/`taxonomy` + 落分类目录）；根 `CHANGELOG.md`（user-visible：新增 `01` 子族目录、`style list` 结果集不变但目录路径变）。
- **Test scenarios**：`ls references/styles/` 顶层无 `NN_来源_*`。
- **Verification**：新进货 brief 过 stem 唯一性 + lint；来源目录清空；`style list` 与迁移前逐一对应。

#### （Phase 3，可选）briefs/ 单树拍平

> 原 KD-1 的「全部 brief 拍平进 `briefs/` 单树、分类纯靠元数据」**降级为可选 Phase 3**——边际收益仅「运行时可只扫一个目录」。Phase 2 来源归位后 01/02/03 分类树已干净，是否再拍平待评估，不作为默认交付。

---

## Verification / Definition of Done

- **默认交付路径为 Phase 0 → Phase 2**；可选 Phase 1 → Phase 3 后置，视需要再执行（见 KD-3/KTD1 排序理由）。各阶段独立出口，Unit Verification 全绿方可推进下一阶段；跳过可选阶段不影响默认交付的 DoD 判定。
- **零回归硬证据**：全程对固定 `style render` 调用集做逐字节快照断言（缺省路径，重排前后一致）。
- **治理 lint 全绿**：`lint_style_briefs` / `lint_style_index`（含计数真值断言）/ `lint_layout_grid` / `lint_style_governance` / 新增 stem 唯一性 lint 退出码 0。
- **引用完整性**：`check_references` 风格库内悬空归零（Phase 2 起适用；Phase 1 若执行同样适用）。
- **金样板与对账**：`generate_style_gallery.py`（Phase 2 后需重生成，见 U2.1a）`--check` 无漂移；`capability_manifest.py --compare` 文件级 diff 可解释。
- **变更记录**：面向用户的结构/命名变化（如 stem 改名、`style list` 可见项变化、新增 `01_通用母版` 子族目录）在根 `CHANGELOG.md` 按 Keep a Changelog 记录并标 `(user-visible)`；lint 命令登记进 `AGENTS.md`/`CLAUDE.md` 仓库级检查清单。
