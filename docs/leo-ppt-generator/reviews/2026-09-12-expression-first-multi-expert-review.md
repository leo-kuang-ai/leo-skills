# 表达优先模板重构方案 · 多领域专家复审（2026-09-12）

审查对象：`docs/plans/2026-09-11-004-feat-leo-ppt-expression-first-plan.md`
修订基线：HEAD `710846e20a900e02bd5349629015d6e3bd441510`（dirty worktree；`leo-ppt-generator/` 子树干净）
被审文档摘要（SHA-256 前 16 位）：`5e598ea77d6be030`，90,345 字节，1,002 行
文档分类：`spec-unified-plan/v1` + `implementation-ready` → `unified-plan`
本轮变更策略：`report-only / default-review-report-only`——只产出findings，未修改被审方案

---

## 一、方法、分母与独立性

本次按"多领域专家 + 第一性原理 + 分而治之 + MECE + 逻辑层次 + 系统联动 + 双向钢人"的要求执行：

1. 编排者先建立**代码事实基线**（非抽查）：逐文件核对方案中引用的全部源码 hash、目录计数、catalog 指针、实体身份与关键行为分支，并对每个 finding 的关键断言再次读码复核（复核项见 findings 表"编排者复核"列）。
2. 计划尝试按 coherence（内部一致性）、feasibility（系统架构/可实施性）、adversarial（前提与决策证伪）、scope-guardian（抽象与复杂度收支）、product-lens（战略后果与交付替代路径）五种角色派发独立 worker；所有派发均因宿主容量返回 `429 Too Many Requests`，没有 worker 返回结构化 findings。本记录因此只包含主 Agent 的源码核对、角色化自审与双向钢人论证。
3. 主 Agent 按五轮顺序完成角色化审查：第一轮冻结源码/资产分母，第二轮按 unit 拆分依赖与 owner，第三轮做 MECE/traceability 检查，第四轮检查迁移、catalog、binding、lane 的系统联动，第五轮对关键决策做双向钢人论证。五轮均不是独立 worker 证据。

```text
cost-shape: profile=full(override=user「多个领域专家」) N=5 personas=[coherence, feasibility, adversarial, scope-guardian, product-lens] skipped_conditional=[security-lens:no-auth/PII/外呼API, design-lens:非UI/交互设计面] doc_bytes=88384 slices=full isolation=unknown
worker_dispatch_authorization: user-requested(personas) | capability_probe: generic worker available | worker_dispatch_capability: available-but-capacity-blocked | worker_context_isolation: unknown | worker_model_override: unsupported | worker_bounded_parallelism: supported | worker_dispatch_outcome: failed(429 Too Many Requests; 5/5 no return)
```

**独立性声明：** 本轮没有独立 worker 返回，`independent_review=partial/degraded`，不能称为五路独立专家评审。结论来自主 Agent 的源码证据、角色化自审和双向钢人论证；未运行实现测试、catalog 构建、真实导出与人工视觉验收，因此本记录只构成**文档层与代码事实层**的证据。

### 代码事实基线与方案的吻合度（编排者亲测）

| 核对项 | 方案声明 | 实测 | 结论 |
| --- | --- | --- | --- |
| catalog 指针 | `e483ed0d93736774ab3142848dbec997` | 同 | ✅ |
| registry 实体分母 | 565 = style 320 / axis 124 / layout 42 / brand 36 / theme 18 / template 15 / preset 8 / font 2 | 逐 kind 完全一致 | ✅ |
| axis 身份格式 | `builtin:axis:<slug>`，共 124 | 124 个全部匹配 | ✅ |
| component 实体 | 0 | `component.json` = 0，仅 chart-palettes/pool.json | ✅ |
| 13 个源码快照 hash | 逐文件列出 | 当前工作树逐项一致 | ✅ |
| 2 个文档快照 hash（PRD/003） | 逐文件列出 | 当前工作树逐项一致 | ✅ |
| 方案新增文件 | 标记"新增" | 11 个全部不存在（符合"待实施"） | ✅ |
| 关键行为断言 | v1 binding 保留读取、point 隐式回填、causal→system、同代原地刷新、canonical-rebuild 自扫 | 逐条在代码中确认存在 | ✅ |

---

## 二、结论

**方案方向成立，旧复审提出的主要迁移 P1 已在当前方案中落位；本轮新增的 N1–N5 也已完成方案级修订，下一步只需由代码实现和运行证据验证。当前不能把它写成独立专家通过，也不能把仍在实施前的证据门写成已通过。**

用用户框架概括：

- **第一性原理**：方案的根问题是"页内内容关系能否被看见"，落脚点是表达合同 + 关系统一资格，方向与用户原话（"文不如图，图不如表"）一致，未把"换模板/换色"当答案。✅
- **分而治之**：U1–U13 每个单元都有 Goal / Requirements / Dependencies / Files / Approach / Test / Verification，依赖图为**有向无环**（编排者按各单元 Dependencies 重建校验）。✅
- **MECE**：当前方案已覆盖 executable guides、`evals/` 和仓库级文档根，并收敛重复能力真值；仍需为共享文件指定单一阶段写入 owner。⚠️
- **逻辑层次**：需求→KTD→单元→验证→DoD 的层级链完整；缺陷是少数 KTD 未回挂到单元 Requirements（F25）与指标标签错位（F28）。⚠️
- **系统联动**：当前方案已补入 U12 旧链基线、U13→U8 时序和 U11 delivery convergence；这些是方案约束，仍需后续实现和运行证据验证。✅（文档层）
- **双向钢人**：见第五节（结论是保留方向、补证据与基线，不是回退方案）。

