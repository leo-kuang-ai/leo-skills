---
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: spec-plan-bootstrap
execution: code
status: active
created_at: 2026-08-29
title: leo-ppt-generator 风格系统优化（评审落地）- Plan
origin: docs/leo-ppt-generator/reviews/style-review.md
review: 2026-08-29 spec-doc-review（coherence/feasibility/adversarial 三 persona，round 1 findings 已合成修复）
---

# leo-ppt-generator 风格系统优化（评审落地）- Plan

## Goal Capsule

- **Objective**：把 `docs/leo-ppt-generator/reviews/style-review.md` 的十档优化点落成可执行改造：修复库内既成缺陷、补图表样式与设计护栏规范、落地风格 token 三层化与 brief schema 化、扩展版式库与趋势风格、接入评测。
- **Recommended approach**：三波推进——W1 纯修正（引用完整性 + 图表规范文档）、W2 系统性短板（护栏成文 + 版式补缺 + token 化 + schema/lint）、W3 合同与内容增强（动效/断言标题/密度 + 趋势风格 + 评测）。文档单元与 runtime 单元分离，每个单元可独立原子落地；W1 开工前先留档评测基线。
- **Decision focus**：HEX token 三层化的落地形态与存量迁移（KTD2）；护栏前移采用 `--guardrail` 旗标而非缺省追加（KTD6）；麦肯锡近重复的收敛方式与回退成本（KTD3）；px 口径的算术判据（KTD4）；与多行业技术方案的两处边界裁决（KTD8、Interface Contracts）。
- **Verification focus**：引用完整性机检归零；lint 全库结构错误为 0；**unittest discover 真实发现并执行测试**（含 countTestCases>0 前置检查）；`style render` 缺省输出与改前逐字节一致；skill-up 对照改动前基线无回归。
- **Largest risk / boundary**：本计划只动**风格系统**（references/styles、护栏文档、styles/templates runtime、lint、evals 扩展）；多行业技术方案（`docs/leo-ppt-generator/tech-plans/multi-industry-optimization-tech-plan.md`）拥有的 content_rules 轴、`--brand` 全链路注入、dark-deck 预设变体**不在本期**，三处交叉冲突（visual-qa 断言判据行、user-colors 覆盖通道、版式编号 P23–P29）已在 KTD8/Interface Contracts/Deferred 显式裁决（见 A5/A6，版式编号让渡见 U5 与 Deferred）。

---

## Product Contract

### Summary

以风格系统评审为唯一需求来源，将其 P0/P1/P2 十档优化点全部纳入实施：两档 P0（悬空引用修复、图表样式规范）、四档 P1（排印 token、无障碍体系化、版式补缺、HEX token 化）、四档 P2（deck 级动效、断言标题与密度上限、趋势风格与明暗配对、schema+lint 前移）。产出形态为规范文档、版式/风格库内容、runtime 小改动与 lint 工具、评测用例，不改变四条硬约束（Gate 0 阻断、样张门、真实派发、completed≠闭环）与控制面五字段合同。

### Problem Frame

风格库骨架（六轴正交 + 内容-版式匹配 + 对抗式 QA）领先业界，但评审实证了四类系统性短板与若干既成缺陷：`data-journalism` 被 14 个文件悬空引用且图表样式全库零规定；排印参数几乎全是模糊自然语言；无障碍只有一条 4.5:1；`设计体系.md` "风格不带 HEX" 宣称与 138 份写死 HEX 的实现脱节；麦肯锡风格两份近重复且措辞已分叉；P23/P24 被引用但无文件；目录/团队/引用/数据大屏版式无骨架；deck 级动效空白；断言式标题与信息密度上限无合同。这些缺口每一条都有文件级证据（见 origin 文档 §二、§三）。方案审查另实证两个计划期必须吸收的事实：`python3 -m unittest discover -s leo-ppt-generator/tests` 当前**发现 0 个测试**（子目录无 `__init__.py`，存量 7 个测试从未被该命令执行）；全库 brief 的 `color_palette` 值为**散文式描述**（0/136 纯 role→HEX，accent 仅 49/136 含任何 HEX）——token 与验收合同必须按此实况设计。

### Key Decisions

- **十档全量纳入、三波推进**（session-settled: user-approved — 用户要求"详细的技术优化方案"覆盖评审全部优化点；分波依据评审 P0/P1/P2）。
- **多行业评审重叠项只协同不重复**：断言式标题、无障碍程序化、品牌 token 链路、版式缺口四处交叉验证点，本计划实现风格系统侧的一半，内容管线侧（标题连读稿、compose 阶段对比度计算、`--brand` 注入、行业版式深化）留给多行业线，边界在 Scope Boundaries 声明（session-settled: agent 拆分 — 两评审互补声明）。
- **图片式路线 stylized 图表局限对用户显式披露**，数据密集场景路由层默认导向 editable（评审 §二.4 结构性矛盾的处置）。

### Requirements

