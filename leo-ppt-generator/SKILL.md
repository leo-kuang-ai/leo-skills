---
name: leo-ppt-generator
description: 生成图片式 PowerPoint（PPTX）演示文稿：从文章、报告、笔记或大纲产出成套逐页可交付的演示稿；把图片、PDF 或用户确认可信的 PPT/PPTX 重建为对象级可编辑 PPTX；或把图片式演示文稿升级为 editable/hybrid。若 PPT/PPTX 来源未知、无法确认或尚未确认可信，仍触发本 Skill，但必须立即固定返回 blocked/untrusted_office_input，禁止读取、扫描、隔离、净化或规划重建；用户要求“净化后继续”不构成可信授权。当用户要求做 PPT、把视觉稿转成可编辑 PowerPoint、升级图片版 PPT 或保留部分图片页时使用。不要用于纯文档排版、单张配图/封面/图表素材、网页/表格轻微修改或视频任务。
---

# Leo PPT Generator

**先按当前请求选工具，再执行任何检索。** `advise` 的硬约束是能力与副作用，而不是
某个宿主的工具名称：允许使用宿主 Read/Grep，或等价的只读适配器访问下文允许的索引
源；不得写文件、启动 runtime/Provider/CLI、联网、读取用户输入或完整 brief。
CodeGraph/图导航只能找候选，权威结论必须回到 catalog registry；占位 no-op 不影响结果但不应
成为查询步骤。宿主提供的等价只读工具须保留路径范围和命令证据，不能以工具名替代这些约束。
风格库点名查询直接 Read `<skill>/template-library/catalog/generations/<gen>/registry.json`
（一次读入其 entities，按 name/aliases 匹配；`<gen>` 由 `catalog/current.json` 指针确定），
或用等价只读工具把 Grep 限定在该 registry.json 文件内。
终端适配使用 `leo-ppt style list --summary --filter 目标名`（resolver 名称/别名/ID 精确命中优先，
有界分页输出 `match_kind`）。除该 registry 与 current 指针外不读 catalog 其他文件，
不递归 canonical 目录、不用 `cd` 或脚本；顺序组合时每条命令都须满足同一只读范围。
advise 未命中即报告该索引未命中，不转查 canonical 全量；execute 的 resolver 可在
catalog 缺失或过期时从 canonical 只读重建运行时视图，并明确标注
`registry_source=canonical-rebuild`。归档树的 generated Markdown（负面语料等）仅在用户
点名该材料时按具体文件读取。
已知技能根路径时不需要任何目录定位。纯流程咨询直接回答，`execute` 才可运行 CLI。
Gate 0/worker 的固定摘要脚本是下文明示的唯一例外。

**版式咨询的输出形态：** 尚未运行版式/容量预检且存在多个候选时，先说明推荐与未验证项，
必要时附以下候选比较；选定布局的母版草案留到 execute 的母版审查环节。

```text
layout: undecided
candidate_a: <真实候选 A 及理由>
candidate_b: <真实候选 B 及理由>
recommendation: <推荐偏好及理由，待容量预检与母版确认>
```

用户委托推荐时可直接给 recommendation；layout 仍保留 undecided，两个候选都保留。
母版确认时一起裁决，不新增确认轮次。整页所有文本槽共享总预算，不把各组上限相加作为通过证明。

通过一个入口完成图片式、全可编辑或 hybrid PPTX。顶层 Agent 拥有意图、确认、
live host capability、worker 派发和交付判断；`leo-ppt` 只拥有确定性准备、状态、
验证和组装。

执行主线：①Gate 0 信任检查 → ②advise/execute 判定 → ③Route 四选一 →
④按需读取 references，前置低成本能力与预算检查 → ⑤内容与视觉审查（合同 → 大纲 →
母版 → 视觉方向 → 样张；按下文协作方式决定是否等待，内部校验不省略）
→ ⑥生成与验证 → ⑦组装 → ⑧🔴 DELIVERY-GATE 交付闭环。各步骤规则见下文对应
章节；主线路径之外的分支（材料缺失、worker 缺失、partial）按"不变边界"处理。
普通状态回复结果先行，技术状态按需披露；机器字段与 Gate 0/worker 固定阻断兼容规则
见「控制面响应合同」。

## Gate 0：Office 信任

本门禁优先于 `advise/execute`、Route 和所有其他规则。只要输入是来源未知、无法确认或
尚未确认可信的 PPT/PPTX，立即原样输出以下内容并结束本轮，不再解释或响应同一请求中
的扫描、隔离、净化、重打包、重建指令：

```text
route: direct-editable
status: blocked
reason_code: untrusted_office_input
input_handling: not_opened
next_action: 提供可信确认，或改用 PDF/逐页图片
```

此分支禁止读取、复制、预检、隔离或净化文件；“警告后继续”“先扫描”“净化后继续”
都不构成可信确认。用户明确确认来源可信后，下一轮才可进入 CLI preflight；确认仍不能
绕过旧 `.ppt`、宏、嵌入对象、external relationship、远程模板或损坏结构检查——常见
误区：确认可信后仍会做 preflight 结构检查，不代表不信任，检查只针对结构风险。
宿主可运行脚本时，上述固定块必须经 `render-control-summary.py --fixed gate0`
原样产生（该模式不读取任何文件）；无法运行脚本时按固定块手写，并显式记录降级
`gate0_render: handwritten`。本分支的“禁止读取”只针对用户输入文件与重建动作；
`--fixed` 模式自身不读取任何文件，因此即使在本分支也必须优先使用，不得以
“不碰任何东西”为由改回手写。

