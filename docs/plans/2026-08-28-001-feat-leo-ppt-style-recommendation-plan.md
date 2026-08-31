---
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: spec-brainstorm
execution: code
status: active
created_at: 2026-08-28
title: leo-ppt-generator 模版推荐与用户选择 - Plan
---

# leo-ppt-generator 模版推荐与用户选择 - Plan

## Goal Capsule

- **Objective**：为 generate 路线补上"模版（视觉风格）推荐与用户自主选择"的交互合同：推荐是信号驱动的默认项，选择是低摩擦的 override。
- **Recommended approach**：纯文档合同层实施——新增 `references/style-recommendation.md` 承载推荐/选择/照图/双生合同，workflow 步骤 4/6 与 SKILL.md 首屏钩子挂载，评测沿用自包含 judge 模式；零 runtime 代码改动（`style list`/`style render` 已存在直接复用）。
- **Decision focus**：四式指定的优先序落点（点名 > 参考图 > 推荐）；双生提议制措辞；照图提取的边界（只提视觉系统）。
- **Verification focus**：≥5 新 eval 用例（judge 双向离线自检）+ 3 回归抽样 + 安装副本同步后全绿。
- **Largest risk**：新契约只放 references 深层导致单轮回复失真（质量回路轮实测教训）——SKILL.md 首屏钩子为强制项。

## Product Contract

### Summary

在既有"视觉方向确认"点上叠加模版推荐与选择合同：agent 由内容合同字段驱动给出 2–3 个风格候选与带归因的默认推荐；用户可点名、沿用上次、或给参考图"照图做"；纠结时可升级为样张双生二选一。不新增确认门，全部交互寄生在既有确认序列内。

### Problem Frame

风格库有 136 份可加载风格与六轴路由表，但选择发生时缺交互合同：推荐靠模型即兴（内容合同字段没有显式喂给路由决策）、默认推荐无归因、用户点名/沿用/照图四种指定语义只有两种有路径（点名查索引、沿用自定义风格），"照一张图做"完全没有合同化路径。选视觉是视觉决策，纯文字推荐是盲选；而图片式路线每张图都有真实成本，选错方向的代价是整副重做。

### Key Decisions

- **四块全量纳入本期**（推荐合同、自主选择配套、照图做、样张双生）(session-settled: user-approved — agent 拆分四块后用户全选)。
- **寄生于"视觉方向确认"点，不新增确认门** (session-settled: user-approved — 推荐合同描述内含此约束并被选中；与 deck 方法论 S10 确认经济学一致)。
- **样张双生采用提议制**：agent 侦测到纠结信号后一句话提议（含"多一张图"成本告知），用户点头才出 (session-settled: user-directed — chosen over 仅用户显式要求/高保障档自动：提议权在 agent、决定权在用户，成本可控)。
- **照图做的验证复用既有样张里程碑**：参考图提取的 brief 直接作为选定方向，样张产出时与参考图并排呈现供"像不像"比对，零额外图片成本 (session-settled: user-directed — chosen over 纯复用（比对判据不显式）/方向阶段预览样张（多一轮成本）)。
- **仅覆盖 generate 路线**：direct-editable/upgrade 维持"跟随原稿/冻结原风格"既有合同 (session-settled: user-directed — chosen over 扩展可编辑/全路线：与 upgrade 保真合同冲突)。
- **指定优先序：显式点名 > 参考图 > 推荐** (session-settled: user-approved — 综合确认时用户认可：给了参考图就跳过推荐直行)。

### Requirements

**推荐合同**

- R1. 推荐由内容合同字段驱动：受众保守度、使用场景、数据密度（图表页占比）、行业轴、`LEO_PPT_HOME` 自定义风格（存在同名时优先列为候选），不靠模型即兴。
- R2. 每个候选方向以四行呈现：风格名 / 为什么（信号归因一句）/ 长什么样（网格、主色、图表占比）/ 换它的代价（换风格＝重过样张）。
- R3. 默认推荐必须给出归因句；tie-break 判据为场景匹配 > 受众风险偏好 > 数据密度 > 自定义风格复用。
- R4. 候选清单末行统一给出换法指路：回一个字母锁定默认，或点名任何风格（可要求按行业/气质/场景列出子集）。

**自主选择**