- **R1（P0 引用完整性）**：`data-journalism` 14 处悬空引用、`视觉风格配对.md` 表格断裂、麦肯锡近重复全部消除，且修复后引用完整性可机检（rg 一条命令归零）；主索引与总索引的规模计数同步更新。
- **R2（P0 图表样式规范）**：新建图表样式规范文档，覆盖坐标轴（线宽/刻度/网格线）、图例（位置与替代规则）、数据标签（直接标注优先）、色盲安全序列；图片式路线 stylized 图表的披露规则成文；14 处引用改指该文档；新文档注册进按需索引链（style-library.md 元结构 + `_INDEX.md`）。
- **R3（P1 排印 token）**：通用设计规范新增全局中西文字体栈（含 fallback）、行高阶梯、px 口径基准声明；字号下限按确定算术判据校准（换算 pt 低于 PPT 正文下限区间即上调，判定过程可复核）。
- **R4（P1 无障碍体系化）**：大字 3:1、非文本 3:1、双重编码升格为铁律并写入 visual-qa.md 可执行阈值表。
- **R5（P1 版式补缺）**：Swiss Image Split / Swiss Evidence Grid 与目录/agenda、团队、引用/金句、数据大屏、纯氛围全图共七个骨架入库，**编号 P30–P36（P23–P29 让渡多行业线，见 Deferred 跨方案协调）**；`版式内容Schema.md` 与 `00_选版式P0原则.md` 路由行同步（含既有 P23/P24 Swiss 引用行改指 P30/P31）。
- **R6（P1 HEX token 三层化）**：brief 的 `color_palette` 重定义为"角色默认值（散文描述内嵌 HEX 锚点，运行时提取）"，deck 级 colors 锚点可覆盖；`style render` 支持覆盖入参且缺省输出保持逐字节确定；**12 份顶层内置 brief 的 palette 定型为四角色含 HEX 默认值**（迁移最小集）；`设计体系.md` 宣称与实现一致。
- **R7（P2 动效/断言/密度）**：deck 级动效规范（转场白名单、时长预算、降级策略）成文；"标题必须是完整句断言"进护栏与 visual-qa 检查项（判据行由本计划独占落地，见 KTD8）；每页字数与要素总数上限成文。
- **R8（P2 趋势风格与明暗配对）**：新增迷幻国潮 2.0、暖调柔形至少 2 份风格 brief（palette 沿用"散文含 HEX"库内惯例并过 lint）；light/dark 配对机制说明成文（不逐风格做变体）。
- **R9（P2 schema + lint + 前移）**：brief JSON Schema 与 lint 脚本落地（纯 Python、零新依赖，**lint 从 schema 文件加载必需键与 HEX 规则以保持单真值源**）；`style render --guardrail` 旗标输出确定性护栏摘要（缺省输出不变）；lint 命令登记进 AGENTS.md/CLAUDE.md 仓库级检查清单。
- **R10（评测接入）**：新增行为评测用例覆盖护栏注入可见性与断言标题/密度上限判据（advise 模式轻量用例）；改动前先留档全量评测基线，回归以基线为比对基准。

### Success Criteria

- 引用完整性：`rg -n "data-journalism" leo-ppt-generator/references` 结果中不再有指向不存在文件的引用（改指新规范文档后归零或仅剩历史文档提及）。
- lint：`python3 leo-ppt-generator/scripts/lint_style_briefs.py` 退出码 0（结构错误为 0；HEX 缺失等存量偏差进 warning 白名单，白名单含 owner 与纪律声明）。
- runtime：`python3 -m unittest discover -s leo-ppt-generator/tests -p 'test_*.py'` **真实执行 ≥1 个测试（前置检查 countTestCases>0，杜绝 0 测试假绿）**，含新增 token 覆盖、shadow path 与确定性测试。
- 评测：`cd leo-ppt-generator && skill-up run evals/eval.yaml` 对照 W1 开工前留档的基线报告，既有 21 用例无回归；新增用例通过，或按 U10 政策如实记录 FAIL 原因并完成 known-issues 记账（不静默）。
- 确定性：`style render` **缺省调用**输出与改动前逐字节一致（含 U6 不传 `--color`、U7 不传 `--guardrail` 两条路径的快照断言）。

### Scope Boundaries

**In scope**：`leo-ppt-generator/references/styles/**`（规范、版式、风格、索引）、`references/visual-qa.md`、`references/style-library.md`、`references/image-deck-workflow.md`、`references/backend-selection.md`、`runtime/src/leo_ppt_generator/{styles,templates}.py` 及其 CLI 参数面、`scripts/` 新 lint、`runtime/src/leo_ppt_generator/schemas/` 新 schema 文件、`tests/`（含存量子目录可发现性修复）、`evals/`、根 `CHANGELOG.md`、根 `AGENTS.md` 与 `CLAUDE.md`（仅 lint 命令登记一行，R9 交付物归属）。

**Out of scope（非目标）**：

- 多行业技术方案拥有的内容管线侧：content_rules 行业轴、数字元数据三级标注、敏感数据分级、`style render --brand` 全参数与 `brand_assets` 契约块、compose 阶段程序化对比度计算、标题连读稿工件与校验器、行业版式深化（参数表/BOM/教学三件套等）。
- `11_图表语法` 的机器加载器（templates.py 现不加载该轴，维持文档级；加载器属内容管线侧）。
- 逐风格 dark 变体、风格缩略图 gallery、`09_结构布局` 多画幅适配规则细化。
- 存量子目录风格（124 份 reference brief）的 palette HEX 定型——本期只迁移 12 份顶层内置（R6 最小集），其余进白名单并登记 owner 与目标批次。

### Deferred to Follow-Up Work

- dark-deck 预设变体（多行业 §四）：待本计划 KTD2 token 机制落地后在其上推导，owner = 多行业线。
- visual-qa 机检的程序化实现（对比度计算器进 validate_pptx.py）：本计划先成文阈值，程序化归多行业线 compose 阶段方案。
- 图表样式规范与 mermaid 图表语法的样式合并（若未来 11_图表语法 进入机器加载）。
- **跨方案协调三项（owner = 多行业线技术方案）**：(1) 本计划已按真实需求（R6）建立 deck 级 `--color` 覆盖通道（即对方 v1 删除的 user-colors 中间层），覆盖优先级声明见 Interface Contracts，对方 D1 的覆盖顺序表需吸收该层；(2) visual-qa.md "标题读作断言"判据行由本计划 U8 独占落地（KTD8），对方 E2 保留校验器与连读稿，不再重复添加判据行；(3) **版式编号分配**：P23–P29 归对方批次 3（章节隔页/数字冲击页/规格表/文献页/教学三件套），本计划七骨架编号 P30–P36，`00_选版式P0原则.md` 既有 P23/P24 Swiss 引用行由本计划 U5 改指 P30/P31。两方案的相对执行时序未知，后落地方负责对齐。
- 存量子目录风格 palette 的渐进 HEX 定型（owner = 风格库维护者，批次目标登记在 lint 白名单文件头）。