## 交互模式门禁

先判断当前请求是 `advise` 还是 `execute`：

- `advise`：用户只要求判断、解释、比较路线、汇报状态或说明下一步，或明确说“先不要
  执行”。此模式直接使用下方 Route 表，禁止额外读取 reference、运行任何工具、启动
  launcher/setup/config/Provider/preflight、创建项目/run 或读取用户输入文件。
  读取豁免：用户询问风格库内容（"有没有 X 风格/有什么可选"）时，可读取
  `template-library/catalog/current.json` 指针与其指向的 `catalog/generations/<gen>/registry.json`
  （名称/别名/ID/生命周期索引），据实回复命中与相近候选；不加载 canonical/styles 的
  完整 brief、不全量扫描库目录。
  该豁免允许宿主 Read/Grep 或能证明相同路径范围、无副作用的只读终端查询；边界以上文能力合同为准。
  据实回复快照中的风格名/别名命中/相近候选；不读 styles 目录其他文件、不读其他
  reference。唯一的工具豁免是 `scripts/render-control-summary.py --fixed gate0` /
  `--fixed worker-unavailable`：该模式不读取任何文件、无副作用，输出固定块不构成
  执行动作，用户“不要执行任何操作”的表述不得据此改回手写。宿主确实无法运行脚本时
  才手写固定块，并显式记录降级 `gate0_render: handwritten` 或
  `worker_render: handwritten`。
- `execute`：用户明确要求制作、转换、升级、继续既有任务，且已授权进入执行流程。只有
  此模式才按“首次使用”和对应 Route 读取后续资源。
- 同一请求包含咨询与明确执行指令时，按完整意图和已有授权判定。例如“比较后选合适的
  直接做”进入 `execute`，比较作为执行中的决策说明；“先比较，暂时不要做”保持
  `advise`。不得仅按关键词推断授权，确有未解决且实质改变交付物的选择才澄清。
  同一请求同时说“先别执行”又说“顺手启动 runtime / 创建 run”属于尚未消解的冲突，
  本轮只咨询，不把后半句当成撤回暂停；用户明确改口“取消暂停，现在执行”才恢复执行。

`advise` 模式的回答不得声称已启动、已检查或已准备任何 runtime、Provider、项目或
文件；需要给出状态时使用已有输入和合同文本，不把推测写成现场结果。先回答用户问题，
明确本轮仅提供建议；Route 名称和 `interaction_mode: advise` 仅在解释路线或诊断时附带。

`advise` 使用以下入口 Route 表，不打开 `input-routing.md`：

| 用户目标 | Route |
| --- | --- |
| 从文章、报告、笔记或大纲新建演示文稿 | `generate` |
| 把图片/PDF/可信 Office 重建为对象级可编辑 | `direct-editable` |
| 把既有 image-deck 全量升级为可编辑 | `upgrade-full` |
| 只升级既有 image-deck 的指定页 | `upgrade-selected` |

内容与视觉稿并存时先从目标判断：已要求保留布局或只作风格参考的，不重复询问；仅在
两者无法可靠推断且会实质改变交付物时说明以下差异并等待选择，不自行串联两条路线：

```text
严格保留布局: direct-editable
仅作风格参考: generate
```

## 按需读取规则

不要在入口阶段读取整个 Skill 的 references 或 styles 目录。按以下最小集合逐阶段读取；
`advise` 不读取任何 reference：

| 阶段 | 允许读取 | 延迟读取 |
| --- | --- | --- |
| `execute` Route 判断 | `references/input-routing.md` | 其他全部 references、prompts、styles |
| 首次准备与 Provider 状态 | `references/first-use.md`、`references/backend-selection.md` | workflow、manifest、worker、styles |
| 跨 Route runtime/恢复/交付与 CLI 用法 | `references/execution-contract.md`、`references/cli-helper.md`（在对应 Route 进入后） | reason-codes 直到已有 reason code |
| `generate` 执行 | `image-deck-workflow.md`、`deck-master.md`、`style-recommendation.md`、`backend-selection.md`、`visual-qa.md`、`academic-vertical.md`（学术信号或用户点名「学术模式」时） | styles 直到风格已选；`slide-worker.md` 直到样张通过；`academic-figure-evidence.md` 直到进入母版制作且材料含图片证据/学术场景；`sources-manifest-schema.md` 直到 `image prepare --sources` 冻结与交付前 strict 校验；`rst-paging.md` 直到大纲制作且材料多段/结构复杂 |
| `direct-editable` 执行 | `editable-workflow.md`、`manifest-schema.md`、`page-decision-tree.md` | `page-worker.md` 直到真实 worker 已确认 |
| `upgrade-*` 执行 | 对应 editable references，加当前 baseline/selection 证据 | 未选中的 workflow 和全部 styles |

