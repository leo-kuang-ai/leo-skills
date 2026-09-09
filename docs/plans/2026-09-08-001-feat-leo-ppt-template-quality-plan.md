---
title: "PPT 模板系统全量重构与生成质量优化技术方案"
date: 2026-09-08
updated: 2026-09-08
version: 4
type: refactor
status: active
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: spec-plan-bootstrap
execution: code
planning_scope: prelaunch-template-system-rebuild
target_repo: leo-skills
source_revision: a5a60e4bca82eeb239f24f926cb669260c78f83b
source_state: dirty-worktree-reviewed
implementation_status: not-started
review_resolution: six-findings-addressed-in-design
supersedes:
  - docs/plans/2026-09-07-006-leo-ppt-industry-aesthetics-skin-system-plan.md
---

# PPT 模板系统全量重构与生成质量优化技术方案

## Goal Capsule

**结论：利用尚未上线的窗口，整体重组模板资产目录，统一身份、数据模型和所有消费者，并重建从模板质量到实际生成的完整链路。**

本方案不再把物理迁移和稳定 ID 后置，也不为旧路径、旧索引、旧参数或旧 prompt 输出保留长期兼容层。按依赖分批实施，最终只留下一个有效目录、一套当前协议和一条权威解析路径。全量重构指资产和消费链覆盖完整，不等于另建所有工具，更不以删除存量或全库付费出图衡量完成。

**用户明确的前提：** 当前尚未上线；彻底重构优化、采用最佳方案实践，并更新技术方案。整体重组和移除兼容负担来自本次明确指令；文件名、模块拆分和 schema 是本方案的技术建议，不冒称用户逐项验收。

**正式交付：** 全量资产处置账本、目标目录、结构化合同、稳定 ID、统一 resolver 和 catalog、内容治理、双路线编译、主题/图表消费、推荐、真实验证、打包与维护闭环。目录重组和身份解耦必须完成，不能以“后续再做”结项。

**本轮仅更新文档。** 不开始修改运行时代码、移动模板、重写用户目录、付费生成、提交或发布。implementation-ready 表示设计可作为后续实施输入，不表示已实现、已验收或获得外部执行授权。

**验收重点：** 资产无遗漏、消费者不依赖旧路径、选择到产物一致、主题与约束真实生效、精选有视觉证据、新包可独立运行。旧成品保留为历史，新系统不承担旧 run 续跑兼容。

## Product Contract

### 问题与边界

当前目录把通用气质、行业、场景和来源批次混排，身份依赖文件名，brief、版式、HTML、预览、验证分散。继续补索引不能单独解决维护职责、生成投影和质量问题。

范围限定为 leo-ppt-generator/ 的模板资产及源码、脚本、测试、文档、分发消费者。兄弟 Skill、控制台重设计、渠道配置、外部发布不在范围内。事实保真、行业内容规则、样张决策与现有任务状态机保持各自职责。

### Requirements

| ID | 要求 | 验收方向 |
| --- | --- | --- |
| R1 | 全部模板资产进入完整账本，按类型与 owner 管理 | 每项旧资产有处置，无遗漏和无声删除 |
| R2 | 全库结构化迁移、逐项内容审阅、精选修订 | 分开已审阅、草稿、参考、已验证 |
| R3 | 验证绑定修订、路线、依赖和页面范围 | 旧证据不能证明新组合 |
| R4 | 推荐结合任务、执行能力和证据 | 候选有依据，点名优先 |
| R5 | 有效视觉系统完整编译到最终输入 | 不丢约束、不注入治理信息、不改正文 |
| R6 | HTML、图表、字体、几何和质检消费同一主题 | 换肤真实生效，容量和可读性正确 |
| R7 | 新调用统一新协议，用户选择语义和数据保留 | 不长期双轨，不自动改用户文件或旧成品 |
| R8 | 依赖变更精准失效，运行输入冻结 | 新失败不被旧通过掩盖，恢复不混版本 |
| R9 | 本期完成稳定身份、物理重组和全部消费者切换 | 活动代码无旧路径/stem/双真值依赖 |
| R10 | 沿用现有流程入口和样张决策 | 不引入额外审批或平行任务台账 |

### Acceptance Examples

- AE1：风格同时出现在医疗、汇报、浅色视图，磁盘只有一个作者真值；分类变化不改 ID、不移动实体。
- AE2：点名草稿时准确查到并披露缺口；静态条件满足可隔离出样，不能声称已验证或静默换成精选风格。
- AE3：用户同名覆盖后，摘要、预览、主题、绑定、证据都跟随实际用户资产；完整 builtin ID 仍能精确选内置资产。
- AE4：实体改名或移动后，消费者经 registry 定位；同 ID 重复定义拒绝，不按扫描顺序选第一个。
- AE5：深色变体让标题、正文、注释、表格、图例和数据序列同步生效；白字白底、缺字、超容量不能通过。
- AE6：改字体或负面约束使相应证据失效；仅来源备注变化且实际投影/依赖相同，可建立新关联而不重画。
- AE7：旧 PPT、图片、用户素材保持原样；旧 run 协议明确拒绝续跑，材料可显式导入新 run，不改旧记录伪装兼容。
- AE8：转换失败、索引断写或输入漂移时不宣布新库可用；新包不能靠开发机旧目录才能运行。

### 范围清单

本期必须完成全部模板目录及模板领域 schema 整理、稳定 ID、唯一解析/索引、原资产结构化处置及逐项审阅、双路线贯通、首批精选验证、分发切换、旧活动目录清理。

不强制把每个长尾条目变成可执行模板。低质量、信息不足或来源不明的内容必须明确 draft/reference 及原因，不能凑字段或伪造 token 晋升；全量覆盖是每项有处理结论，不是迁移后数量必须等于旧库。

不建设模板市场、通用 token 平台、向量库、独立推荐服务或新任务状态机。不扩大素材采集，不复制兄弟 Skill。未定位的 blueprint/doodle 不作为在库能力或强制恢复对象；找到后按同一准入规则处理。

## Planning Contract

### 1. 决策来源与单一入口

本文 v4 是本次模板系统重构的唯一实施入口，保留 v3 六项审查修订，并逐节实质吸收行业皮肤方案的设计、资产与验收。用户“尚未上线、彻底重构”的新指令取代 v1 的渐进兼容安排；旧架构的冻结流程不再构成预发布重构的外部门禁。技术不变量仍须由本文验证合同证明。

| 文档 | 当前定位与处理 |
| --- | --- |
| [已完成索引方案](2026-09-05-002-feat-leo-ppt-engineering-optimization-plan.md) | 历史依据；复用发现、摘要和原子构建逻辑，不保持旧路径/输出协议 |
| [行业皮肤方案](2026-09-07-006-leo-ppt-industry-aesthetics-skin-system-plan.md) | 设计与任务已逐节吸收至 §8.1–8.4、行业视觉验收和 U1/U3/U4/U5/U6/U7/U9；处置表见附录，不独立执行 |
| [20 行业内容评测](2026-09-07-005-leo-ppt-20-industries-content-quality-evaluation-plan.md) | 独立内容 owner；复用任务定义，保持停在样张前边界 |
| [旧目标架构](../leo-ppt-generator/architecture/style-library-target-architecture.md) | 历史参考；沿用身份/真值分层原则，目录、JSON 合同与实施条件以本文为准 |
| [旧目录迁移方案](2026-09-02-001-refactor-leo-ppt-style-library-restructure-plan.md) | superseded 历史文档，不执行 |

“最佳方案实践”具体为结构化数据、单一真值、显式依赖、确定性构建、分层证据、内容驱动版式和实测验收，不是未经验证的外部产品排名。未复核的行业统计和合成专家观点不作为当前事实。

### 2. 当前基线与复用 owner

基线来自本会话 2026-09-08 的实际检查。HEAD 见元数据，工作区有并行修改；U1 必须按实际文件 hash 冻结，不只记录 commit。

| 项目 | 观察事实 | 影响 |
| --- | --- | --- |
| 旧 styles 源资产 | 597：style 311、layout 47、axis 151、rule 10、pool 7、reference 70、unknown 1 | 全量对账，初始分类不是最终质量结论 |
| 普通风格 | 311，独立非变体 294，摘要全部 full | 字段覆盖不代表优秀 |
| 负面约束 | 318 brief 中 124 份不足三条 | 按真实风险修订，不凑条数 |
| token | 311 份无 token_sidecar，7 份字符串，无结构化对象 | 不假定已有完整主题 |
| 版式 | 36 全局版式、11 风格路由 | 统一身份、容量和实际 renderer 支持 |
| HTML | 七模板未消费主题全局变量 | 全部重构真实换肤 |
| 画廊 | 22 个有封面的目录，脚本名单 19 个 | 逐项判来源、覆盖和价值 |
| 样张 | 手绘白板页显示规则文本；星月夜无笔触 | 旧图不能作新风格还原证明 |
| 静态检查 | brief/索引/治理/七 HTML 通过，网格三项豁免 | 只证明旧合同，不证明重构完成 |

unknown 是带占位 JSON 的作者模板，迁入 governance/authoring。上一轮索引检查用项目虚拟环境解决系统 Python 缺 jsonschema；未做全库视觉验收或本方案实现测试。

源码 owner 位于 leo-ppt-generator/runtime/src/leo_ppt_generator/：styles.py、templates.py、layout_bank.py、image_deck/adapter.py、application/sample_decisions.py、render/ 下 page/chart/fonts/assets/provenance/receipt。脚本 owner 位于 leo-ppt-generator/scripts/：capability_manifest、suggest_layout、lint、intake、pack、gallery 等。保留有效逻辑，移除被替代的名称递归扫描、同名 sidecar 及 Markdown JSON 正则解析。

新增 asset_resolver.py 统一路径/身份，新增 style_validation.py 管证据适用性。二者不接管内容规则、推荐政策或任务状态机。

### Key Technical Decisions