---

## Planning Contract

Product Contract unchanged (bootstrap-authored this run; WHAT 全覆盖映射 origin §0 矩阵——R7 承接矩阵 P2 的动效与断言/密度两行，R9/R10 拆分 schema+evals 行，P23/P24 由 R5 承接，其余一一对应).

### Key Technical Decisions

- **KTD1 · 图表规范落点为 `00_索引/图表样式规范.md`，纯文档级**。`templates.py` 不加载 `11_图表语法` 轴（已核实：仅 06/07/08/12 轴有 loader），图表规范只需文档存在且被正确引用，不触发 runtime 改动。消费链依赖 agent 经按需索引读到该文档或其引用方——以 R2 的索引注册缓解，不为此加机器消费方。备选"顺带新增 chart loader"被否决：超出风格系统边界且无消费方。
- **KTD2 · HEX token 采用"角色默认值 + deck 覆盖"落地，而非撤回宣称；brief 的默认值形态是"散文描述内嵌 HEX 锚点"**。实况：全库 136 份 brief 的 palette 值均为散文（如麦肯锡咨询风 accent 为纯文字描述，无 HEX），运行时覆盖与护栏派生都必须按"提取散文中的 HEX token"设计。`compose_style()` 现逐字转发 brief 的 `color_palette`（`runtime/src/leo_ppt_generator/templates.py:170-176`）；在其上叠加可选 colors 覆盖参数（role→HEX 合并）。**配套最小迁移**：12 份顶层内置 brief 的 palette 定型为四角色均含 HEX 锚点的描述（人工定型，保留用法说明文字），使三层结构的中间层对内置风格真实成立；124 份 reference 风格渐进迁移（Deferred 登记 owner）。撤回宣称是备选，被否决：与多行业线 brand VI 链路方向冲突。
- **KTD3 · 麦肯锡去重采用"删顶层、母版为唯一真值"**。`styles.py` 的 `list_styles` 顶层优先遮蔽子目录（`runtime/src/leo_ppt_generator/styles.py:138-150`），当前顶层 `麦肯锡风格.md` 与 `01_通用母版/商务专业/麦肯锡咨询风.md` 内容同义且措辞已分叉。删除顶层文件后 `麦肯锡咨询风` 经 rglob 自动可见。备选"内容同步为逐字节一致"被否决：漂移面仍在。**用户可见变化**：`style list` 名称由 `麦肯锡风格` 变为 `麦肯锡咨询风`，style-library.md 记更名指引。**回退成本**：git 撤销删除容易，但"退回复选"意味着重建两份已分叉文档的同步版本 + 二次清理全库引用，需专门单元——handoff 时更名决定一旦确认即视为锁定（A2）。
- **KTD4 · px 口径显式声明为 1920×1080 HTML 画布基准 + 换算表，校准主判据为确定算术而非观感**。声明写入通用设计规范；校准判据：按 1920px→13.33in→96dpi 换算 pt 值，与 PPT 正文常用下限区间（≥14pt）比对，低于即同单元上调 18px 下限并同步换算表；样张渲染仅作可选佐证（图片后端不可用不阻塞，判据过程与数值记入 CHANGELOG 条目，可复核）。
- **KTD5 · lint 纯 Python 零新依赖，且以 schema 为单真值源**。`runtime/constraints/*.txt` 未确认含 jsonschema；lint 脚本用 stdlib `json` 读取 `style-brief-v1.schema.json`，**必需键与 HEX pattern 一律从 schema 派生**，脚本只保留 schema 表达不了的数量子集校验（layout_blueprints[].sections[].count 正整数）——避免 schema 与 lint 成为两份独立真值源、schema 落地即死工件。
- **KTD6 · 护栏前移采用 `--guardrail` 旗标，缺省输出保持逐字节不变**。`style render` 的 stdout 是 `style-library.md` 已发布的"同输入逐字节确定"输出面；无条件追加护栏块会破坏任何以快照比对 render 输出的外部消费者。改为：`compose_style(..., guardrail=False)` 可选参数 + CLI `--guardrail` 旗标；缺省路径输出与改前逐字节一致；旗标路径输出含护栏摘要块（固定文案 + 从 brief 提取的 accent HEX 派生行，**无 HEX 时整行省略**），同输入逐字节确定。注入合同写在 style-library.md：agent 为 deck_spec 注入 render 输出时使用 `--guardrail`。备选"在 prepare_slide_prompts 注入侧拼装"被否决：该文件在 `_vendor/codex_ppt/`，改动需走 patches 流程，超出本期边界。
- **KTD7 · 版式扩展沿用现有文件协议**。新骨架文件命名 `NN_Name.md` + `# 版式：` 标题 + `**用途**/**适用内容类型**/**骨架**/**关键类**/**动效 recipe**` 字段，`load_layout()`（`templates.py:94-109`）与 `list_templates()` 自动收纳，无需 runtime 改动。
- **KTD8 · 断言式标题落护栏 + visual-qa 检查项，判据行由本计划独占；连读稿 defer**。与多行业技术方案 E2 的交叉冲突已核实（对方 E2 原文含"visual-qa 文字区加'标题读作断言'判据"）：**本计划 U8 独占落地 visual-qa.md 的该判据行**，多行业 E2 保留校验器与连读稿工件（已在 Deferred 向对方登记）；U8 验收含"该判据行全库仅一处"机检，防止双写。
- **KTD9 · 测试可发现性先于一切测试编写**。实况：`tests/` 三个子目录（boundary/installer/upstream）均无 `__init__.py`，`unittest discover` 当前发现 0 个测试——存量 7 个测试从未被该命令执行。本计划新测试一律放 `tests/` 顶层（对齐 evidence-first-writing 的可发现布局）；U7 顺带为存量子目录补 `__init__.py` 使其可被发现，若因此暴露存量失败，如实记录 known-issues 并修复或显式登记，不静默。验收前置检查 countTestCases>0。

### Interface Contracts