---

## 三、历史 findings 的当前状态

下表先于历史 finding 明确当前状态。F1–F9、F12、F14、F16、F18–F24 的核心建议已在当前方案中落位；它们仍需要实施验证，但不能再作为“当前方案未修复”的问题重复计数。F10/F11 的 hash 漂移已由方案重算关闭，F17 的独立性矛盾已由本记录和方案统一为 `partial/degraded`。F13、F15、F25–F29、F30、F32–F35 属于待实施或低置信一致性项，保留在后表供执行前核对。

| 状态 | Finding | 当前判断 |
| --- | --- | --- |
| 已落位，待实现验证 | F1–F9、F12、F14、F16、F18–F24、F31 | 当前方案已提供位置合同、完整 closure roots、U12 基线、U13→U8 时序、delivery convergence、relation oracle、派生能力视图、双层 binding、proposal 回流和覆盖测量；不能据此声称 runtime 已实现。 |
| 已关闭 | F10、F11、F17 | 方案已采用当前 hash；本记录已统一独立性为 `partial/degraded`，没有独立 worker 返回。 |
| 仍待收口 | F13、F15、F25–F30、F32–F35 | 这些项目需要在实施前补齐位置/产物参数、traceability、owner 顺序、回滚语义、证据载体和视觉校准。 |

## 四、本轮 findings 与修订状态

| # | 严重度 | 当前问题 | 代码/方案证据 | 建议收口 |
| --- | --- | --- | --- | --- |
| **N1** | P1 | **generation 与 capability evidence 曾形成循环依赖。** | 旧版 KTD9/U8 同时让 generation 和 evidence 互相决定。 | **已修订：** `asset_generation → evidence_set_digest → catalog_generation` 单向计算；待实现验证无自引用。 |
| **N2** | P1 | **表达选择摘要曾被 catalog generation 牵连。** | 旧版 KTD5 把 catalog generation 放入 expression identity。 | **已修订：** expression identity 改用 regime/policy revision；catalog generation 仅进入 execution/materialization binding。 |
| **N3** | P1 | **image-only layout 曾缺少合法执行配对身份。** | 当前 42 个 layout 中 27 个仅支持 image，15 个模板均为 HTML。 | **已修订：** image lane 允许 `template_identity: null`，改用 recipe/layout capability identity；待 runtime probe 验证。 |
| **N4** | P1 | **逐路径 CAS 曾缺少并发停写边界。** | 多入口可在 CAS 间隙读写模板库。 | **已修订：** publish 前进入 maintenance 并取得全局锁；外部漂移只返回 blocked，不覆盖外部修改。 |
| **N5** | P2 | **scorecard 曾无法表达当前失败与失效。** | 现有 `quality_metrics.py` 仍使用旧状态集合。 | **已修订：** 新增 `deck_quality` 四通道和 `failed/stale/error`，按当前 receipt 计算；待 schema/回归实现。 |

以下历史 findings 仅保留为证据索引，状态见第三节；不要把其“问题”列直接解释为当前方案仍未修复。

下表保留历史证据和定位，供实施者逐项核对；不要把表中“问题”列直接解释为当前方案仍未修复。当前待收口项以第七节为准。

严重度按"不修会怎样"定级：P1 = 会让某道验收门给出错误结论或无法执行；P2 = 会造成实现分歧、重复真值或证据链断裂；P3 = 可机器修复的一致性瑕疵。conf 为合并后锚点；"复核"列为编排者是否亲自验证。

### 领域 A：结构/位置合同（U7）