| ID | 决策 | 理由 |
| --- | --- | --- |
| KTD1 | 全量重组，最终只支持新协议 | 无上线兼容负担 |
| KTD2 | template-library 五区 | 正式、参考、治理、索引、证据分开 |
| KTD3 | 作者真值使用纯 JSON | 标准解析与 schema 直接验证，消除 MD 嵌入 JSON 双义 |
| KTD4 | 类型化稳定 ID，路径/名称为属性 | 移动与分类不破坏绑定 |
| KTD5 | theme 独占 token，layout 独占几何 | 避免 brief/theme/HTML 三份真值 |
| KTD6 | 一个 resolver、一个 builder | 替代重复实现，不增常驻服务 |
| KTD7 | 两路线共享解析输入、分别编译 | 统一设计来源，保留执行差异 |
| KTD8 | 全库逐项审阅，精选真实验证 | 全量治理与付费成本分开 |
| KTD9 | 质量由证据派生，精选由真实维护者记录 | 文件存在与模型评分不等于优秀 |
| KTD10 | 新 run 冻结新协议依赖，旧 run 只读 | 保留数据，不续跑旧状态协议 |

### 3. 本期目标目录

下面结构必须在本次实施完成，不能作为后续愿景。

~~~text
leo-ppt-generator/
├── SKILL.md
├── references/                       # 流程说明，引用新库，不存模板真值
├── template-library/
│   ├── library.json                  # 库版本与分区声明，不手填成员表
│   ├── canonical/
│   │   ├── styles/<slug>/
│   │   │   ├── brief.json            # 身份、适用性、指令、绑定
│   │   │   └── README.md             # 可选设计理由，不复制机器字段
│   │   ├── themes/<slug>/theme.json  # 语义色、字体角色、形状、明暗变体
│   │   ├── layouts/<slug>/layout.json # slot、容量、几何、renderer 绑定
│   │   ├── templates/<slug>/
│   │   │   ├── template.json         # 输入、主题角色、slot、依赖
│   │   │   └── page.html             # 可含相邻 CSS/JS，依赖须声明
│   │   ├── components/<slug>/       # 可复用数据组件与图元合同
│   │   ├── axes/                    # 论证、渲染语言、图表语法、页面语义
│   │   ├── brands/<slug>/brand.json
│   │   ├── presets/<slug>/preset.json
│   │   ├── fonts/<slug>/            # manifest、字重文件、许可证
│   │   └── ornaments/<slug>/        # manifest 与静态装饰
│   ├── reference/
│   │   ├── sources/<source>/<snapshot>/
│   │   ├── candidates/
│   │   ├── pools/
│   │   └── historical-gallery/
│   ├── governance/
│   │   ├── schemas/                 # 模板领域 schema 唯一源
│   │   ├── vocabularies/
│   │   ├── rules/                   # 行业规则、设计 canon、质量规则
│   │   ├── authoring/
│   │   ├── curation.json            # 精选政策，不写自报 pass
│   │   └── migration/               # 全量映射、处置、核验记录
│   ├── catalog/                     # 自动生成、可完整重建
│   │   ├── registry.json
│   │   ├── catalog.json
│   │   ├── build-manifest.json
│   │   └── views/
│   └── evidence/<validation-id>/    # 不可变 input/output/review/manifest
├── assets/render-vendor/             # 第三方执行引擎，不是模板知识
├── runtime/src/leo_ppt_generator/
├── scripts/
└── tests/
~~~

在此前四区概念上单列 evidence 第五区，避免验证记录混进作者真值或被 catalog 重建删除。reference 是上游/未转化资料，evidence 是本系统的实际验证，不能合并。风格引用共享 theme/layout/font 和证据，不把依赖复制到每个实体包。

模板领域 schema 从旧 runtime/schemas 迁入 governance/schemas；非模板的配置/状态 schema 保持原 owner。代码用统一 library 根加载 schema，不保留人工同名副本。用户素材库 ${LEO_PPT_HOME}/library/ 仍属于 library_catalog.py，不与模板库混数据。

### 4. 完整迁移映射

| 当前来源（包内） | 新库目标 | 处理 |
| --- | --- | --- |
| references/styles 顶层 11 brief | canonical/styles | 分配 ID、提取主题、保留名称/别名语义 |
| 01 通用、02 行业、03 场景 | styles 或 reference/candidates | 逐项审阅，分类改多值字段 |
| 04/05/15/16 来源目录 | styles/components/reference | 按实体真实角色，不按来源目录猜类型 |
| 06 论证、07 信息图、08 渲染、09 结构、11 图表、13 页面语义 | canonical/axes 或 governance/rules | 显式 manifest 和正文引用，去掉标题嗅探 |
| 12 版式库 MD + 36 sidecar | canonical/layouts | 合并几何真值，P1–P36 为别名，绑定用 ID |
| 顶层 11 .layouts.json | brief.bindings.layout_routes | 薄路由内聚；容量因子归实际 profile |
| 10 品牌身份 | canonical/brands | 保留核验状态，不冒称官方 VI |
| 14 参考池及其他 pool | reference/pools | 不再作为一个风格整体执行 |
| 00 索引 | governance/authoring/catalog | 逐文件分流，去掉手工计数与成员双真值 |
| _content_rules.md | governance/rules/domains | 规则含义不变，任务 domain 显式关联 |
| references/style-presets.* | canonical/presets + 生成说明 | JSON 唯一作者源 |
| assets/render-templates | canonical/templates | 七模板全部切换主题与输入合同 |
| assets/render-fonts | canonical/fonts | 字重、覆盖、许可独立登记 |
| samples/style-gallery 与相关 reference-golden | reference/historical-gallery 或 sources | 原件保留，不赋予新验证资格 |
| references/styles/generated | catalog 重建 | 不将旧派生文件当真值 |
| 模板相关 runtime schema | governance/schemas | 所有校验者同批切换 |

U1 补齐表外实际资产，不能以覆盖常见目录代替逐文件盘点。全量账本记录原路径/hash/角色/owner、目标 ID/路径/处置、内容差异、依赖变更、审阅与验证。处置为转换、原样迁移、并入、转参考、删除可重建产物；并入列清所有源与依据，上游原件和用户数据不得无声删除。

### 5. 结构化实体与稳定身份

#### 5.1 ID 与修订

asset_id 使用 <scope>:<kind>:<immutable-slug>，如 builtin:style:clean-professional、builtin:layout:system-diagram。首次迁移一次分配并登记，不从当前名称/路径/hash 动态生成。目录名默认易读但不做主键；名字、别名、分类和存储位置变化不改 ID。

内容修订由规范 JSON 及声明依赖 hash 计算。variant_of、presets、bindings 和收据都引用 ID；重复 ID、坏引用和循环拒绝。builtin 不依赖 user，变体不自动继承质量通过。

user:<kind>:<slug> 在当前 home 唯一；有效身份为 (origin_scope, asset_id)，origin_scope 由可信库根派生，manifest 不能自行冒充 builtin。导入内置包到用户空间时记录 upstream_asset_id 并生成/核对 user ID；同 ID 冲突拒绝。

名称查询保持用户同名优先，完整 ID 查询保持精确；别名多命中完整消歧，不自动挑第一个。新用户库为 ${LEO_PPT_HOME}/template-library/，旧用户 styles 只作为显式离线导入源，不自动搬动。

#### 5.2 唯一真值与最低字段

| 实体 | 作者职责 | 不拥有 |
| --- | --- | --- |
| brief.json | ID、name、aliases、lifecycle、source、taxonomy、recommendation_features、视觉语言、约束、bindings | 精确色板、字体文件、几何、通过状态 |
| theme.json | ID、mode、语义色、字体角色、形状与装饰引用 | 正文、行业义务、slot 几何/容量 |
| layout.json | ID、page_role、slot/容量、几何 profile、节奏、renderer bindings | 风格配色、业务内容 |
| template.json | ID、输入 schema、slot 到 DOM、theme role、依赖 | 第二份几何规则和硬编码风格 |
| axis manifest | ID/kind、正文引用、适用限制 | 另一份风格身份 |
| curation | 维护者选择、任务范围、暂停理由 | 自报 visual.pass |
| evidence | 输入输出、检查、评审、版本关系 | 作者事实或任务接受状态 |

新 style-brief-v2、render-theme-v1、layout/template 等 schema 在治理区唯一维护，封闭字段、版本明确。JSON Schema 管结构；语义校验管引用图/scope/角色；真实验证管结果，不能互相替代。

lifecycle=draft/active/retired 只表示作者状态。active 满足结构与静态执行资格，但不等于精选。无法可靠提取主题的旧 brief 保留原件与 adaptation_gaps，明确 draft/reference，不猜第一个 HEX 或默认字体来凑完成率。

theme 是精确颜色与字体唯一源：image 编译成视觉语言，HTML 编译成角色 token。HTML 需要真实字体文件/字重，image 可以只描述字族气质；lane 资格独立，不能把一个适配器的证据外推给另一个。

行业规则按任务 domain 装载，用户换艺术风也继续生效，不借迁移改法规含义。unknown 许可只表示未核验；字体/图片是否可分发按依赖自身证据判断，不能用风格的标签代替所有素材权利。

### 6. 唯一解析与确定性目录

新增 asset_resolver.py 统一身份、路径、scope、依赖和 revision；styles.py 保留语义入口并委托它。templates/layout_bank/render/intake/pack/lint 都消费 registry，不各自递归扫描名称或拼编号目录。

根定位沿用 LEO_PPT_BUNDLE、安装标记和仓内入口，但只认新库 library.json。路径必须在显式可信根内，拒绝 traversal、符号链接越界、类型错误和用户冒充。resolver 不推荐风格、不决定行业规则、不持久化任务。

capability_manifest.py 是唯一 builder，生成同一 generation 的 registry/catalog/views。不存在 v1+quality 扩展双接口，缺字段不假装旧兼容。用户 overlay 本地合并，不回写内置 catalog。

摘要覆盖 canonical、schema/词表/规则、curation、完整已发布 evidence 集合与依赖；不包含 catalog 自身。证据集合不能只取旧 catalog 已引用的记录。reference 正文不参加执行根摘要，单独 reference inventory 供浏览；真正采用的参考图进入执行依赖指纹。

build-manifest 分开记录 source/dependency/evidence/policy digest 和输出 hash。构建前后输入变化则中止；临时目录完整校验后原子发布。读到陈旧质量为 stale/unknown，空证据为零已验证，损坏/权限错误明确诊断。