- **`leo-ppt style render` CLI**：新增两个可选参数——(1) 重复参数 `--color <role>=<HEX>`（role ∈ {primary, secondary, accent, neutral}）；(2) 旗标 `--guardrail`。缺省（两参皆不传）输出与现状逐字节一致（向后兼容）。错误合同：非法 role、非 HEX 值、**请求的 role 不在目标 brief palette 中**、**brief 无 color_palette 而又请求覆盖**——四种情形统一抛新增 reason code `style_color_override_invalid`（不复用 template_store_error 家族，保持语义独立；`styles.py` 现有 `StyleStoreError` 子类机制可直接承载）。合法 role 但 brief 缺该键**不得静默跳过**（实况 6/136 份内置 brief 缺至少一个 role，静默丢弃与"非法输入清晰失败"合同精神相悖）。
- **覆盖优先级（跨方案声明）**：显式 `--color`（本次调用）> 用户品牌（`--brand`，多行业线，持久化档案）> 风格角色默认值（brief 内 HEX 锚点）。理由：显式调用意图强于持久化档案，且允许品牌 deck 做单点微调。多行业技术方案 D1 的覆盖顺序表（现为"用户品牌 > 风格默认"，且其 v1 曾删除 user-colors 中间层）需吸收本层——已登记 Deferred，由后落地方对齐。
- **brief JSON Schema（`runtime/src/leo_ppt_generator/schemas/style-brief-v1.schema.json`）**：声明必需键（type/style_name/best_for/visual_direction/canvas/color_palette/typography/layout_patterns）与 color_palette 各 role 的格式口径——**值须为含用法说明的自然语言且至少内嵌一个合法 `#RRGGBB` token（HEX 缺失为 warning 级，非 error）**，`layout_blueprints` 声明为可选键（现存 brief 均有，但 schema 不强制，lint 对其只做存在性子集校验）。生产者：风格库作者（人/agent）；消费者：lint 脚本（唯一现役消费者，required 与 pattern 从 schema 派生，KTD5）。**Parser 状态**：`compose_style` 用正则提取 ```json 块（已存在），schema 不改变解析路径；lint 独立解析同格式。

### Assumptions

> bootstrap 无上游 Product Contract，以下 WHAT 级选择由计划期推荐、待 owner 在 handoff 确认；不确认即维持现状的部分已标注。

- **A1**：KTD2 方向（token 落地而非撤回宣称）— 与 `设计体系.md` 既有宣称一致；但注意多行业技术方案 D1 曾显式删除 user-colors 通道（"待有真实需求再立合同"），本计划即以 R6 作为该真实需求立项，优先级声明见 Interface Contracts，跨方案对齐已登记 Deferred。
- **A2**：KTD3 麦肯锡更名属用户可见变化且回退成本不对称（回退 = 重建同步两份分叉文档 + 二次引用清理，需专门单元，见 KTD3）— handoff 确认后视为锁定，列为**必须显式确认项**。
- **A3**：px 口径按 1920×1080 声明为初始假设，算术判据校准后允许同单元调整数值（KTD4）。
- **A4**：评测面诚实登记——**既有 21 用例对本次改动的行为面（排印 token、断言标题护栏、密度上限、护栏注入）零断言覆盖**（核对过 21 用例全为 advise/门禁类，无一触及标题句式或注入面），"靠回归兜底"不成立；故 U10 除护栏用例外补 2 个 max_turns=1 轻量 advise 用例（断言标题判据、密度上限），仍保持克制；评测为模型驱动、单次运行有波动，回归结论以 W1 前留档基线为比对基准。
- **A5**：跨方案时序未知——多行业技术方案若先落地，其 E2（visual-qa 判据）、D1（compose_style 加 load_brand 合并）、批次 3（P23–P29 版式编号）与本计划 U8/U6/U5 的冲突从潜在变为实际返工；本计划已单方面让号（P30–P36）并登记其余两项，后落地方负责对齐（Deferred 已登记三项）。
- **A6**：12 份顶层内置 brief 的 palette 人工定型（KTD2 迁移）以"保留散文用法说明 + 补 HEX 锚点"为口径，不机械替换为纯 HEX——保持库内表达惯例（与 R8 的 U9 新风格口径一致）。

---

## Implementation Units

### U1. 图表样式规范文档（R2）

- **Goal**：新建 `leo-ppt-generator/references/styles/00_索引/图表样式规范.md`，作为全库图表视觉样式的唯一规范，终结"14 文件悬空引用 data-journalism"的目标缺口。
- **Requirements**：R2。
- **Dependencies**：无。
- **Files**：`leo-ppt-generator/references/styles/00_索引/图表样式规范.md`（新建）、`leo-ppt-generator/references/style-library.md`（元结构清单注册一行）、`leo-ppt-generator/references/styles/00_索引/_INDEX.md`（总索引条目）。
- **Approach**：内容结构对齐 `设计体系.md` 的分节惯例：定位（一段）→ 坐标轴（线宽 1–1.5px 与 08_图片渲染 数字仪表盘条款对齐、刻度密度、网格线弱化规则）→ 图例（默认禁用、以直接标注替代；必须图例时的位置与排序规则）→ 数据标签（直接标注优先、数值格式、单位口径）→ 色盲安全序列（与 R4 双重编码联动）→ **stylized 图表披露规则**（图片式路线图内图表不含真实数据值时的交付话术与适用边界）→ 与 `12_版式库` 数据版式（P6/P7/P20/P21）的引用关系。同步把新文档注册进 style-library.md 按需索引链与 `_INDEX.md`（否则发现链退化为"恰好读到 11_图表语法 某文件"）。
- **Test scenarios**：`Test expectation: none — 纯规范文档`；验收走 U2 的引用完整性机检与人工评审。
- **Verification**：文档存在、含上述七节、08 渲染轴数值条款与其一致（无互相矛盾的线宽/圆角值）；style-library.md 元结构与 `_INDEX.md` 可检索到新文档。

### U2. 引用完整性修复包（R1、R2 引用条款）

- **Goal**：消除风格库全部已核验的悬空引用与既成缺陷。
- **Requirements**：R1；R2 的"14 处引用改指"条款。
- **Dependencies**：U1（data-journalism 14 处改指新文档）。
- **Files**：`leo-ppt-generator/references/styles/11_图表语法/*.md`（12 份引用行）、另 2 处 data-journalism 引用文件（实现期 rg 定位）、`leo-ppt-generator/references/styles/麦肯锡风格.md`（删除）、`leo-ppt-generator/references/styles/00_索引/视觉风格配对.md`（表格修复）、`leo-ppt-generator/references/style-library.md`（麦肯锡更名指引 + 规模计数 136→135、顶层 12→11）、`leo-ppt-generator/references/styles/00_索引/_INDEX.md`（同名计数与条目同步）、根 `CHANGELOG.md`。
- **Approach**：四件事——(1) 14 处 `data-journalism` 引用统一改指 `00_索引/图表样式规范.md` 相对路径；(2) 删除顶层 `麦肯锡风格.md`（KTD3），rg 全库扫旧名引用并更新，style-library.md 加一行更名指引；(3) `视觉风格配对.md:46` 附近空行打断的表格行合并（注意：`templates.py::_pairs()` 逐行正则解析，空行不影响运行时，此修复纯为人读，**不得改动任何配对内容**）；(4) style-library.md 与 `_INDEX.md` 的可加载风格计数同步（删除顶层一份后 136→135、顶层内置 12→11）。
- **Execution note**：先跑 `rg -n "麦肯锡风格" leo-ppt-generator/` 建立旧名引用清单再动手，避免漏改。
- **Test scenarios**：`Test expectation: none — 文档修复`；机检见 Verification。
- **Verification**：`rg -n "data-journalism" leo-ppt-generator/references | grep -v 图表样式规范` 归零；`rg -n "麦肯锡风格" leo-ppt-generator/` 仅剩 style-library.md 更名指引；`leo-ppt style list` 输出含 `麦肯锡咨询风` 且不含 `麦肯锡风格`；`style render 麦肯锡咨询风` 成功；style-library.md/_INDEX.md 计数与 `ls` 实际数目一致。

### U3. 图片式路线披露 + 数据密集路由（R2 披露面）

- **Goal**：把"图片式路线 stylized 图表不承载真实数值"的局限从暗伤变成明示合同。
- **Requirements**：R2（披露规则部分）。
- **Dependencies**：U1（披露话术引用规范文档）。
- **Files**：`leo-ppt-generator/references/backend-selection.md`、`leo-ppt-generator/references/styles/00_索引/风格路由.md`、`leo-ppt-generator/references/image-deck-workflow.md`。
- **Approach**：backend-selection.md 增一条能力对照（数据密集 deck → editable/hybrid 优先，注明判据：数据版式页占比）；风格路由.md 八步决策的图表步引用 U1 规范；image-deck-workflow.md 交付节加一句固定披露（数据页为 stylized 表现、真实数值以母版/可编辑版为准）。
- **Test scenarios**：`Test expectation: none — references 文档`；行为面由 U10 新增轻量用例与既有 evals 回归兜底（不改控制面字段）。
- **Verification**：三处文档互相引用一致；披露句不进入五字段控制面块（人工确认位置在解释区之后）。

### U4. 设计护栏成文包：排印 token + 无障碍体系化（R3、R4）

- **Goal**：把字号/字体/行高/对比度从散点口头约定升级为成文、可引用、可 QA 的护栏。
- **Requirements**：R3、R4。
- **Dependencies**：无（与 U6 共享 token 命名，先落地者定名，后者跟随）。
- **Files**：`leo-ppt-generator/references/styles/00_索引/通用设计规范.md`、`leo-ppt-generator/references/visual-qa.md`。
- **Approach**：通用设计规范新增三节——(1) **全局字体栈**：中文黑体系（思源黑体/Noto Sans SC 系）、西文（Inter/Helvetica Neue 系）、衬线备选（Noto Serif SC/宋体系）三档栈写法 + 风格文件 override 规则（只许换族、不许绕过下限）；(2) **行高阶梯**：标题/正文/caption 三档数值（如 1.1–1.2 / 1.4–1.6 / 1.5，实现期可调）；(3) **px 口径声明 + 换算表**（KTD4）。无障碍节：4.5:1 之外补大字（≥24px 或 ≥18.66px bold）3:1、非文本（图形/图标/边框）3:1、双重编码从 visual-qa 建议升格为铁律表述。visual-qa.md 阈值表同步加三行（3:1×2、双重编码铁律化）。
- **Execution note**：px 校准主判据为确定算术（KTD4）：18px@1920 画布按 1920px→13.33in→96dpi 换算 pt，与 PPT 正文 ≥14pt 下限区间比对，低于即上调下限并同步换算表；样张渲染仅可选佐证（后端不可用不阻塞）；判定算式与结论记入 CHANGELOG。
- **Test scenarios**：`Test expectation: none — 规范文档`；数值合理性由 U10 轻量用例与人工评审兜底。
- **Verification**：两文档新增节齐备；与 `12_版式库/01_常犯错误.md` 既有排印条款无矛盾（rg 交叉核对字号数字）；换算表与算术判据可复核。

### U5. 版式库扩展包（R5）

- **Goal**：补齐被引用不存在的 P23/P24 与五类高频缺口骨架。
- **Requirements**：R5。
- **Dependencies**：无。
- **Files**：`leo-ppt-generator/references/styles/12_版式库/`（新建 `30_Swiss_Image_Split.md`、`31_Swiss_Evidence_Grid.md`、`32_Agenda.md`、`33_Team_Grid.md`、`34_Quote_Hero.md`、`35_Data_Wall.md`、`36_Ambience_Full_Bleed.md`）、`leo-ppt-generator/references/styles/00_索引/版式内容Schema.md`、`leo-ppt-generator/references/styles/12_版式库/00_选版式P0原则.md`、`leo-ppt-generator/references/style-library.md`（版式计数同步）、`leo-ppt-generator/references/styles/00_索引/_INDEX.md`（条目同步）。
- **Approach**：七个新骨架全部按 KTD7 协议编写（`# 版式：Pxx Name` + 五字段）。**编号让渡**：多行业技术方案批次 3 已将 P23–P29 分配给章节隔页/数字冲击页/规格表/文献页/教学三件套，本计划七骨架改用 P30–P36，并同步把 `00_选版式P0原则.md:31-32,50-51` 既有的 P23/P24 Swiss 引用行改指 P30/P31（消除"引用无文件"缺陷的最终形态）；P30/P31 内容依据该两行已写明的定位（单图解释论点 / 2–3 张同类图片证据链）展开，P32–P36 依次对应目录、团队、引用金句、数据大屏、纯氛围全图。`版式内容Schema.md` 每版式补必填内容字段与数量硬约束（沿用 P4=6 的风格）；`00_选版式P0原则.md` 路由表补对应行。多行业 §六 点名的隔页/参数表/教学三件套等在 00 原则文末加一张"已知缺口与归属"表，注明归多行业线。
- **Patterns to follow**：`12_版式库/06_KPI_Tower.md`（数据类）、`03_Statement.md`（陈述类）的字段密度与动效 recipe 写法。
- **Test scenarios**：`leo-ppt style render <风格> --layout P30` 等 7 个新名逐一可加载（`load_layout` 命中）；`style render --list-templates` 的 layouts 列表含 7 个新 stem；`rg -n "P23|P24" leo-ppt-generator/references/styles/12_版式库/00_选版式P0原则.md` 不再指向不存在的 Swiss 版式。
- **Verification**：7 文件齐、Schema/路由行同步、`list_templates()` 枚举含新项（可在 U7 lint 或一次性 python -c 验证）；style-library.md/_INDEX.md 版式计数与实际一致。

### U6. 风格 token 三层化 + 内置 palette 定型（R6）

- **Goal**：`color_palette` 角色默认值 + deck 覆盖机制落地，内置 12 份 brief 定型，`设计体系.md` 宣称与实现重新一致。
- **Requirements**：R6。
- **Dependencies**：无硬依赖（建议在 U4 后执行以复用 token 命名；**Verification 示例使用 `麦肯锡咨询风`，依赖 U2 先落地——或改用任一未被顶层遮蔽的既有风格名验证**）。
- **Files**：`leo-ppt-generator/runtime/src/leo_ppt_generator/templates.py`（`compose_style` 增加 `colors` 参数）、`leo-ppt-generator/runtime/src/leo_ppt_generator/cli.py`（`style render` 增加 `--color` 重复参数）、`leo-ppt-generator/tests/test_compose_style_colors.py`（新建，**置于 tests/ 顶层以保证可发现**，KTD9）、`leo-ppt-generator/references/styles/*.md`（12 份顶层内置 brief 的 palette 定型）、`leo-ppt-generator/references/styles/00_索引/设计体系.md`（"风格不带 HEX"节改写为三层表述）、`leo-ppt-generator/references/style-library.md`（render 合同补 `--color` 说明）。
- **Approach**：`compose_style(visual_style, *, mode=None, colors=None)`——`colors: dict[str, str]` 在 brief `color_palette` 之上做角色级合并（仅接受四个既定 role；非法 role、非 HEX 值、role 不在目标 palette、palette 缺失四种情形统一抛 `style_color_override_invalid`，见 Interface Contracts）。CLI `--color primary=#0B1220` 可重复，聚合为 dict。输出 JSON 中 color_palette 为合并后值。**palette 定型**：12 份顶层内置 brief 逐份人工补齐四角色的 HEX 锚点（保留散文用法说明，A6 口径）。设计体系.md 改写为"三层：护栏（通用设计规范）→ 风格角色默认值（brief 内 HEX 锚点，运行时提取）→ deck 锚点覆盖（`--color` / deck colors）"。
- **Technical design**（方向性）：合并即 `{**brief_palette, **{k: v for k, v in colors.items() if k in brief_palette}}` 前置 role 存在性校验（缺失即抛错，不静默过滤）；brief 无 palette 且 colors 非空时同抛错；确定性天然保持（纯函数）。
- **Test scenarios**：(1) 覆盖 primary 后输出 palette 的 primary 为新值、其余键不变；(2) 非法 role（如 `brand`）抛 `style_color_override_invalid`；(3) 非 HEX 值（如 `blue`）抛错；(4) 合法 role 但目标 brief 缺该键抛错（不静默）；(5) brief 无 color_palette 且传 colors 抛错（nil path）；(6) 不传 colors 时输出与改动前逐字节一致（快照断言）；(7) 同参数两次调用输出逐字节一致；(8) 定型后的 12 份内置 brief palette 四角色均含合法 HEX（提取校验）。
- **Verification**：单测 8 场景全绿（discover 真实执行）；`style render 麦肯锡咨询风 --color accent=#C0FF00` 输出可见覆盖生效。

### U7. brief JSON Schema + lint + 护栏旗标（R9）

- **Goal**：风格库内容质量从"QA 事后打回"部分前移为"生成/入库前机检"，并修复测试可发现性存量缺陷。
- **Requirements**：R9。
- **Dependencies**：无（U9 依赖本单元的 lint）。
- **Files**：`leo-ppt-generator/runtime/src/leo_ppt_generator/schemas/style-brief-v1.schema.json`（新建）、`leo-ppt-generator/scripts/lint_style_briefs.py`（新建）、`leo-ppt-generator/scripts/style-lint-baseline.txt`（新建，warning 白名单）、`leo-ppt-generator/runtime/src/leo_ppt_generator/templates.py`（`compose_style` 增加 `guardrail` 参数）、`leo-ppt-generator/runtime/src/leo_ppt_generator/cli.py`（`--guardrail` 旗标）、`leo-ppt-generator/tests/test_render_guardrail_block.py`（新建，**tests/ 顶层**）、`leo-ppt-generator/tests/{boundary,installer,upstream}/__init__.py`（新建，存量可发现性修复，KTD9）、`leo-ppt-generator/references/style-library.md`（lint 用法一句 + `--guardrail` 注入合同）、根 `AGENTS.md` 与 `CLAUDE.md`（lint 命令登记进仓库级检查清单）。
- **Approach**：schema 按 Interface Contracts 口径声明（散文含 HEX、layout_blueprints 可选）；lint 启动时 stdlib `json` 读 schema，required 键与 HEX pattern 从 schema 派生（KTD5 单真值源），脚本仅自实现数量子集校验；扫描 `references/styles/**/*.md` 提取 ```json 块，**结构缺失（必需键）为 error，HEX 缺失为 warning**，warning 落 `style-lint-baseline.txt` 白名单（文件头注明存量迁移 owner 与批次纪律：**新增文件不得进白名单**），error 为 0 才退出 0。`compose_style(..., guardrail=False)`：旗标开启时输出末尾追加护栏摘要（固定文案 + accent 提取行，无 HEX 整行省略，KTD6）；缺省输出不变。AGENTS.md/CLAUDE.md 仓库级检查清单各加一行 lint 命令（R9 归属）。
- **Execution note**：先跑 lint 全库收集存量偏差再定白名单；预期大量 reference 风格 palette 无 HEX 属 warning（渐进迁移已 Deferred），12 份内置在 U6 定型后应为 0 warning。
- **Test scenarios**：(1) 合法 brief fixture 通过；(2) 缺 `color_palette` 报 error；(3) palette 值无任何 HEX 报 warning 不影响退出码；(4) 白名单内 warning 不影响退出码、白名单外 error 退出非 0；(5) lint 的 required 键集合与 schema 文件派生结果一致（守恒断言，防双真值源漂移）；(6) `--guardrail` 输出含护栏摘要块、accent 无 HEX 的 brief 该行省略；(7) 缺省输出与改动前逐字节一致（快照断言）；(8) 旗标路径同输入两次运行逐字节一致；(9) `tests/` 三个存量子目录被 discover 真实收集（countTestCases 计数含存量 7 测试）。
- **Verification**：`python3 leo-ppt-generator/scripts/lint_style_briefs.py` 退出 0；单测全绿；`python3 -m unittest discover -s leo-ppt-generator/tests -p 'test_*.py'` 的 countTestCases ≥ 10（存量 7 + 新增，杜绝空转绿）；AGENTS.md/CLAUDE.md 登记可见。