| # | 严重度 | conf | 问题 | 证据（方案 + 代码事实） | 建议落点 | 来源 | 复核 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **F1** | P1 | 100 | **executable 侧 51 个指南实体无位置合同。** 迁移表把 `axes/structure`、`axes/rendering` 移入 `canonical/executable/layouts/guides/`、`renderers/guides/`，但 `axis-guide` 行只声明 semantic 三个实体根，`layout`/`renderer` 行又明确"exclude `guides/` 子树"，收尾规则还规定实体位的 `guides` 目录被拒绝——这 51 个资产既解析不出 kind，也无法进入 catalog 与对账。 | 方案："`axis-guide` \| `canonical/semantic/expressions/guides/<family>/<slug>/`, `canonical/semantic/argument-modes/<slug>/`, `canonical/semantic/page-types/<slug>/`"；"directions named `guides` … in an entity position are rejected"。代码实测：axes/structure=8、axes/rendering=43，合计 51；axis 总计 124。 | asset-locations-v2 表补 `axis-guide` 的 executable 两个实体根与模式；或显式新增 `layout-guide`/`renderer-guide` kind | feasibility(P1/100) + coherence(P2/75) | ✅ 亲自点数 |
| **F3** | P1 | 75 | **`leo-ppt-generator/docs` 是不存在的扫描根。** U7 的 closure 调用合同把它列为 activity doc 根，并禁止"未扫描 docs/ 得到零命中"；但该目录在仓库中不存在（仓库级 `docs/` 有 131 个文件）。执行时只能二选一：脚本报错（零错误门过不去）或空扫（重新落入被禁模式）。 | 方案："--scan-root docs/plans --scan-root docs/prd --scan-root leo-ppt-generator/docs"；"本包 `docs/`"。实测：`ls -d leo-ppt-generator/docs` → No such file or directory。 | 把该 root 改指 `docs/leo-ppt-generator`，或声明"缺失 scan root 必须显式失败"并在账本登记为待创建 | coherence(P1/75)+feasibility(P2/75)+adversarial(P2/75) | ✅ |
| **F2** | P1 | 100 | **closure 扫描根漏 `leo-ppt-generator/evals/`。** 该目录含旧协议与旧路径材料（`fixtures/quality-replay-v1/content-pack.json` 为 `schema_version: 1`；6 个文件直写 `canonical/...` 路径），而 U6/U9 要求重建/删除这些 fixture、账本又要求以 `test-fixture` 分类登记。不扫它，则 fixture 迁移完全未做也能得到 `active_legacy_hits=0`。 | 方案调用合同无 evals root；"旧协议 fixture 删除或仅作一次性迁移输入"；"逐文件记录处置类别：… `test-fixture` …"。实测：evals 下 6 个文件命中 `canonical/`。 | 调用合同加入 `--scan-root leo-ppt-generator/evals`，或在 `--exclude` 中逐目录显式登记并说明理由 | feasibility(P1/100) | ✅ 亲自计数 |
| **F13** | P2 | 100 | **位置表缺 `ornament`（与 `qa-profile`）行。** 表的自述是"唯一声明 kind/路径/实体文件"，同节的匹配清单却包含 `canonical/visual/ornaments/*/manifest.json`；resolver 仍把 `ornament`、`qa-profile` 当一等 kind（`ornament-manifest-v1.schema.json`、`KIND_ENTITY_FILE`），而表的收尾规则是"Unknown kinds … rejected"。 | 方案同节三处冲突；代码：`asset_resolver.py:34-43` 含 `"ornament": "manifest.json"`、`"qa-profile": "profile.json"`。 | 补 `ornament` 行；`qa-profile` 明确继续由 `governance/rules/` 承载或声明退役 | coherence(P2/100)+feasibility(P3/50) | ✅ |

### 领域 B：时序与基线（U8/U11/U6）——本轮的核心系统发现

| # | 严重度 | conf | 问题 | 证据 | 建议落点 | 来源 | 复核 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **F4** | P1 | 75 | **U8 的构建/验证门在时序上无法在 U11 之前成立。** U8 出口要求"从新 canonical 构建 registry/views 并与 offline inventory 一致"，但资产要到 U11 才迁移，而 U11 依赖 U8。实施者只能绕过"唯一迁移入口"预搭目录，或把迁移倒序塞进 U8，使 U11"只按冻结账本一次性迁移"的合同形同虚设。 | 方案 U8 步骤 3 与 Verification；"**Dependencies:** U7, U8, U9"（U11）；"4. 一次性迁移源资产（U11）：… 重建 catalog。" | 依赖顺序改为"迁移 apply → 在已迁移树上执行 U8 构建与验证"，或让 U8 的构建门以 U11 verify 报告为证据来源 | adversarial(P1/75) | ✅ 编排者独立复现 |
| **F5** | P1 | 75 | **隔离 checkout 的验证结果没有回到交付仓库的路径。** apply/cleanup 必须在隔离 clean checkout 执行，快照与身份映射取自共享工作树；但没有任何单元规定"隔离树验证通过"如何成为目标仓库的交付状态，也没有规定并行任务的未提交改动如何进入迁移后的树。结果是结构重构可被判"完成"，而实际仓库仍是旧链或半迁移。 | 方案："`apply` 和 `cleanup` 必须在由 preview 记录的隔离 clean checkout 执行"；"全量资产/消费者对账通过，新链隔离安装…才可称结构重构完成"；"现有工作树含其他任务修改"。 | U11 增加"交付收敛"步骤：隔离树结果以可复核提交落到目标仓库，并对目标仓库重跑 closure 与 catalog 一致性检查 | adversarial(P1/75) | ✅ |
| **F6** | P1 | 75 | **视觉门的"旧链配对基线"无人产出、且材料在清理后不可再生。** 视觉门要求"至少两维优于旧链"，需要同一冻结材料下的旧链导出；而唯一做前后对照的步骤被明确限定为"只核对事实/几何，不作为视觉证据"，旧 pack/binding/reader 又在同一次切换中被删除。专项只能长期停在 not_run，或降级为"新旧不可比"。 | 方案："≥3 册…至少两维优于旧链"；"该项只核对事实、几何、主题和实际资产内容完整…不把它当作新表达视觉通过证据"；"迁移前旧输出只作为质量对照样本，不要求新 runtime 运行旧协议"。 | 在 U11 cleanup **之前**登记"旧链配对基线"交付项（固定材料 + 重构前 runtime 导出 + hash 入账 + 四维评分） | adversarial(P1/75)+product-lens(P2/75) | ✅ |
| **F7** | P1 | 75 | **"U11 先于写入新表达资产"的排序把唯一用户可见的改善串行化在整条结构重构之后。** U11 是 565 实体搬迁 + 124 次更名 + 协议替换 + 消费者切换 + 旧实现删除的一次性批次；任何一环拖延，AE1–AE8 回放、双 lane 导出、视觉评分全部无证据。而新资产完全可以在现路径下先创建、由 U11 账本按"新增资产"一并搬迁（账本已区分盘点分母与新增资产）。 | 方案："U11 必须在 U1、U2 开始写入新表达/能力资产前完成"；"盘点分母与新增资产分开"。 | 把约束收窄为"新 kind 必须先被新 reader 认识（U8）"，允许 U1/U2 先在现有 canonical 创建并登记为账本新增项 | product-lens(P1/75)+scope-guardian(P2/75) | ✅ |

