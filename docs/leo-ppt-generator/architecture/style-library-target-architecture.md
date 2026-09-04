---
title: leo-ppt-generator 风格库理想态目标架构（北极星）
type: architecture
date: 2026-09-02
status: reference
version: v4.5
status_note: >
  draft — 五 Agent 对抗式评审确认 6 个 P0 与 11 个 P1，v4.4 的 frozen 已撤回。本版闭合全部 P0
  与关键 P1；重新冻结的前置是 §0.5 解冻退出条件全绿，其中含两项必须由代码/CI 侧提供的载体。
scope: 目标架构参考，独立于迁移方案；定义目标合同，不含迁移排期与实现任务
supersedes: v4.4
authority: 与 related 中任何实现计划冲突时，以本文为准（见 §0.4）
related:
  - docs/plans/2026-09-02-001-refactor-leo-ppt-style-library-restructure-plan.md   # needs-rewrite：目标目录与字段形状冲突，见 §0.4
  - docs/plans/2026-09-01-001-feat-leo-ppt-style-recommendation-coordinate-plan.md # partial-conflict：tier 与首推门口径相反（requirements-only，非执行入口），见 §0.4
  - leo-ppt-generator/references/style-library.md                                  # 局部过期：stem 式 sidecar 命名与写死计数
  - leo-ppt-generator/references/style-recommendation.md                           # 局部过期：写死计数与家族真值 owner
revision_note: >
  v4.5（2026-09-03，据五 Agent 对抗式评审撤回冻结后修订）：闭合 6 个 P0 与 11 个 P1——
  ① 收据移出 `deck_spec.style`，prompt projection 改为显式白名单，消除架构自身违反 §13.1 的缺陷；
  ② 许可门拆 advisory/enforcing 两级，枚举补自研与已核验值并纳入 versioned vocabulary，
  user-local 不反转现状首选，区分 bundle 兼容闭包与对外分发子集；③ 降级出口从「0 个方向」改为
  「0 个语义排序方向 + 强制浏览 fallback」，统一原则层/漏斗/降级三处方向基数；④ L1 拆
  L1a–L1d，all-or-nothing 收窄到 lint 翻门，补配对表与 golden roster 前置、四类耦合面与第四条
  CLI 退出证据；⑤ 补发布序列与回滚深度，显式声明 L1c 为单向门；⑥ 补 §0.4 实现计划对齐关系与
  L↔Phase 无映射声明。P1 侧澄清 `stale` 为收据状态并补 tier 派生规则、补 `coverage_state`
  与 reason code 一一映射、给机械门标最低生效层级、修负反馈可达性、补确定性序列化 profile、
  Candidate 补 `enrichment`/`evidence_status`、补 freshness 检测 owner、定义 `prefer`、
  给 pool 移出可执行面排级、§17 改为真实取舍清单。原则骨架不变。
  v4.4（2026-09-02，据最终四 Agent 终审窄解冻后重新冻结）：闭合六个实施前合同缺口——
  ① evidence 收据集与 digest 进入 catalog 重建及 bundle 兼容闭包；② L1 负责叶子实体包形状归一化
  与消费者切换，L3 只搬父目录和删兼容层；③ L1 派生 experimental/candidate/deprecated 基线资格，
  L2 只叠加 verified/stale 证据置信；④ license=unknown 采用按 scope、默认 fail-closed 的晋升/推荐/
  发布门；⑤ user canonical 与 catalog 共享 generation/freshness 合同，并采用 reader-first 发布序列；
  ⑥ typed query 返回 request-scoped coverage/degradation，不把富化子集最优冒充全库最优。原则骨架不变。
  v4.3（2026-09-02，据四角色对抗性验证收敛并冻结）：补齐三条实施前必须钉死的边界并冻结北极星——
  ① §8 增防长尾饿死判据：富化覆盖率可观测，未富化风格在浏览/点名路径必须可达且显式标 name-only，
  不因缺特征而在推荐面静默消失；② §11 写死 stale 语义：stale 只暂失 verified 加成与高保障档准入、
  不影响 candidate 默认首推资格，并区分全局资产版本变更与单 style 内容变更的 stale 传播范围；
  ③ §15 明确 L1 边界：所有 stem-based 定位与身份推导必须与 style_id 铸造在 L1 同批退役，实体包
  重命名与 prompt projection 字节回归是 L1 退出证据，不留到 L3。除此之外架构骨架不变。
  v4.2（2026-09-02，据业界同类布局对标优化）：① 目标树改为 canonical authored、contracts、
  evidence、generated 四区分层，保持 authoring 真值与生成/验证产物物理隔离；② canonical 内仍按
  稳定资产角色组织，不把 family/domain/scenario/source 编码进路径；③ style brief 从扁平同名
  文件对改为每 style 一个实体包（brief.md + layouts.json），提升数百风格下的维护、导出与同位
  约束；④ 删除只有单一子角色的 compositions/presets 与 overlays/brands 包装层，直接使用
  presets/ 与 brands/；⑤ user plane 镜像最小 canonical + generated 边界；⑥ 同步 sidecar、resolver、
  机械不变量与 L3 迁移合同。digest/content-addressing 仍只用于发布、evidence 与复现，不进入人工
  authoring 路径。
  v4.1（2026-09-02，据三专家会议裁决优化）：① 统一 candidate 可默认首推、但不得标成 verified
  或进入高保障档，verified 仅承担排序加权、验证标签与高保障档准入；② 明确 L0 只用现有 brief
  合同的临时校验 profile 富化 source/families，完整 style-brief-v2（含 style_id）自 L1 原子切换后
  强制；③ 非 style 资产 ID 改为 canonical/同位 sidecar 持久身份，补 L1 resolver 消费者闭包并
  将 L3 收敛为纯物理迁移；④ hard-rule lock 拆为 required_include / exclusive_lock，定义 MMR
  降级与可观察 reason code；⑤ 补齐 text_density / visual_evidence 到 versioned recommendation
  features 的一一映射；⑥ 引入覆盖完整有效组合的 composition_resolution / resolved_input_digest，
  golden/readiness 据此失效，并新增 builtin 兼容 bundle 发布/回滚合同。另以最低限度补充稳定匹配
  决策桶、behavioral append-only 补偿和 deprecated tombstone/replacement 方向，不展开实现机制。
  v4（2026-09-02，据第三轮对抗性审查修订）：① "已定决策"拆为原则层（锁定）与机制层
  （按 L 级采用、库小时可长期不建），消除比例性锁定矛盾；② 新增被引用资产（rendering/
  mode/layout/component/brand）的最小身份合同，补齐组合关系图；③ 稳定 style_id 铸造与
  resolver 化从 L0 下沉到 L1 并标注 all-or-nothing，L0 回到零迁移集；④ readiness 拆分
  首推资格与出图验证置信——candidate 即可首推、verified 仅加权与高保障档，不回退现状
  首推面；⑤ 新增 authored lifecycle 承载 deprecated；⑥ 删冗余 layout_profile_id、统一并发
  口径、补 variant_of 跨 scope 与合并计数 owner、统一请求基数与 data_density 命名、收据补
  引擎/权重版本。
  v3（2026-09-02，据第二轮对抗性审查修订）：① 以 fenced JSON style-brief-v2
  取代不存在且会双写的 YAML frontmatter，拆分 authored / computed / evidence 三类数据；
  ② 增稳定 ID、builtin/user/behavior 三平面与统一 AssetResolver；③ 补齐推荐请求、
  候选结果、硬规则、readiness、MMR 的类型化接口；④ 将渲染配对、版式路由、preset、
  components 与 pools 纳入组合关系模型；⑤ 定义 catalog 发布、失效、降级、原子更新与
  解析收据；⑥ 重排分级落地，目录迁移后置。
---

# leo-ppt-generator 风格库理想态目标架构（北极星）

> **一句话北极星**：以 `style-brief-v2` 为内置/用户风格的 authored 真值，以稳定 ID 和
> `AssetResolver` 隔离物理路径，以 builtin catalog、user overlay、behavioral state 三平面
> 组成查询视图；分类、索引、坐标和 readiness 都是可追溯派生物，最终推荐由类型化漏斗与
> 人在回路共同完成，目录只负责资产角色，不承担分类、身份或推荐语义。

---

## 0. 文档定位与决策状态

### 0.1 这份文档是什么

本文定义风格库的**理想态目标合同**，用于回答：

- 什么是可执行风格、组合轴、组件、规则、品牌、预设与参考池；
- 每类数据谁是 owner、谁是派生物、谁可以写；
- Agent、CLI、推荐器和治理脚本如何查询同一套资产；
- 推荐候选如何从内容合同进入硬规则、准入、排序、去同质化与人在回路；
- 物理目录变化时，运行时如何保持稳定；
- 生成物如何发布、校验、失效和降级。

它是迁移方案和后续实现计划的方向锚，不包含文件搬迁步骤、相位排期或代码任务。

> **命名约定**：本文出现的具体标识符（reason code、文件名、CLI 旗标、函数签名）为示意，用于
> 表达合同形状；最终命名以实现计划为准，其变更不构成对本架构的偏离。

### 0.2 这份文档不改变什么

- 不改变 Gate 0、样张门、真实派发、DELIVERY-GATE 与 `completed ≠ 交付闭环`；
- 不改变视觉方向确认门必须有可确认工件这一前提：任何降级都不得让该门无工件可确认（§8.3）；
- 不改变「用户自定义风格在同场景下优先列为候选」这一既有推荐面能力（§6.2）；
- 不改变现状已生效的负向反馈可达性：拒绝必须能真实压低后续推荐（§6.3）；
- 不把推荐算法变成新的确认门；
- 不让 catalog、索引、resolution receipt 或反馈记录进入图片 prompt——这是可机检的白名单约束，
  不是意向声明（§13.1、§14.4）；
- 不把用户本地风格、品牌、推荐历史写入 Skill 安装目录或仓库；
- 不要求一次性验证全部存量风格，也不以目录重排冒充推荐质量提升。

### 0.3 已定决策

锁定强度分两级：原则层永不重开；机制层是方向承诺、按 L 级采用、库小时可长期不建（见 §15 / §18）。

**原则层（锁定）**

| 原则 | 目标态 |
|---|---|
| authored 真值 | brief 内 fenced JSON `style-brief-v2`；不新增重复 YAML frontmatter |
| 实体身份 | 身份与名称/路径解耦：不可变 `style_id` 承载身份，`style_name` 与文件名是可变展示/存储属性 |
| 数据分层 | authored / computed / evidence 概念分离；catalog 是确定性派生的只读缓存 |
| 分类 | `visual_family` 单值管主身份，`families[]` 多值管推荐/规则 |
| 索引≠推荐 | 索引只到候选；方向由硬规则、准入、相关度、MMR、反馈与人在回路产生。常态 2–3 个；受 `exclusive_lock` 或语义覆盖不足约束时可少于 2，但必须同时给出浏览/点名 fallback，**不存在“零出口”降级**（§8.3） |
| 目录 | 只表达资产角色；分类、来源、推荐与身份均不编码进路径 |
| 组件 / pools | 组件是可选组合资产（非 canon）；pool 是孵化资产，晋升为 brief 后才能 render/recommend |

**机制层（方向已定，采用时机随规模/痛点）**

| 机制 | 引入层级 | 库小时的最小形态 |
|---|---|---|
| 稳定 ID 铸造 + AssetResolver | L1 | 起步薄 adapter |
| builtin / user / behavioral 三平面物理拆分 | L1 | builtin 单平面 + 用户目录 |
| typed query CLI、resolution receipt | L1 | 起步按名查询 |
| bindings / presets / components / evidence 收据 | L2 | 可后置 |
| `asset-registry` / `_contracts/` / `_evidence/` 独立目录、facet shard、MMR | L2 | 可长期不建 |
| 角色目录物理重构 + 旧路径退役 | L3 | 迁移期由 resolver 屏蔽 |

### 0.4 与既有实现计划的关系

本文是目标合同的唯一真值。`related` 中的实现计划在与本文冲突处一律让位；计划自身的 `status`
字段不构成对本文的豁免。

> **编号警告**：本文的 **L0–L3 与 `2026-09-02-001` 的 Phase 0–3 没有对应关系**，编号相似纯属巧合。
> 不得把「Phase 3 可选后置」读成「L3 可选后置」，更不得据此跳过 L1 身份层——计划中不存在 ID 铸造
> 与 resolver 条目。

| 计划编号 | 本文对应层级 | 关系 |
|---|---|---|
| Phase 0 元数据化 | 大体对应 L0 | 方向一致，但**字段形状冲突**（见下表） |
| Phase 1 类型分区重命名 | 无对应 | 目标分区已被 v4.2 否决 |
| Phase 2 来源文件夹归位 | 落在 L3 域，但目标形态冲突 | 计划的默认交付会造出本文 §3.1 禁止的物理分类树 |
| Phase 3 briefs 拍平 | ⊂ L3 | 目标树以本文 §3 为准 |
| — | **L1 身份与查询闭环** | **两份计划均无对应条目**，是最大的覆盖缺口 |

已被本文取代、需要重写或标注 `superseded` 的具体条目：