### U8. P2 合同包：动效规范 + 断言标题 + 密度上限（R7）

- **Goal**：deck 级动效、断言式标题、信息密度三份缺失合同成文。
- **Requirements**：R7。
- **Dependencies**：U4（同文档新增节，避免编辑冲突与口径分叉）。
- **Files**：`leo-ppt-generator/references/styles/00_索引/通用设计规范.md`、`leo-ppt-generator/references/styles/06_论证模式/结论先行金字塔.md`（断言标题判据示例）、`leo-ppt-generator/references/visual-qa.md`。
- **Approach**：通用设计规范新增两节——**deck 级动效**：转场白名单（fade/morph）、总时长预算（如单页内动效 ≤1.5s、deck 级转场统一一种）、降级策略（导出静态/PDF 时动效语义等价）、图片式路线零内动效的交付披露句；**信息密度上限**：每页正文字数上限（中文，如 ≤80 字/页，实现期依版式 Schema 校量）与要素总数上限（要点 ≤6、模块 ≤4 与既有版式约束对齐）。断言标题：护栏一句（"标题必须是完整句断言，禁止话题词短语"）+ **visual-qa.md 判据行由本单元独占落地**（KTD8，多行业 E2 不再重复添加；连读稿 defer 已登记）。
- **Test scenarios**：`Test expectation: none — 合同文档`；行为面覆盖由 U10 的两个轻量 advise 用例承载（既有 21 用例无此面断言，A4 已诚实登记）。
- **Verification**：三份合同齐备且与 `12_版式库/01_常犯错误.md`、`版式内容Schema.md` 数值无矛盾；`rg -n "标题读作断言|标题必须是完整句断言" leo-ppt-generator/references/visual-qa.md` 判据行仅一处（KTD8 防双写机检）。