### 领域 C：能力模型与证据强度（KTD2/KTD6/KTD9）

| # | 严重度 | conf | 问题 | 证据 | 建议落点 | 来源 | 复核 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **F8** | P1 | 75 | **关系硬资格只靠人工声明，无逐项最小可执行证据。** KTD6 把关系覆盖定为硬资格，但自动检查只有 schema/lint 的结构闭合（slot→field→anchor）；"登记真实支持"由实现方自证。叠加"有解覆盖 ≥90%"的门，最省事的做法就是扩大声明——资格门名义通过、页面仍不对齐，正是用户投诉的失败模式。 | 方案："为首批矩阵的…资产登记真实支持；未登记不获得自动池资格"；"有解覆盖≥90%"。 | 每个 relation capability 附一条最小可执行证据（能渲染出该关系编码的 probe/fixture + 反例），无证据的声明不得进自动池 | adversarial(P1/75) | ✅ |
| **F31** | P2 | 75 | **AE4 类页面（关系图 + 关键数据）的可承载基础资产未测量，组件池为 0。** 现有 15 个模板中只有 2 个携带 `chart_svg` 字段（`body-basic`、`kpi-stat`）；U5 的测试却把"生成包含两个既有承载区的提案"写成预期结果。若前提不成立，这类页面（恰是用户抱怨的类型）只能得到不适配报告。 | 方案 U5："Covers AE4. 关系图＋关键数据缺口生成包含两个既有承载区的任务提案"；"当前组件实体为 0"。实测：`chart_svg` 仅见 2/15 模板。 | 切换前对全部 base 资产做一次 patch 覆盖清单（哪些表达组合可承载），结果入 U7 账本 | adversarial(P2/50→编排者复核提升) | ✅ 亲自统计 |
| **F14** | P2 | 100 | **KTD9 的 composition 引用清单漏 renderer，与 U10 及设计步骤互相矛盾。** 同一合同内三处表述不一致，directly 决定"缺 renderer 依赖即不合格"这条检查能否成立。 | KTD9："composition 只引用表达、layout、template、可选 component 与 QA 规则"；U10："composition 引用 expression、layout、template 和实际所需的 component/renderer"；设计步骤 2："composition 展平为对 expression/layout/template/可选 component/renderer 的引用"。 | 以 KTD9 补 `renderer` 为准统一三处 | coherence(P2/100) | ✅ 亲自比对 |
| **F12** | P2 | 100 | **KTD13 称 `catalog_missing`/`catalog_invalid` 为"现有错误码"，实际不存在。** 现有只有 `stale_catalog`（`StaleCatalogError`）与 `library_missing`；缺失指针当前走 `_scan_canonical()` 回退成功。按"保持现有"实现的执行者会无码可保，可能把新语义并入 `library_missing`，破坏"缺失=只读状态 / 损坏=拒绝"的二分。 | 方案 KTD13 原文；代码：全仓 `grep catalog_missing\|catalog_invalid` 仅命中方案自身；`reason_code="stale_catalog"`、`LibraryMissingError`。 | 改为"新增 `catalog_missing`/`catalog_invalid`，保留唯一既有码 `stale_catalog`；`library_missing` 仅指库根缺失" | feasibility(P2/100)+coherence(P2/75) | ✅ |
| **F19** | P2 | 75 | **新增 `expression.json` 资产 kind 与既有页型真值源重复。** `governance/rules/page-type-regime-v1.json` 已是 `page_intent` 与 `lint_page_type_regime.py` 的真值源，含 comparison/trend/process/system/statement 与逐项 `semantic_requirements`；再建一套 expression 枚举 + schema + catalog 视图 + revision 钉住，等于同一枚举两条演化路径。 | 方案 Interface Contracts"表达定义（新增）"；实测 regime 文件含上述枚举与 `semantic_requirements`。 | 表达定义落在 `governance/rules/`（扩展 regime 或同目录规则），由现有 lint 一并校验，不新增资产 kind/schema/view | scope-guardian(P2/75) | ✅ |
| **F20** | P2 | 75 | **模板级 `expression_bindings` 引入第三份能力真值。** layout 的 `structure`（`reading_order`/`groups[].relation`/`encodings`，已由 `structure_fingerprint` 指纹化）与 template `input_fields`/`slot_bindings` 已在描述同一件事，且 builder 已用 `derive_structure_admission()` 从结构指纹 + `renderer_support` 派生准入（注释明确"不另存手写准入名单"）。再加一层手写映射，三处任一处漂移都会让"未登记不获资格"与既有准入视图分叉。 | 方案 KTD2/U2；代码：`layout_selection.structure_fingerprint`、`capability_manifest.derive_structure_admission`（L90-108）。 | 只扩展 layout.structure 承载关系/编码能力，由配对模板继承并派生能力视图，删去模板级 `expression_bindings` | scope-guardian(P2/75) | ✅ |
| **F21** | P2 | 75 | **新增 `renderer.json` 与既有 `renderer_support` 双声明。** 每个 layout 的 `renderer_support` 已按 lane 声明实际支持（`render:html`→template id，image→构图说明或 null），并在 projection/selection/render 多处被消费；方案自己也要求"可用性由探针核实"。再挂一个必须被探针复核的资产 kind，等于让"某 lane 可用"有两个作者来源。 | 方案"renderer 描述（新增）"；代码：`layout_selection.py:113,464,503`、`content_projection.py:243-247`、`capability_manifest.py:107`。 | 由 `renderer_support` + runtime lane 探针直接生成 lane-capabilities 视图，不新增人工编写的 renderer 资产 | scope-guardian(P2/75) | ✅ |
| **F9** | P1 | 75 | **composition 资产层相对既有配对是"命名 + 打包"，却成为双 lane 交付的前置。** 组合的全部内容（表达+layout+template+可选 component+qa_profile）在 15 模板、0 组件的库中等价于"manifest 已有配对 + 一项表达"；方案亦声明组合不提供独立评分或推荐路径、需额外去重规则。代价是新 kind + schema + `examples/` + index 视图 + binding 三字段 + 整个 U10，而 U4（双 lane 物化）声明依赖 U10。 | 方案 KTD9、U10、Interface Contracts"组合方案（新增）"；"`builtin:layout:p25-spec-table` + `builtin:template:spec-table`…这一配对来自当前 manifest"。 | 组合改为由既有配对 + 表达定义 + 可选 component/qa_profile 派生的 catalog 视图；binding 引用取自视图（无则 `null`） | scope-guardian(P1/75) | ✅ |