| 计划 | 失效条目 | 冲突点 |
|---|---|---|
| `2026-09-02-001` | KD-1 四分区 `_meta/ briefs/ axes/ overlays/` | `overlays/` 已在 v4.2 显式删除；`_meta/` 无对应物 |
| `2026-09-02-001` | R1「`01/02/03` 分类树保留」及新建家族子目录 | §3.1「family/domain/scenario/source 绝不复制成物理分类树」 |
| `2026-09-02-001` | `taxonomy` 字段形状（`visual_family` 为数组、无 `families[]`、`industry`/`scenario` 单数无命名空间） | §4.4 要求 `visual_family` 单值 + `families[]` 含主身份 + `industries[]`/`scenarios[]` 带命名空间。**该冲突会写进全库 brief，是最贵的一条** |
| `2026-09-02-001` | `source` 无 `license` 键 | §4.3 的许可门以 `source.license` 为唯一判定输入 |
| `2026-09-02-001` | KD-4「运行时几乎不动」 | §7.3 要求 L1 全部身份/路径敏感消费者经 resolver |
| `2026-09-02-001` | R5/KTD4 把 stem 唯一性当**长期去重键** | §15 要求 stem 身份推导在 L1 整批退役；唯一性 lint 本身不冲突，仅是过渡期守护 |
| `2026-09-02-001` | R6「sidecar 与 brief 同名同目录」及其零回归口径 | §4.5 sidecar 在实体包内以 `style_id` 回指；零回归口径见 §15 退出证据③（计划口径只覆盖 CLI stdout，漏 prompt 组装层与覆盖旗标） |
| `2026-09-01-001` | KD-1「首推必出已验证池」（口径为金样板名单）、KD-5 tier 枚举 `builtin/reference/source` | §11.2 的 tier 是 `experimental/candidate/verified/deprecated`（资格等级，非来源标签），且 `candidate` 即可默认首推、`verified` **不作首推硬门槛** |

**两份计划的风险等级不同**，标注与处置也不同：

| 计划 | readiness | 是否 `spec-work` 执行入口 | 标注等级 |
|---|---|---|---|
| `2026-09-02-001` | `implementation-ready` | **是** —— 按其默认交付实施会产出需回滚的结构 | `alignment: needs-rewrite`（阻断性标注） |
| `2026-09-01-001` | `requirements-only` | 否 —— 按 spec-plan 规则属 enrichment input | `alignment: partial-conflict`（局部修正） |

**治理动作状态（2026-09-03）**：两份计划已在各自 frontmatter 加 `alignment` / `alignment_source` /
`alignment_checked` 字段，并在标题下加入逐条失效清单与重写指引。**`status` 未改动**：两份仍为
`active`。若需在工具链层面**机械阻断**执行入口（`spec-write-tasks` 只从 `status: active` 编译任务，
`superseded` 会返回 `source_plan_non_active`），需把 `2026-09-02-001` 的 `status` 改为 `superseded`；
该操作按 spec-plan 规则**不可逆**（`superseded` 不得再改回 `active`），因此留待 owner 决定。
在此之前，冲突处以本文为准，且文档级标注已足以让读者在进入实施前看到冲突。

### 0.5 重新冻结的退出条件

v4.4 曾在「六项合同已闭合」的结论下标记 `frozen`，随后的对抗式评审在同一文本上确认了 6 个 P0。
根因是当时的验证方式是**锚点存在性断言**（关键词是否出现），它能证明「话说了」，不能证明「话之间
不矛盾」「话有载体」。因此本版不自我宣告冻结，改为列出可核验的退出条件：

| # | 退出条件 | 谁能证明 |
|---|---|---|
| 1 | prompt 白名单与「收据不进 prompt」有实际 fixture，且跑在最终逐页 prompt 上 | 代码侧（需先造冻结 deck fixture） |
| 2 | `license` vocabulary 首版枚举落地，存量回填口径与 advisory→enforcing 的准入数值确定 | 实现计划 + 治理 owner |
| 3 | 方向基数三处一致，且覆盖不足时的浏览 fallback 有正反 fixture | 代码侧 |
| 4 | L1a–L1d 拆分被实现计划采纳，且**存在 CI 载体**承载 §14.4 的扫描门 | 代码/CI 侧 |
| 5 | name-keyed 成员表（family 成员、alias 表、golden 代表）有存在性 lint | 代码侧 |
| 6 | ~~`related` 两份计划已按 §0.4 标注对齐状态~~ **已完成（2026-09-03）** | 治理动作 |

条件 4、5 **架构文档无法自证**：截至本版，仓库无 CI 编排文件，§14.4 的「CI 拒绝新增 stem/路径拼接」
与 §15 退出证据①的「CI 扫描」尚无载体；上述成员表亦无任何 lint 校验其成员可解析到真实 brief。
在这两项落地前，相关机械门只是**待建门**，不得记为已生效。

---

## 1. 目标与成功判据

### 1.1 目标

1. **一个实体一个 authored 真值**：名称、别名、来源、分类、适配特征和绑定关系不双写。
2. **路径不进入领域语义**：重分目录、改展示名或增加来源批次，不破坏引用与运行时解析。
3. **内置与用户资产同接口、不同作用域**：用户风格可优先复用，但不会污染仓库或他人推荐。
4. **机械索引与策展推荐分离**：索引可重建、可检查；推荐可解释、可反馈、可人工覆盖。
5. **组合关系可执行**：style、rendering、layout、mode、brand、preset 的依赖和 fallback 有稳定 ID。
6. **readiness 有证据**：不存在“有缩略图就算通过”或“代表风格通过则全家族通过”。
7. **Agent 上下文可控**：advise 读取紧凑索引；execute 通过查询接口取得小型候选结果。
8. **生成与发布可恢复**：catalog 缺失、损坏、过期或版本不兼容时有明确 reason code 和降级边界。

### 1.2 架构完成判据

本节是目标态全部到位（L3 完成）的判据，不是任一分级的准入线；分级见 §15。目标态只有同时
满足以下条件才算成立：

- L0 以现有 brief 合同的临时校验 profile 完成 `source`/`taxonomy.families` 富化；L1 原子切换后，
  所有可执行 brief 统一通过完整 `style-brief-v2` schema，且不保留第二套长期 schema；
- 所有 style 与被引用资产都有持久稳定 ID，ID、名称、别名与文件路径冲突均可检测；
- L3 后 authored assets 只位于 `styles/canonical/`，每个 style 以
  `canonical/briefs/<id-slug>/{brief.md,layouts.json}` 为实体包；contracts、evidence、generated 不混入实体包；
- builtin catalog 可从 `styles/canonical/`、`styles/_contracts/` 与 `styles/_evidence/` 中的验证收据集
  byte-identical 重建；大型样张/制品可外置，但其 artifact refs 与 digest 必须由收据绑定；
- user catalog 只在 `${LEO_PPT_HOME}` 内生成，并与 user canonical 共享可检测的 generation/freshness；
  source/catalog 失配时必须重建或显式降级，不得继续声称推荐完整；
- 推荐请求的 `data_pages`/`text_density`/`visual_evidence` 与 recommendation features、硬规则字段一一映射，
  未知或缺失信号不被臆测；
- 候选结果带匹配原因、准入状态、资产指纹和类型化 rule effect；`required_include` / `exclusive_lock`
  与 MMR 的交互可观察；
- L1 后所有身份或路径敏感消费者经 resolver 定位资产，不再拼接编号目录；
- style → rendering/layout 与 preset fallback 无悬空引用；
- readiness 能区分 `passed/failed/not_run/stale`，并绑定完整有效组合的 `resolved_input_digest`；
- advise 路径无需读取全量 catalog 或全部 briefs；
- 一次生成冻结实际解析组合中各资产的 ID、scope、digest、`selected_by` 与 composer/validator 版本；
- builtin canonical assets、contracts、evidence receipts、resolver/runtime 与 generated set 作为同一兼容
  bundle 构建、发布和回滚；bundle 兼容闭包与对外分发子集是两个集合，许可门只作用于后者；
- prompt projection 与 resolution receipt 在 deck spec 中是顶层兄弟键，收据字段不出现在任何逐页 prompt 中，
  且该隔离由机械门看护，不依赖下游逐个过滤；
- 每次语义查询返回 request-scoped `coverage_state` 与对应降级 reason code，且**响应永不为空**——
  方向数不足时必带浏览/点名 fallback；
- 许可治理以 advisory 级为默认，enforcing 级独立排级并以澄清覆盖率为准入；`origin: native` 的资产
  有合法许可取值可填；
- 全库风格计数只有单一口径，且不在 prose、reference 文档或代码常量中写死；
- CLI 用户可见输出在身份迁移期保持兼容，或差异已列举并记入 CHANGELOG；

---

## 2. 资产角色模型

现库内容不是一种“模板”，而是六种交互性质不同的资产。顶层先按角色分开，再由元数据提供
分类视图。

| 角色 | 目标目录 | 交互动作 | 可直接执行 |
|---|---|---|---|
| **Style briefs** | `canonical/briefs/<id-slug>/` | deck 级挑一个主风格 | 是 |
| **Axes** | `canonical/axes/` | 叠加 mode/rendering/layout/chart/page semantic | 由 composer 消费 |
| **Components** | `canonical/components/` | 按页选择可复用视觉/结构组件 | 由 composer 消费 |
| **Compositions** | `canonical/presets/` | 选择预设组合与 fallback 链 | 解析后执行 |
| **Canons / overlays** | `canonical/canons/`、`canonical/brands/` | 强制规则 / 身份覆盖 | 不单独执行 |
| **Pools** | `canonical/pools/` | 浏览、蒸馏、晋升 | 否 |

### 2.1 角色边界

- **Canon** 只放所有相关资产都必须遵守的规则，如版心、图表诚实、排印和对比度纪律。
- **Component** 是可选组合件，不因存在就自动作用于全部页面。
- **Brand** 是身份 overlay，覆盖风格默认 token，不是视觉风格分类。
- **Preset** 是多个资产 ID 的组合与 fallback，不复制参与资产内容。
- **Pool** 是源矿/参考集合；没有合格 brief 就不能出现在 `style list` 或默认推荐中。

---

## 3. 目标目录：四区分层，canonical 内按角色

```text
styles/
├── canonical/                        # 人工维护的 authored 真值
│   ├── briefs/                       # 每个 style 一个实体包；目录名是存储属性，不是身份
│   │   ├── consulting-precision-grid/
│   │   │   ├── brief.md              # 唯一 style-brief-v2 authored owner
│   │   │   └── layouts.json          # 本 style 的 authored 版式路由 sidecar
│   │   └── academic-defense/
│   │       ├── brief.md
│   │       └── layouts.json
│   ├── axes/
│   │   ├── modes/
│   │   ├── renderings/
│   │   ├── infographics/
│   │   ├── chart-syntax/
│   │   ├── layouts/                  # P1–P36 全局版式定义与 sidecar
│   │   ├── page-semantics/
│   │   └── structural-layouts/
│   ├── components/                   # 原 guizang 等可选组件模板
│   ├── presets/                      # style + layout + mode + density + fallback
│   ├── brands/                       # 内置品牌身份；用户品牌在 LEO_PPT_HOME
│   ├── canons/
│   │   ├── design-system.md
│   │   ├── page-canon.md
│   │   ├── chart-canon.md
│   │   ├── palette-behavior.md
│   │   └── general-design-rules.md
│   └── pools/                        # 非执行资产；每池带 manifest/source/license
├── _contracts/                       # authored schemas、ID 规则与 versioned vocabularies
│   ├── schemas/
│   └── vocabularies/
├── _evidence/                        # validator-owned 持久收据；禁手改，作为 catalog 输入
│   └── styles/<style-id>/
└── _generated/                       # catalog/registry/indexes；禁手改，可整体重建
    ├── builtin-catalog-v2.json
    ├── asset-registry-v1.json
    └── indexes/
        ├── by-name-alias.md
        ├── facets/
        │   ├── by-family/
        │   ├── by-domain/
        │   ├── by-scenario/
        │   └── by-tone-hue.md
        ├── readiness.md
        ├── provenance.md
        └── counts.md
```

### 3.1 为什么使用 style 实体包，而不按分类建目录

`visual_family`、industry、scenario 与 source 都是可变、多值或治理属性，不是身份。若把它们编码进
路径，重新分类、家族改名或来源治理都会制造无意义的文件移动和链接漂移。目标态因此选择：

- `canonical/briefs/<id-slug>/` 是 style 的最小 authored、导出和迁移单元；
- 实体包固定以 `brief.md` 承载唯一机器真值，以 `layouts.json` 承载该 style 的 authored 路由；
- 实体目录名建议取 immutable ID slug 以便人读，但目录名仍不是主键，改名不改变 `style_id`；
- family/domain/scenario/source 浏览走生成 facets，绝不复制成物理分类树；
- validator-owned 收据留在 `_evidence/`，generated preview/catalog/index 留在 `_generated/`，不得因“同
  一个 style”就回塞实体包并混淆 authored owner；
- 若某 style 暂无路由，可不创建空 `layouts.json`；一旦存在 sidecar，就必须与 `brief.md` 同实体包且
  回指同一 `style_id`。

相较扁平 `briefs/<slug>.md + <slug>.layouts.json`，实体包在数百风格下避免单目录堆积，并为 export、
许可说明或后续 authored sidecar 保留边界；它不是按分类分层，不会恢复路径语义。

### 3.2 四区所有权

- `canonical/`：style library 作者维护的领域真值；catalog generator 只从这里和 `_contracts/` 读取 authored source，并只从 `_evidence/` 聚合 evidence；
- `_contracts/`：schema、词表、ID 与兼容规则；是 authored governance，不是可执行 style；
- `_evidence/`：validator 写入的持久证据；作者不得用手改收据提升 readiness；
- `_generated/`：从前三者确定性构建的 registry/catalog/index，可删除后完整重建。