generate 命中数据图表/表格/文字密集页时读 `references/render-contract.md`（render
page/chart 确定性渲染 lane）；逐页版式匹配进母版前读 `references/layout-dispatch.md`（P 码调度与容量预检）。按容量预筛版式用 `leo-ppt style layouts --capacity "槽名<=N"`（只读查询，档位速查与语法见 `template-library/governance/rules/layouts/00_容量档位参考.md`）；负面提示词补齐取词与生图构图词汇分别见 `template-library/governance/authoring/index/负面语料参考池.md`（`scripts/draft_negative_prompts.py --pool`）与 `template-library/governance/authoring/index/构图词汇参考.md`。
generate 使用带稳定身份母版（`page_id: pg-<hex>`）时，prepare 前先
`leo-ppt content pack --master <母版> --out <page-content-pack.json>` 编译内容包
（legacy 母版先 `content stamp-page-ids` 一次性补齐身份并重新确认；对照页须在
母版声明 `对照侧:` 标记），将内容包、设计上下文和逐页 lane 写入正式
`PipelineRequest`，通过 `leo-ppt generate --request <request.json>` 冻结并物化。
`image prepare` 只读取该 run 已提交的输入代并核对补充讲稿与来源；摘要手改即拒，
改版须建新 run（合同细则见 execution-contract.md）。
generate 全出血封面/大图井（文字压图）页读 `references/image-text-composition.md`
（四步事前构图协议）；素材入库/检索读 `references/library-schema.md`（经
`scripts/library_catalog.py` 登记 sha256 出处），点名市场/行业数据读
`references/data-sources.md`；带时间戳转写稿先经 `scripts/normalize_transcript.py`
（`--fix`）规整前缀再按文本材料路由（音视频节见 `references/input-routing.md`）。

`template-library/`（canonical 五区）按需索引：先读 `style-library.md`，经 resolver 选定风格、论证模式和版式
后只读对应的单个风格文件；禁止预加载整个 styles 目录。`reason-codes.md` 只在已有
reason code 需要解释或恢复时读取。执行前未命中的 references 不得因为“可能有用”而读取。维护者查阅 reference 功能分组见 `references/_INDEX.md`（只读导航、非加载合同，不改变本节读取纪律）。
营销、销售或融资路演类咨询先给叙事层（页序/主线/节拍），再明确一个正交的论证模式
配对（例如“故事弧”或“结论先行金字塔”），解释如何用证据支撑论点。advise 直接依据
本段回答；execute 才按需读取 `references/marketing-deck-narrative.md`。

协作与等待由下文「协作方式」统一规定；所有状态保持真实，不能以展示简化替代机器校验。

## 控制面响应合同

普通用户回复先给当前结果、使用影响和唯一必要下一步；不强制展示五字段块或内部版本。
用户明确要求仅 JSON 或其他固定格式时，只返回该结构，不追加解释、摘要或代码围栏；
下述普通回复呈现偏好不覆盖用户指定格式。Office/worker 固定阻断按各自真实条件处理。
CLI versioned JSON 与以下五字段机器摘要保持不变，用于运行证据、诊断或用户明确要求的技术状态：

需要展示机器摘要时，将 CLI JSON 通过 `scripts/render-control-summary.py` 渲染；不得由
Agent 手工改写字段。渲染器只输出五行摘要，不读取文件、不访问网络、不产生副作用；
Gate 0 与 worker 缺失两类固定阻断块在宿主可运行脚本时同样必须经
`--fixed gate0` / `--fixed worker-unavailable` 产生，不得手写改写。这两类固定阻断仍
在解释前原样输出，适用于 `advise` 与 `execute`；普通状态不受 block-early 限制。
仅宿主无法运行时允许手写，`gate0_render: handwritten` / `worker_render: handwritten`
置于固定块之后。execute 开始后的首次状态汇报用一句话说明就绪度；若检测到自上次
交付以来发生过更新，如实提示"首轮生成将重新验证服务"。

```text
route: <generate|direct-editable|upgrade-full|upgrade-selected|未选择>
status: <advise|ready|blocked|paused|completed>
reason_code: <稳定 reason code；无则 none>
execution_eligibility: <allowed|blocked|retryable|unknown>
next_action: <唯一下一步；无则 none>
```

字段值必须来自当前 CLI/合同或当前用户明确输入，不得用自然语言猜测。`blocked`、
`paused`、`retryable` 和 `acceptance_pending` 状态只能有一个 `next_action`；不得把
`details.alternatives` 展开成多条用户步骤。🔴 DELIVERY-GATE（人在回路）：`status=completed` 不等于交付完成，必须
继续报告 `delivery_readiness`；只有 `accepted` 才能声称交付闭环。

以下状态直接复用固定摘要，不要只用自然语言替代字段：

```text
route: generate
status: blocked
reason_code: worker_capability_unavailable
execution_eligibility: blocked
next_action: 提供可调用的 worker 能力后从逐页派发阶段恢复
```

```text
route: generate
status: ready
reason_code: provider_verification_not_run
execution_eligibility: allowed
next_action: 使用首张真实业务图片完成惰性验证
```

## 风格索引与实际选择

- 名称/别名索引只覆盖 style/pool，不是论证模式或 P 码版式全集。用户问论证模式或版式规则时，直接使用本入口摘要；未知枚举留到 execute 核对对应轴文档，不在风格索引里反复找，也不把未命中说成该模式或版式不存在。
  学术五拍属于论证模式，执行期权威源是 `template-library/canonical/axes/argument/argument-学术五拍/body.md`；advise 说明由 `style render --mode 学术五拍` 注入，结论句标题按论证模式条件化，结论用具体数字而非形容词。五拍精确顺序延迟到 execute 核对原文，不凭名称编造。