### 领域 D：语义与验收口径

| # | 严重度 | conf | 问题 | 证据 | 建议落点 | 来源 | 复核 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **F16** | P2 | 75 | **U1 的 AE2 用例要求 `independent`，但该关系不在任何枚举/编码定义中。** Assumptions 的首批关系编码（比较/趋势/流程/因果/证据/KPI/表格/陈述/列表）与 KTD15 的最小编码（comparison/trend/process/causal）都不含并列/independent，而 KTD12 要求未声明 relation 一律 `expression_incomplete`。同一合同下 independent 既缺依据又被要求可用。 | 方案 Assumptions 与 KTD15、U1 测试场景三处；"非法边或未知关系被拒绝"。 | 在 Assumptions 首批枚举或 KTD15 中显式加入并列关系及其可验证编码 | coherence(P2/75) | ✅ |
| **F15** | P2 | 75 | **迁移四阶段合同的中间产物路径未定义。** `apply` 必填 `--plan`、`cleanup` 必填 `--delete-allowlist`，作用域枚举也把 plan/report/allowlist 视为三种产物，但 `preview` 只声明 `--report` 一个输出。 | 方案迁移命令合同四行；"生成逐文件计划、目标 hash 预期、`delete_allowlist` 及其 `allowlist_sha256`"。 | preview 明确 plan/allowlist 的落盘参数（`--out-plan`/`--out-allowlist`），或声明 report 即 plan 且 allowlist 为内嵌字段 | feasibility(P2/75) | ✅ 亲自比对四行 |
| **F17** | P2 | 75 | **独立性披露自相矛盾。** 一处称"独立 worker 和独立文档审查本轮未运行…不能称独立专家评审"，另两处称"runtime reviewer 返回了完整覆盖报告"且 `independent_review: partial`。批准者无法判断实际获得多少独立复核。 | 方案 Appendix 两段 + 文末状态段。 | 统一口径：说明"本轮"各指哪一轮、runtime reviewer 是否独立派发；让 Appendix 与 `review_status` 取自同一事实 | coherence(P2/75) | ✅ |
| **F18** | P2 | 75 | **image lane 无法证明承载同一表达。** image 侧只把结构/required text/来源投影成 recipe prompt，文字与关系保真留给成品 QA；因此 digest 相等只证明两 lane **输入**相同，而 KTD4/Interface Contracts/DoD 却把"同一有效绑定、漂移 fail closed"写成两 lane 的共同保证。 | 方案："image 只把确定性结构、required text 和来源要求投影给既定 recipe，文字保真仍以成品 QA 为准" vs "HTML、image、预览、QA 和 receipt 使用同一有效表达绑定…均 fail closed"。 | 按 lane 限定表述（输入绑定一致 + image 成品保真由 QA 判定），并为 image 增加可核验的成品检查项与失败码 | adversarial(P2/75) | ✅ |
| **F10** | P2 | 100 | **`capability_manifest.py` 快照 hash 已漂移。** 方案引 `94f46e24556b8fca`，HEAD 实为 `e808f4e19a32d8b2`；前者是上一提交（7f45612）的版本，HEAD 提交 6e6a5ce 改动了该文件——正是"U11 发布前必须修正同代原地刷新分支"这条硬前置的事实依据。**结论经复核仍成立**（原地刷新分支确实存在），但证据链已断。 | 方案 L925；`git show 7f45612:…` = 94f46e24…，`git show HEAD:…` = e808f4e1…。 | 重算替换该行 hash；或标注快照提交并补记重读结果 | coherence/feasibility/adversarial（三方）| ✅ |
| **F11** | P2 | 75 | **PRD 与 003 计划两个文档 hash 均不匹配。** 方案 Sources 表引 `667535df7fe85e72`（PRD）与 `5b2128afa47c2dbe`（003 计划），实际为 `faf33146f837bb45` 与 `4ff65f52c595a857`（两者在 HEAD 上均未修改）。 | 方案 Sources and Limitations 表；`shasum -a 256` 实测两个文件。 | 重算两行 hash；若取自更早快照，注明不可复现 | adversarial(残留)+编排者 | ✅ 亲自复算 |