- R5. 用户点名风格时跳过推荐直行：查索引定位文件、读完整 brief、`style render` 注入，风格不存在时列相近候选。
- R6. 用户要求沿用上次时优先读取自定义风格；无保存风格时如实说明并回落到推荐。
- R7. 用户要求自己挑时呈现三视图摘要（行业/气质/场景各列前若干项），禁止一次性倾倒全部 136 项。
- R8. 选择与场景明显错配时（依风格路由表场景轴）劝阻一次；用户坚持即执行，并在 style 合同记录用户选择依据。
- R9. 交付闭环后追加一句可选的沉淀询问（"这套风格要存成自定义风格吗"），不强制、不影响交付状态。

**照图做**

- R10. 用户给风格参考图时跳过推荐直行：提取可复用视觉系统（配色、字重气质、纹理、留白密度），不提取业务正文与个人信息，写成 style brief。
- R11. 参考图 brief 作为选定方向走正常样张流程；样张产出时与参考图并排呈现供比对，用户确认"像"之后才锁定并进入批量。
- R12. 用户给两张参考图时直接进入样张双生（见 R14），不等待纠结信号。

**样张双生**

- R13. agent 侦测到纠结信号（如"拿不准/两个都想要"）时提议一句"各出一张同内容样张二选一"，并告知多一张图片成本；用户点头才执行。
- R14. 双生产出默认方向与最强备选各一张同内容样张，用户二选一；落选方向即弃，不自动追加第三方向。
- R15. 双生选择计入既有样张里程碑确认（一次二选一交互），不构成新的确认点。

### Key Flows

- F0 主推荐流
  - **Trigger**：generate 路线，逐页母版确认后进入视觉方向确认。
  - **Actors**：用户、agent。
  - **Steps**：合同字段 → 路由候选 2–3 个 → 四行呈现 + 默认归因 → 用户回字母/点名/给图/要求浏览 → 锁定方向 → `style render` 注入。
  - **Outcome**：视觉方向确认完成，进入样张。
- F1 点名/沿用流：跳过推荐 → 索引定位或自定义风格读取 →（错配则劝阻一次）→ 锁定。
- F2 照图流：参考图 → 提取 brief → 样张并排比对 → 确认"像" → 锁定（两张参考图时转双生）。
- F3 双生流：纠结信号/双参考图 → 提议（含成本）→ 双样张 → 二选一 → 落选即弃。

### Acceptance Examples

- F1. 推荐带归因
  - **Given** 内容合同为"投资人路演、数据密集、受众保守"
  - **When** 进入视觉方向确认
  - **Then** 默认推荐出现且带信号归因句（如"路演+数据密集→结论先行+克制配色"），候选各含四行要素
  - **Covers** R1 R2 R3
- F2. 点名直行
  - **Given** 用户回复"就用瑞士网格风"
  - **When** agent 处理指定
  - **Then** 不再呈现推荐清单，直接定位风格文件并进入注入；风格不存在时列出相近候选
  - **Covers** R5
- F3. 参考图跳过推荐
  - **Given** 用户提供一张风格参考图
  - **When** 进入视觉方向确认
  - **Then** 跳过推荐，提取视觉系统写 brief；样张产出时参考图与样张并排呈现
  - **Covers** R10 R11
- F4. 双参考图直接双生
  - **Given** 用户提供两张风格参考图
  - **When** 样张阶段到达
  - **Then** 两方向各出一张同内容样张供二选一，不等待纠结信号
  - **Covers** R12 R14
- F5. 错配劝阻一次
  - **Given** 用户为学术答辩点名"蒸汽波风"
  - **When** agent 检测到场景错配
  - **Then** 给一句风险提示；用户坚持后执行且 style 合同记录用户选择依据，不再重复劝阻
  - **Covers** R8
- F6. 纠结提议
  - **Given** 用户对两个候选说"拿不准"
  - **When** agent 侦测到纠结信号
  - **Then** 提议"各出一张同内容样张二选一"并告知多一张图片成本；用户点头才出
  - **Covers** R13
- F7. 沉淀回流一句
  - **Given** deck 交付闭环完成且风格为用户选定或照图提取
  - **When** agent 收尾
  - **Then** 追加一句可选沉淀询问，用户不回应不影响交付状态
  - **Covers** R9

### Success Criteria

- 新增行为评测用例覆盖全部 Acceptance Examples（judge 断言归因在场、点名直行、并排比对、劝阻一次、提议制双生），评测通过且既有 21 用例无回归。

### Scope Boundaries