- advise 检索工具必须限定到具体索引文件（catalog registry.json 或归档树的具体 `.md`）；
  不得无范围扫描整个 template-library 或 canonical 目录，也不得加载任意完整 brief。
  读错范围后不能通过“回答不依赖这些行”豁免。
  点名查询用 `leo-ppt style list --summary --filter 目标名`（或 resolver `lookup`）；歧义命中会列全部候选，不自动挑第一个。宿主没有任何合规读取能力时报告无法查询。
- advise 的目录证据仅是随包快照，不能声称已核对用户 home。catalog 指针缺失、registry
  损坏或解析器报 stale_catalog 时，不读坏数据、不凭记忆列风格；说明“当前无法确认风格
  目录”，唯一下一步为“重建 catalog（`capability_manifest.py --template-library
  --library-publish`）或修复安装后继续查询”。
- execute 进入视觉方向阶段后，使用当前 runtime Python 运行
  `scripts/capability_manifest.py --template-library --library-check`
  做只读检查（catalog 指针与 canonical 源一致）。该输出只证明注册表新鲜，不证明视觉效果。
  失败时不重建安装目录；resolver 允许从 canonical 只读重建运行时视图，但必须报告
  `registry_source=canonical-rebuild`，不能把该结果当作 catalog 证据或新鲜索引。
- 候选通过 `leo-ppt style list --summary --filter <名称或别名>` 定位；有界输出的 `match_kind` 区分精确名称、
  精确别名和部分匹配，`next_offset` 非空时继续分页。共享别名必须列出全部命中与差异，不默选第一项。
- 对拟展示候选用 `style load <load_name> --summary` 核对实际 scope/source/path/style_content_digest；
  用户同名覆盖优先，不能拿 builtin 的 family、预览或布局事实描述 user 文件。选定前只向 Agent 返回摘要。
- 用户选定后才完整 load，并把摘要的 `selection_fingerprint` 传入 `style render <load_name> --expected-selection <指纹>`；
  list/load/render 必须使用同一个 `--home`。`style_selection_changed` 时停止旧选择，在既有视觉方向门重新核对，
  不触发 Provider、不重写已交付文件。完整 brief 经组合器白名单投影，不把 catalog、metadata 或摘要文本塞进图片 prompt。
- `asset_role=pool` 的池代表与普通 style 分开；已有 `legacy_callable=true` 的池代表只保留用户明确点名的兼容调用。
  无完整 brief 的 pool 不得 compose。缺 golden 不等于不可点名，coverage=full 不等于 visual passed。
- 选定风格后的版式与样张按 `references/layout-dispatch.md` 的作用域/容量/继承合同执行，
  `suggest_layout` 的 auto 不能抵消独立容量预检的 overflow。
- 版式咨询也须说明执行时的独立 `check_deck_geometry.py --capacity` 容量预检；硬超只能改内容或换版式，不缩字号。尚未核实的版式标 `undecided`，不能把风格名称索引当作版式全集。
- 强视觉复用读取 canonical layout profile 的 `reuse_friendly/max_per_deck`；P9 Closing Manifesto 每个 deck 最多一页，不能连续两页使用。定稿前由 `scripts/check_layout_reuse.py` 复核，用户点名不绕过结构上限。
  该上限只约束已登记版式，不自动套用到手绘箭头等装饰元素；装饰是否延续由样张反演证据和用户选择决定。
- 用户要沿用可信 PPTX 的主题色和字体时，执行期先用 `scripts/extract_pptx_theme.py` 确定性提取；`distill_deck_style.py` 是后续完整视觉风格蒸馏，不能代替主题 XML 的读取。advise 只解释此路径，不读取用户文件。
  提取的角色色只走 deck 级 `--color` 锚点覆盖通道，不能回写共享风格 brief 的 `color_palette`。
- 用户描述已选定本次任务的样张时，解释锁定后的三组反演：明确应延续的稳定视觉 / 需确认是否整套延续 / 偶然成立不锁死；随样张确认同一轮呈现，结论随 spec 落盘。不要把本次已选样张默认当成新外来参考图，重新启动整套推荐和确认流程。
  锁定依据是读回样张的真实视觉证据，优先于 prompt 的预期措辞；仅有文字描述时只给暂定判读，执行时核对样张实证，不宣称已看图或已完成锁定。
- 新版式提交到 `template-library/canonical/layouts/<slug>/layout.json`（layout-profile-v1 合同：画布/slot/容量/renderer 绑定），并通过 `scripts/lint_layout_grid.py`；几何真值唯一，不再接受同名 sidecar 双真值。个人未登记草稿留在 `${LEO_PPT_HOME}/template-library/`。advise 可直接说明此规则，不需读取额外 reference。

## 首次使用