### 领域 E：抽象收支与交付路径

| # | 严重度 | conf | 问题 | 证据 | 建议落点 | 来源 | 复核 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **F22** | P2 | 75 | **一次性迁移工具链超出单次切换所需。** 未发布、不需兼容、迁移只发生一次，却要新增 closure schema、legacy-signatures 规则、专用扫描脚本与专用测试，并把三开关迁移脚本改造为四子命令 + 4 个 expected-sha + 7 类失败码 + plan/report/allowlist 的 sha 链；迁移完成后这些工件没有第二个消费者，而 closure 门还在关键路径上。 | 方案 U7 Files、迁移命令合同、U11 Verification。 | 保留现有入口与单一账本，补源摘要期望与精确 allowlist；旧路径清零用普通检索 + 分类账本证明 | scope-guardian(P2/75) | ✅ |
| **F23** | P2 | 75 | **表达合同的"书写面"没有交付物。** 上游 Agent 必须在母版阶段写出关系最小编码、焦点与阅读顺序，但没有任何单元负责把这一书写面落到母版文档/SKILL/prompt/示例，也没有对"内容其实是对比、声明却是 statement"的不一致给出诊断。书写成本高时最省力策略就是最小声明，页面退回弱表达而机器门全过。 | 方案："新表达合同应在母版确认时形成而非生成后猜测"；`page_expression` 语义"由上游 Agent 在母版确认范围内产生"。 | U1 一并交付母版书写面（`references/deck-master.md` 表达式语法 + 示例 + 委托指引），U1/U3 增加"结构与声明不一致"的可诊断提示 | product-lens(P2/75) | ✅ |
| **F24** | P2 | 75 | **任务内提案的缺口信号无回流路径。** 提案本身是"没有合格共享资产"的真实需求证据，方案要求它冻结进 run、进 receipt 与 disclosure，却规定不自动晋升 canonical，也没有任何单元把缺口回收成新的 layout/composition 候选。同一页型会在后续 run 继续走提案或不适配，专项不产生复利。 | 方案："不将一次新布局自动晋升为共享模板"；"任务内提案随 run 生命周期保存或按规则清理"。 | 增加回流规则与 owner：提案缺口按类型/次数汇总为可审计的能力缺口证据，交既有 curation 流程复核（仍不自动写 canonical） | product-lens(P2/75) | ✅ |

### P3（机器可修复的一致性瑕疵）

| # | 问题 | 证据 | 来源 |
| --- | --- | --- | --- |
| F25 | KTD12（自带 U1/U4/U8/U11 指派）、KTD14（U5）、KTD16（U6）未出现在任何单元的 `Requirements:` 行 | U1/U5/U6/U8/U11 的 Requirements 行 vs 闭环映射表 | coherence(P3/75) |
| F26 | 硬验收项 6 的分类清单只有 5 类，漏 `plan-control`（U7 为 6 类） | 硬验收项 6 vs U7 账本分类枚举 | coherence(P3/75) |
| F27 | U1 Files 的 `page-expression-v1.schema.json`、U5 的 `layout-proposal-v1.schema.json` 未标"新增"（Interface Contracts 已标） | U1/U5 Files 行 | coherence(P3/75) |
| F28 | 切换顺序第 6 步标签"（U1–U6）"却含 U10 的组合资产，且 U10 在依赖图里排在 U4 之前 | 开发期一次性切换顺序步骤 6 + 依赖图 | coherence(P3/75) |
| F29 | 外部需求 ID 写法不一致：全文 `R75`（4 处）vs `R-85`/`R-77`/`R-85b` | KTD14/U5/Interface Contracts | coherence(P3/75) |

