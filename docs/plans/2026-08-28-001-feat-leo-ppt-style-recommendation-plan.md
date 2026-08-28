---
artifact_contract: spec-unified-plan/v1
artifact_readiness: requirements-only
product_contract_source: spec-brainstorm
execution: code
status: active
created_at: 2026-08-28
title: leo-ppt-generator 模版推荐与用户选择 - Plan
---

# leo-ppt-generator 模版推荐与用户选择 - Plan

## Goal Capsule

- **Objective**：为 generate 路线补上"模版（视觉风格）推荐与用户自主选择"的交互合同：推荐是信号驱动的默认项，选择是低摩擦的 override。
- **Product authority**：当前会话用户（skill 产品 owner）。
- **Open blockers**：无产品级阻塞；两个实现落点问题推迟到规划（见 Outstanding Questions）。

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