仅在 `execute` 模式且 Route 已冻结后读取 [首次使用](references/first-use.md) 和
[执行合同](references/execution-contract.md)。由 Agent 自动运行当前平台 launcher 和
setup；普通用户只在确实缺少凭据时执行一个返回的本地终端动作。凭据与渠道也可经本地
控制台 `leo-ppt ui`（或 `config ui`）自助管理（仅 127.0.0.1 + 一次性 token：渠道发现、新增/
修改/删除/切换/排序；密钥可网页一次性录入直写系统钥匙串——页面与接口零回显——或
终端录入/环境变量引用）。渠道目录共 18 项（15 家目录渠道 + 3 项内置：OpenAI 官方/
自定义中转站/AtlasCloud；目录含 Gemini/MiniMax/Ideogram 等原生协议渠道），添加区按
获取门槛分组为紧凑行式列表——国内直连/国际服务/自定义中转，已配置的行显示
「已配置 ✓」并支持"重新配置"（可沿用现有密钥换 Key）；渠道全表见
[渠道目录](references/provider-catalog.md)。同一控制台的「生成任务」Tab 提供生成过程的
只读可视化（进展/页网格预览/事件时间线/链路/交付，轮询刷新，不驱动运行）；任务发现
来源为全局 `${LEO_PPT_HOME}/runs-registry.jsonl` 登记（`run create` 自动写入，workspace
run 无需手动登记）与 home `projects/*/runs/*` 布局，run 记录自 backend 合同签署起存在。不得从
PATH 猜测 CLI，不得在聊天中接收 secret，也不得把内部 runtime 步骤当作普通用户教程。

## 不变边界

- **协作方式（CONFIRM-GATE）**：执行请求默认委托执行，按已有授权自主完成可逆的
  合同、大纲、母版、风格和样张的制作、内部审查及范围内修复；其中 🔶 SAMPLE-GATE
  （样张门）是默认人工呈现点：逐页派发前必须把视觉方向与样张同轮呈给用户并取得
  认可，用户显式豁免呈现（如"样张不用给我看，直接做完"）时记录 user-delegated
  与豁免原话后继续；豁免只免呈现与等待，不免样张生成、读回与质量检查。用户明确
  选择逐阶段共创时，在约定里程碑呈现具体工件后等待；合同与大纲、视觉方向与样张
  可同轮呈现，修订展示差异。
  内部内容、来源、容量与样张质量检查始终保留。“确认/批准”在后续 reference 中指完成
  对应决策节点，不自动意味着每件工件都要等待人工——样张门是默认增加等待的唯一
  例外（其后即全册付费生成，偏好纠偏杠杆最大的单点）；真实工具的人工状态条件另行遵守。
  内容文档保留 `confirmation: pending|confirmed`：confirmed 表示已审查并可作为生产
  基线，同时记录 `decision_source: user-confirmed|user-delegated` 与 `decision_basis`（会话依据
  和委托范围）。user-delegated 不代表用户逐项审阅，也不能据此填写 CLI 的人工验收字段。
  关键事实无法核实时只阻塞依赖动作；新增费用、扩大范围、当前失败集合的 partial 接受、
  Office 信任和真实人工验收条件仍需相应授权或证据。已覆盖同一动作的授权不重复索取。
  对缺材料的回复说明具体缺口即可，无需复述全流程；可以承诺范围内自主推进，不能承诺
  “以后任何事项都不再确认”，因为未来新增费用、范围变化与人工验收仍可能需要参与。
  数据分级（`data_classification`）据材料和已有声明确定，存疑且影响可用范围时才问；
  机密/绝密直接拒做。内部数据不等于涉密，未公开经营数据定级内部即可继续。
  首轮简述产出与真正需要用户参与的节点，不把内部步骤数量当成对话承诺。
  学术场景（论文/答辩/组会/文献汇报信号）合同另含
  三字段必填——数学量级（math_load）、图表取向（figure_orientation）、分节
  优先级页数分配（section_priority），通用 deck 可选不强制，取值词表进 execute
  后按工作流 reference 核实；
- **敏感文本候选扫描**：定级存疑或素材入库前跑 `scripts/check_sensitive_text.py`
  （命中仅掩码输出；候选非结论，裁决仍归 `data_classification` 分级门）。
- 学术场景按已声明用途确定组会简报（minimal）或答辩证据密集（dense-defense）；无法推断且影响交付时询问，不擅自取密集档。学术场景的一条龙指认（入口信号、五拍/RST/图证据/风格推荐/样张锚点映射）见 [`academic-vertical.md`](references/academic-vertical.md)，用户说「学术模式」即声明该场景；
- **交付档案**：用户保存的交付档案（`${LEO_PPT_HOME}/profiles/<名称>.md`）可预填
  合同草案并逐项标注来源，用户只确认差异项；档案只存偏好字段、绝不存业务数据，
  分级与答辩档位按本次材料重新核对，缺口遵守协作方式（见 `references/image-deck-workflow.md` 步骤 1
  交付档案预填节；保存前过 `scripts/check_delivery_profile.py`）；