### FYI（advisory，不构成决策项）

- **F30**（conf 50）：R75 容量提案与 U5 task-local 提案被声明为不同 owner，但同一容量超限页面上没有规定谁先跑、谁的结果进 receipt 与披露；U5 要求 `content_immutable: true`，R75 的可行路径之一恰是"用户确认的内容减法"。
- **F32**（conf 50）：`--library-rollback` 保留后的回切目标可用性未定义——若旧代目录被 cleanup 删除，回切目标与历史 receipt 的可核验性完全依赖各 run 自身快照字节。
- **F33**（conf 50）：用户库（无 catalog）走"按新规则只读扫描即推荐"还是"`catalog_missing` 只读拒绝"，两处表述给出不同答案（U8 步骤 1 vs 切换顺序步骤 3）。
- **F34**：R-85 replay 门的证据载体未验证——现有回放 fixture 只有 2 页（`quality-replay-v1`），而门要求 30 格 / ≥60 页 / 6 deck；`skill-up` 用例目前是行为级用例，能否承载逐页 30 格证据尚未验证。
- **F35**：四维视觉 rubric 首次执行没有校准集或对照记录，"≥4/5、两维优于旧链"缺少评分者间一致性的锚定证据。

---

## 五、MECE、层次与系统的交叉检查（编排者视角）

**覆盖（MECE）**：当前 U1–U13 已覆盖 executable 指南、`evals/` 和仓库级 `docs/leo-ppt-generator`；这些曾经的漏洞已转为“待实现验证”。当前仍需关注共享文件的写入 owner，以及验证工件是否能承载方案要求的逐页证据。

**共享文件的写入次序**：`capability_manifest.py` 被 U2/U8/U9/U10 四个单元同时列为 Files；`content_projection.py`（U1/U3/U4/U10）、`asset_resolver.py`（U5/U8/U10）、`lint_template_contract.py`（U2/U10）同理。依赖链保证了顺序可行，但方案未声明"同一文件在同一阶段只能有一个写入 owner"，多单元并行开发时会出现同文件语义漂移。

**层次**：U8 的 Verification 里包含"活动入口不再包含旧 reader 或兼容映射"——这是 U9 的交付物；单元的完成信号越界引用了下游单元的结果，会让 U8 单独无法收口（建议改为"resolver/builder 层不再保留旧 reader"）。

**系统联动（本轮头号发现）**：F4 + F5 + F6 是同一个结构洞——方案把验证分成"切换前（旧链）"与"切换后（新链）"，却没有定义**必须在切换前捕获、此后不可再生的基线**：旧链视觉对照样本、隔离树到交付树的收敛步骤、以及 U8 构建门在真实迁移树上的执行时点。三者任一缺失，都会让某个门给出"看起来通过"或"永久未验证"的结论。

---

## 六、双向钢人论证（Steel-man，逐项给出裁决）

### 5.1 "结构重构先于表达资产写入"（F7）

- **支持方（最强论证）**：新 kind（expression/composition/renderer）必须先被新 reader 认识，否则写进去的资产既不被发现也不被校验；先切协议再写新资产，可避免同一批资产被迁移两次、避免作者在旧路径下二次返工；且账本要求"逐项 hash 与依赖核对"，在迁移窗口内写入的新文件会让分母漂移，破坏 KTD11 的可重放性。
- **反对方（最强论证）**：真实约束只是"新 kind 可被解析"，那由 **U8** 决定，而不是 U11 的全库搬迁；把表达专项押在全库搬迁之后，等于让唯一与用户抱怨直接相关的交付（AE1–AE8、双 lane、视觉评分）排在最重、最不可逆、且失败恢复只有 Git 的一步之后；账本已具备"新增资产"分类，先写后搬在工程上完全可行。
- **裁决**：反对方成立，但支持方的账本可重放顾虑必须保留。**建议的收口**：把约束改写为"新 kind 写入须在 U8（协议解析）之后"，并在 U7 账本中为新资产单列"新增项"以便 U11 一并搬迁。这样既保住协议先行，又把用户可见改善移出关键路径。

### 5.2 声明式能力模型（KTD2/KTD9/KTD6，对应 F8/F19/F20/F21）

- **支持方**：模板"能否承载某种关系"无法从 HTML 自动推断，声明是唯一可审计、可版本化、可 lint 的来源；显式声明让库在不改代码的前提下扩容，并让"未登记即不获资格"成为可执行的硬门。
- **反对方**：系统已有派生真值——`structure_fingerprint` 指纹化的 `structure` 声明 + `renderer_support` 已能派生准入（代码注释明确"不另存手写准入名单"）。再叠一层手写映射，是把同一事实写成三份；更关键的是，声明自身没有证据约束——叠加 ≥90% 有解覆盖门后，扩大声明是成本最低的通过策略，而这正是用户投诉的失败模式（"套了模板但没表达关系"）。
- **裁决**：双方各对一半。**保留一处声明（layout.structure），其余全部派生；并为每条关系声明附加一条最小可执行证据（probe/fixture + 反例），无证据声明不得进自动池。** 这同时关闭 F8、F19、F20、F21。