如迁移期暂时保留旧编号或来源目录，resolver 必须屏蔽物理差异，lint 必须保证同 ID 全库唯一；旧树只
是兼容输入，不是目标分类法。`canonical/` 包装层属于 L3 物理布局，不要求在 L1 身份切换前提前建立。

---

## 4. Canonical style contract：`style-brief-v2`

### 4.1 单一 authored 真值

当前 brief 已由 Markdown 中 fenced JSON 驱动 schema、lint 与 `compose_style()`。目标态延续
这一正确 owner：**JSON brief 是唯一 authored machine truth**，Markdown 其余散文只用于人读，
不得复制机器字段；不存在另一份 YAML frontmatter。

````markdown
# 咨询精密网格风

人读说明……

```json
{
  "schema_version": 2,
  "style_id": "builtin:consulting-precision-grid",
  "style_name": "咨询精密网格风",
  "aliases": ["韩式咨询正型", "consulting-grid"],
  "lifecycle": "active",
  "source": {},
  "taxonomy": {},
  "recommendation_features": {},
  "bindings": {},
  "variant_of": null,
  "best_for": "...",
  "visual_direction": "...",
  "canvas": {},
  "color_palette": {},
  "typography": {},
  "layout_patterns": []
}
```
````

> 上例只展示领域分层，不替代正式 JSON Schema。既有渲染字段继续由 schema 约束；新增元数据
> 不得未经显式投影就进入图片 prompt。

### 4.2 稳定身份

```jsonc
{
  "style_id": "builtin:consulting-precision-grid", // minted once，之后不可改
  "style_name": "咨询精密网格风",                  // 可变展示名
  "aliases": ["consulting-grid"],                 // 可变检索名
  "variant_of": "builtin:consulting-grid"         // 引用稳定 ID，不引用名称
}
```

规则：

1. `style_id` 在 merged view 内唯一，格式为 `<scope>:<immutable-slug>`；namespace 是 scope 的
   单一 authored 来源，catalog 中的 `scope` 由它派生；
2. 文件 slug 默认与 ID slug 一致，但文件名不是主键；
3. `style_name` 可改名，改名不改变 ID；
4. alias 冲突不得静默决策，返回歧义候选；
5. 用户同名风格与内置风格是两个实体，由 resolver precedence 决定，不合并 ID；
6. `variant_of`、preset、bindings、反馈和收据都引用 ID；
7. `variant_of` 只能指向同 scope 或更权威 scope 的主风格——`user:` 可指向 `builtin:` 主风格，
   `builtin:` 不得指向 `user:`（内置只读，不依赖用户本地资产）。

### 4.3 来源与许可

```jsonc
"source": {
  "origin": "native|imported|distilled|user",
  "batch": "C2",
  "upstream_ref": "slides-grab/韩式精密网格",
  "snapshot": "2026-08-31",
  "license": "native-owned|cleared-no-restriction|MIT|CC-BY-4.0|third-party-licensed|unknown",
  "license_note": null,
  "license_approval_ref": null
}
```

`license` 是 **versioned vocabulary**（与 §4.4 的其他枚举同等待遇，首版取值与升级策略见 §18），
不是硬编码的三值常量。它必须能表达存量真实存在的每一类权利状态，否则门会把自己无法表达的情况
一律判成风险：

| 取值 | 含义 | 典型来源 |
|---|---|---|
| `native-owned` | 自研自著，无第三方权利 | `origin: native` 的内置风格 |
| `cleared-no-restriction` | 已核验、无附加要求，但不属于标准 license | 思想级改写、公开事实性素材 |
| `MIT` / `CC-BY-4.0` / … | 标准开源/共享协议 | 具名上游 |
| `third-party-licensed` | 有单独或线下授权，凭 `license_note` + `license_approval_ref` | 商业素材库 |
| `unknown` | **尚未核验**，不等于「无权利问题」也不等于「有问题」 | 待澄清存量 |

`unknown` 只表示未核验，不能用 `null` 模糊「未记录」与「已核验无额外要求」——后者有专门取值
`cleared-no-restriction`。**`origin: native` 必须能取 `native-owned`**：把自研资产逼进 `unknown`
再由门判死，是判定链设计错误，不是合规严谨。

#### 许可门分两级（v4.5）

v4.4 把「不得晋升 + 不得执行 + 不得发布」写成一道同时生效的 fail-closed 门。该设计在
`source.license` 覆盖率为 0 的现状下会让可用风格池瞬间归零（含全部自研内置），且它被挂在 L1 上，
等于把 L1 的完成时间交给不受工程控制的上游许可澄清。因此拆为两级，**分别排级、分别准入**：

| 级别 | 生效内容 | 引入时机 | 准入条件 |
|---|---|---|---|
| **advisory** | 计算 `license_policy_result`；`unknown` 不进**默认推荐面**并返回 scope-aware reason code；provenance 索引如实展示 | L1 随许可策略注入 | 无（不依赖回填进度） |
| **enforcing** | 追加：`unknown` 不得晋升 `candidate`/`verified`、不得执行、不进**对外分发子集** | **独立里程碑，不挂 L1** | 许可澄清覆盖率达到治理 owner 设定阈值（阈值为实现参数，见 §18） |

advisory 级不阻断执行与分发，因此可以在回填未完成时安全开启；enforcing 级只有在存量已被澄清到
足以不伤害可用池时才允许开启。两级都必须可观察，且**不得跳过 advisory 直接开 enforcing**。

#### scope 与 owner 边界

- **builtin `unknown`**：advisory 级下留在 inventory/pool、浏览索引与 provenance 索引，可被显式点名
  解析，但不进默认推荐；enforcing 级下按上表收紧。例外必须有显式、可审计的批准收据，记录 owner、
  适用 scope 与有效期；**收据过期后自动回落到该级别的默认行为**（不静默延期，也不追溯撤销已交付 deck）；
- **user-local `unknown`**：在本机**默认可用**，包括 §6.2 的「同场景优先列为候选」——用户自己导入的
  资产不因未填许可字段而被判成风险资产。仅在 export、共享或提升为 builtin 时必须过许可门，此时
  返回明确的待澄清 reason code。这条明确覆盖 v4.4 中「user-local unknown 不进默认推荐」的写法；
- **`license_policy_result`** 只从 authored `source.license` 与批准收据派生，由治理策略/validator 计算
  并进入 catalog eligibility。recommender 不得把许可状态混成 relevance 权重；用户点名可以在本机使用
  待澄清资产，但**不能绕过对外分发的合规门**（二者是不同的边界，不可互相推导）。

### 4.4 分类与适配特征分离

```jsonc
"taxonomy": {
  "visual_family": "family:precision-grid",
  "families": ["family:precision-grid", "family:korean-consulting"],
  "industries": ["domain:consulting-legal"],
  "scenarios": ["scenario:reporting", "scenario:pitch"]
},
"recommendation_features": {
  "genres": ["report", "pitch"],
  "domains": ["consulting", "finance"],
  "audiences": ["executive", "professional"],
  "cultures": [],
  "formality_range": [0.7, 1.0],
  "data_density_range": [0.4, 1.0],
  "text_density_levels": ["medium", "high"],
  "visual_evidence_levels": ["medium", "high"],
  "content_shapes": ["data-heavy", "argument-heavy"],
  "risk_profile": "conservative"
}
```

- `taxonomy` 回答“它是什么、从哪些分面浏览”；
- `visual_family` 必须同时出现在 `families[]`，保证主身份是多归属集合的一个合法成员；
- `recommendation_features` 回答“什么请求适合使用它”；`data_pages` 归一化为
  `data_density_range`，`text_density` 映射到 `text_density_levels`，`visual_evidence` 映射到
  `visual_evidence_levels`，三者均引用 versioned vocabulary/尺度；
- `best_for` 只作人读摘要，不能承担机器推荐真值；
- 所有枚举引用 versioned vocabulary；自由文本不能直接变成筛选键，未知或缺失值必须保留为
  `unknown`/absent，不能臆测为最接近枚举。

### 4.5 绑定关系

```jsonc
"bindings": {
  "rendering_id": "rendering:editorial-flat",
  "compatible_mode_ids": ["mode:claim-evidence"]
}
```

绑定只保存 ID，不复制 rendering/mode 内容。版式路由不进 binding：它由 style 实体包中的
`layouts.json` sidecar 承载，sidecar 内声明 `style_id` 回指同包 `brief.md`（两方一致即可）。人读的
视觉配对表与版式路由表均由 brief binding 与 sidecar 生成，不手维护第二份映射。

> 不引入独立 `layout-profile:` 命名空间：per-style sidecar 与 brief 一一对应、同实体包，用 `style_id`
> 关联即足。若未来出现多 style 共享同一路由 profile 的真实需求，再按机制层规则（§0.3 / §18）提升为
> 具名 profile 资产。

### 4.6 被引用资产的最小身份

style 是推荐主体，需要富元数据（taxonomy / recommendation_features / readiness）。但被 binding 或
preset 引用的其他资产（rendering、mode、layout、component、brand）是**词表项**，只需要能被稳定引用
与校验存在，不需要推荐元数据。

- 每个此类资产携带稳定 `<role>:<slug>`（如 `rendering:editorial-flat`、`layout:P6`、
  `mode:claim-evidence`、`component:...`、`brand:...`）；该 ID 必须持久化，不能由运行时反复按路径推导。
  **载体二选一必须定死，不能两种并存（v4.5）**：默认写在 **canonical asset 本体**（该资产已有结构化
  区块时嵌入其中）；**仅当资产格式无法承载结构化字段时**才用同位 sidecar。实现计划必须给出「角色 →
  载体」的唯一映射表；两种载体并存会产出物理布局与 lint 都不兼容的两套库；
- 文件 stem 或声明码（P 码）只可作为首次 mint 的建议输入；ID 一经 mint 即 immutable，后续改名、
  移动或重组目录均不改变 ID；
- 生成的 registry 从这些持久 ID 派生 `id → 路径`，存在性、唯一性和 ID/sidecar 对应关系由 lint
  保证（§14.2 的引用完整性据此成立）；
- 这些资产不携带 taxonomy / recommendation_features / readiness；
- 迁移期由 resolver adapter 把现有“按名/子串”解析映射到 ID，收敛后 lint 升级为 ID 引用完整性。

这样 §10 组合关系图两侧都有可校验的身份，而不是 style 侧完整、axis 侧悬空。

---

## 5. 真值 DAG：authored、computed、evidence 必须分开

### 5.1 三类数据

| 类型 | 示例 | 写入 owner | 可否手改 catalog |
|---|---|---|---|
| **Authored** | ID、名称、`lifecycle`、来源、taxonomy、recommendation features、bindings、视觉 brief | brief / sidecar 作者 | 否 |
| **Computed** | palette anchors、lightness、hue、路径、digest、facet、variant closure | catalog generator | 否 |
| **Evidence** | schema/golden/thumbnail 检查收据 | 对应 validator | 否 |

有效 catalog 条目由三类输入聚合：

```text
style entity package: brief.md + optional layouts.json
  ├─ authored metadata（含 _contracts 中的 schema/vocabulary）
  ├─ deterministic feature derivation
  └─ _evidence 中的 verification receipts
       ↓
  catalog entry + readiness tier + indexes
```

### 5.2 禁止回写的派生字段

以下字段不进入 authored brief：

- `palette_anchors`
- 自动推导的 `lightness_tier` / `hue_bucket`
- 文件路径和 sha256
- `has_gold_sample`
- `in_thumbnail_coverage`
- `in_candidate_pool`
- `readiness_tier`
- 计数与分面位置

确有误判时，只允许 authored `coordinate_override` 携带原因；catalog 同时保留
`derived_value` 与 `effective_value`，避免覆盖算法证据。

> 退役是 authored 决策：brief 携带 `lifecycle: active | deprecated`（缺省 `active`）。`deprecated`
> tier（§11.2）由该 authored 字段派生，因此 readiness tier 仍是 computed，不构成对“readiness 不
> authored”的反例。退役后至少保留可按原 ID 解析的 tombstone；可选 `replacement_id` 只指向替代资产，
> 不改变原 ID 身份。

---

## 6. 三平面 catalog 与作用域合并

### 6.1 Builtin plane

- 来源：仓库 `styles/canonical/` canonical assets **+ `_contracts/` schema/词表 + `_evidence/` 收据集**
  （三者共同构成重建输入闭包，与 §1.2、§12.1、§14.3 同口径；v4.4 此处只写 canonical，是 evidence
  作为一等输入在全文唯一的漏写点）；
- 生成物：`styles/_generated/builtin-catalog-v2.json`；
- 写入时机：开发/发布阶段；
- 属性：只读、可重建、随 Skill 包发布；
- 内容：内置 briefs、axes、components、presets、brands、pools 的 registry 与关系。

### 6.2 User overlay plane

```text
${LEO_PPT_HOME}/
├── styles/
│   ├── canonical/
│   │   └── <style-id-slug>/
│   │       ├── brief.md
│   │       └── layouts.json         # 可选；存在时回指同一 style_id
│   ├── _evidence/                   # L2 可选；validator-owned user receipts
│   │   └── styles/<style-id>/
│   └── _generated/
│       └── catalog-v2.json
├── brands/
└── recommendation/
```

- 用户 `brief.md` 通过同一 `style-brief-v2` schema，实体包目录名不承担身份；
- `style save/import/remove` 必须先校验实体包，再以一个逻辑 generation 提交 user canonical 与匹配 catalog；
  对外成功点是二者 generation/source digest 一致且均可读，而不是“canonical 已写入”；