### U9. 趋势风格新增 + 明暗配对说明（R8）

- **Goal**：补中文市场趋势缺口与暗色系统化说明。
- **Requirements**：R8。
- **Dependencies**：U7（新 brief 须过 lint）、U1（图表条款引用）。
- **Files**：`leo-ppt-generator/references/styles/01_通用母版/艺术表现/迷幻国潮风.md`（新建）、`leo-ppt-generator/references/styles/01_通用母版/极简排版/暖调柔形风.md`（新建）、`leo-ppt-generator/references/styles/00_索引/视觉风格配对.md`（配对行 ×2）、`leo-ppt-generator/references/styles/00_索引/设计体系.md`（light/dark 配对机制节）、`leo-ppt-generator/references/style-library.md` 与 `00_索引/_INDEX.md`（计数与条目同步）。
- **Approach**：两份新 brief 按抽样核实的固定 schema 编写（type/style_name/…/reference 全键），palette 值沿用"散文用法说明 + 内嵌 HEX 锚点"库内惯例（A6，与 schema 口径一致），迷幻国潮 2.0 定位（东方意象 + 高饱和渐变 + 故宫红/琉璃色系）与暖调柔形（暖中性色 + 柔和形状 + 有机圆角）均来自 origin §一 趋势 2/8；配对表各加一行（迷幻国潮→矢量插画或复古海报、暖调柔形→暖光场景，实现期按 08 轴定位微调）。设计体系.md 增"明暗配对机制"节：同一风格 light/dark 由 palette 角色推导（背景/正文/强调互换 + 对比度复检 4.5:1），dark-deck 预设变体 defer 已登记。
- **Test scenarios**：两份新 brief 过 lint（0 error 0 warning——新文件不得进白名单）；`style render 迷幻国潮风` 可加载且含配对 rendering 段。
- **Verification**：lint 0 错 0 白名单新增；索引计数与实际一致。