### 5.3 开发期一次性切换、无兼容窗口（KTD8）

- **支持方**：用户明确否决向下兼容；未发布系统保留双 reader/writer 的成本高于收益，且兼容窗口会把旧协议固化进新资产；一次性切换让"旧路径清零"成为可验证的硬门（closure = 0 命中），而不是无限期的"暂时兼容"。
- **反对方**：一次性批次把 565 实体、124 次更名、协议、消费者与删除绑在一起，失败恢复只有备份与 Git；且验证发生在隔离树，交付树可能与之分叉；视觉对照样本会随旧链一同删除。
- **裁决**：**切换本身成立，不因风险回退**——但反对方指出的三个缺口必须补上，否则"完成"的定义不成立：交付收敛步骤（F5）、旧链配对基线（F6）、以及 closure 扫描范围修正（F1/F2/F3）。换言之，不是加兼容窗口，而是加**切换前基线捕获**。

### 5.4 关系硬资格 + ≥90% 有解覆盖（KTD6 / R-85 门）

- **支持方**：硬资格正是用户诉求的直译——不把内容硬塞进不合适的模板；覆盖率下降是"库能力不足"的诚实信号，方案已用有解/无解独立分母报告，并禁止把拒答事后改标域外。
- **反对方**：在 15 模板、0 组件、2 个模板带 `chart_svg` 的现状下，严格编码很可能让"无解"从异常变成常态——用户抱怨的"页面难看"会变成"没有页面"，而 R-85 的 ≥90% 门会同时把责任人推向"扩大声明"（见 F8）。
- **裁决**：保留硬资格，但**先测量再冻结**：在切换前用真实/等价 fixture 跑一遍"每类关系的可承载资产覆盖清单"（F31），据此决定 proposal 与 report 的默认策略，并把该测量结果作为 KTD6 是否足够、是否需要优先补齐资产或组件的判断依据。

---

## 七、实施前收口清单

**第一优先（进入 `spec-work` 前）**

1. N1–N5：先闭合 generation/evidence DAG、页级失效边界、image-only pairing、publish maintenance lock/CAS 恢复语义，以及 scorecard 的失败/失效状态。
2. F13：最终确认 `ornament` 的实体位置与 `qa-profile` 的非实体处置，并在 lint 中锁定。
3. F15：为迁移 plan、report、allowlist 规定唯一落盘字段和命令参数，避免实现者自行解释。
4. F25–F29：补齐 KTD→unit、验收分类、`新增` 标记、切换顺序和外部需求 ID 的机械一致性。

**第二优先（实施中必须有证据）**

5. F30：明确 R75 容量菜单与 U5 proposal 的先后、receipt 归属和用户确认边界。
6. F32–F35：在真实实施前固定 rollback 目标、用户库无 catalog 语义、R-85 replay 证据载体和视觉评分校准集。
7. 共享文件 owner：为 `capability_manifest.py`、`content_projection.py`、`asset_resolver.py`、`lint_template_contract.py` 指定单一阶段写入 owner，其他 unit 只消费其输出。
8. U8 Verification：只验证 resolver/builder 层的 v2 行为；活动消费者清零属于 U9/U11，避免 unit 完成条件越界。

F1–F9、F12、F14、F16、F18–F24、F31 不再列为待改文档项；它们的关闭条件已进入当前方案，剩余工作是实现、运行和证据采集。

---

## 八、验证结果、限制与未验证项

本轮已执行的只读检查：

- `source leo-ppt-generator/runtime/.venv/bin/activate && python scripts/lint_page_type_regime.py`：`0 ERROR`。
- 同一虚拟环境运行 `python -m unittest discover -s tests -p 'test_page_intent_routing.py'`：10 tests，`OK`。
- `python3 scripts/lint_layout_grid.py`：errors 0。
- `python3 scripts/lint_style_briefs.py`：320 briefs，errors 0，warnings 0。
- `git diff --check`：通过。

用户此前给出的 `leo-ppt-style-index-workspace/.venv` 路径在当前工作区不存在；验证使用项目实际存在的 `leo-ppt-generator/runtime/.venv`，没有创建兼容路径。

- 本轮仍是**文档层 + 代码事实层**复审：未运行完整实现测试、catalog 构建、故障注入、真实 HTML/image 导出、人工视觉评分或用例回放；上述 focused lint/test 只证明对应现有检查通过。
- 所有"未实施"结论以 2026-09-12 的 dirty worktree 为基；本记录生成后方案仅作了独立性声明和 QA profile 处置的文字校准，相关当前 hash 与状态以文档顶部和第三节为准。
- 本轮没有五位 reviewer 返回；所有 finding 的判断来自主 Agent 的源码证据、角色化自审与双向钢人论证。编排者对依赖代码事实的断言逐条复核（表中"复核"列），未复核的部分（如 R-85 门的证据载体能力）已在 FYI 中标注。
- 用户所指差页仍无可回放身份，因此"表达优先"是否解决用户个案问题在本轮仍不可判定；完成状态的上限仍是方案自述的"通用能力已验证，用户问题未验证"。