- 若 canonical 已提交而 catalog 构建/激活失败，返回 retryable `user_catalog_rebuild_required`；任一语义查询
  必须先检测 freshness，能同步重建则重建，否则降级为精确 load/list，绝不继续读取旧 catalog 声称推荐完整；
- generation 的物理实现可用 lock/CAS/journal/原子指针，§18 保留选型自由，但不能改变上述可观察语义；
- 迁移期 resolver 可读取旧的 `${LEO_PPT_HOME}/styles/<name>.md` 平铺格式，但新写入只使用实体包；
- 一个损坏用户 brief 只隔离自身并返回明确诊断，不得毒化整个 builtin catalog；
- 用户 catalog/evidence 不进入 Git、安装目录或团队共享包，除非用户显式 export；
- user styles 默认可作为候选（含 §4.3 的本机 `unknown` 许可条目），但 readiness 与 builtin 分开计算；
  L2 若创建 user `_evidence/`，收据 owner 与 builtin 相同；没有对应 user 收据时最高只能是 `candidate`，
  不得伪造 `verified`；
- **user evidence 也进 freshness fence（v4.5）**：一旦启用 user `_evidence/`，user catalog 必须与 builtin
  侧对称地携带独立 `evidence_digest`，并纳入 generation/freshness 判定。否则 user 收据变化不会使
  catalog 失新，user readiness 会长期停留在陈旧证据上——这与 §12.1 「证据变化刷新 readiness、不伪装成
  authored 变化」的分离原则矛盾。若实现计划选择「user readiness 不由收据驱动」，必须在此显式声明，
  不得默认沉默。

### 6.3 Behavioral state plane

只保存推荐行为状态，不保存风格正文或用户业务原话：

- family/style 的 boost/decay；
- 最近使用与场景复用摘要；
- 反馈算法版本与更新时间；
- 隐私和清理边界。

强正样本只能来自 `sample_accepted` / `delivery_accepted`；改选、拒绝或终止不直接改写历史权重，
而以幂等、append-only 的补偿语义记录。这里只锁定反馈语义，不展开事件 schema 或存储机制。

**负向信号必须可达（v4.5）**：v4.4 把拒绝的效果写成「抵消对应影响」。纯抵消语义在数学上只能消除
**已存在的正样本**，因此一个从未被接受过的家族其净值永不为负，decay 永远不可达——而现状实现的净值
口径（选中数减拒绝数，净值低于阈值即 decay）**是可达的**。若按纯抵消语义迁移，会造成可观察的能力
倒退：用户反复拒绝某风格，它仍然被推荐。

因此锁定：**拒绝是一等负向信号，不是正样本的逆运算**。append-only 与幂等约束适用于**事件记录**
（同一次拒绝重复上报不叠加），不适用于**聚合口径**——聚合必须允许净值为负并触发 decay。同时保留
两条边界：decay 只在同一 eligibility pool 内调整排序，不得越过硬规则（§8.3）；负向信号不修改
authored taxonomy。

它不是 catalog，也不改变 authored taxonomy。删除 behavioral state 后，资产库仍完整可用。

### 6.4 合并优先序

```text
显式 qualified ID
  > 用户同名/别名精确命中
  > 内置同名/别名精确命中
  > merged recommendation candidates
```

- 显式点名仍 bypass 推荐硬规则，但错配提示与 user sovereignty 合同保持不变；
- scope/name/alias 解析必须先进入稳定决策桶（qualified ID、canonical name、alias、recommendation），
  同一规范化输入不得因目录顺序、遍历顺序或索引布局变化而换桶；
- alias 命中多实体时返回歧义，不按目录顺序或遍历顺序静默选择；
- “跟上次一样”只在 user plane 有可验证记录时成立；
- user overlay 缺失时回落 builtin，并如实报告。

---

## 7. AssetResolver：隔离路径与作用域

所有 runtime 与治理消费者通过统一解析合同定位资产，不再自行拼接目录：

```text
resolve_style(style_id_or_name, scopes)
resolve_style_sidecar(style_id)
resolve_asset(asset_id)
resolve_brand(brand_id_or_name, scopes)
list_assets(role, filters)
resolve_preset(preset_id)
```

### 7.1 Resolver 拥有

- ID/name/alias 到实体的解析；
- user > builtin 的 scope precedence；
- 路径与 package layout 适配；
- 歧义、缺失、损坏和版本不兼容的稳定 reason code；
- `brief.md` 与同实体包可选 `layouts.json` sidecar 的关联；
- 返回资产 digest 和来源 scope。

### 7.2 Resolver 不拥有

- 推荐相关度和 MMR；
- taxonomy 或 bindings 的业务真值；
- 用户点名是否错配的产品策略；
- brief/schema 校验规则的复制实现；
- 另一份持久化 registry 真值。

`asset-registry-v1.json` 是 resolver 的生成式加速索引，不是新真值。迁移期可由 adapter 同时
解析旧编号目录与目标目录；所有旧路径消费者收敛后再移除 adapter。

### 7.3 L1 消费者闭包

L1 完成时，所有身份或路径敏感读取者——composer、brief/sidecar loader、pack/gallery、
preview/golden、catalog/index generator、lint 与 docs 工具链——都必须通过 resolver 获取资产身份、
路径、scope 与 digest；`name`/`alias` 仍可作为兼容输入，但内部必须先解析为持久 ID。CI/机械门禁止
新增按编号目录、文件 stem 或固定相对路径直接拼接的消费者。L1 关闭的是消费者切换；L3 只利用这一
闭包搬迁物理目录和退役兼容层，不再承担泛化“消费者迁移”。

---

## 8. 类型化推荐接口

### 8.1 RecommendationRequest

请求字段与现有内容合同、`style_hard_rules` 一一映射：

```jsonc
{
  "genres": ["thesis-defense"],
  "domains": ["academic", "medical"],
  "audiences": ["committee"],
  "cultures": [],
  "formality": 0.95,
  "content_shape": {
    "data_pages": 0.6,
    "text_density": "high",
    "visual_evidence": "high"
  },
  "named_style": null,
  "reference_image": false,
  "allowed_scopes": ["user", "builtin"]
}
```

- 多值信号键 `genres`/`domains`/`audiences`/`cultures` 与 §4.4 recommendation_features 同名同形，统一为
  数组；归一化层接受标量或数组、内部一律规整为数组（对齐 `style_hard_rules` 的 `_as_text_list` 语义）。
  标量键只有 `formality`（float）。
- `content_shape.data_pages`（0..1）派生为 feature `data_density`，与 `data_density_range` 匹配；
  `content_shape.text_density` 映射到 `text_density_levels`，`content_shape.visual_evidence` 映射到
  `visual_evidence_levels`。三条映射使用 versioned vocabulary/尺度，候选匹配标签分别为
  `data_density`、`text_density`、`visual_evidence`。
- 归一化把合同中文自然语言映射到 versioned vocabulary；原始用户文本不直接作为 catalog 筛选表达式。
  未知值保留为 `unknown`，缺失值保持 absent，二者都不得臆测成最接近标签或默认高/低档。

### 8.2 Candidate

```jsonc
{
  "style_id": "builtin:academic-defense",
  "style_name": "科研答辩风",
  "scope": "builtin",
  "families": ["family:academic-defense"],
  "feature_matches": ["genre", "formality", "data_density", "text_density", "visual_evidence"],
  "hard_rule_effects": ["required_include:family:academic-defense"],
  "license_policy_result": "eligible",
  "readiness_tier": "verified",
  "evidence_status": "passed|failed|not_run|stale",
  "enrichment": "enriched",
  "relevance_score": 0.87,
  "diversity_coordinate": {"lightness": "light", "hue": "blue"},
  "brief_sha256": "...",
  "reason_codes": ["genre_match", "data_density_match", "required_include_satisfied"]
}
```

候选必须携带可解释信号和 digest；不能只返回风格名列表。Candidate 属于 versioned query envelope；
envelope 还必须携带本次请求的语义覆盖与降级状态，而不是把全局 `counts.md` 当作单次查询证明：

```jsonc
{
  "coverage_state": "complete|partial|insufficient",
  "coverage_summary": {
    "eligible_enriched": 24,
    "eligible_name_only": 7,
    "matched_facets": ["domain:academic", "scenario:thesis-defense"]
  },
  "degradation_reason_codes": ["semantic_coverage_partial"],
  "browse_fallback": {
    "facet_entries": ["by-domain/academic", "by-scenario/thesis-defense"],
    "name_only_reachable": 7
  },
  "candidates": []
}
```

具体覆盖阈值由实现计划决定；状态、摘要口径和降级可观察性是稳定合同。三项字段级约束（v4.5）：

- **`coverage_state` 与 reason code 一一对应**，不允许孤立状态：`complete` → 无降级 code；
  `partial` → `semantic_coverage_partial`；`insufficient` → `semantic_coverage_insufficient`。
  v4.4 只定义了 `insufficient` 一个 code，使 `partial` 无名可用，实施者只能复用（丢失区分）或自造
  （词表分叉）；
- **`candidates[]` 只包含已富化条目**。`name-only` 条目不混入候选数组，只出现在 `coverage_summary`
  与 `browse_fallback` 中。Candidate 携带 `enrichment` 字段是为了让「该条目是否参与过语义排序」
  在单条粒度上可判定，从而使 §14.3 的「不得把 name-only 伪装成已排序」成为可执行断言而非空门；
- **`evidence_status` 与 `readiness_tier` 是两个正交字段**（见 §11.2）：tier 是资格等级，
  `evidence_status` 是收据状态。`stale` 只能出现在后者。`browse_fallback` 在 `coverage_state` 非
  `complete` 时必须非空（§8.3 的无零出口要求）。

### 8.3 推荐漏斗

```text
Request normalization
  → merged catalog query
  → hard rules（exclude / required_include / exclusive_lock / prefer）
  → provenance/license eligibility
  → baseline readiness eligibility
  → request-scoped semantic coverage assessment
  → relevance scoring
  → rule-aware family quota + MMR diversity
  → behavioral boost/decay（不得越过硬规则）
  → 0–3 个语义排序方向 + 归因
  → 方向数 < 2 时强制附加浏览/点名 fallback（无零出口）
  → 人在回路确认 / 样张门
```

边界：

- **候选池是一次查询的结果对象，不是全库单一 `candidate-pool.md`。**
- taxonomy 生成分面，recommendation features 参与相关度；二者不能互换。
- `required_include` 只锁首方向或要求结果至少包含指定家族；满足后其余方向仍可跨家族参与 MMR。
- `exclusive_lock` 把 eligibility pool 限制在指定家族；结果可只有一个方向，或在同家族内按坐标产生
  差异化方向。跨家族多样性因此放宽时返回 `diversity_relaxed_by_exclusive_lock`，候选不足时返回
  `insufficient_candidates`，不得为凑满 2–3 个方向越过规则。
- behavioral boost 只能调整同一 eligibility pool 内排序，不能越过上述 effects，也不能把
  failed/deprecated 资产推入首推。
- 用户点名、参考图、推荐的优先序保持“点名 > 参考图 > 推荐”；显式点名仍 bypass 推荐硬规则。
- 最终确认、双生样张与反演仍由现有 Skill 合同拥有。
- **防长尾饿死（v4.3）**：`relevance` 权重虽是实现参数（§18），但富化覆盖不得变成推荐偏差——
  富化覆盖率（有 `recommendation_features` 的 style 占比，按 family/domain 分布）必须由 `counts.md`
  可观测；未富化风格在浏览与点名路径必须始终可达，并显式标注 `name-only`，绝不因缺语义特征而在候选
  面静默消失。语义排序只在已富化子集内竞争，`name-only` 风格仍可经点名/浏览进入 deck。
- **请求级覆盖降级（v4.4，v4.5 修订降级出口）**：每次 semantic query 必须从本次 eligibility pool
  计算 `coverage_state`；`partial`/`insufficient` 时显式说明“仅在已富化子集中排序”，返回稳定
  reason code。不得用全局覆盖率替代请求级判断，也不得把富化子集最优表述为全库最优；更不得为凑满
  2–3 个方向而越过资格门。
- **降级必须有出口，不存在“零出口”（v4.5）**：v4.4 允许覆盖不足时“返回 1 个或 0 个默认方向”。
  0 个方向会让视觉方向确认门无工件可确认，流程直接死锁；这不是诚实降级，是把“不给答案”写成合同。
  修订如下——**语义排序方向可以为 0，但一次查询的响应不可以为空**：

  | 语义方向数 | 必须同时返回 | 跨家族多样性约束 |
  |---|---|---|
  | 2–3（常态） | 归因 | 生效 |
  | 1 | 归因 + 浏览/点名 fallback + 降级 reason code | **自动不适用**，返回 `diversity_not_applicable_single_direction`；不得因无法满足而删除该方向 |
  | 0 | **强制** taxonomy/facet 浏览入口 + `name-only` 可达清单 + 精确点名入口 + 降级 reason code | 不适用 |

  即：覆盖不足时系统改为「我无法用语义排序给出推荐，这是可浏览的全集入口」，而不是「无可推荐」。
  三处方向基数由此统一——§0.3 原则层、本节漏斗与本表一致，均为「常态 2–3、下限 0 且必带 fallback」。