### U10. 评测与验收接入（R10）

- **Goal**：护栏前移、断言标题与密度上限的行为面进入评测闭环，回归有可比基线。
- **Requirements**：R10。
- **Dependencies**：U1–U9 全部（回归基线要求其余单元已落地；**基线留档本身在 W1 开工前执行，见 Approach**）。
- **Files**：`leo-ppt-generator/evals/cases/style-render-guardrail-visible.yaml`（新建）、`leo-ppt-generator/evals/cases/assertion-headline-advisory.yaml`（新建）、`leo-ppt-generator/evals/cases/density-cap-advisory.yaml`（新建）、`leo-ppt-generator/evals/eval.yaml`（注册 3 个新用例）。
- **Approach**：**基线先行**：W1 开工前先跑一次 `skill-up run evals/eval.yaml` 全量并存档 JSON 报告与各 case 结论（基线路径记入 CHANGELOG），U10 的"无回归"以该存档为比对基准——否则模型驱动用例的偶发失败无法归因是本计划引入还是存量。三个新用例：(1) generate 路线触发 `style render --guardrail` 后输出含护栏摘要关键行（宽松子串匹配，涉模型能力处打 `model_gating` 标签）；(2)(3) 两个 max_turns=1 轻量 advise 用例——断言标题判据与密度上限在 advise 回复中可被引用（沿用既有 script-judge 双向自检模式，A4 覆盖缺口的最低成本补法）。
- **Test scenarios**：三个新用例首轮跑通或如实记录 FAIL 原因（恒定 FAIL 需 known-issues 记账，不静默）；基线报告存在且含 21 用例结论。
- **Verification**：`cd leo-ppt-generator && skill-up run evals/eval.yaml` 全量结果：对照基线 21 旧用例无回归 + 3 个新用例有明确结论（通过或记账）。