物理发布采用 `catalog/generations/<generation-id>/` 保存不可变的 registry/catalog/views/build-manifest，`catalog/current.json` 为唯一原子替换的指针。上方目录树表示该代的逻辑文件。reader 一次读取指针并固定 generation，不能逐文件重读 current；构建锁覆盖输入校验到指针切换，进程中断留下的未引用 generation 不视为发布。相同输入的产物内容一致，时间戳等运行信息不进入确定性摘要。读取已发布代后若源发生变化，执行前重新校验依赖并冻结快照，不能用构建锁冒充全程输入不变。

resolver 最小接口为 `lookup(query, scope, kind)`、`resolve(asset_id, context)` 和 `resolve_dependencies(asset_id)`：lookup 返回全部命中和消歧信息；resolve 返回实际 ID、可信根、类型、相对路径、revision、依赖与当前资格。失败使用稳定 reason code，如 `ambiguous_name`、`duplicate_id`、`dependency_missing`、`unsupported_schema`、`scope_violation`、`stale_catalog`，CLI 展示层负责中文说明。执行资格和推荐排序由各自 owner 消费解析结果，不塞入路径解析器。

execute 缺索引可从新 canonical 只读重建内存视图，不改安装目录；advise 只看有界生成摘要，缺失则披露。生成源失败不能回退旧树。

**F1：证据新鲜度独立于 catalog 发布。** `style_validation.py` 枚举每个有效库根下全部已发布验证 manifest 与 `evidence/revocations/` 中的不可变撤销记录，按相对路径和文件 hash 计算 `evidence_set_digest`，包含尚未被 catalog 引用的新失败。revocations 和 staging 是保留目录名，validation_id 不得占用。撤销记录引用验证 ID、范围和原因，不修改或删除原证据。staging 不参加集合；正式目录内坏 manifest、缺文件、重复 ID 或集合不可读均报告完整性错误，不当作空集合。

每次质量查询比较真实集合摘要与 catalog 的摘要，不能只信旧指针或目录 mtime。读取前后集合变化则有界重读；仍不稳定时返回 `quality_unavailable`。不一致时，advise 撤下该失配库根贡献的 verified/精选标签并披露陈旧，可继续浏览静态候选；execute 由同一质量 owner 只读重算当前资格。重算后的失败只影响实际关联组合，未知状态不能进入要求验证的路线。注册表未变化不能豁免质量重算。

证据发布与撤销 writer 复用库级锁；样张接受及成功收据写入前重新核对质量摘要和冻结依赖，变化则重新判断当前组合，不用过期资格成功落账。验收固定交错：E1 通过已入索引 → E2 同组合失败落盘 → catalog 发布失败 → 新查询不得返回旧 verified；另测撤销、删除、权限错误以及读取中发布。该机制由 U2 实现，U6 消费，U7 故障验收。

当前 wheel 依赖完整 Skill bundle。新分发继续 bundle + 受管 runtime，不复制作者库进 wheel；脱离 bundle 明确 library_missing。安装核验库/schema/runtime 版本，不靠开发目录 fallback 掩盖漏包。

### 7. 统一设计输入与双路线编译

~~~mermaid
flowchart TD
    A[任务合同与行业规则] --> B[合格候选与用户选择]
    C[注册表及当前质量视图] --> B
    B --> D[实际 ID 与完整依赖解析]
    D --> E[内容到 slot 与有效几何]
    E --> F[冻结 resolved_design]
    F --> G{选定路线}
    G --> H[图像 prompt 编译]
    G --> I[HTML 与图表主题编译]
    H --> J[样张与既有决策]
    I --> J
    J --> K[逐页生成和检查]
    K --> L[PPTX 全稿核验与收据]
    L --> M[脱敏证据登记]
    M --> C
~~~

resolved_design 是现有 deck/run 工程记录中的唯一编译输入，含资产/依赖 revision、主题变体、页型/layout/template、字体/参考资料、生成条件和编译器版本。不新增平行台账。prompt 和 HTML data 是投影，不携带治理分数、许可路径或目录元数据。

#### 7.0 统一组合合同（F3）

`templates.py` 承担设计组合 owner，调用 resolver、质量 owner 和 theme 编译器；`resolved-design-v1.schema.json` 归 governance/schemas。图像与 HTML 适配器不得各自重新选择风格、合并品牌或读取最新主题。style 的 variant_of 是关系元数据，不隐式继承字段；正式变体必须有完整 brief 和明确主题绑定，避免隐藏继承链。

| 阶段 | 确定规则 | 禁止行为 |
| --- | --- | --- |
| 选择 | 名称查找先完成用户覆盖/消歧；preset 只提供未指定的 style/theme/mode/layout 默认 ID，任务显式选择替换同一选择器 | 不把用户与内置同名 brief 逐字段拼接，不让 preset 改正文 |
| 基础主题 | 选定 style 的默认 theme；显式 theme 可替换，但必须满足风格及模板的必需角色、lane 与约束 | 不通过浅合并把两个主题拼成缺角色的对象 |
| 明暗变体 | 对选定 theme 应用其声明的 mode；未指定用主题默认，未知 mode 拒绝 | 不猜相近变体，不跨主题借 mode |
| 品牌 | 在当前 mode 上应用 brand 声明且获主题允许的色彩/字体/装饰角色 | 不改正文、数字、几何、容量或删除可读性约束 |
| 任务视觉覆盖 | 最后应用任务显式视觉角色值，仅限 theme 声明的 overrideable_roles；品牌 locked_roles 不得改 | 不用“最后写入优先”绕过品牌锁或设计硬限制 |
| 页面解析 | 页级显式 layout 优先于 preset 页型路由，再用 style 路由；校验实际 renderer 和内容容量 | 不按模板同名猜绑定，不做隐式页级换主题 |
| 最终校验 | 校验角色完整性、字体、对比度、lane、布局和约束；记录每项有效值来源并冻结 | 不让执行适配器自行补颜色、字体或删除冲突约束 |

覆盖均是 schema 白名单叶子路径的赋值；未出现的键保持原值，null 非删除指令且非法；数组整体替换并验证元素，不按位置合并。主题必需角色不能删除。数据序列色、字体 fallback 等数组可整体替换；行业、品牌和布局硬约束另按稳定约束 ID 合取，重复同义约束去重，矛盾即 `design_constraint_conflict`，不允许覆盖数组清除硬限制。散文建议只用于设计说明，不能改变结构化真值。字体角色在 theme 中拥有 family/weight/size/line_height；所有空间尺寸归 layout。

组合实例：用户按名称选择同名风格，实际解析为 user 风格；preset 默认 light、任务指定 dark，则选该 user 风格绑定主题的 dark。其背景为 #111111、正文为 #FFFFFF；brand 将强调色设为 #00A6A6 并锁定该角色，任务可把未锁定的 muted 设为 #B8B8B8，但试图把强调色改红则失败。页级指定三列规格表，绑定到对应 HTML 模板。两适配器得到同一份上述有效值、字体角色、布局及冻结正文，不再访问 preset/brand 的活动文件；HTML 用精确值，image 将相同值编译为指令，不因此声称像素精确还原。

冻结记录的最小字段为 schema_version、实际选择 ID/revision、effective_theme、effective_constraints、pages 中的 content_ref/layout_id/profile_id/template_id/slots、依赖清单及其 hash、编译器版本和 source_map。正文引用必须指向 run 内不可变副本，字体/模板等执行依赖同样快照化。规范序列化按固定键序、UTF-8、保留数组次序并拒绝 NaN/Infinity；`design_digest` 覆盖实际有效值、正文、依赖和编译器，不包含时间、绝对路径及其自身。`source_map` 与审阅治理记录不进入视觉投影；另存 authored digest 供归因。U9 定义 schema，U4 实现组合，U5 消费；双适配器输入 hash 一致、覆盖正反例和同输入确定性属于硬验收。

#### 7.1 图像路线

所有新任务使用当前唯一 compose_style 合同，删除 legacy 输出分支。有效主题、canvas、视觉语言、页型、允许/禁止元素、负面约束和本页构图完整注入，不倾倒整库蓝图。

正文来自冻结母版，主题负责颜色/排印，layout 负责语义关系。品牌覆盖仅作用于定义的视觉角色并重新校验。结构冲突拒绝，散文冲突通过母版/样张审阅明确处理，不静默删约束。

去重不能截断正文或关键条件；预算不足则改写设计指令或拆页。最终每页检查必需文字不变、约束有效、出处/规则编号未成为图上正文。

终点是包内 runtime/src/leo_ppt_generator/_vendor/codex_ppt/prepare_slide_prompts.py 的最终 prompt。优先在 adapter/组合器改表示；必要 vendor 改动同步 patches/ 和 scripts/sync_upstreams.py，不仅修改投射副本。

#### 7.2 HTML 与图表路线

七模板全部消费主题和 layout profile。标题、正文、注释、表格、背景、边框、图表序列和状态色都来自角色绑定，不再固定商务纸色/字体。

render/theme.py 只处理校验、覆盖、角色解析；page/chart 接收同一 effective theme，Mermaid 通过显式适配表转换。layout.json 唯一拥有几何，template 把逻辑 slot 映射 DOM；字体、字号、行高、边距变化重算容量。

**F4：版式数据到页面的可执行边界。** 本期统一逻辑画布 1280×720，空间值为逻辑 px，导出 2560×1440 只改变采样倍率。`layout-profile-v1.schema.json` 的 profile 必须声明 canvas、具名 slot、布局类型、区域 x/y/width/height、padding/gap、内容 cardinality 及 renderer 支持。首批布局类型限定为固定区域、行/列堆叠、网格和表格，不能塞任意 CSS 表达式代替合同。流式区域按容器剩余空间求解，坐标越界、负尺寸、循环依赖均拒绝；字号/行高从 effective_theme 引用，不再写一份。

`template.json` 定义稳定 slot 到 DOM selector 的一对一绑定。新增 `render/layout.py` 只把已校验 profile 编译为几何 CSS 变量、网格 track 和 slot 样式，不重选布局；HTML 保留 DOM 结构与主题角色样式，禁止自有列宽、区域 padding/gap 等拥有真值的字面量。reset 等非设计几何规则列入明确白名单；lint 加实际 DOM 比对，不能只靠 grep 判断消费。