- **方向数 < 2 时的多样性语义**：跨家族多样性是**对多方向结果的约束**，方向数不足 2 时该约束自动
  不适用并返回 reason code，而不是被违反、也不是反过来强迫补齐方向。`exclusive_lock` 造成的单方向
  同理（返回 `diversity_relaxed_by_exclusive_lock`）。

### 8.4 硬规则纯函数边界

```python
evaluate(request, family_vocabulary) -> RuleEffects
```

- 核心 evaluate 无文件 I/O、无随机、无 catalog 全局读取；
- `RuleEffects` 只输出类型化 `exclude` / `required_include` / `exclusive_lock` / `prefer` 及稳定 reason code，
  不用含糊 `lock` 同时表达“必须包含”和“排他限制”；
- **四种 effect 的效力必须各自有定义（v4.5）**：`exclude` 从 eligibility pool 移除；`required_include`
  要求结果至少包含指定家族；`exclusive_lock` 把 pool 限制在指定家族。**`prefer` 是软加权**——只在
  relevance 排序阶段生效，不改变 eligibility pool、不保留名额、不保证入选，并返回
  `prefer_applied` reason code。`prefer` 与 behavioral boost 的叠加顺序固定为**先 `prefer`、后
  boost**，且二者都不得越过前三种 effect。v4.4 三处列举了 `prefer` 但从未定义其效力，实施者只能
  各自猜测它是软加权还是名额保留；
- adapter 通过 resolver/catalog 提供不可变 family vocabulary；
- RULES 只引用 family ID，不维护 style members；
- family members 从 authored `taxonomy.families` 派生；
- catalog 缺失/不兼容在 adapter 边界失败，不污染纯规则自测。

---

## 9. Agent 与 CLI 查询面

### 9.1 Advise 模式

Advise 不运行一般工具，读取生成的紧凑 Markdown：

- 精确查名称/别名：`indexes/by-name-alias.md`；
- 按行业/场景/家族浏览：读取对应 shard；
- 不读取 `catalog.json`；
- 不读取全部 briefs；
- 未知查询先走 name/alias 索引，不能假定它属于哪个 facet。

每个 shard 必须定义最大条目数或 token 预算；超限按 vocabulary key 继续分片。

### 9.2 Execute 模式

Execute 通过只读查询接口取得小型结果：

```text
style lookup <name-or-alias>
style query --request <normalized-request>
style resolve <style-id>
```

查询接口返回 versioned JSON envelope 和 reason codes；Agent 只在用户锁定风格后读取该单个完整
brief。CLI 是 resolver/recommender 的接口，不重新维护索引规则。

### 9.3 人读索引

生成物至少包括：

- `by-name-alias.md`：紧凑存在性、别名、scope 和 ID；
- `by-family/<id>.md`：多归属家族视图；
- `by-domain/<id>.md`、`by-scenario/<id>.md`；
- `by-tone-hue.md`：坐标分布与拥挤提示；
- `readiness.md`：tier 与证据状态；
- `provenance.md`：来源、批次、许可和晋升状态；
- `counts.md`：口径定义与派生数字。

索引只作浏览和 advise 输入，不作为 runtime 领域真值。

> 用户可见的“可选风格数”是查询接口在合并视图上的**即时计算值**：`counts.md` 拥有 builtin 口径，
> user catalog 拥有 user 口径，合并在 API 期完成。任何 prose 不得写死合并计数——这闭掉计数漂移在
> 合并侧的最后一道缝。

---

## 10. 组合关系：style 不是孤立模板

### 10.1 Style → Rendering

现有视觉风格配对表的目标 owner 是 brief `bindings.rendering_id`。人读配对表由 bindings 生成，
不能继续手改第二份映射。

### 10.2 Style → Layout

- 全局 P 码定义在 `canonical/axes/layouts/`；
- 每个 style 实体包内的 `layouts.json` 是 preferred/discouraged、capacity factor 与 page-role routing 的
  唯一 authored owner，只引用全局 layout ID；
- sidecar 内声明 `style_id` 回指同包 `brief.md`，与 brief 的 `style_id` 一致即可（两方一致，不再有独立
  profile ID 的三方一致负担）；
- capacity/reuse 的全局定义与 per-style 调整边界必须在 schema 中唯一明确。

### 10.3 Preset

Preset 是独立 composition：

```jsonc
{
  "preset_id": "preset:investor-tech-pitch",
  "style_id": "builtin:dark-tech",
  "mode_id": "mode:claim-evidence",
  "layout_ids": ["layout:P6", "layout:P21"],
  "density": "medium",
  "fallback_style_ids": ["builtin:light-tech"]
}
```

preset 只引用 ID，参与资产缺失时按 fallback 链降级并返回证据；不得复制完整 style/layout 内容。

### 10.4 Components

组件是可选 page-level asset，拥有独立 `component_id`、输入槽位、适用 page semantic、容量与
兼容约束。它不进入 canons，也不因导入就自动进默认 layout 路由。

### 10.5 Pools

Pool manifest 记录成员、来源、许可、主题和蒸馏状态。生命周期：

```text
intake → pool → curation → distill → style-brief-v2 → validate → candidate/verified
```

Pool 自身不出现在 `style list`、候选池或 `compose_style`；“使用某池”必须先解析到已晋升的 style ID，
否则明确返回不可执行，而不是用池名伪装风格名。

> **「移出可执行面」需要排级（v4.5）**：现状存在参考池条目携带与普通风格无差别的完整可执行 brief，
> 因而已经出现在列举、加载与 compose 面上——内容嗅探无法区分它们。要落实本节，需要 authored 侧的
> 判别依据（`lifecycle` 或显式角色键），属 **L0/L1d 的 schema 面**，不能等到 L2 的 pool promotion。
> v4.4 只声明了终态约束而未排级，等于把一条已被违反的规则挂在未来。

---

## 11. Readiness：从证据派生，不用布尔猜测

### 11.1 验证收据

```jsonc
"verification": {
  "schema": {
    "status": "passed",
    "brief_sha256": "...",
    "validator_version": "..."
  },
  "golden": {
    "status": "passed|failed|not_run|stale",
    "resolved_input_digest": "...",
    "artifact_refs": [],
    "verified_at": "...",
    "validator_version": "...",
    "evidence_scope": "style|family-representative"
  },
  "thumbnail": {
    "status": "passed|failed|not_run|stale",
    "resolved_input_digest": "...",
    "artifact_sha256": "..."
  }
}
```

`resolved_input_digest` 由 §13 的 `composition_resolution` 确定性计算，覆盖该验证实际使用的完整有效
组合，而不是只绑定 brief/sidecar。

### 11.2 Tier 规则

把“能否默认首推”与“是否已出图强验证”拆成两条正交轴：前者是廉价的推荐资格闸，后者是昂贵的
置信标签，二者不得互相冒充。**阶段边界固定如下**：L1 必须从完整 v2 schema、`lifecycle`、当前已启用
引用解析、静态 compose/sanity 与许可策略派生 `experimental | candidate | deprecated` 基线资格，使 typed
Candidate 和 eligibility 漏斗在没有 L2 evidence 时也完整可用；L2 才加入 verification receipts，并可把
当前 `candidate` 升为 `verified`，或在证据失效时标记 `stale` 后回落到 candidate 权益。L1 不得伪造
`verified`，L2 也不得重新定义 candidate 的默认首推资格。

| Tier | 最低条件 | 默认可首推 | 附加语义 |
|---|---|---|---|
| `experimental` | schema 未通过或元数据不完整 | 否 | — |
| `candidate` | schema + 引用/bindings 解析 + 静态检查（palette 锚在、缩略图/静态渲染 sanity） | **是（默认可推池）** | 不得标“已验证”或进入高保障档 |
| `verified` | candidate + 当前 `resolved_input_digest` 对应的 style-level golden 通过 | 是 | 排序加权、验证标签、高保障档准入 |
| `deprecated` | authored `lifecycle=deprecated` | 否 | 仅显式兼容解析；保留 tombstone 与可选 `replacement_id` 方向 |

- **`candidate` 即可默认首推**；它与 `verified` 的差异只在强验证置信，不得把 candidate 标成
  `verified` 或放入高保障档。
- `verified` 只承担排序加权、验证标签和高保障档准入，**不作默认首推硬门槛**；默认可推池明确为
  `candidate ∪ verified`，不包含 `experimental` 或 `deprecated`，因此不回退现状首推能力。
- tier → 推荐资格的具体策略归坐标系 / recommendation plan 拥有；本架构只约束上述资格与标签边界。
- `family-representative` 证据只证家族参考覆盖，不能把全部成员标成 verified；
- style、sidecar、rendering、mode、layout、brand、preset/fallback、component、影响输出的 canon/contracts，
  或 composer/validator 版本任一变化，只要改变 `resolved_input_digest`，相关 golden/readiness 证据即置为
  `stale`；
- **`stale` 是收据状态，不是 tier（v4.5 澄清）**：上表的 tier 枚举是**封闭四值**，`readiness_tier`
  不能取 `stale`。`stale` 只出现在 §11.1 的收据 `status` 字段，与 `passed/failed/not_run` 同层。
  v4.4 的正文把 stale 当作 style 的状态来写（“标记 stale 后回落到 candidate 权益”“只 stale 该 style”），
  在缺少派生规则的情况下会让实施者各自发明第五个 tier 值。**派生规则固定如下**：

  | 收据状态 | 若 candidate 条件满足 | 若 candidate 条件不满足 |
  |---|---|---|
  | `golden.status = passed`（且绑当前 digest） | `verified` | `experimental` |
  | `golden.status ∈ {failed, not_run, stale}` | **`candidate`** | `experimental` |

  也就是说「stale 回落到 candidate 权益」的准确表述是：**tier 从 `verified` 派生为 `candidate`，
  同时 `evidence_status` 保留 `stale` 以说明原因**。查询面据此可以既不丢失「需重验」信息，
  也不需要新增 tier 值（§8.2 的 Candidate 因此同时携带 `readiness_tier` 与 `evidence_status`）。
- **stale 语义（v4.3）**：收据置 `stale` 只使 style 暂失 `verified` 加成与高保障档准入，**不影响其
  `candidate` 默认首推资格**——stale 表示“需重验”，不是质量回退。stale 传播必须区分范围：单 style
  内容（brief/sidecar）变更只使该 style 的收据 stale；canon/contracts/composer 等全局资产版本变更会
  同时使大量 style 的收据 stale，属预期的批量重验信号，不得被呈现或治理误读为全库质量下降，也不得
  因此收窄现状可推面；
- “有文件”不等于 `passed`；readiness 是 catalog 派生结果，不写回 brief。

---

## 12. Catalog 与生成物生命周期

### 12.1 Builtin 生成管线

```text
scan canonical assets
  → parse + schema validate
  → identity/reference/invariant checks
  → derive features and digests
  → join verification receipts
  → build registry/catalog/indexes in temp dir
  → full validation
  → atomic replace generated set
```

生成物携带：

```jsonc
{
  "catalog_schema_version": 2,
  "generator_version": "...",
  "vocabulary_version": "...",
  "source_digest": "...",
  "evidence_digest": "..."
}
```

实际 catalog 另携由生成器计算的整数 `entry_count`；架构文档不写死当前条目数。`source_digest`
覆盖 canonical authored assets 与 contracts，`evidence_digest` 独立覆盖验证收据，使视觉证据变化
能够刷新 readiness，而不伪装成 authored source 变化。

**`evidence_digest` 在收据面尚未建立时的取值（v4.5）**：验证收据属 L2（§0.3、§15），而 catalog 与
typed query 在 L1d 就要交付。为避免同一 `catalog_schema_version` 出现两种字段集，固定：**该字段自
L1d 起即必须存在**，收据集为空时取空集的确定性摘要，而非省略字段。§14.3 的相关机械门在收据面建立
前是空门而非失败门（见 §14 的层级标注）。

**确定性序列化 profile（v4.5）**：`byte-identical` 若不指定序列化规范，会在跨平台与跨版本时无声失效。
v4.4 只排除了生成时间与绝对路径，尚不足。补充两点：

- **重建状态元组**为 `canonical + contracts + evidence + generator_version + vocabulary_version +
  serialization_profile`。v4.4 的元组缺后三项，而 `generator_version` 本身就写在产物里——生成器一升级
  字节必变，`--check` 会产生假失败，团队的自然反应是弱化这道门；
- **`serialization_profile` 必须钉死**：键排序用码位序（不用 locale collation，否则中文键/值在不同
  ICU 版本下顺序不同）、字符串统一 NFC 归一（避免 macOS NFD 与 Linux NFC 产生不同 digest）、行尾统一
  LF、数值用定点或十进制字符串（不用浮点 repr）、非 ASCII 转义策略固定。具体取值见 §18。

### 12.2 提交与发布

- **术语（v4.5）**：**bundle = 兼容闭包**，包含全部 canonical assets、contracts、evidence receipts、
  resolver/runtime 与 generated set；**分发子集 ⊆ bundle**，是实际对外提供、可执行的那部分。二者不是
  同一集合。许可 enforcing 级（§4.3）排除的是 **eligibility 与分发子集**，**不是**从 bundle 闭包中删除
  文件——把 authored 文件从闭包中剔除会直接破坏 §14.3 的 byte-identical 重建与 `source_digest` 一致性，
  并造成「索引可点名、实体不存在」的悬空；
- builtin canonical assets、contracts、evidence receipts、resolver/runtime 与 generated set 构成一个带兼容版本的
  发布 bundle，必须一起构建、校验、发布和回滚；bundle manifest 同时绑定 `source_digest` 与
  `evidence_digest`。大型样张/制品可外置，但其 refs/digest 必须由同版收据锁定；