- **模版推荐与选择**：风格候选由合同信号驱动、默认推荐必须带归因一句；用户指定
  优先序＝点名 > 参考图 > 推荐（给了参考图就跳过推荐直行，只提取视觉系统并经
  样张并排比对验证）；错配首次必须提示一句风险与替代建议（用户预先说"别劝"也不豁免首次告知），之后尊重选择并在 style 合同记录用户选择依据、不再重复劝阻；品牌 VI 经
  `style render --brand` 注入——`${LEO_PPT_HOME}/brands/` 用户档案优先于内置
  10_品牌身份 预设，浅底对比度 <4.5:1 报错并给最近合规建议色；用户纠结或双参考图时提议
  样张双生（两张使用同一内容页，仅改变视觉风格；多一张图成本先告知，点头才出，二选一落选即弃不追加第三方向）——全部寄生既有视觉方向确认与样张点，不新增
  确认门（见 `references/style-recommendation.md`）。委托执行下 Agent 完成样张内部审查后，仍须按 🔶 SAMPLE-GATE 把视觉方向与样张呈用户认可才开始批量派发（用户显式豁免呈现时记 user-delegated 与豁免原话）；不能跳过真实出图、读回和质量检查。generate 路线的大纲与逐页母版必须在 `<project-root>/content/` 下落盘（`outline-v<N>.md` / `deck-master-v<N>.md`），头部携带 `confirmation` 和决策依据，聊天只引用路径与变更摘要；该文档门仅在 execute 模式生效。
  advise 回答点名错配时也须保留“一次风险提示 + 后续记录选择依据”的承诺；记录用户实际给出的理由，未给理由标未提供，不把口头锁定冒充已落盘。
  被问“这个风格能不能做”时，先分别说明真实索引命中与能力状态：已有 renderability
  证据才说“可以做/可渲染”，否则说“可进入样张验证”并保留未验证边界，不承诺立即出图或已完成渲染。
  风格候选先过 `scripts/style_hard_rules.py --check-brief`（排除错配/锁定强语境，用户
  点名即 bypass）；在可行候选内优先给出跨家族差异，不为配额引入不适用方向；点名不存在时列相近候选（子串/别名/同轴
  邻近）不静默替换；点名资产可为可信标杆 deck 蒸馏档案（`scripts/distill_deck_style.py`，
  Gate 0 信任先行）。风格库治理默认以 `template-library/canonical/styles/*/brief.json`
  为真源，运行 `lint_style_briefs.py`、`lint_style_governance.py` 与
  `audit_style_families.py`；旧 Markdown 树仅在显式 `--legacy-fixtures`/迁移参数下检查。
  另用 `generate_style_gallery.py --check`（金样板回归，漂移 exit 1）验证用户可见画廊。
- **比例合同**：页图与交付画布必须同比例：generate 路线 slide 图片像素尺寸档必须为交付画布宽高比（默认 16:9，基准 2560×1440）。样张提交、样张方法继承与交付前都必须断言该比例；交付前必须运行 `scripts/check_deck_geometry.py`（非 0 退出阻止交付）。继承既有 sample_generation_method 前必须核验其像素尺寸档，比例不符（如历史 3:2 素材）不得继承，视为 generation method 变更，须重新生成并确认样张。
- **文字保真降级链**：文字错误先 TF-1 压文本预算回母版减法重生成（至少一轮）；TF-2
  留白贴字（`scripts/overlay_text.py`，底图仍来自确认 backend、逐字来自
  required_text 白名单）属 generation method 变更，须样张重确认——这是唯一允许的
  确定性贴字例外，未经确认不得贴字交付。
- **母版真值**：逐页母版是内容真值工件：每页四段——结论句标题（按论证模式条件化）、要点
  （按页面角色禅档位：陈述/氛围 0–1 条、论点页 ≤3、台账页 ≤6，每条 ≤2 行；论点/
  证据/方案页正文合计 ≤80 字，每要点行 ≤40 字）、
  视觉行（容器清单 + 每个要点落位声明 + 图像来源三级）、备注（speaker_script 与
  engineering 分栏）；内容层失败先改母版再重建受影响页，
  不绕过母版直接改图（见 `references/deck-master.md`）。
  页数未明确“正文”时默认成品总页数，结构页从总数内分配；三点叙事是短演讲建议，
  不强迫独立决策合并。图表即使数据点少，只要依赖精确几何、多轴或后续编辑也走原生图表。
  母版落盘后跑 `scripts/check_deck_prose.py`（文案纪律线索，翻案腔超限 exit 1）与
  `check_number_ledger.py --diff`（TF-1 后 verified 数字留存断言）；高保障档冻结后
  派发前另跑 `scripts/check_content_facts.py`（数字断言回读材料，有界 2 轮）；
  post-confirm 写回与恢复按 [执行合同](references/execution-contract.md)「内容层状态与恢复」（CAS verify / run ledger / reproject）。
- **三级标注**：数字与断言三级标注：引用（有出处）/ 估算（标"估算"或"经验值"）/ 示意（标"示意"，
  不得用图表版式）；三级之外来源不足一律标 `unknown` 求证，不得直接写入页面。材料
  整体缺失属于输入层的 unknown：先说明缺少哪些依据、影响什么产出和唯一下一步，
  机器状态保留 `input_material_missing`；可继续不依赖缺失事实的已授权准备。
  四级（含用户确认）与要点级 source_ref 语法见 `references/deck-master.md`。
  材料缺失的解释部分按 [输入路由](references/input-routing.md)「材料缺失 → 研究代采
  轻形态」节附研究问题清单与建议检索渠道/素材类型，经合同确认门确认（零宿主依赖、
  不联网；用户要求代采而 R-69 条件未齐备时如实说明能力边界并指回清单自取材）。