规格表示例合同：三列 profile 的内容区为 x=90、y=170、width=1100、height=470，列权重为 30/45/25，单元格 padding 为纵向 15、横向 18；表头与单元格字号/行高分别引用主题 table_header/table_body。输入列数必须等于 profile 列数；2、4、5、6 列使用各自声明的权重 profile，未声明则报不支持，不能把三列比例硬套任意列数。示例数值是待校验的设计起点，不是已测容量。

容量先按真实列宽扣除 padding，等待字体加载后测量换行与每行最高单元格，累计表头、行高、边框和 gap 与可用高度比较；字符数和条数仅作预筛。最小可用字号由主题角色及可读性规则共同限制，不能通过字体缩小或图表整体缩放绕过硬超。超容量返回具体 slot、需要/可用空间，由内容规划重新分配到已声明布局或拆页，并重新冻结设计。图像路线使用同一结构描述与容量约束，但结果仍需图像核验，不能把 DOM 测量当作图像通过证据。

U5 先以规格表完成纵向验证：只修改 JSON 列权重 30/45/25 → 25/50/25、padding 15 → 12，HTML 源码不变；实际列宽分别匹配 275/550/275，误差最多 1 逻辑 px，文字布局及容量检查随之变化。另用固定临界文本证明增大字体后重新计算、硬超拒绝；覆盖动态列数和 DOM 绑定缺失。通过后将相同机制推广至七模板，U9 提供合同，U7 复验。

36 个 P 码不等于 36 个 HTML 模板。每布局声明实际 image/html 支持，未实现 HTML 时明确报缺，不能套 body-basic 冒充。七模板为 cover-basic、body-basic、compare、timeline、spec-table、pull-quote、frame-shot，迁移后使用类型化 ID。

首批任务确需 KPI/矩阵且现有结构不能表达时，组件、输入、layout、容量和验证同批新增，不凭相近名称绑定。图表和页面保持数字/单位/标签一致。

字体 manifest 列文件、字重、覆盖、许可；缺字/缺重/加载失败显式处理并重验，不随机依赖系统字体。普通文字对比至少 4.5:1，符合条件的大文字和信息标记至少 3:1；透明/图案背景按实际承载面验证。必查角色由模板定义，主题不能删项。

容量估算、DOM/字体/可见性、像素与文字核验分层。硬超不缩字号兜底。文件大小只是异常信号；BLANK-01/CONT-01 不是 WCAG 或事实完整性，按 lane 用正常/缺陷样本校准，不临时调低门槛。

#### 7.3 可执行模板信任边界（F2）

JSON 风格/主题属于数据；HTML/JS、CSS 外部引用和 SVG 活动内容属于执行面。导入包的 hash 只证明完整性，scope 只证明来源空间，二者都不授予代码执行资格。内置代码绑定受管 bundle 的代码摘要；用户导入可执行模板默认进入 reference/candidates 隔离区，可浏览、静态检查和转换，不能自动出样。采用为可执行模板需经实际代码审阅并由本地维护记录绑定模板及全部代码依赖摘要；沿用任务授权记录真实操作者，不能用包内自报 trusted 或模型伪造人工认可。代码或依赖变化后重新审阅。

U5 改造浏览器及本地资产服务：只暴露本次冻结依赖的 URL 到文件白名单，不暴露整个库目录；请求校验拒绝 traversal、越界符号链接和未声明资源。浏览器只允许当前资产服务的精确 origin 与白名单资源，阻断外网、其他回环地址、重定向逃逸、WebSocket、弹窗和下载，禁止 Service Worker。服务端 CSP 禁止连接、子框架、对象与表单，脚本只允许已审阅依赖及固定注入脚本；禁用 WebRTC，浏览器保留 sandbox，不能以 `--no-sandbox` 换取运行。策略安装必须先于导航和数据注入，超时或违例使当前页失败并清理上下文。浏览器隔离不宣称能安全运行任意恶意代码，未审阅代码仍不得执行。

正文用 textContent 等文本 API 注入。SVG 通过结构化解析的元素/属性允许集处理，拒绝脚本、事件、foreignObject、外部 href、CSS import/url 和实体扩展；Mermaid 使用严格模式，不把任意输入直接交给 innerHTML。本期图表只接纳此静态 SVG 子集，不支持的输出明确失败，不静默删标签或图表；需要外部图片时先作为获授权的本地资产规范化。字体、装饰与截图也通过冻结白名单供给。

U8 负责导入隔离与审阅记录，U5 负责执行限制。U7 植入读取正文后外发、请求其他本地端口、恶意 SVG、越界资源及修改已审阅 JS 的用例：未审阅模板在注入前被拒；已采用模板出现上述行为时请求不离开允许边界、页面失败；正常离线字体/图表/图片必须仍可渲染。

### 8. 全库内容优化与推荐

每份原 brief 都需处置审阅：保留、修订、并入、draft 或 reference，并记录理由。自动机械转换不能代替逐项语义审查。intake 拥有的生成资产从其映射修订，原来源保真归档。

| 维度 | 精选标准 |
| --- | --- |
| 适用性 | 明确任务/受众/密度/环境及反例 |
| 可辨识 | 至少两个可观察构图/排印/材质特征 |
| 构图 | 关系、顺序、主视觉、占比具体，不只是章节名 |
| 主题 | 色彩/字体唯一且可执行，无冲突散文值 |
| 数据 | 数字、单位、图例、来源、不确定性有合适载体 |
| 负面约束 | 针对真实失败、可观察，不凑模板话术 |
| 连续性 | 封面/内容/数据/结尾各有纪律，不全套重复封面 |
| 可维护 | 来源、许可、owner、依赖、影响明确 |

同色板只作相似诊断，不能自动并身份；不同色也可能是同系统变体，不能改一个 HEX 绕门。首批九方向：管理、咨询、科技、金融、医疗、教育、政务、品牌、学术；保留旧皮肤方案的八类种子并补齐主方案的管理方向，初始最多 12 个逻辑风格控制验证成本，不限制全库合格资产。

可检索、静态可尝试、范围内已验证、精选推荐分别计算。draft 可浏览，静态满足可隔离出样；active 不自动精选。无已验证候选可以披露探索方向，不选择不适配但证据多的模板凑数。

**F5：精选整稿与精选页面分开。** curation 的 kind 为 deck-style 或 page-component，前者必须在每个声明为整稿支持的 lane/mode/locale 范围内覆盖封面、普通正文、复杂证据、结尾四角色。可以绑定共享或补充 layout，但须使用同一已解析主题并有该组合证据，不能借其他风格的正文证据凑覆盖。只验证封面的条目只能标精选页面，不能满足九方向整稿交付或占据整稿默认推荐位。页面组件仍可在匹配的单页请求中推荐。

推荐沿用有效 hard rules 和角色/容量/节奏逻辑，改为 ID/结构化数据；去掉人工成员表和重复 family 名单。输入含任务、行业、受众、正式度、密度、环境和用户资产，缺值显式标记。

先过滤适用与依赖，再按场景/受众/密度/用户复用排序，通常给 2–3 个实质不同方向，一个就给一个。点名 > 参考图 > 推荐；点名不覆盖硬错误。参考图形成 run-local 规范化输入，不强制入库，不把业务正文或私有标识变共享资产。

**F6：推荐有效性独立验收。** U1 在旧树退役前冻结 24 个任务及当前推荐输出：八个初始方向各三种条件，至少包含同一行业的管理层/专业受众对照、相同受众的低/高密度对照及展示环境变化。每题记录任务输入、可接受候选集合、明显不适配集合、角色/密度/环境约束、允许单候选与否、参考理由及标签来源。标签按任务需求审阅后冻结，不由新推荐结果反推；模型辅助标注保留来源与维护者裁决。资产旧名经迁移账本映射到稳定 ID，baseline 无结果按未命中记录。

候选集合可以有多个合理答案，但至少八组成对任务须具有明确不相交的首选集合，且不存在对全部 24 题都可接受的单一风格。U6 采用现有推荐 owner 消费结构化特征，不要求另建评分服务；U7 独立读取冻结标签评判，不让被测推荐器给自己判分。评估查询可见相同预算的候选输入；新增资产带来的提升与排序逻辑的提升分别报告，另在共同候选子集上比较，避免将扩库收益全部算作排序收益。

固定完成线：Top-3 命中 24/24、Top-1 至少 20/24，明显不适配候选出现在推荐列表为零；有两个以上合格方向的题至少给出两个在构图/排印/材质特征上实质不同的方向，别名和仅换色不算差异。理由必须引用真实任务条件和候选特征，不得虚构字体、行业资格或验证状态。新旧共同候选范围上的 Top-1/Top-3 不退步；此阈值是本项目验收合同，非外部行业基准或效果预测。

固定请求与执行条件独立运行两轮，分别过线，不取最好一轮。注入“始终返回同一风格”“交换高低密度候选”“忽略受众”“捏造推荐理由”四类错误，判官必须拒绝；正常多解答案不误判。首样接受率、重试和成本继续通过真实生成测量，推荐离线命中不能替代这些业务效果。

评测时任务输入与答案分开投放：被测推荐器只收到任务和正式候选摘要，不把 labels、baseline 或判官解释加入可读任务工作区或 prompt；判官读取其原始输出后再对答案。标签修订须解释任务/资产事实变化并重跑两套结果，不能只更新 expected 让新系统过线。

预览标上游参考、历史样板、当前实际组合样张；只有最后一类证明当前效果。同名/同家族不继承证据，反馈仅记脱敏标签，不单次自动改变政策。

### 8.1 行业审美种子与资产归属

“行业皮肤”是 style/theme/layout/component 的经过验证的组合，不新增 skin 资产类型或 industry-skins 目录。适用行业、受众保守度、正式度、密度、组件偏好归 brief.recommendation_features；精确颜色与字体归 theme；可执行布局归 layout；实际兼容与精选资格由证据派生。以下 slug 为拟定值，U1 查重并一次分配类型化 ID；气质是设计起点，不作为行业禁色或强制字体规则。