- builtin catalog、registry 与 advise 必需索引随仓库和 Skill 包发布；
- CI 用 `generate --check` 对比 canonical + contracts + evidence receipts 的重建结果；
- 发布包测试确认生成物被打包，不能只验证源码仓库可读；
- 禁止单独回滚 generated set，避免旧索引/registry 与新 canonical、resolver 或 contracts 形成伪兼容；
- user canonical assets 不随 builtin bundle 自动回滚；升级或回滚后由兼容 reader 重建 user catalog，
  不兼容条目按条隔离并给出 reason code，其余用户资产继续可用；
- 首次启用实体包 writer 必须采用 reader-first、writer-second：先发布能双读旧平铺与新实体包、但仍写旧
  格式的 bridge reader；只有可回滚目标已具新格式读取能力后，下一发布才切新 writer。pre-L1 reader
  不得被承诺为新 writer 的安全回滚目标；
- 所有路径写成相对 bundle path，不写机器绝对路径；
- 生成时间不得参与确定性 digest；如需时间，仅放非比较性 provenance 字段。

#### 12.2.1 发布序列与回滚深度（v4.5）

v4.4 同时写了「五类产物必须一起回滚」与「pre-L1 reader 不得作为新 writer 的回滚目标」，但没有说明
二者组合后的实际回滚能力。显式声明如下：

| 项 | 结论 |
|---|---|
| L1c 的发布数 | **两个**：`R(n)` bridge reader（双读旧平铺与新实体包，仍写旧格式）→ `R(n+1)` writer 切换 |
| `R(n+1)` 的合法回滚目标 | **只有 `R(n)`**；两者必须在同一兼容版本窗口内 |
| 回滚深度 | **1 个版本**。这不是保守估计，而是上限 |
| 跨越 writer 边界回滚到 pre-L1 | **禁止操作**。pre-L1 reader 无法读取新实体包，回滚后 user canonical 中已按新格式写入的资产会全部落入「不兼容条目」，使「其余用户资产继续可用」成为空集 |
| L1c 的性质 | **单向门**。跨过 `R(n+1)` 后，严重缺陷只能 forward-fix；实现计划必须为此指定责任人与响应路径 |

因此 §15 的分级把叶子成包单列为 L1c：它是全流程唯一的单向步骤，必须与可回滚的 L1a/L1b 分开发布，
不能被"L1 原子切换"的表述掩盖。若要保留双向回滚能力，唯一方式是额外提供「实体包 → 平铺」的降级
writer 或导出路径；本架构不要求它，但要求实现计划**显式选择**其中一条，不得默认沉默。

### 12.3 User catalog 更新

- `style save/import/remove` 为一次逻辑 mutation，携带 `mutation_id`、目标 `source_digest` 与 catalog
  generation；只有 canonical 与匹配 catalog 均可读且 freshness 一致时才返回完整成功；
- canonical 实体包与 generated catalog 各自仍使用临时文件 + 原子 rename；二者的跨文件一致性由 generation/
  digest fence、恢复记录或原子激活指针保证，不能把两个独立 rename 冒充一次事务；
- 并发/失败写不得覆盖较新 generation，冲突返回 retryable reason code（lock/CAS/journal 选型见 §18）；
- canonical 已提交但 catalog 未追平时，不得回报普通成功：返回 retryable `user_catalog_rebuild_required`
  并保留已提交 generation 事实；
- **失配的检测与降级主体唯一（v4.5）**：freshness 检测与同步重建触发由 **resolver/store 的读路径**
  拥有——它是所有语义查询的必经入口。recommender 与 Agent 都不是该判定的 owner，也不得跳过它直接
  读取 catalog（§16 有对应 owner 行）；
- **两个生命周期用两个 code（v4.5）**：`user_catalog_rebuild_required` 只用于 **mutation 结果**
  （retryable，调用方可重试）；查询路径检出失配且**无法同步重建**时，返回
  `user_catalog_stale_degraded` 并进入 §8.2 envelope 的 `degradation_reason_codes`，同时降级到精确
  load/list。v4.4 用同一个 code 同时表达 retryable 与已降级服务态，调用方无法区分该重试还是该展示降级；
- last-known-good catalog 只有在其 `source_digest` 仍匹配当前 canonical 时才可继续服务 semantic query；
- user catalog 可删后重建，不是用户资产真值。

### 12.4 缺失、损坏与版本不兼容

| 场景 | 行为 |
|---|---|
| 开发/CI builtin catalog 漂移 | fail closed |
| 安装包 catalog 缺失/损坏 | 返回 `style_catalog_degraded`；可扫描支持精确 load/list，不声称推荐完整 |
| catalog schema 过新 | `style_catalog_version_unsupported`，不静默猜读 |
| user source/catalog generation 不一致 | 返回 `user_catalog_rebuild_required`；先重建，失败则只支持精确 load/list |
| 单个 user brief 损坏 | 隔离该条目，报告路径/原因，其余资产继续可用 |
| user catalog 失配且无法同步重建 | 返回 `user_catalog_stale_degraded`，降级到精确 load/list（与 mutation 的 retryable code 区分） |
| 请求语义覆盖部分不足 | 返回 `semantic_coverage_partial` 与 coverage summary；仅在已富化子集排序，附浏览 fallback |
| 请求语义覆盖不足 | 返回 `semantic_coverage_insufficient` 与 coverage summary；不声称全库最优，**必须附浏览/点名 fallback**（§8.3 无零出口） |
| license advisory 判定为待澄清 | 从**默认推荐面**排除并返回 scope-aware reason code；仍可显式点名解析与执行；不降格成相关度扣分 |
| license enforcing 判定为不允许 | 追加从**可执行面与对外分发子集**排除；不从 bundle 兼容闭包中删除文件（§12.2） |
| evidence stale | 收据置 `stale`，tier 由 `verified` 派生为 `candidate`（§11.2），不删除资产 |

任何 fallback 都必须可观察；不能悄悄使用旧 catalog 给出“高质量推荐”。

---

## 13. Runtime 投影与可复现收据

### 13.1 两个输出面

Resolver/composer 产生两个相互隔离的输出：

1. **Prompt projection**：`visual_direction/color_palette/typography/layout/rendering` 等确定性渲染字段；
2. **Resolution receipt**：身份选择信息，以及 resolver/composer 计算的 `composition_resolution` 与
   `resolved_input_digest`。

**隔离必须是物理的，不能只是概念的（v4.5）**：两个输出面在 deck spec 中必须是**顶层兄弟键**，
收据不得嵌在 prompt projection 的子树内。理由是下游 prompt 组装对 projection 子树做**整体序列化**
（当前实现把 `deck_spec.style` 整个字典转储进每页 prompt 的 Global Style 块，无字段白名单），
因此任何挂在该子树下的字段都会逐字节进入图片 prompt。v4.4 曾把收据放在 `style.resolution`，
在该组装方式下必然违反本节自身的隔离要求——这是本版修订的第一优先项。

由此派生两条硬约束：

- **projection 面是白名单**：只有本节第 1 项列举的确定性渲染字段可进入 `deck_spec.style`。新增
  authored 或治理元数据一律默认在外，需要显式投影才能进入；
- **收据面禁止进入 prompt**：`style_resolution`、catalog digest、readiness、ID、scope、
  `selected_by` 等字段不得出现在任何逐页 prompt 中，由 §14.4 的机械门看护。

若某个组装环节无法逐字段过滤（例如属于 vendored 边界、改动成本高），**正确的解法是调整收据挂载
位置，而不是在下游加过滤**——前者是架构形状问题，后者会把隔离责任推给每一个下游消费者。

`composition_resolution` 逐项冻结实际参与输出的 style、sidecar、rendering、mode、layout、brand、
preset/实际 fallback、component、影响输出的 canon/contracts，以及 composer/validator 版本；每一项记录
`role`、稳定 `id`、`scope`、`digest`、`selected_by`。canon/contracts 只需 versioned 声明身份，不因此
引入完整 axis 富 schema。尚未启用的 L2 角色可以 absent；合同只要求角色一旦参与输出就必须入清单，
不以收据形状提前强制全部 L2 能力。`resolved_input_digest` 是对该规范化组合清单与版本字段的确定性摘要，
不包含原始用户业务文本。治理元数据不直接注入图片 prompt，避免 token 膨胀和输出变化。

### 13.2 冻结到 deck spec

两个面是 deck spec 的**顶层兄弟键**，不是嵌套关系：

```jsonc
// ① prompt projection 面：白名单渲染字段；允许被整体序列化进逐页 prompt
"style": {
  "name": "科研答辩风",
  "visual_direction": "...",
  "color_palette": {},
  "typography": {},
  "layout_patterns": []
},

// ② 收据面：deck spec 顶层键，与 style 平级；禁止进入任何逐页 prompt
"style_resolution": {
  "style_id": "builtin:academic-defense",
  "source_scope": "builtin",
  "catalog_digest": "...",
  "matched_by": "recommendation",
  "match_bucket": "recommendation",
  "variant_master_id": null,
  "selection_reason_codes": ["genre_match", "required_include_satisfied"],
  "recommendation_engine_version": "...",
  "weights_version": "...",
  "composition_resolution": {
    "assets": [
      {"role": "style", "id": "builtin:academic-defense", "scope": "builtin", "digest": "...", "selected_by": "preset_fallback"},
      {"role": "style_sidecar", "id": "builtin:academic-defense", "scope": "builtin", "digest": "...", "selected_by": "style_binding"},
      {"role": "rendering", "id": "rendering:editorial-flat", "scope": "builtin", "digest": "...", "selected_by": "style_binding"},
      {"role": "mode", "id": "mode:claim-evidence", "scope": "builtin", "digest": "...", "selected_by": "preset:presentation-default"},
      {"role": "layout", "id": "layout:P6", "scope": "builtin", "digest": "...", "selected_by": "page_role_route"},
      {"role": "brand", "id": "brand:default", "scope": "builtin", "digest": "...", "selected_by": "scope_default"},
      {"role": "preset", "id": "preset:presentation-default", "scope": "builtin", "digest": "...", "selected_by": "recommendation"},
      {"role": "component", "id": "component:evidence-card", "scope": "builtin", "digest": "...", "selected_by": "page_component_selection"},
      {"role": "canon", "id": "canon:page", "scope": "builtin", "digest": "...", "selected_by": "mandatory_canon"},
      {"role": "contract", "id": "contract:style-brief-v2", "scope": "builtin", "digest": "...", "selected_by": "schema_version"}
    ],
    "fallbacks": [
      {"role": "style", "id": "builtin:academic-defense", "scope": "builtin", "digest": "...", "selected_by": "preset_fallback", "used": true}
    ],
    "composer_version": "...",
    "validator_version": "..."
  },
  "resolved_input_digest": "sha256:..."
}
```

> **迁移注记**：若既有实现已把收据写在 `style.resolution`，该字段是本版的**破坏性变更点**。
> 收据是 L1 新增面（§15），不存在需要长期兼容的历史 deck；因此直接改挂载位置，不引入
> `style.resolution` 的兼容读路径——保留它等于保留一条把收据注入 prompt 的活路径。

同名 user/builtin、alias 命中或 builtin 更新后，历史 deck 仍能解释当时实际解析了哪份组合。若要
精确复现，必须能按收据 digest 找到归档资产或明确报告版本不可得，不能只按当前名称重新解析。

> 收据范围是**身份与内容可复现**，不含精确排序回放：`recommendation_engine_version` / `weights_version`
> 只标注当时引擎与反馈权重版本，不存全量排序快照；收据也不保存用户业务原话——最终选择由人确认，
> 排序回放非目标。

---

## 14. 机械不变量与质量门

> **门的最低生效层级（v4.5）**：本节多数条目依赖尚未建立的能力（收据面属 L2、resolver 属 L1b、
> 收据字段属 L1d）。每条门在其依赖建立之前是**待建门**，既不应被当作失败，也**不得被记为已生效**。
> 实现计划必须为每条门标注最低生效层级；涉及 evidence 的条目在收据面建立前按空集处理（§12.1）。
>
> **可机械判定 ≠ 写在本节（v4.5）**：本节部分条目实际需要人工语义判断，或依赖尚未确定的参数，
> 例如「对应关系合法」「未登记歧义」「只有一个 owner」「实际输入均已入清单」「影响输出的
> canon/contract」「不超过约定预算」「哪个数字算计数」，以及一切需要静态扫描代码属性的条目
> （动态拼接、配置驱动、间接常量都会让扫描退化为启发式）。这些条目**不得因为写在本节就宣称已被
> 机械验证**；实现计划需为它们各自给出可判定的收窄定义，或明确标为人工评审项。
>
> **依赖 CI 的门在 CI 载体存在前不成立**：见 §0.5 条件 4。

### 14.1 Schema / identity

- L0 的现有 brief 合同校验 profile 只增加 `source`/`taxonomy.families` 等地基字段；L1 原子切换后，
  每个 brief 恰好一个可解析的完整 `style-brief-v2` JSON block，不并存第二套长期 schema；
- `style_id` 全局唯一且 immutable；非 style 资产 ID 持久化在 canonical asset 或同位 sidecar，
  不得在运行时持续由 stem/P 码派生；