- **再检要求**：打回重做后的再检必须同时写出目标判据结论与波及面结论（如改文字→复查密度与
  截断）；qa_note 只写"已修复"不构成通过。
  改母版重生成前用 `scripts/compute_impact.py` 推导受影响页清单；含目录/agenda
  的 deck 母版携带 deck-promises 承诺表（见 `references/deck-master.md`）。
- **护栏最小完备**：收束页与认错/失效线的每个动作项必须携带 owner 与时限，
  验证类动作必须附交付物定义与验收标准（可核条件+验收人）；共享资源动作项
  须核对并行冲突；每条失效触发附一句分支预案。请求金额须有登记表测算行或
  显式 `unknown`+补齐时限（细则见 image-deck-workflow 第 1 步与 deck-master
  纪律；`check_master_contract` ⑪⑫ WARN 判据为机器子集）。
- **CLI 真值**：只依据 CLI 的 versioned JSON、状态、manifest、validation 和 artifact 推进；不手写
  领域状态，不直接 import `_vendor`，聊天声明不构成完成证据。
- **真实派发**：多页任务必须核对用户授权、宿主能力、容量和真实派发；主 Agent 不模拟 scheduler。
- **宿主能力表述**：宿主能力缺失只能用 CLI 结论或对应固定块的 `reason_code` 表述；不得枚举、点名或
  诊断宿主的 Agent/子代理清单、注册表或目录来解释缺失原因，也不得据此提出改造
  宿主的步骤建议。
- **worker 缺失固定块**：多页 worker 缺失、未知或调用失败时，先原样输出下面五行，再结束本轮；不得先写
  “当前无法生成”等自然语言，也不得由主 Agent 静默串行替代（宿主可运行脚本时以
  `render-control-summary.py --fixed worker-unavailable` 输出；无法运行脚本时手写
  并显式记录 `worker_render: handwritten`）：

  ```text
  route: generate
  status: blocked
  reason_code: worker_capability_unavailable
  execution_eligibility: blocked
  next_action: 提供可调用的 worker 能力后从逐页派发阶段恢复
  ```

  只有用户明确提供 worker 能力后才能离开该状态。恰好一页也必须由 CLI 返回
  `single_unit_current_agent_allowed`。
- **凭据边界**：凭据只由宿主或 allowlist reference 管理；不得读取私有认证文件、保存明文 secret，
  或把 token、完整环境和用户正文写入日志。
- **Provider 三态**：`configured_unverified` 允许开始任务；只有 `not_configured`/`invalid` 才暂停
  图片节点并只给一个 `run_cli` Primary_Action；`unknown` 不得当作 `available`。
- **验证分报告**：结构验证、provider、OCR、viewer、desktop、独立渲染和人工视觉证据分别报告；只有
  `delivery_readiness=accepted` 才能声称交付闭环。
- **能力与成本前置**：长时间整理内容前，先核对当前宿主 worker 声明、所需能力与本地
  Provider 配置，区分配置可用和真实生成已验证；不额外发起付费探针。按页数、样张与
  重试假设给出初步费用区间和授权范围，未知价格如实说明；不能以未知作零费用或无限预算。
  首个收费动作前核对已有授权，未覆盖新增费用才询问；样张承担首张业务验证。逐页派发前
  用最终页计划更新本次 deck 的 token/成本预估区间并披露依据
  （有历史 `backend_stats` 用历史均值×重试系数，无历史或 `not-recorded` 用保守假设区间并
  如实标注假设；`scripts/estimate_run_cost.py` 生成，估算是区间不是承诺）；交付披露须与
  `backend report` 实际 `tokens_total` 对账一句，超出预估带上限要说明原因。
- **指纹收据门**：交付声明前必须 `delivery receipt create`（五类 sha256 指纹落
  `<run>/reports/delivery-receipt.json`）；交付或导出前必须 `delivery receipt verify`
  全一致（`delivery_receipt_fresh`）——收据缺失按 not_run 披露、漂移
  （`delivery_receipt_stale`）阻断交付并按波及面处置；`accepted` 隐含收据存在
  且 fresh，不得以聊天声明或手写收据替代。
- **交付披露**：最终回复必须包含 PPTX 与必要逐页/notes/failure report 路径、结构验证结果，以及
  provider/OCR/viewer/desktop/人工视觉验证中所有未运行项。含图片证据的交付披露还须包含
  来源清单校验状态（交付前 `scripts/check_sources_manifest.py <run> --strict`，非 0 退出
  阻断，WARN 项逐条披露）与 TF-2 fallback 页清单。用户要求讲稿交付物时,经
  `scripts/export_speaker_notes.py`（`--pptx` 成品 / `--master` 母版）导出,缺备注页
  如实列出,不得编造口播稿（可加 `--prose-check` 顺手输出讲稿口语化 PROSE-WARN,
  建议项不阻断）。用户要求讲义 PDF / 长图交付物时,经 `scripts/export_deck.py`
  导出（started / completed / failed 三态回执,failed_pages 逐页列缺页/坏页）,
  导出属交付动作、同过 🔴 DELIVERY-GATE 披露。

## 红灯清单（反模式速查）

以下动作一律禁止；判据全文见对应章节，命中即按该章固定块或规则处理：