| 方向 / 拟定 slug | 视觉与排印起点 | 信息结构与组件 | 行业样张必验内容 |
| --- | --- | --- | --- |
| 管理 / management-clear | 中性底、清晰字阶、克制状态色 | 决策摘要、KPI、进展/风险对照 | 结论与证据对应、数字单位、决策事项 |
| 金融 / finance-navy | 蓝灰、细网格、可核验衬线标题候选 | 密集规格表、KPI、对照 | 数字右对齐、单位/口径/来源、地区涨跌惯例 |
| 咨询 / consulting-pyramid | 浅底、分组线、严格脚注层级 | 结论标题、矩阵、瀑布或合适替代 | 结论与脚注对应、分组和比较尺度 |
| 科技 / tech-dark | 暗底、受控强调、等宽点缀；另验 light | 系统图、回路、时间线 | 系统关系可辨、亮环境可读、不靠辉光承载信息 |
| 政务 / gov-red | 庄重对称、红金可选、规范中文排印 | 清单、规格表、时间线 | 仅按任务保留文号/密级/来源，不自造标识 |
| 医疗 / health-clean | 浅底蓝绿候选、大字号、少装饰 | 层级、时间线、KPI | 长术语、证据限制、非绝对化结论 |
| 教育 / edu-bright | 清晰明度、图文节奏、亲和字体候选 | 教学顺序、问答、少量信息组 | 概念顺序、认知负荷、图文共同解释 |
| 品牌 / brand-creative | 真实素材、可控纸感/贴纸等设计语言 | 大图、引语、叙事卡 | 有真实视觉素材、正文不受装饰遮挡 |
| 学术 / academic-austere | 黑白或克制配色、规范中西排印 | 图表、公式、引用、论证链 | 图例/引用/公式可读，数据比较与来源准确 |

金融可复用旧方案色值起点：primary #1E3A8A、on_primary #FFFFFF、accent #0369A1、background #F8FAFC、surface #FFFFFF、text #1F2430、muted #475569、warn #92400E、border #64748B。不是已验证主题；所有实际角色对仍需校验。颜色数量不硬定为 5–7，角色完整性优先。

### 8.2 字体、图表、装饰与质量检查档

字体矩阵按实际角色而非行业刻板印象组织：中文无衬线正文、中文衬线标题候选、拉丁数字/等宽点缀，逐 family/weight 登记文件、覆盖和许可证。仿宋或圆体仅在合法可分发且有真实文件时采用；不能用相似气质描述冒充该字体。允许经核验可分发的许可证，不机械限于 OFL/APACHE；NOTICE 跟随实际依赖。中西间距通过排版实现，不插改冻结正文字符；不合成缺失字重。

数据组件按任务需求配置 KPI 与矩阵，若七模板无法表达则 U5 同期实现，不能把它们永久停在偏好列表。条形/趋势优先复用 Mermaid；瀑布、公式等先核对实际能力，不能用名称匹配宣布支持，不引入 ECharts 作为本期新增依赖。theme 到 Mermaid 的语义角色映射须逐方言列出 primary/on_primary/background/border/data-series 及 xyChart 配置；缺映射阻断，不默默回落默认。数据语法仍拥有数值、单位、坐标基线和比较尺度，主题不能修改。

装饰只通过注册 ID 和允许参数注入指定插槽，不能携带任意脚本或自行 fetch。占用空间的边框/内距必须进入 layout；装饰不得进入正文、遮挡标签或改数值。frame-shot 截图保持真实比例，禁止倾斜和透视，即使主题装饰允许旋转也不得覆盖该限制。

新增 `governance/rules/render-qa-profiles.json`，由 `visual_qa.py` 消费，schema 归治理区；模板/路线/明暗/密度选择经校准档位，theme 只可引用可用档，不得自带数值阈值。密度须在 U9 盘点现有 zen 档位并登记确定映射，禁止“高可扫读”等自由文本直接执行。档位用固定正常/缺陷样本校准，不逐图调参；WCAG 下限、内容完整性及溢出不能放宽，无法同时避免误阻与漏检则修检测器或明确不支持。QA 档版本、字体、装饰、CSS、图表适配版本及嵌入图表 hash 全部进入执行快照和失效闭包。

### 8.3 长尾主题转换与路由缺省

U3/U4 在现有 intake/组合入口扩展候选转换，Agent 可辅助提取散文，确定性 CLI 不另建 LLM 编排器。输出完整候选及逐字段来源 explicit/inferred/default、原文定位、原 hash、转换版本和 adaptation_gaps；来源信息归归因记录，不混入主题 token 或 prompt。default 只能引用具名版本化默认项且明确采用依据，缺精确字体/布局不得凑值晋升。候选通过静态与依赖检查后可隔离验证；F2 的可执行代码审阅边界仍生效。固定三个真实长尾 brief，验证来源不伪造、缺口不静默丢失，报告可用率及失败原因；旧方案 2/3 目标作为观察指标，不能驱动猜值或降低准入。

行业未知保留 unknown，推荐通用方向；受众保守度、正式度缺失可按 medium 进行推荐试探并标默认来源，不能改写任务事实。展示环境未知优先已验证 light，明亮环境不能默认推只支持 dark 的组合；显式 dark 点名先披露适配缺口，仍受可读性硬检查约束。冻结后不自动换 mode、主题或路线。地区色义只有具体地区/用途/证据才作提示，不推导“金融禁红”等规则。沿用原内容规则 owner，皮肤只承载已有结论标题与行业义务，不新造监管要求。

### 8.4 行业方案研究依据与采用边界