---

## Verification Contract

- **分层**：文档单元 → rg/find 机检 + 人工评审；runtime 单元（U6/U7）→ unittest；行为面（U10）→ skill-up 对照基线。
- **测试可发现性前置**（KTD9）：任何"单测全绿"结论前先确认 discover 真实收集——`python3 -m unittest discover -s leo-ppt-generator/tests -p 'test_*.py'` 后 countTestCases>0（存量 0 收集的缺陷由 U7 修复）。注：该命令在 AGENTS.md 中原为 evidence-first-writing 记录（其测试在 tests/ 顶层故可发现）；leo-ppt-generator 侧的可发现布局由本计划建立并登记。
- **命令**：
  - `python3 -m unittest discover -s leo-ppt-generator/tests -p 'test_*.py'`（含 countTestCases>0 前置检查）
  - `python3 leo-ppt-generator/scripts/lint_style_briefs.py`
  - `cd leo-ppt-generator && skill-up run evals/eval.yaml`（比对 W1 前基线存档）
  - `rg -n "data-journalism" leo-ppt-generator/references`
  - `find . -mindepth 2 -maxdepth 2 -name SKILL.md`、`git diff --check`
- **确定性回归**：U6 与 U7 各含"缺省调用（不传 `--color`/`--guardrail`）输出与改前逐字节一致"快照断言；旗标/覆盖路径断言"同输入两次运行逐字节一致"。保护 `style-library.md` 逐字节确定性合同。
- **回归红线**：四条硬约束与五字段控制面不动；任何 evals 判官红线不放宽。

## Definition of Done

- R1–R10 全部满足对应 Success Criteria；三波单元全部落地或明确记 defer 与 owner。
- 引用完整性、lint、单测（含可发现性）、评测四类机检证据留存（命令 + 结果记入 CHANGELOG 条目）。
- `设计体系.md` 宣称与实现一致（三层 token 表述 + 12 份内置 palette 定型完成）；麦肯锡更名指引在 style-library.md 可见。
- 多行业线协同项（dark-deck、--brand、程序化对比度、连读稿、user-colors 通道登记、visual-qa 判据行归属）在两技术方案与本计划 Deferred 三处口径一致。
- 改动前评测基线报告已存档且路径可追溯。

## Sources & Research

- **Origin**：`docs/leo-ppt-generator/reviews/style-review.md`（2026-08-29，本计划唯一需求来源；十档优化点 = 其 §0 矩阵，事实断言已 grep/diff 复核）。
- **交叉**：`docs/leo-ppt-generator/reviews/multi-industry-expert-review.md` §四/§五/§六（交叉验证点与边界划分）、`docs/leo-ppt-generator/tech-plans/multi-industry-optimization-tech-plan.md` D1/E2/批次 3（跨方案冲突三处，已逐字核实并在 KTD8/Interface Contracts/Deferred/U5 裁决）、`docs/leo-ppt-generator/reviews/optimization-review.md`（评测克制与恒定 FAIL 教训）、`docs/plans/2026-08-28-001-feat-leo-ppt-style-recommendation-plan.md`（样张双生验收场，趋势风格联动）。
- **源码/实况核实**（本计划方案审查 round 1 实测）：`runtime/src/leo_ppt_generator/styles.py`（存取层、顶层遮蔽、`_is_style_md`）、`runtime/src/leo_ppt_generator/templates.py`（轴 loader 范围、`compose_style` 转发、`_pairs` 逐行解析）、`evals/eval.yaml`（21 用例结构）、`python3 -m unittest discover -s leo-ppt-generator/tests` 实测 0 测试（子目录无 `__init__.py`）、全库 palette 散文实况（0/136 纯 HEX、accent 含 HEX 49/136）。
- **外部**：见 origin 文档调研来源节（WCAG 2.2、Slidesgo/SketchBubble/Envato 2026 趋势、assertion-evidence、Analyst Academy）；本计划未新增外部依赖。