- `style_name`、文件 slug 与由 ID namespace 派生的 scope 对应关系合法；
- aliases 不与其他 canonical name/alias 产生未登记歧义；
- `variant_of` 存在、无环，且遵守 §4.2 跨 scope 规则（`builtin:` 不得指向 `user:`）；
- deprecated 资产保留可解析 tombstone；声明 `replacement_id` 时目标必须存在且不得形成替换环；
- authored 字段中不存在 computed/readiness 字段。

### 14.2 Reference / composition

- bindings、preset、sidecar、component 引用的 ID 全部存在；
- style 实体包中的 `brief.md` 与可选 `layouts.json` 同包，二者声明的 `style_id` 一致；
- layout capacity/reuse 只有一个 owner；
- preset fallback 无环且最终可解析；
- `composition_resolution` 中所有实际输入均有 ID/scope/digest/selected_by，规范化重算得到同一
  `resolved_input_digest`；
- pool 不被可执行列表或推荐器消费；
- deprecated 资产只可显式解析，不进默认候选。

### 14.3 Catalog / query

- 同一状态元组（canonical + contracts + evidence + `generator_version` + `vocabulary_version` +
  `serialization_profile`，§12.1）重建 byte-identical；序列化 profile 的排序/归一/行尾/数值策略被断言，
  跨平台重建结果一致；
- catalog `source_digest` 与 canonical/contracts 一致，`evidence_digest` 与实际收据集一致；
- builtin bundle 兼容清单同时绑定 canonical assets、contracts、evidence receipts、resolver/runtime 与
  generated set；generated set 单独回滚会被机械门拒绝，外置 artifact refs/digest 必须可核对；
- user canonical 与 catalog generation/source digest 一致；失配可检测、可恢复并在恢复前禁止完整
  semantic query；首次新 writer 发布满足 reader-first 兼容矩阵；
- builtin 与 user 合并优先序、稳定决策桶有正反例，遍历/索引顺序变化不改变桶选择；
- query 的 happy/unknown/ambiguous/error 路径都有 fixture；
- request 的 `data_pages`/`text_density`/`visual_evidence` 分别只映射到
  `data_density_range`/`text_density_levels`/`visual_evidence_levels`，unknown/absent 不被补猜；
- hard rule 不做 I/O，rules 引用的 family ID 全部存在，effects 只能是
  `exclude`/`required_include`/`exclusive_lock`/`prefer`；
- recommendation 结果可追溯到 feature match、rule effect、license policy、baseline eligibility 与
  readiness evidence；
- 每次 semantic query 返回 request-scoped `coverage_state`/summary，且状态与 code 一一对应
  （`partial` → `semantic_coverage_partial`，`insufficient` → `semantic_coverage_insufficient`）；
  `candidates[]` 内每条携带 `enrichment`，使「`name-only` 未参与语义排序」可逐条判定而非靠聚合数推断；
- `coverage_state` 非 `complete` 时 `browse_fallback` 非空；**不存在方向数为 0 且无浏览出口的响应**
  （§8.3 无零出口）；
- 许可门两级各有正反 fixture：**advisory** 级下待澄清条目不进默认推荐但仍可显式点名执行；
  **enforcing** 级下追加不得晋升/执行/进分发子集，且**不从 bundle 兼容闭包中删除文件**；
  user-local 本机使用与 export/共享分别有正反 fixture；用户点名不能绕过对外分发合规门；
- `origin: native` 的资产存在合法 `license` 取值，不会被迫落入 `unknown`（§4.3）；
- `required_include` 满足后仍允许跨家族 MMR；`exclusive_lock` 限制家族时允许 1 个或同家族差异化方向，
  并在放宽多样性/候选不足时分别返回 `diversity_relaxed_by_exclusive_lock` /
  `insufficient_candidates`；
- MMR 与 rule effects 不能被 behavioral boost 绕过；强正样本来源及 append-only 补偿语义可审计。

### 14.4 Agent / docs

- advise 精确查询只需读取 `by-name-alias.md`；
- 任一 facet shard 不超过约定预算；
- **prompt 白名单门（v4.5，最高优先）**：最终逐页 prompt 中不出现 `style_resolution`、catalog digest、
  `resolved_input_digest`、readiness、tier、scope、`selected_by` 等任何收据或治理字段；断言跑在**落盘
  的最终逐页 prompt** 上，不是 compose 层的局部返回（§13.1、§15 退出证据③）；
- **name-keyed 成员表存在性 lint（v4.5）**：family 成员表、alias 表、golden 家族代表表中的每个成员都
  必须解析到真实 brief。这是第 (d) 类耦合（§15）唯一的安全网，缺它则改名会静默把风格挤出推荐资格池；
- **CLI 表面兼容门（v4.5）**：L1b–L1c 期间 `style list`/`load`/`layouts` 等缺省调用输出逐字节不变，
  或差异已列入经批准的 user-visible 变更并记 CHANGELOG；
- 文档计数只出现在生成区或由生成物引用，不在多份 prose 手写；**代码内的帮助文本、常量与注释同受此约束**
  （现状存在把库内条目数硬编码进 CLI help 的既存违例）；
- L1 后 composer、loader、pack/gallery、preview/golden、generator、lint/docs 等身份或路径敏感消费者
  全部经 resolver，CI 拒绝新增直接路径/stem/P 码拼接；**「风格库根」的定位也必须收口到 resolver**
  （现状存在多份独立的根定位实现，含依赖安装布局的上溯逻辑，是最容易漏的旁路）；
- 目录迁移后运行真正的 Markdown 相对链接检查器；
- `scripts/check_references.py` 只用于学术 DOI/参考文献校验，不能冒充 Markdown 链接检查器。

### 14.5 Golden / evidence

- golden roster 选择逻辑不依赖旧顶层目录，**且 roster 与产物路径都不以风格显示名为键**（v4.5）——
  否则改名会让基线全量漂移，且无法区分「改名导致」与「真实渲染回归导致」。该项是 L1 的前置（§15），
  不是 L1 之后的收尾；
- style-level 与 family-representative evidence 明确区分；
- 任一实际输入资产、影响输出的 canon/contract 或 composer/validator 版本变化，只要导致
  `resolved_input_digest` 改变，旧证据自动 stale；
- `not_run`、`failed`、`stale` 不可等价为 false/缺字段；
- verified tier 必须绑定当前完整有效组合 digest，candidate 不得继承 verified 标签或高保障档资格。

---

## 15. 分级落地：先闭合同，再搬目录

| 级别 | 必做内容 | 交付价值 | 明确不做 |
|---|---|---|---|
| **L0 正确性地基（零迁移）** | 计数单一真值 + `--check` 并**退役既有多份并存口径**；按现有 brief 合同的 L0 校验 profile 就地加 `source`（含 `license`）/`taxonomy.families`；别名撞名与 stem 唯一性 lint；**name-keyed 成员表存在性 lint**（§14.4）；pool 与可执行风格的 authored 判别字段（§10.5）；最小 catalog builder（解析+校验+出 counts/name-alias index）；**冻结逐页 prompt 基线 fixture**（L1 退出证据③的前提）；实体仍按名引用 | 消灭计数漂移、来源可查、家族多归属显式化、为 L1 建立安全网与基线 | 不铸 ID、不强制完整 v2、不搬目录、不做 MMR、不开许可 enforcing |
| **L1a 身份地基（加性、可增量）** | 全量铸造 style 与被引用资产稳定 ID，作为**新增字段**写入；ID 全局唯一性 lint 绿；旧 stem 解析仍是权威 | 身份可用，零行为变更 | 不切换解析权威、不改文件形状、不改 `style_name` |
| **L1b 消费者收敛（含唯一的原子步）** | resolver 双读等价（同一输入经 stem 路径与 ID 路径返回同一实体，全库 CI 断言）→ 逐个把 composer、loader、pack/gallery、preview/golden、generator、lint/docs 切到 resolver → **最后一步把「按 stem/编号目录定位」从合法降为 CI ERROR** | 路径与身份解耦 | 不改叶子文件形状 |
| **L1c 叶子成包（单向门）** | 在现有父目录内把每个 style 归一为 `<id-slug>/{brief.md,layouts.json}`；按 §12.2 的 reader-first / writer-second 两次发布完成 | style 成为独立维护与导出单元 | 不搬 canonical 角色父目录、不改 `style_name` |
| **L1d 查询与治理面（允许输出变化）** | 原子切换完整 `style-brief-v2`；builtin/user 两平面；推荐特征合同；typed query；许可 **advisory** 门；`experimental/candidate/deprecated` 基线资格；request-scoped coverage/degradation；硬规则依赖注入；composition resolution 基础收据（未引入的 L2 角色可 absent） | 用户复用与候选推荐真正闭环 | 不要求全库 golden；**不开许可 enforcing 级**（见 §4.3） |
| **L2 组合与证据** | bindings、presets、components、pool promotion、verification receipts、`verified/stale` 证据置信、分面 shards 与 MMR；新增角色一旦参与输出即纳入既有 composition resolution | 高质量组合、可解释准入与长期治理 | 不重新定义 L1 candidate 资格；不强迫一次性补齐全部存量 |
| **L3 物理重构** | 在既有 contracts/evidence/generated 边界上收敛 `canonical/` authored 区；将 L1 已归一化的 style 实体包原字节搬到 `canonical/briefs/<id-slug>/`，按角色搬迁其余 authored assets；重建 Markdown 链接/清单/生成物，退役兼容 adapter 与旧父路径 | source/build 边界清晰、style 可独立维护/导出、编号/来源目录退役 | 不再改叶子文件形状、不迁移消费者、不改变已铸身份或推荐合同 |

> **all-or-nothing 的正确范围（v4.5 修订）**：v4.4 断言「L1 不存在半迁移的合法中间态」，因此把
> 身份铸造、消费者切换、叶子成包与全部查询/治理面压成一个不可分割批次。该论证把「不变量在批次
> **结束时**成立」偷换成「批次**中间**不存在安全态」，并因此产生两处硬冲突：与 §12.2 的 reader-first
> 两次发布互斥，且让字节回归门与同批的许可门互相否证。
>
> 实际只有**一个**步骤是真正 all-or-nothing 的：**把「按 stem 定位」从合法降为 CI ERROR**（L1b 末步）。
> 在此之前，加性铸 ID（L1a）与 resolver 双读等价期都是合法中间态——身份字段已存在但解析权威未变，
> 任一步都可独立回滚。这个真正的原子步成本极低，因为它只翻转一条 lint 规则。
>
> 由此，**字节回归门只适用于 L1a–L1c**：这三步按设计不改变任何输出。**L1d 明确允许输出变化**，
> 因为许可 advisory 门与基线资格会按设计改变候选面与首推面；对 L1d 施加「prompt 逐字节不变」是
> 自相矛盾的要求。L1d 用 typed query / coverage / 许可的正反 fixture 作为退出证据。

> **stem 退役与 L1/L3 唯一边界（v4.4，v4.5 扩充耦合面与退出证据）**：当前实现存在“风格名 =
> 文件 stem = 同名 sidecar = 事实身份”的四位一体耦合。所有 stem-based 定位与身份推导必须与
> `style_id` 铸造在 L1 同批退役，不得留到 L3。L1 在旧角色父目录内完成叶子形状归一化（L1c），
> 拥有“成包”，但**不拥有** `canonical/briefs/` 父目录迁移；L3 只把已归一化的包原字节搬到目标父目录、
> 搬其余角色资产并删除兼容层，禁止再次改变叶子形状或迁移消费者。这条 L1/L3 边界本身不变。

#### 耦合面是四类，不是一类（v4.5）

v4.4 只举了三个点状例子，实际扫描面是四类，其中第四类无法用路径正则发现：

| 类 | 形态 | 迁移含义 |
|---|---|---|
| (a) **name → 路径拼接** | style / rendering / mode / layout / brand / infographic 的按名定位；「风格库根」本身存在多份独立定位实现 | resolver 化必须一并收口根定位，否则留下旁路 |
| (b) **file stem → 事实身份** | 列举接口以 stem 为去重主键；人读配对表以 stem 为行键 | 去重键必须换成 `style_id`，否则改名即改身份 |
| (c) **编号/家族目录名 → 分类与计数语义** | lint 计数口径、路由可达性的组级桥注、家族审计以父目录名为家族 | 这些口径必须先由 authored `taxonomy` 供给（L0） |
| (d) **`style_name` 字符串 → 硬编码成员表** | family 成员表、alias 表、golden 家族代表表 | **最危险且零机检**：改名不会报错，风格会**静默掉出推荐资格池**。路径扫描对它完全无效，必须靠成员存在性 lint |

#### L1 的前置项（必须先于 L1b 末步与 L1c 改名）

以下四项不是 L1 的一部分，而是它的**准入条件**；缺任一项，L1 的退出证据都无法成立：

1. **name-keyed 成员表存在性 lint**（可在 L0 完成）：断言每个成员都能解析到真实 brief。这是第 (d) 类
   耦合唯一的安全网；
2. **人读配对表 owner 迁到 brief `bindings`**（§10.1，原列 L2，**前移为 L1 前置**）：该表同时被 stem
   键与 name 键消费，改名时两侧不可同时满足——要么治理 lint 报大批缺失，要么 composer 查不到而使
   prompt 少一段。owner 收敛后该冲突消失；
3. **golden roster 与产物路径去显示名化**（§14.5）：roster 与缩略图产物目录若继续以顶层目录和风格
   显示名为键，改名会让 `--check` 全量漂移，且无法区分“改名导致”与“真实渲染回归导致”；
4. **CI 载体存在**（§0.5 条件 4）：退出证据①依赖 CI 扫描，无 CI 时它只是一句话。