- 仅 generate 路线；direct-editable/upgrade 的风格语义不在本期（后者与"冻结原风格"保真合同冲突）。
- 不扩充风格库内容，不做风格缩略图 gallery 渲染（图片式路线缩略图即真图，成本另计）。
- 不新增确认门：所有交互寄生于视觉方向确认与样张里程碑。
- "照 deck 做"（既有 PPTX 输入）维持 input-routing 既有分型，仅在推荐流程中给一句指路。

### Outstanding Questions

**Deferred to Planning**

- 推荐信号 → 风格路由的映射落点：新建 `references/style-recommendation.md` 还是扩展 `references/styles/00_索引/风格路由.md`（倾向前者，按需加载纪律）。
- 纠结信号的具体识别词表与"场景明显错配"的判定粒度（风格路由表场景轴 vs 新增映射表）。

### Sources

- `leo-ppt-generator/references/style-library.md` — 136 可加载风格、`style render` 确定性注入、自定义风格保存与同名优先规则（snapshot：本会话 2026-08-28 读取；失效条件：风格库规模或 render 合同变更）。
- `leo-ppt-generator/references/styles/00_索引/风格路由.md` — 内容→四维组合推荐表与气质速查表（三视图摘要的数据来源）。
- `leo-ppt-generator/references/image-deck-workflow.md` 步骤 4 — 既有"提供 2–3 个视觉方向，确认一个"确认点（寄生宿主）。
- `docs/leo-ppt-generator-quality-loop-optimization.md` — 逐页母版工件（推荐发生在母版确认之后的时间锚）。


## Planning Contract

Product Contract unchanged (byte-preserved upstream source slice).

### Key Technical Decisions

- **KTD1 落点选择（Outstanding Q1 裁决）**：推荐合同落新建 `references/style-recommendation.md` 而非扩展 `风格路由.md`——后者是索引/数据面，前者是交互合同面；按需加载纪律下分层更清晰，`风格路由.md` 仅追加"视觉方向确认步骤见 style-recommendation.md"指路半句。
- **KTD2 SKILL.md 首屏钩子（必须）**：不变边界加一条最短钩子（指定优先序 + 照图 + 双生关键词），generate 导航节挂载 reference——质量回路轮已证新契约不上首屏则单轮评测与真实首答必然失真。
- **KTD3 零 runtime 改动**：`leo-ppt style list`/`style render --list-templates` 命令面已存在（cli.py style 子命令），推荐/浏览/点名全部复用；参考图提取由 agent 按 style-library 合同执行（视觉系统提取是判断性工作，不做脚本）。
- **KTD4 纠结信号与错配判定粒度（Outstanding Q2 裁决）**：纠结信号=用户对候选表达犹豫的语句（"拿不准/都想要/再想想"式），不做关键词穷举表（措辞随机性高），由合同描述语义 + eval 用语义组断言；错配判定=风格路由表场景轴的行业×场景行明显冲突，一次劝阻。
- **KTD5 照图提取的单向边界**：从参考图只提取可复用视觉系统（配色/字重气质/纹理/留白密度），业务正文、人脸、可识别标识不提取；提取结果走既有样张里程碑 + 并排比对呈现（AE3），不新增预览样张轮次。

### Implementation Units

### U1. 推荐合同 reference

- **Goal**：承载推荐与选择的完整交互合同（Product Contract R1–R9 的执行细则）。
- **Requirements**：R1 R2 R3 R4 R5 R6 R7 R8 R9。
- **Dependencies**：无。
- **Files**：`leo-ppt-generator/references/style-recommendation.md`（新建）。
- **Approach**：六节——信号映射（合同字段→路由输入，含自定义风格优先）、候选呈现（四行格式+统一换法尾行+tie-break 判据）、指定优先序（点名>参考图>推荐；点名直行/沿用回落/浏览三视图禁倾倒）、冲突劝阻（一次+记录依据）、照图做（提取边界+并入样张里程碑+并排比对）、样张双生（提议制/双参考图直入/落选即弃/计入样张里程碑）。
- **Patterns to follow**：`references/deck-master.md` 的合同文体（判据化、失败路径完备）。
- **Test scenarios**：文档合同——由 U5 eval 覆盖（无独立单测）。
- **Verification**：文件成文且 SKILL.md/workflow 挂载指向它（U2 完成后链接可达）。

### U2. workflow 步骤 4 重写与 SKILL 挂载