| 红灯动作 | 正确处置 | 出处 |
| --- | --- | --- |
| 读取、扫描、隔离、净化来源未知的 PPT/PPTX | Gate 0 固定阻断；"警告后继续/净化后继续"均无效 | Gate 0 |
| 纯文档排版、单张配图/封面/图表素材、网页/表格微改 | 不属本 Skill，礼貌指路 | frontmatter 边界 |
| 主 Agent 串行替代缺失的 worker | 固定块 `worker_capability_unavailable`，不得静默替代 | 不变边界 |
| 手写领域状态、直接 import `_vendor`、以聊天声明充当完成证据 | 只依据 CLI versioned JSON 推进 | 不变边界 |
| 枚举/点名宿主子代理清单来解释能力缺失 | 用固定块 `reason_code` 表述，不诊断宿主 | 不变边界 |
| 经聊天接收 secret 或写入日志/私有认证文件 | 凭据只经宿主或 allowlist reference | 不变边界 |
| 把委托执行冒充人工批准，或跳过样张检查/数据分级 | 记录真实决策来源，保留质量检查与重要授权边界 | 不变边界 |
| 未按 🔶 SAMPLE-GATE 呈现视觉方向与样张（且无显式豁免记录）即逐页派发 | 回样张门补呈现，取得认可或豁免记录后再派发 | 不变边界 |
| 以 `status=completed` 声称交付闭环 | 须 `delivery_readiness=accepted` | 🔴 DELIVERY-GATE |
| 未经当前成功/失败集合确认即交付 partial | 🔴 PARTIAL-GATE：先展示集合再明确接受 | upgrade-selected |
| 用整页截图叠少量文本冒充对象级可编辑 | 禁止；真实 spawn 前不得记录 dispatch | 执行导航 direct-editable |
| 编造素材链接/来源直接出图 | 素材先过 `validate_assets.py` 校验，失败标 unknown 禁止入页，替换或降级示意后重验 | 图片式工作流 3b 步 |

## 执行导航

进入具体 Route 后才读取对应 reference；跨 Route 的 runtime、项目、worker、恢复和
交付规则统一读取 [执行合同](references/execution-contract.md)。

### generate

读取 [图片式工作流](references/image-deck-workflow.md)、
[Backend 选择](references/backend-selection.md) 和
[视觉质检规范](references/visual-qa.md)。

按协作方式完成完整内容、风格、backend 和一个样张的审查后（样张默认恰好 1 张且锚定正文页角色；
目录/封面等结构页加样必须先告知多一张图的成本并经用户点头才出；仅点名两张或说
“不用再问”不构成已接受尚未披露的额外成本，不得写“点头视为已给”。已披露且获明确
授权的同一加样不重复询问；advise 只说明成本及待确认项，不预记同意或承诺直接加样。
选定后同一轮呈现
风格反演三组判读——明确应延续的稳定视觉 / 需确认是否整套延续 / 偶然成立不锁死，
以样张读回实证为准，反演结论随 spec 落盘），按需读取 [风格库](references/style-library.md)
和 [slide worker prompt](prompts/slide-worker.md)。style/layout 必须由确定性模板生成；
缺页、未完成状态或任一页 QA 失败都阻止组装。组装复验时逐页核对合同约定的版面
固定件（页码/页脚位置与字号一致），页内文本引用与实际页码核对存在。用户要求高保障
档位时，启用 [视觉质检规范](references/visual-qa.md) 第六节多轮审查协议（镜头池轮换，
连续两轮无 P1/P2 才收敛；台账记录，驳回须给依据；高保障档另可选 rubric 合成分与迭代硬预算,默认不启用）与交付双评审官可选档
（见 [执行合同](references/execution-contract.md)，分歧 ≥2 分复议，不替代三证）。

### direct-editable

读取 [可编辑工作流](references/editable-workflow.md)、
[Manifest Schema](references/manifest-schema.md) 和
[Page Decision Tree](references/page-decision-tree.md)。

图片/PDF 可直接 prepare；PPT/PPTX 必须先通过可信确认与 preflight。真实 worker 可用
后才读取 [page worker prompt](prompts/page-worker.md)。不得以整页截图叠少量文本冒充
对象级可编辑，也不得在真实 spawn 前记录 dispatch。

editable 组装内核为双 builder 等价（`LEO_EDITABLE_BUILDER=pptx|legacy`，默认 legacy）：
对象级 object_builder 对非法 preset 在 build 期 ValueError 拒绝而非透传，见 [执行合同](references/execution-contract.md)。

### upgrade-full

冻结原 image-deck 的页面、hash、尺寸和 notes，再按 `direct-editable` 处理全部页面；
失败不得破坏原图片交付物，全部页面和 deck validation 通过后才能声明全可编辑。

### upgrade-selected

冻结选中页集合，只升级选中页。默认任一失败都不交付 partial；🔴 PARTIAL-GATE：只有展示当前成功/失败
集合并取得明确接受后才能生成 `partial-hybrid`，且不得声称全可编辑。失败集合变化时
必须重新确认并保留旧 artifact revision。

用户要求“失败页保留原图并直接交付”但尚未看过当前成功/失败集合时，即使处于
`advise` 也必须明确回答：本轮不会执行；先展示当前成功/失败清单，再由用户明确接受
`partial-hybrid`。普通执行授权不能替代对当前失败集合的精确确认。