另有一条贯穿约束：**L1a–L1c 全程不得改动 `style_name` 字符串**。风格显示名会进入最终 prompt，改名
与「prompt 逐字节不变」直接冲突。L1 改的是**路径与文件形状**，不是展示名；确有改名需求时，单独排
一次带 CHANGELOG 的 user-visible 变更，且不与身份迁移同批。

#### 四条硬退出证据及其归属

| # | 证据 | 归属 | 可执行定义 |
|---|---|---|---|
| ① | 无任何消费者按 stem/编号目录定位或推导身份 | L1b 末步 | CI 扫描四类耦合面；第 (d) 类由成员存在性 lint 覆盖 |
| ② | 旧平铺与新叶子包 fixture 均经同一 resolver 成功解析 | L1c | 两套 fixture 同一断言集 |
| ③ | 切换前后**最终逐页图片 prompt 逐字节不变**，且收据字段不出现在 prompt | L1a–L1c（**不适用 L1d**） | N 个**冻结 deck fixture** × M 个**显式点名**风格 × 覆盖旗标矩阵（含 brand / anchor / materialize / layout-lock），逐页 prompt 落盘后 `diff` 为空；显式断言 `style_resolution`/catalog/ID/digest/readiness 不出现在 prompt 文本中。**不能只比较 compose 层的局部返回**；选样集合不得包含会被许可 advisory 门改变可见性的风格 |
| ④ | **CLI 表面兼容**（v4.5 新增） | L1b–L1c | `style list`/`load`/`layouts` 等缺省调用输出逐字节不变，或列出经批准的 user-visible 差异并记 CHANGELOG。v4.4 的三条证据只覆盖 prompt 与 resolver，遗漏了用户直接可见的 CLI 面 |

证据③依赖两个当前不存在的前提：可复用的冻结 `deck_spec` fixture，以及把逐页 prompt 落盘用于比对的
既有入口。落盘入口已存在，fixture 需在 L1a 之前建立并冻结——**基线必须在任何身份改动之前采集**。

### 15.1 为什么 L0 必须有最小生成器

计数、catalog 和索引若要求“不漂移”，就不能同时声称“无生成器”。L0 的最小 builder 只需：

- 按现有 canonical brief 合同解析资产；
- 用 L0 校验 profile 检查 name/alias 唯一性与新增的 `source`/`families` 地基字段；
- 输出 compact catalog、counts 与 name/alias index；
- 支持 `--check`。

> **「单一真值」的真实工作量（v4.5）**：现状并非「没有生成器」，而是**已有多份互不相等的口径**同时
> 存在——不同脚本各自定义「什么算一份可加载 brief」，多个用户可见数字并存于索引、reference 文档与
> CLI 帮助文本中。因此 L0 的任务是**收敛与退役**，不是新增：新建第七份口径只会让漂移更难查。
> 现状已有一个具备派生清单、逐文件摘要、分层 digest、`--compare` 与确定性排序的清单脚本，功能上
> 覆盖了最小 builder 的大部分；实现计划应优先**扩展它**并逐个废止旧口径，同时把散落在 prose 与代码
> 常量中的写死数字改为引用生成物。

L0 profile 只是原合同上的迁移期校验投影，不是第二套长期 schema；它不铸 ID、不要求完整
`style-brief-v2`、不实现推荐器、不迁移目录，因此仍是最小而诚实的零迁移地基。

### 15.2 存量富化策略

- L0 中新增/修改 brief 只需满足现有 brief 合同及 L0 校验 profile；L1 原子切换完成后，新增/修改及
  全量存量 brief 才统一强制完整 `style-brief-v2`（含 `style_id`），并删除 L0 profile 的过渡职责；
- 存量可按命中频率、推荐使用和来源批次渐进富化；
- 缺 recommendation features 的存量只可按名称浏览，不冒充高质量语义推荐；每次 query 的 coverage
  summary 必须把这些 `name-only` 条目计入可达但未参与语义竞争的口径，覆盖不足时按 §8.3 降级；
- 未完成 style-level golden 的资产保持 candidate，仍可默认首推，但不得标成 verified 或进入高保障档；
- 不用批量模板化标签制造虚假完备度。

---

## 16. Owner 边界

| 合同 | Owner | 非 Owner |
|---|---|---|
| brief schema / authored metadata | style library | recommender、index Markdown |
| computed catalog / indexes | catalog generator | 人工编辑 |
| user style files | user store | builtin catalog |
| user source/catalog generation 与 freshness | user store + catalog generator | recommender、旧 catalog |
| user catalog freshness **检测与重建触发** | resolver/store 读路径 | recommender、Agent、各查询消费者 |
| `license` vocabulary 与两级门阈值 | `_contracts/` 词表 + 治理 owner | 硬编码枚举、recommender |
| license policy / approval receipts | provenance governance + validator | relevance/MMR、用户点名 |
| request-scoped coverage/degradation | catalog query + recommendation engine | `counts.md` 全局统计、Agent 猜测 |
| behavioral weights | recommendation state | taxonomy/source |
| hard rule policy | style hard rules | catalog generator |
| family membership | brief taxonomy | hardcoded `FAMILIES` members |
| relevance/MMR | recommendation engine | indexes |
| style/render/layout bindings | brief/sidecar/preset schemas | 手写配对表 |
| path/scope resolution | AssetResolver | 各消费者自行拼路径 |
| composition resolution / resolved input digest | resolver + composer | recommender、indexes |
| verification receipts / readiness | validator + catalog generator | brief 作者、缩略图存在性 |
| prompt projection **白名单** | composer | catalog/indexes、下游 prompt 组装、收据面 |
| deck spec 中收据的**挂载位置** | 本架构 §13.2（顶层兄弟键） | 各下游消费者自行过滤 |
| final choice | user + existing confirmation flow | recommender 自动锁定 |

---

## 17. 风险与明确取舍

> **本节的形式要求（v4.5）**：一条取舍必须写出**代价**与**补偿路径**，而不是论证「结构是必要的」。
> v4.4 的本节 6 条全部是必要性自辩，且漏掉了当时全部未被发现的 P0 级代价——这使它无法作为风险清单
> 使用。以下每条都给出「取舍 / 已知代价 / 补偿」。

1. **复杂度**：三平面与 resolver 增加结构。
   *代价*：抽象层变多，新人理解成本上升；resolver 成为单点，其缺陷会同时影响全部消费者。
   *补偿*：它们属机制层（§0.3 / §18），库小时可长期只用薄 adapter；resolver 的双读等价期（L1b）
   提供了在切换前验证其正确性的窗口。
2. **兼容**：`style_name` 保留，`style_id` 承担稳定身份。
   *代价*：同一实体长期存在两个标识符，文档与人际沟通中容易混用。
   *补偿*：ID 只在机器面出现，用户面继续用名称；L1a–L1c 明确禁止改动显示名（§15），避免两者同时变动。
3. **证据**：不追求全库立刻 verified；candidate 可默认首推。
   *代价*：默认推荐面中存在未经出图强验证的风格，可能出现个别渲染质量问题。
   *补偿*：样张门与人在回路仍在链路上；`verified` 承担加权与高保障档准入，用户在高风险场景仍有更强档位。
4. **目录**：四区分层 + style 实体包，分类只在元数据与 facets 表达。
   *代价*：一次性物理迁移（L3）成本高，且迁移期需要 resolver 屏蔽双形态。
   *补偿*：L1c 已完成叶子成包，L3 只搬父目录且是原字节移动；不把 digest/blob 路径引入人工 authoring。
5. **索引**：候选是查询结果，不再维护全量候选池 Markdown。
   *代价*：失去一个可以直接人读浏览的全量清单。
   *补偿*：facet shards 与 `by-name-alias.md` 承担浏览面，且这是覆盖不足时的强制 fallback（§8.3）。
6. **推荐**：behavioral state 可持续调优。
   *代价*：反馈会引入随时间漂移的排序，历史推荐难以完全复现。
   *补偿*：收据记录引擎与权重版本（§13.2）；排序回放明确不是目标，身份与内容可复现是目标。
7. **许可门（v4.5 新增）**：引入 scope-aware 的许可治理。
   *代价*：这是本架构对现状**杀伤力最大**的单点。`source.license` 当前覆盖率为 0，若一次性开启完整
   fail-closed，可用风格池会瞬间归零（含全部自研内置），高敏场景家族尤其脆弱。
   *补偿*：拆 advisory / enforcing 两级（§4.3），enforcing 以澄清覆盖率为准入且不挂 L1；枚举补
   `native-owned` / `cleared-no-restriction` 使自研与已核验资产有值可填；user-local 本机默认可用。
8. **覆盖降级（v4.5 新增）**：语义覆盖不足时如实降级，不假装全库最优。
   *代价*：用户可能拿到少于 2 个、甚至 0 个**语义排序**方向，体验上不如「总是给三个」。
   *补偿*：响应永不为空——强制附浏览/点名 fallback（§8.3 无零出口），确认门始终有可确认工件。
9. **L1c 单向门（v4.5 新增）**：叶子成包后不可回滚到平铺。
   *代价*：回滚深度只有 1 个版本，跨越 writer 边界后只能 forward-fix。
   *补偿*：reader-first 两次发布把风险前置到只读阶段（§12.2.1）；实现计划须显式选择是否提供降级
   writer，不得默认沉默。
10. **L1 工作量（v4.5 新增）**：身份与消费者收敛无法回避。
    *代价*：耦合面是四类而非一类，其中 name-keyed 成员表零机检；全库 brief 需要字段回填；退出证据
    依赖当前不存在的 CI 载体与 prompt 基线 fixture。
    *补偿*：拆 L1a–L1d 使每步可独立回滚（唯一原子步是翻转一条 lint 规则）；把成员表 lint、配对表
    owner 收敛、golden roster 去显示名化、基线 fixture 全部前置到 L0/L1 前置项。

---

## 18. 非阻断开放项

以下问题可在实现计划中拍板，不改变本架构 owner：

- immutable slug 的首次 mint 规则与保留字（持久化、mint 后 immutable 已锁定）；
- vocabulary 的初始枚举值及版本升级策略，包括 `text_density_levels` / `visual_evidence_levels` 与
  **`license` 的首版取值**（`license` 属 versioned vocabulary、必须能表达自研与已核验无限制，已锁定）；
- 许可 **advisory → enforcing 的准入阈值**与存量回填批次划分（两级门的存在、顺序与各级效力已锁定）；
- `serialization_profile` 的具体取值（排序键、Unicode 归一形式、行尾、数值表示、转义策略；**必须钉死
  且进入重建状态元组**已锁定）；
- 逐页 prompt 基线 fixture 的规模与选样（deck 数 × 风格数 × 覆盖旗标矩阵；「跑在最终逐页 prompt 上、
  不含会被 advisory 门改变可见性的风格」已锁定）；
- 非 style 资产 ID 的「角色 → 载体」映射表（**默认写在 asset 本体、两种载体不可并存**已锁定）；
- L1b–L1c 期间 CLI user-visible 差异的审批口径（差异必须列举并记 CHANGELOG 已锁定）；
- installed runtime 降级扫描的性能预算；
- user catalog 并发/激活实现采用文件锁、CAS、journal 还是原子 generation pointer（成功点、freshness 与
  降级语义已锁定）；
- request-scoped coverage 的分层阈值与离线放量门数值（状态/摘要/reason code 与不冒充全库最优已锁定）；
- license approval receipt 的具体载体与审批系统（默认 fail-closed、scope/owner/有效期与审计要求已锁定）；
- recommendation relevance/MMR 的具体权重（`required_include` / `exclusive_lock` 语义与 reason code 已锁定）；
- 稳定决策桶的规范化细节；
- behavioral 事件 schema、存储和压实方式（强正样本来源及幂等 append-only 补偿语义已锁定）；
- `resolved_input_digest` 的规范化序列化/摘要算法、历史 digest 资产由 release 包、风格包还是项目归档保存；
- builtin bundle 兼容版本格式与 reader 支持窗口；
- deprecated tombstone 的保留时长与 replacement 呈现方式；
- facet shard 的具体 token/条目上限。

这些是实现参数。锁定强度分两级：

- **原则层（不得重新打开）**：JSON brief 单真值、身份与名称/路径解耦且 ID 必须持久化、
  authored/computed/evidence 概念分离、索引 ≠ 推荐、目录只编码角色、candidate 可默认首推但
  verified 标签/高保障档须有证据、硬规则 effect 语义可区分、完整有效组合以 digest 绑定收据与证据、
  **prompt projection 与收据物理隔离且收据不进 prompt**、**降级永不产生零出口响应**、
  **治理门不得以牺牲现状可用能力为代价一次性开启**（后三条为 v4.5 补入）。
- **机制层（方向承诺、非时序承诺；在其 L 级引入，库小时可长期不建；重开实现方式不构成对本架构的
  偏离）**：三平面的物理拆分、完整 resolver 抽象、`asset-registry` 文件与 `_contracts/`/`_evidence/`
  独立目录、typed query CLI、facet shard 与 MMR。

---

## 附：最终北极星

> **风格库不是一棵目录树，而是一组有稳定身份、明确角色、类型化关系和可验证状态的资产。**
> Canonical brief 管 authored 事实，generator 管派生 catalog 与人读索引，resolver 管路径和作用域，
> recommender 管候选排序，evidence 管 readiness，composer 管 prompt 投影，用户与既有样张门管最终
> 选择。任何一层都不得复制另一层真值，也不得用“目录更整齐”替代真实的推荐、验证与可复现性。