- **Goal**：把"提供 2–3 个视觉方向，确认一个"升级为结构化推荐与选择入口。
- **Requirements**：R1 R4 R5 R16（寄生既有确认点）。
- **Dependencies**：U1。
- **Files**：`leo-ppt-generator/references/image-deck-workflow.md`（步骤 4）、`leo-ppt-generator/SKILL.md`（不变边界钩子 + generate 导航挂载）。
- **Approach**：步骤 4 改写为"模版推荐与选择：按 `style-recommendation.md` 执行（信号→候选→默认归因→四行呈现→用户回字母/点名/给图/浏览）"；SKILL.md 不变边界加最短钩子一条；generate 行挂载 reference。
- **Patterns to follow**：质量回路轮的 SKILL.md 钩子文体（一行内说清关键语义）。
- **Test scenarios**：eval 覆盖（U5）；`git diff --check` 干净。
- **Verification**：SKILL.md 含钩子关键词（点名/参考图/双生）；workflow 步骤 4 引用新 reference。

### U3. 照图做路径合同

- **Goal**：参考图→风格 brief 的合同化路径（R10–R12）。
- **Requirements**：R10 R11 R12。
- **Dependencies**：U1。
- **Files**：`leo-ppt-generator/references/style-library.md`（新增"照图做"节）、`leo-ppt-generator/references/input-routing.md`（风格参考指路句）。
- **Approach**：style-library 增节——提取边界（只提视觉系统）、写 brief 进 `deck_spec.style`、样张并排比对呈现、确认"像"后锁定并可沉淀；input-routing 在"风格/素材参考"分支加指路半句。
- **Test scenarios**：eval 覆盖（U5 `style-from-reference-image`）。
- **Verification**：两文件成文；与 U1 的照图节无冲突表述。

### U4. 样张双生合同

- **Goal**：双生的提议制触发与执行细则（R13–R15）。
- **Requirements**：R13 R14 R15。
- **Dependencies**：U1。
- **Files**：`leo-ppt-generator/references/image-deck-workflow.md`（步骤 6 扩展）、`leo-ppt-generator/references/visual-qa.md`（并排比对呈现注记）。
- **Approach**：步骤 6 追加双生条款——侦测纠结信号提议（含"多一张图"成本告知）、双参考图直入、二选一落选即弃、计入既有样张里程碑确认；visual-qa 独立复核节注记参考图并排比对形态。
- **Test scenarios**：eval 覆盖（U5 `dual-sample-proposal`）。
- **Verification**：步骤 6 条款与 R13–R15 一一对应。

### U5. 评测与安装副本同步

- **Goal**：行为验收与回归。
- **Requirements**：Success Criteria（全部 AE）。
- **Dependencies**：U1 U2 U3 U4。
- **Files**：`leo-ppt-generator/evals/cases/{recommend-with-default,user-picks-style,style-from-reference-image,mismatch-warning-once,dual-sample-proposal}.yaml` + `evals/fixtures/scripts/judge_*.py`（5 个自包含）+ `evals/eval.yaml` + `evals/known-issues.md`。
- **Approach**：judge 全部自包含（沙盒单文件教训）、拒绝/提议类断言用语义组正则、good/bad 双向离线自检后上线；`install.sh --host claude --upgrade` 同步安装副本（diff 验证）后跑新用例 + 3 回归抽样（advice-only / execute-keeps-confirmation-gates / master-before-render）。
- **Test scenarios**： Covers AE1.（推荐带归因+四行）Covers AE2.（点名直行）Covers AE3.（参考图并排比对）Covers AE5.（劝阻一次）Covers AE4/AE6.（双参考图直入/纠结提议——合并为 dual-sample-proposal 用例的两断言组）。
- **Verification**：5 新用例全绿 + 3 回归抽样通过 + known-issues 记录。

## Verification Contract

| 命令 | 适用 | 通过信号 |
|---|---|---|
| `cd leo-ppt-generator && skill-up run evals/eval.yaml --include-case-name <新用例>` | U5 五用例逐个或成组 | 全部 PASS |
| `cd leo-ppt-generator && skill-up run evals/eval.yaml --include-case-name advice-only-no-execution,execute-keeps-confirmation-gates,master-before-render`（多次 --include-case-name 形式） | 回归抽样 | 全 PASS（model_gating 除外口径不适用于此三例） |
| `diff leo-ppt-generator/SKILL.md ~/.claude/skills/leo-ppt-generator/SKILL.md` | 同步验证 | 无差异 |
| `git diff --check` | 提交前 | 干净 |

## Definition of Done

- U1–U5 全部落地且 Verification Contract 全绿。
- CHANGELOG.md 同步（user-visible 标注）；known-issues.md 记录本轮 judge 设计。
- 未提交项待用户授权（仓库纪律）。