采用精选可组合主题、原始值到语义角色再到组件槽、数据结构支撑结论、任务受众优先于行业标签四项原则。参考入口为 [Gamma 模板](https://gamma.app/templates)、[Material Design tokens](https://m3.material.io/foundations/design-tokens/overview)、[zeroheight 多品牌](https://zeroheight.com/learn/multi-brand-multi-product-and-white-label-token-architecture/)。这些是方法线索，本次未在线逐篇复核；旧方案产品数量、信任比例、字体心理和跨文化概括不作为已核验事实或硬阈值。合成专家圆桌仅是历史分析方法，不作为真实专家认可。无需阅读旧方案才能实施上述合同，其余来源链接仅供历史追溯。

### 9. 证据、失效与恢复

证据 manifest 含验证 ID、schema、资产/依赖 revision、lane、变体、layout/template/页型/密度/locale 范围、输入快照、输出 hash/尺寸、检查、真实评审来源、rubric、supersedes。空支持集合不代表全支持。

必查项通过、视觉问题处置、实际依赖匹配才得到 verified；not-run/unknown/缺项不能 pass，not-applicable 必须由检查合同允许。外部导入“人工通过”只是声称，不能自行晋升精选。

同组合显式 supersedes，不按时间择优；新失败使范围失效，矛盾未裁决为 conflict。保留原始失败，后续真实复验才能恢复。

分别计算 authored、visual_projection、layout_binding、execution、evidence digest。metadata-only 且实际投影/绑定/依赖/方法相同，可新增关联复用样张，不改旧证据。字体、模型、backend、模板、检查 profile 改变重验相应范围。

新 run 样张前冻结实际输入/依赖，接受绑定快照；变化返回当前决策点。沿用锁与原子写，快照漂移拒绝成功记录。新收据只用当前版本，必须保存可读输入或明确 unavailable，仅 hash 不足以恢复。私有快照只留本地。

每个验证包至少含 `manifest.json`、`input.json`、`checks.json`、`review.json` 和输出文件清单。manifest 记录 schema/version、validation_id、资产 ID/revision、依赖摘要、lane/backend/model、编译器与检查 profile、fixture、实际页型/变体、运行标识、结果、文件 hash、评审来源及可选 supersedes。缺失必需输出、未知检查版本或 hash 不符一律不能派生 verified；模型评审和人工评审分别标记，不接受作者填一个 pass 即晋升。

验证包先写 staging，完整性校验成功后移入不可变 evidence 路径，再重建 catalog；catalog 构建失败不删除证据，也不让旧代宣称已包含新结果。相同适用范围出现尚未裁决的矛盾结果时取消通过加成；局部失败只失效其依赖及适用组合。删除被引用证据属于完整性错误，不能降成“从未验证”掩盖失败。公开入库前去除私有正文、引用图及个人标识，无法脱敏的验证只保留在用户本地。

### 10. 一次性迁移与变更边界

旧结构仅是离线转换输入，最终产品无旧树 fallback。开发按单元推进不代表中间状态可发布。

| 可直接改变 | 必须保留 |
| --- | --- |
| 内部路径、CLI shape、schema、pack | 新协议完整、消费者全覆盖 |
| prompt、默认配色、视觉、字阶 | 正文/数字正确、真实验收 |
| MD 内 JSON、同名 sidecar、分类树 | 原件与处置可追溯 |
| 旧实现快照测试 | 业务不变量与有效负例 |
| 旧 catalog/派生文件 | 新源可完整重建 |

隔离根转换后比较 hash/语义和引用，全部消费者切换后才完成正式重组。输入漂移重做受影响项，不能覆盖并行修改。旧活动目录退役，必要原件归档。

旧 run 不续跑，材料显式导入新 run；旧 pack 仅离线转换，正式 reader 不保留 v1。用户目录不自动迁移。恢复依范围明确的变更集/快照，不做全仓 destructive reset；未上线不授权删除个人数据、未提交工作或篡改历史结果。

### 11. 消费者闭包

| 消费面 | 必须切换 |
| --- | --- |
| styles/CLI | 新 schema、ID、overlay、resolver |
| templates/品牌/轴 | JSON、主题单源、当前投影 |
| layout/suggest/geometry/reuse | ID、slot/profile、renderer 支持 |
| image adapter/worker/vendor patch | 新设计输入、冻结、最终 prompt |
| render assets/fonts/page/chart/readiness | 新根、主题/几何、真实依赖 |
| provenance/receipt/sample_decisions | 新协议/快照、旧 run 拒绝 |
| builder/lint/hard_rules/gallery/feedback | 单源、视图、证据 |
| intake/pack/distill/extract/deck_template | 新 writer、格式和关系 |
| installer/bootstrap/pyproject/NOTICE | bundle、版本、依赖完整 |
| Skill/references/README/tests/Judge/CI | 活动路径和协议同批更新 |

完整 grep 只作发现，还要 API/CLI、打包、干净安装、导入导出证明。旧路径只在迁移工具、历史文档与明确旧输入 fixture 白名单保留。style_pack 把 layout 称 token_sidecar 的歧义在新类型中消除。frame-shot 用户截图不迁入共享 canonical。

### 12. 顺序与风险

顺序：U1 → U9 → U10 → U2/U3/U4/U5/U8 的对应工作 → U6 → U7。U9/U10 本版新增，U1–U8 保留职责编号。U10 完成结构转换与路径切换；各功能的语义完善由其 owner 单元负责，最终闭包在 U7 验收，不能因交叉文件产生循环开工门槛。

风险与处置：全量账本防漏项；draft/gaps 防猜 token；单 resolver 防旧树残留；theme 单源防双真值；固定矩阵防费用扩张；业务负例防测试变弱；隔离安装防漏包；输入 hash 防覆盖并行修改。

U1 按机械迁移、人工审阅、主题/模板组合和消费者估算工作量，不承诺无证据工期。外部能力只阻塞对应视觉验证，缺少时整体仍未完成，不以静态成功替代。

## Implementation Units

路径别名仅为本文缩写：B=leo-ppt-generator/，R=leo-ppt-generator/runtime/src/leo_ppt_generator/，L=leo-ppt-generator/template-library/，T=leo-ppt-generator/tests/。实施新增路径标“新增”，文件角色与迁移映射共同限定范围。

### U1. 全量资产与消费者基线

**需求/依赖：** R1/R2/R7/R9，无依赖。
**文件：** B/scripts/audit_style_families.py、B/scripts/capability_manifest.py、T/test_style_asset_inventory.py；新增 docs/leo-ppt-generator/template-rebuild-baseline.md、L/governance/migration/。
**工作：** 重新全量盘点、逐项 ID/目标/owner/处置、冻结 dirty hash；隔离转换草案。
**验证：** 每原路径有去向，占位模板/来源目录/用户同名准确分类；所有消费者有 owner，无假质量状态。

**F6 补充：** 旧树退役前，冻结新增 B/evals/fixtures/template-quality/recommendation-tasks.json、recommendation-labels.json、recommendation-baseline.json，包含 24 题、标签依据和两轮旧输出。新增 T/test_template_recommendation_fixture.py 检查题数、成对差异、标签覆盖、无全题通用答案及旧名到 ID 映射；不运行付费出图。

**行业合并交付：** 新增 B/tests/fixtures/render-theme-baseline/manifest.json，冻结七模板各最小/典型/近容量输入共 21 页的输入、输出、源码 dirty hash、相邻 CSS、字体、命令、浏览器/系统版本及收据。原输出只用于解释重构差异；不沿用旧方案 diff ≤0.001 作为新设计等价门。新增 T/test_render_theme_baseline.py 检查清单完整性。该工作属于 U1，必须在 U10 退役旧树前完成；21 页是本地 HTML 基线，不要求付费生成。

### U2. 质量证据与派生状态

**需求/依赖：** R3/R8，依赖 U9/U10。
**文件：** 新增 R/style_validation.py、L/governance/schemas/style-validation-v1.schema.json、L/governance/curation.json、T/test_style_validation.py；扩展 R/styles.py、B/scripts/capability_manifest.py、T/test_style_index.py。
**工作：** 范围、supersedes、失效和统一质量视图。
**验证：** 缺页/错 hash/scope/缺检查/伪评审/冲突/半写不通过；新失败覆盖旧通过；metadata 复用有依据。Covers AE3/AE6。

**F1/F5 补充：** style_validation.py 拥有完整证据集合扫描、撤销、新鲜度比较及 deck-style/page-component 资格计算；新增 T/test_evidence_freshness.py、L/governance/schemas/evidence-revocation-v1.schema.json。验证 E2 失败已发布但 catalog 重建失败、撤销/删除/坏记录/读中变更；四角色缺一、跨主题和跨 lane 借证据不得取得整稿资格。适用性重算复用同一 owner，不让推荐器另写状态机。

### U3. 全库内容审阅与精选

**需求/依赖：** R2，依赖 U1/U9/U10。
**文件：** L/canonical/styles/、L/canonical/themes/、L/reference/candidates/、L/governance/authoring/；B/scripts/lint_style_briefs.py 与 owning intake_*；T/test_lint_style_briefs.py、T/test_audit_style_families.py、对应 intake 测试。
**工作：** 每项语义处置，精选规则修订，token 唯一化，新 writer。
**验证：** 每项有结论，无误并/改 HEX 绕门；生成源一致，draft 不冒执行能力；视觉由 U7 判定。

**F5 补充：** 为九方向各声明至少一个四角色完整组合，补充布局按同主题绑定；局部风格明确策展为页面组件。curation 的结构与资格规则归 U2，本单元填充维护者选择和任务适用性，不自报验证通过。

**行业合并交付：** §8.1 九种子进入 L/canonical/styles、themes、fonts、ornaments；字体许可证同步 B/NOTICE。新增 T/test_industry_theme_assets.py 验证角色、mode、字体文件/字重、组件绑定、密度映射和行业规则不被主题删除。固定三个长尾 brief 于 B/evals/fixtures/template-quality/theme-projection/，候选来源/差异/gaps 由 U3 维护，U4 实现转换消费；新增 T/test_theme_projection.py。此处声明归属 U3，不额外开启 M1/M2 单元。

### U4. 图像统一编译

**需求/依赖：** R5/R7，依赖 U9/U10，精选来自 U3。
**文件：** R/templates.py、R/cli.py、R/image_deck/adapter.py、B/scripts/build-page-worker-prompt.py、B/patches/；T/test_style_render_options.py、T/boundary/test_prompt_block_regression.py；新增 T/test_design_projection.py。
**工作：** 唯一当前投影，主题/约束/slot 完整传递，vendor 同步。
**验证：** 正文数字不变，关键约束不丢，治理值不泄漏，超预算失败，参考图可临时执行，scope 不串。

**F3 补充：** templates.py 按 §7.0 实现唯一组合器；新增 T/test_resolved_design.py 验证同名替换、preset/显式选择、mode/品牌锁/任务覆盖、数组替换、null 拒绝和硬约束合取。T/test_design_projection.py 验证两路线输入同 design_digest、禁止适配器再次读取活动设计资产、移机后快照可恢复；只把实际有效值编译到 prompt。

### U5. 页面、图表和主题

**需求/依赖：** R6/R8，依赖 U9/U10，正式主题来自 U3。
**文件：** 新增 R/render/theme.py；重构 R/render/assets.py、R/render/fonts.py、R/render/page.py、R/render/chart.py、R/render/readiness.py、R/render/provenance.py、R/render/receipt.py；L/canonical/templates/、L/canonical/layouts/、L/canonical/themes/、L/canonical/fonts/；B/scripts/check_deck_geometry.py、B/scripts/visual_qa.py；T/render/test_page.py、T/render/test_chart.py、T/render/test_overflow_sentinel.py、T/render/test_provenance.py；新增 T/render/test_theme.py、T/test_render_theme_capacity.py。
**工作：** 七模板真实消费、图表同源、renderer 支持明确、新收据。
**验证：** 最小/典型/近容量/硬超、light/dark、缺字体、白字白底、装饰-only、裁切/空正文/缺图表；不支持的布局报缺；数据正确，不强求旧像素。Covers AE5。

**F2/F4 补充：** 新增 R/render/layout.py、T/render/test_layout_profile.py、T/render/test_template_isolation.py、T/render/test_svg_policy.py；扩展 fonts.py 的按次资源服务、page.py 的请求/CSP/上下文策略和 chart.py 的严格静态 SVG 输出。先验证规格表列宽/padding 的 JSON 单点改动驱动 DOM 与容量，再覆盖七模板。Mermaid 禁用 HTML labels 并按本期静态 SVG 子集验证支持的方言；不支持者显式报错。未审阅脚本在数据注入前拒绝；外网/其他回环/重定向/WebSocket/活动 SVG 请求被阻断，正常资源不得误阻。

**行业合并交付：** 新增 L/governance/rules/render-qa-profiles.json、L/governance/schemas/render-qa-profile-v1.schema.json、T/test_render_qa_profiles.py、T/render/test_data_components.py；扩展 B/scripts/visual_qa.py、T/test_visual_qa.py、B/references/render-contract.md 和 B/prompts/render-worker.md。消费 §8.2 的受治理 QA 档、图表逐方言映射、frame-shot 限制与数据组件；测试全部角色颜色对、明暗正常/缺陷样本、图表默认回落拒绝、KPI/矩阵输入及数值保真。缺 KPI/矩阵载体时同批新增 template/layout/component，不能只更新偏好元数据。

### U6. 推荐与工作流

**需求/依赖：** R4/R10，依赖 U2/U4/U5，候选来自 U3。
**文件：** B/SKILL.md、B/references/style-recommendation.md、B/references/style-library.md、B/references/layout-dispatch.md、B/references/image-deck-workflow.md、B/references/deck-master.md、B/references/execution-contract.md；B/scripts/style_hard_rules.py、B/scripts/suggest_layout.py、B/scripts/recommend_feedback.py、R/cli.py；新增 T/test_style_quality_routing.py；T/test_style_index_workflow.py、T/test_sample_decisions.py。
**工作：** 名称/ID/参考图/用户覆盖统一，推荐看 lane/容量/证据，样张门不另造。
**验证：** 无/单候选、草稿、歧义、完整 ID、同名、仅封面证据、缺环境、advise 不生成，无接受或豁免不得派发。Covers AE1–AE3。

**F1/F6 补充：** 查询前核对证据集合，陈旧时撤下验证与精选标签；整稿查询排除仅页面组件。新增 T/test_template_recommendation.py，验证任务条件变化会改变合适候选、理由引用有效特征、只有一个方向时不凑数。消费 U1 固定题集，不回写标签；推荐器不拥有判官或可接受集合。

**行业合并交付：** 新增 T/test_industry_environment_routing.py，覆盖未知行业/保守度/正式度/环境默认来源、tech-dark 的 light 选择、冻结后不换 mode、学术定向推荐、用户点名覆盖审美建议但不覆盖硬失败。路由读取 §8.3 的四键信号，24 题既有基线保持原八方向。

### U7. 全量与真实视觉验收

**需求/依赖：** R1–R10，依赖其他所有单元。
**文件：** L/evidence/、L/catalog/views/、B/evals/eval.yaml；新增 B/evals/cases/template-quality-*.yaml、B/evals/fixtures/template-quality/、B/evals/judges/judge_template_quality.py、T/test_template_quality_judge.py、docs/leo-ppt-generator/template-rebuild-verification.md。
**工作：** 逐文件核验、固定视觉矩阵、负例校准、真实 eval；使用 skill-upper，先 validate/list-cases，再看最终 result 与逐例证据。
**验证：** 全库解析、闭包、分发、双轮视觉、两条路线的完整 PPTX 导出回读；保留失败，不以缺能力为通过。

**F1–F6 补充：** 集成六类反例；新增 B/evals/fixtures/scripts/judge_template_recommendation.py 与 T/test_template_recommendation_judge.py，使用 U1 固定标签、独立解释依据检查和四类错误推荐校准。24 题两轮分别过线、共同候选基线不退步；九方向逐组合四角色验证和四页 PPTX 回读，两份完整 deck 仍另行证明全流程。重建失败后查询及成功收据的交错必须实测，不能只用静态字段断言。

**行业合并交付：** 新增 B/evals/cases/industry-visual-*.yaml、B/evals/fixtures/template-quality/industry-visual/、B/evals/fixtures/scripts/judge_industry_visual.py、T/test_industry_visual_judge.py。按 Verification §3.1 固定 44 单元、校准标签/分歧裁决和两轮结果，模板主题消费及行业适用性分别报告；不复制旧 M3 为另一套评测入口。扩展 template-rebuild-verification.md 登记九种子、24 题、44 单元、两份完整 deck 的四种口径与去重映射。

### U8. 打包、安装与维护

**需求/依赖：** R7/R8/R9，依赖 U9/U10/U2，生成整合等待 U4/U5/U6。
**文件：** B/scripts/style_pack.py、B/scripts/deck_template.py、B/scripts/distill_deck_style.py、B/scripts/extract_pptx_theme.py、B/scripts/runtime_manager.py、B/scripts/leo-bootstrap.sh、B/scripts/leo-bootstrap.ps1、B/runtime/pyproject.toml、B/NOTICE；T/test_style_pack.py、T/test_style_index_distribution.py、T/test_deck_template.py；新增 T/test_library_bundle.py。
**工作：** 新包/依赖/ID、旧输入离线转换、bundle 版本匹配、用户导出脱敏。
**验证：** 冲突、跨 scope、越界、缺依赖、篡改、断写、完整/链接/隔离安装、新 run 恢复/旧 run 拒绝；不改原数据。Covers AE7/AE8。

**F2 补充：** style_pack.py 区分数据导入与代码采用，用户代码默认隔离，包内信任声明无效。本地代码审阅记录放在用户模板库 governance/trust/，schema 为新增 executable-adoption-v1.schema.json，由受管运行时校验；绑定模板及递归代码依赖摘要、实际审阅来源和采用范围。新增 T/test_template_adoption.py 验证伪造包内 trusted、代码变更、缺依赖、内置与用户身份混淆及未审阅模板执行拒绝。内置采用依据为受管 bundle manifest，不向用户目录复制内置信任。

### U9. 统一合同、身份和 resolver

**需求/依赖：** R1/R3/R7/R9，依赖 U1；本版新增。
**文件：** 新增 R/asset_resolver.py、L/library.json、L/governance/schemas/、L/governance/vocabularies/、T/test_asset_resolver.py、T/test_library_contracts.py；R/styles.py、R/layout_bank.py、B/scripts/capability_manifest.py 及 schema consumers。
**工作：** 新实体、ID、主题/layout/template 分工、registry、scope；先最小新库 fixture，不双读。
**验证：** 改名/移动不改 ID；重号、歧义、坏引用、循环、scope 伪装、未知版本、缺 bundle、陈旧和输入变化拒绝；构建无自引用。Covers AE1/AE3/AE4。

**F3/F4 补充：** 新增 L/governance/schemas/resolved-design-v1.schema.json、layout-profile-v1.schema.json；固定选择器/覆盖、角色类型、1280×720 逻辑坐标、布局类型及 slot 绑定契约。schema/语义 fixture 先于 U4/U5 实现，防止组合器、CSS 编译器和容量检查各自定义合同；模板 trust 与 evidence schema 分别由 U8/U2 拥有。

**行业合并交付：** 在 L/governance/vocabularies/ 登记保守度/正式度/环境、现有 zen 密度档映射及主题角色；theme schema 明确模式、字体角色、装饰与 QA profile 引用，静态支持与已验证组合分开。具体 QA schema 的实现 owner 为 U5；U9 先冻结引用合同以支持 U10 结构迁移。

### U10. 全量目录与消费切换

**需求/依赖：** R1/R2/R9，依赖 U1/U9；本版新增。
**文件：** 新增 B/scripts/migrate_template_library.py、T/test_migrate_template_library.py；第 4 节全部资产、第 11 节消费者、L/governance/ 和 L/catalog/。
**工作：** 隔离转换、逐项核对、作者/引用/路径切换；旧活动树退役，功能深化由 U2–U8 拥有。
**验证：** 原集合与映射一致，变体/绑定/别名语义保留，漂移停止，同输入同输出；最终闭包在 U7 证明。Covers AE4/AE8。

## Verification Contract

### 1. 分层完成

| 层 | 验收 |
| --- | --- |
| 结构 | 每项有处置，新合同/ID/引用全部有效，旧树退役 |
| 内容 | 全项审阅，精选规则合格，草稿/参考诚实分类 |
| 执行 | 两路线新解析，七模板消费，新包独立运行 |
| 质量 | 精选真实证据、硬检查、语义评审、全稿交付 |

目录完成不能结项，全量结构不代表全库视觉通过。报告分 active/draft/reference/retired、lane、验证组合和精选覆盖。

### 2. 机制与回归

全库 JSON/ID/引用/schema 校验，逐文件 ledger 核对，所有消费者实际调用。registry/catalog 同输入两次构建一致，构建时源/证据/依赖变更不得成功发布。

业务不变量保留：正文/数字/单位/来源、样张门、容量阻断、用户隔离、原子记录。可替换旧目录/旧视觉实现快照，但必须解释差异，不能批量更新 expected 掩盖失败。

七模板最小/典型/近容量/硬超以及 light/dark 测试，实际字体度量和 DOM 检查。表格与图例逐项回读；不支持结构明确报缺，不能假降级。

### 3. 精选视觉与端到端

九个初始任务方向，各至少一个精选整稿风格，每个至少有一个完整支持的 lane/mode/locale 组合；每个声明为整稿的组合独立覆盖四角色。补充 layout 必须同主题验证；只有封面等局部能力的条目按精选页面组件登记，不能占整稿名额。明确登记支持集合，不能用“所有”代替。

九风格各一个整稿组合时每轮至少 36 页，两轮至少 72 页；九风格均声明两 lane 则每轮至少 72 页，两轮至少 144 页。每组合至少四角色各一页，复杂数据或额外变体按实际覆盖单计，tech-dark 的 light 组合须另外完整验证。缺少某角色使该整稿组合不通过，不能缩小分母伪装完成。执行前固定 fixture、名单、参数、backend、费用与重试上限；本方案不构成付费授权。

同内容检辨识度，行业材料检适用性。两轮独立生成均满足硬检查与逐项语义判断才记稳定通过。image 不要求像素 hash 相同；HTML 锁环境回归，但不强求新样式等于旧错误样式。

每个整稿组合将同轮四角色的已验证图片组装成最小四页 PPTX 并回读，核验标题、页脚、色彩、字体气质、内容密度及角色转换的连续性；复用矩阵图片，不新增付费生成。九方向不能共用一个风格的四页结果替代。注入“只有封面通过”“正文切到其他主题”“跨 lane 借证据”均须被精选资格检查拒绝。

至少两份完整 deck 分别走 image/HTML，覆盖推荐、解析、母版、样张、逐页、PPTX 导出、回读和收据。检查页数、尺寸、缺页、裁切、文字/数字、一致性、指纹，只验证 PNG 不算完成。

### 3.1 行业适配扩展验收（吸收旧 M3）

独立于九方向种子准入与 24 题推荐检查，保留原行业皮肤方案的 44 单元视觉矩阵为本期完成条件：复用 005 的 20 行业任务定义，每行业 light/dark 两类展示环境，共 40 单元；科技/金融/教育/医疗各补一个同材料的受众保守度对照，共 44 单元。每单元固定主要受众、正文和路线，至少封面/正文/数据三页，132 页/轮，两轮至少 264 页。环境不是强制主题 mode；可用有理由的浅底服务暗环境，但不得宣称未验证的深色能力或投影仪现场效果。

该矩阵重点验证 HTML/图表行业皮肤实际适用性，逐例声明路线，不外推为全部 image 组合已通过；图像路线仍由整稿种子支持集合与完整 image deck 验证。20 行业无需 20 套皮肤，使用九方向的合适组合。矩阵与种子页仅当内容、输入、依赖、路线、参数及证据范围完全一致时去重计算实际生成页数，报告两套覆盖映射；两轮不得复用同一次生成冒独立复跑。成本清单另外列七模板 7×3 的改前基线、灰盒 light/dark 机制页、校准页和两份端到端 deck，不能把 264 页当全部项目预算。

005 继续停在样张前，本方案新增 B/evals/fixtures/template-quality/industry-visual/ 的独立 fixture、manifest 和结果，由 U7 拥有；不在 005 的内容结果上追加视觉通过。每行业材料按 §8.1 的行业判据扩展，缺真实素材报缺，不用占位图验收。每页硬检查全部通过，行业语义项给图像位置及理由，分歧裁决不能豁免硬失败。

正式执行前固定合格/不合格语义校准样本各至少十页和实际人工标签；两位独立评审的逐项一致率及各自与人工标签的一致率均至少 80%，并报告分母、初始分歧及裁决结果。硬缺陷每类至少一例且检出率 100%。标签、评审身份或外部能力缺失时报告行业视觉验收未完成，不能以当前会话串行自审冒独立评审；执行授权遵循实际边界，不伪造批准。两轮全部单元硬检查和裁决后的语义项通过才声明 44 单元达标；本次文档合并不运行这些评测。

### 4. 判官与实际证据

植入空正文、装饰-only、错数字/单位、缺字体、白字白底、裁切、布局语义错误、治理信息入正文、错资产绑定，必须被对应检查识别；正常样本不得错误阻断。先固定样本，不逐图调阈值。

语义评审逐页给主视觉/信息支撑/层级/比较/一致性的结论、位置和理由。模型评分不替代真实图片，不伪造人工确认；精选晋升需真实维护者记录，任务样张遵循当前授权，不新增重复审批。

OCR 不证明事实，亮度不等于 WCAG。双评审/外部模型只在真实执行授权和能力具备时运行，未运行明确注明。

### 5. 指标与完成线

| 指标 | 标准 |
| --- | --- |
| 迁移覆盖 | 原资产 100% 有处置，无重复 ID |
| 消费闭包 | 全部消费者通过，旧路径仅历史/迁移白名单 |
| 内容审阅 | 每项有结论，不抽样冒全量 |
| 资格 | 固定请求错 scope/lane/证据/依赖的假可用为零 |
| 证据新鲜度 | 新失败或撤销已发布而 catalog 发布失败时，旧 verified 不得继续对外返回 |
| 模板执行 | 未审阅代码不执行；已采用代码也不得请求白名单之外资源或运行活动 SVG |
| 投影 | 必需正文、数字、关键约束不丢，治理不入内容 |
| 组合与几何 | 两路线同 design_digest；覆盖规则确定；JSON 几何改动驱动真实 DOM 与容量，无模板重复真值 |
| 视觉 | 精选范围双轮无未解决硬失败，语义问题有处置 |
| 整稿精选 | 九方向各有四角色完整组合和四页 PPTX，局部页面证据不能冒整稿 |
| 行业视觉 | 44 单元、每单元至少三页、两轮通过；标签/独立评审/裁决可追溯，和 005 结果分开 |
| 推荐有效性 | 24 题两轮分别 Top-3 全命中、Top-1 至少 20，硬错为零，理由真实且共同候选基线不退步 |
| 恢复 | 新快照可核验，旧协议明确拒绝，不改历史 |
| 收益 | 记录首样接受率、重试、成本、选型时间，固定任务基线比较，不预设无依据降本率 |

### 6. 验证工具与环境

沿用并改造包内 scripts/ 的 lint_style_briefs.py、lint_layout_grid.py、lint_style_index.py、lint_style_governance.py、lint_render_templates.py、capability_manifest.py。旧输出/路径可替换，不要求新库模拟旧树。

先单元定向测试，再相关包级/渲染/样张/分发回归和真实 eval。使用依赖齐全的项目 Python；缺字体/浏览器/后端的 skip 不算通过。git diff --check 只检查文本卫生。新增目录/schema/参数/测试均待实施，本轮未执行不存在的检查。

## Definition of Done

U1–U10 全部完成；目标目录真实落地；全量迁移与内容账本；稳定 ID/JSON/唯一 resolver 生效；所有 consumers/writers/lints/fixtures/docs 新协议；旧活动树退役；双路线/七模板通过；精选矩阵及两份端到端 deck 有证据；完整 bundle 安装、导入导出、新 run 恢复通过。

六项审查修订的机制必须分别落地：独立证据新鲜度与故障交错、模板执行信任边界、确定性设计组合、JSON 到 DOM 的几何消费、九方向整稿覆盖、24 题推荐有效性。正文中的设计合同和负例不能以“已写文档”代替运行证据。

行业方案合并的完成条件另含 §8.1–8.4 的种子/字体/数据组件/QA 档/长尾转换，以及 44 单元行业视觉验收。24 题保持 v3 原八方向的固定基线，不为合并改写旧题集；学术种子的推荐与渲染通过新增定向 fixture 和行业矩阵验证，不能宣称它已包含在原 24 题中。

长期旧协议兼容、历史两模板恢复、全库付费视觉验收、模板市场和向量服务不是完成条件。未上线允许内部破坏性变更，不豁免数据保护、事实保真和真实验收。

本次仅交付文档：主方案完整重写，行业皮肤与架构参考标明替代关系，元数据/引用/结构/逻辑检查完成。实际重构仍 not-started，明确实施请求后才修改代码和资产。

## Appendix

### v4 行业皮肤方案合并账本

本文为完整实施入口，以下处置表覆盖旧方案全部章节；旧文只保留历史证据和来源，不含待单独执行的 M 单元。

| 旧章节 | 处置与当前归属 | 取舍 |
| --- | --- | --- |
| §1 现状与三域审计 | 当前基线、U1 全量账本及七模板改前记录 | 历史九模板/SDLC 不冒充当前在库事实 |
| §2 研究、§3 合成圆桌 | §8.1–8.4 的种子、字体、结构、受众、token 原则 | 数量宣传、心理统计、刻板禁色、真实专家背书不采纳 |
| §4.1 schema | §5/§7/§8.1–8.2、U9 | 不新增 skin 真值；industry-skins 改用 canonical 组合，QA 归治理区 |
| §4.2 投影与兼容输入 | §7.0/§7.1/§8.3、U3/U4 | 采纳逐字段来源与差异报告；删除旧 flat theme、legacy prompt 与双版本分支 |
| §4.3 迁移/容量/基线 | §4/§7.2/§8.2、U1/U5/U10 | 新 ID 和 layout JSON 取代旧 sidecar；保留改前证据，不强求旧像素等价 |
| §4.3 历史两模板 | 保持 reference 历史材料和明确缺口 | 不恢复未定位 blueprint/doodle，不把旧 M0b 留作必需阻塞 |
| §4.4 准入/QA | §8.2/§9、U2/U5/U7 | 保留校准及硬下限；draft 隔离出样与整稿精选分层，不一刀切禁长尾 |
| §4.5 路由 | §7.0/§8.3、U6 | 四键信号/缺省/环境纳入统一选择，不再另存平行 render_theme 绑定 |
| §4.6 溯源/恢复 | §7.0/§9、U4/U5/U8 | 完整快照和依赖失效保留；旧 run 只读，不保留旧协议续跑 |
| §5 八种子 | §8.1、U3/U5 | 八种子全部保留，加入管理共九方向，最多 12 个逻辑风格 |
| §6 M0a/M1 | U1/U9/U10/U3/U5/U6 | 现有单元承接，删除独立路线图 |
| §6 M2 长尾/组件 | §8.2–8.3、U3/U4/U5 | 三 brief 验证、KPI/矩阵、Mermaid 复用；2/3 可用率降为观察指标 |
| §6 M3/视觉矩阵 | Verification §3.1、U7 | 44 单元与评审校准完整保留；首批种子按主方案四角色加强 |
| §7 风险 | §8、§9、顺序与风险、验证合同 | 不采纳 image 仅限封面、旧协议兼容和内容债永久后置 |
| §8 关系/闭合表 | 本表、U1–U10、Definition of Done | 005 保持独立内容 owner；领域数据规则不归主题改写 |
| 来源附录 | §8.4 的方法摘要和历史来源追溯 | 未复核链接不升级为当前证据，开发无须读取旧文补合同 |

合并增加学术种子和 44 单元视觉验证成本，U1 重估实际页数、外部调用及环境依赖；没有运行这些验证之前只可声明文档合并完成。v3 的 F1–F6 仍完整适用，九方向是 v4 对 F5 覆盖范围的扩展。

### v3 审查问题处置

本轮逐项修订 F1–F6，均为方案层闭合；未运行新机制或宣布实现通过。`implementation-ready` 表示本轮具体设计及验收已补齐，implementation_status 仍为 not-started；不表示独立评审通过。

| 问题 | 修订位置 | 实现 owner | 必需反例 |
| --- | --- | --- | --- |
| F1 新失败漏出索引 | §6 与 §9，独立证据集合摘要 | U2，U6 消费，U7 验收 | 失败落盘成功、catalog 发布失败后仍返回旧通过 |
| F2 导入代码无执行边界 | §7.3，审阅绑定、请求白名单、静态 SVG | U8 准入、U5 执行、U7 验收 | 外发正文、其他回环服务、恶意 SVG、代码变化 |
| F3 组合语义不确定 | §7.0，阶段、叶子覆盖、冻结合同 | U9 schema、U4 组合、U5 消费 | 覆盖品牌锁、null 删除角色、两适配器重新解析 |
| F4 几何仍双真值 | §7.2，逻辑 profile 到 CSS/容量 | U9 schema、U5 编译、U7 验收 | 改 JSON 不改 HTML，DOM 或容量不跟随 |
| F5 局部冒整稿精选 | §8 与视觉验收，四角色完整组合 | U3 策展、U2 资格、U7 视觉 | 只有封面或跨主题/跨 lane 借证据 |
| F6 推荐缺效果证明 | §8，24 题固定标签与基线 | U1 基线、U6 推荐、U7 评测 | 恒定风格、密度/受众错配、捏造理由 |

### v1 到 v2

| v1 | v2 |
| --- | --- |
| 保留旧目录，迁移后置 | 物理重组本期必须交付 |
| 临时路径/hash 身份 | 首批稳定 ID/registry |
| MD 内 JSON | 纯 JSON，说明与视图分离 |
| v1 加质量扩展 | 单 catalog 协议 |
| legacy prompt 双轨 | 单一正式编译 |
| 旧 run/pack 续用 | 原件只读，离线转换，新 run 新协议 |
| 皮肤专项独立执行 | 有效设计吸收，唯一入口 |
| 旧架构外部门禁 | 本方案拥有预发布决策与验证 |

### 证据边界

现状数字来自本会话已执行的源码和图片检查，实施内容是设计，未声称已迁移或全库视觉通过。本轮采用编写者自审，不宣称独立专家或外部模型审查。执行时重新核对当前源码、dirty 状态和实际环境。
