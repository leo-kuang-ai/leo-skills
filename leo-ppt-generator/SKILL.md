---
name: leo-ppt-generator
description: 生成图片式 PowerPoint（PPTX）演示文稿：从文章、报告、笔记或大纲产出成套逐页可交付的演示稿；把图片、PDF 或用户确认可信的 PPT/PPTX 重建为对象级可编辑 PPTX；或把图片式演示文稿升级为 editable/hybrid。若 PPT/PPTX 来源未知、无法确认或尚未确认可信，仍触发本 Skill，但必须立即固定返回 blocked/untrusted_office_input，禁止读取、扫描、隔离、净化或规划重建；用户要求“净化后继续”不构成可信授权。当用户要求做 PPT、把视觉稿转成可编辑 PowerPoint、升级图片版 PPT 或保留部分图片页时使用。不要用于纯文档排版、单张配图/封面/图表素材、网页/表格轻微修改或视频任务。
---

# Leo PPT Generator

通过一个入口完成图片式、全可编辑或 hybrid PPTX。顶层 Agent 拥有意图、确认、
live host capability、worker 派发和交付判断；`leo-ppt` 只拥有确定性准备、状态、
验证和组装。

执行主线：①Gate 0 信任检查 → ②advise/execute 判定 → ③Route 四选一 →
④按需读取 references → ⑤🔴 确认序列（合同 → 大纲 → 母版 → 视觉方向 → 样张；
相邻门可同回合呈现——合同+大纲、视觉方向+样张——仍逐件明示确认）
→ ⑥生成与验证 → ⑦组装 → ⑧🔴 DELIVERY-GATE 交付闭环。各步骤规则见下文对应
章节；主线路径之外的分支（材料缺失、worker 缺失、partial）按"不变边界"处理。
任何状态回复都遵守「控制面响应合同」的五字段块输出纪律（block-early：出现在
回复前 3 个非空行之内、先于任何叙述），该纪律适用于全 Skill 所有分支。

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
绕过旧 `.ppt`、宏、嵌入对象、external relationship、远程模板或损坏结构检查。
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
  唯一的工具豁免是 `scripts/render-control-summary.py --fixed gate0` /
  `--fixed worker-unavailable`：该模式不读取任何文件、无副作用，输出固定块不构成
  执行动作，用户“不要执行任何操作”的表述不得据此改回手写。宿主确实无法运行脚本时
  才手写固定块，并显式记录降级 `gate0_render: handwritten` 或
  `worker_render: handwritten`。
- `execute`：用户明确要求制作、转换、升级、继续既有任务，且已授权进入执行流程。只有
  此模式才按“首次使用”和对应 Route 读取后续资源。
- 同一请求同时包含咨询和执行指令时，以咨询为准，先回答是否可以执行；不得因为请求
  中出现“直接做”“顺便生成”等词就进入 `execute`。只有用户在后续消息明确授权后才
  切换模式。

`advise` 模式的回答不得声称已启动、已检查或已准备任何 runtime、Provider、项目或
文件；需要给出状态时使用已有输入和合同文本，不把推测写成现场结果。回答第一行必须
输出 `interaction_mode: advise`；若存在路线选择，随后明确列出候选 Route，不得只用
“严格可编辑”“风格重设计”等自然语言替代 Route 名称。

`advise` 使用以下入口 Route 表，不打开 `input-routing.md`：

| 用户目标 | Route |
| --- | --- |
| 从文章、报告、笔记或大纲新建演示文稿 | `generate` |
| 把图片/PDF/可信 Office 重建为对象级可编辑 | `direct-editable` |
| 把既有 image-deck 全量升级为可编辑 | `upgrade-full` |
| 只升级既有 image-deck 的指定页 | `upgrade-selected` |

内容与视觉稿并存且用户未决定“严格保留布局”还是“仅作风格参考”时，只说明前者对应
`direct-editable`、后者对应 `generate`，然后等待选择。🔴 ROUTE-GATE：不得替用户预选。回答必须先原样输出：

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
| `generate` 执行 | `image-deck-workflow.md`、`deck-master.md`、`style-recommendation.md`、`backend-selection.md`、`visual-qa.md` | styles 直到风格已选；`slide-worker.md` 直到样张通过；`academic-figure-evidence.md` 直到进入母版制作且材料含图片证据/学术场景；`sources-manifest-schema.md` 直到 `image prepare --sources` 冻结与交付前 strict 校验；`rst-paging.md` 直到大纲制作且材料多段/结构复杂 |
| `direct-editable` 执行 | `editable-workflow.md`、`manifest-schema.md`、`page-decision-tree.md` | `page-worker.md` 直到真实 worker 已确认 |
| `upgrade-*` 执行 | 对应 editable references，加当前 baseline/selection 证据 | 未选中的 workflow 和全部 styles |

`references/styles/` 约束为按需索引：先读 `style-library.md`，选定风格、论证模式和版式
后只读对应的单个风格文件；禁止预加载整个 styles 目录。`reason-codes.md` 只在已有
reason code 需要解释或恢复时读取。执行前未命中的 references 不得因为“可能有用”而读取。

所有场景（含 advise、材料缺失、worker 缺失）的回复都必须先输出下节「控制面响应合同」的五字段块，再写任何解释。

## 控制面响应合同

除纯内容创作外，所有 Route、setup、run、worker、验证和交付状态都必须先输出以下五
个字段，再补充解释：

能取得 CLI JSON 时，必须先将其通过 `scripts/render-control-summary.py` 渲染；不得由
Agent 手工改写字段。渲染器只输出五行摘要，不读取文件、不访问网络、不产生副作用；
Gate 0 与 worker 缺失两类固定阻断块在宿主可运行脚本时同样必须经
`--fixed gate0` / `--fixed worker-unavailable` 产生，不得手写改写。该要求对
`advise` 与 `execute` 一律适用：advise 只是禁止执行动作，不是免除控制面输出。
顺序属合同本体（block-early）：五字段块必须出现在回复前 3 个非空行之内、先于
任何叙述；先于块的行只能是元数据性行（如 `interaction_mode:`、简短状态标签，
每行 ≤40 字符），长叙述先行仍属违约。手写降级披露行
（`gate0_render: handwritten` / `worker_render: handwritten`）属于解释部分，
必须置于五字段块之后单独成行，不得插入块前——置于块前即违反位置合同。
execute 开始后的首次状态汇报应附带本地版本与人话就绪度一句；若检测到自上次
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

## 首次使用

仅在 `execute` 模式且 Route 已冻结后读取 [首次使用](references/first-use.md) 和
[执行合同](references/execution-contract.md)。由 Agent 自动运行当前平台 launcher 和
setup；普通用户只在确实缺少凭据时执行一个返回的本地终端动作。不得从 PATH 猜测 CLI，
不得在聊天中接收 secret，也不得把内部 runtime 步骤当作普通用户教程。

## 不变边界

- 🔴 CONFIRM-GATE（人在回路，逐门暂停等待用户明示）：在会改变结果前确认大纲、完整内容、风格、图片 backend、样张或升级页集合，
  以及数据分级（`data_classification`：材料含未公开/涉密样貌数据时必须定级，
  机密/绝密直接拒做）——分级确认同样不因跳过授权而豁免；首轮冻结合同（含材料
  缺失分支）须预告剩余确认序列「合同 → 大纲 → 逐页母版 → 视觉方向 → 样张」，
  用户才知道确认点还有几个；相邻确认点可同回合呈现（合同+大纲同回合、视觉
  方向+样张同回合，逐页母版独立成回合）——合并的是往返不是确认：每件工件仍须
  用户明示确认后才冻结，用户只确认其一时仅冻结其一，材料缺失或口径歧义时仍
  先单独冻结合同；学术场景（论文/答辩/组会/文献汇报信号）合同另含
  三字段必填——数学量级（math_load）、图表取向（figure_orientation）、分节
  优先级页数分配（section_priority），通用 deck 可选不强制，取值词表进 execute
  后按工作流 reference 核实；
- 学术场景还须问明交付档位：组会简报（minimal）还是答辩证据密集（dense-defense），未问明不得默认取密集档；
- **模版推荐与选择**：风格候选由合同信号驱动、默认推荐必须带归因一句；用户指定
  优先序＝点名 > 参考图 > 推荐（给了参考图就跳过推荐直行，只提取视觉系统并经
  样张并排比对验证）；错配首次必须提示一句风险与替代建议（用户预先说"别劝"也不豁免首次告知），之后尊重选择并在 style 合同记录用户选择依据、不再重复劝阻；品牌 VI 经
  `style render --brand` 注入——`${LEO_PPT_HOME}/brands/` 用户档案优先于内置
  10_品牌身份 预设，浅底对比度 <4.5:1 报错并给最近合规建议色；用户纠结或双参考图时提议
  样张双生（多一张图成本先告知，点头才出，二选一落选即弃不追加第三方向）——全部寄生既有视觉方向确认与样张点，不新增
  确认门（见 `references/style-recommendation.md`）。execute 授权或用户的"不用确认"要求不豁免该确认序列，样张确认尤其不可跳过。generate 路线的大纲与逐页母版确认对象是 `<project-root>/content/` 下的版本化文档（`outline-v<N>.md` / `deck-master-v<N>.md`）：提交确认前必须落盘并在头部携带 `confirmation` 状态标记，聊天只引用路径与变更摘要，不整篇复述；该文档门仅在 execute 模式生效。
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
- **三级标注**：数字与断言三级标注：引用（有出处）/ 估算（标"估算"或"经验值"）/ 示意（标"示意"，
  不得用图表版式）；三级之外来源不足一律标 `unknown` 求证，不得直接写入页面。材料
  整体缺失属于输入层的 unknown：同样必须先输出控制面五字段块（如
  `input_material_missing`）再解释，不得以自然语言"要材料"开头；并在解释中重申
  确认序列（大纲/母版/样张）不因用户的跳过授权而豁免。
- **再检要求**：打回重做后的再检必须同时写出目标判据结论与波及面结论（如改文字→复查密度与
  截断）；qa_note 只写"已修复"不构成通过。
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
- **成本预估前置**：逐页派发前必须给出本次 deck 的 token/成本预估区间并披露依据
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
  阻断，WARN 项逐条披露）与 TF-2 fallback 页清单。

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
| "不用确认"跳过样张或数据分级 | 🔴 CONFIRM-GATE 序列不豁免 | 不变边界 |
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

确认完整内容、风格、backend 和一个样张后（样张默认恰好 1 张且锚定正文页角色；
目录/封面等结构页加样必须先告知多一张图的成本并经用户点头才出；选定后同一轮呈现
风格反演三组判读——明确应延续的稳定视觉 / 需确认是否整套延续 / 偶然成立不锁死，
以样张读回实证为准，反演结论随 spec 落盘），按需读取 [风格库](references/style-library.md)
和 [slide worker prompt](prompts/slide-worker.md)。style/layout 必须由确定性模板生成；
缺页、未完成状态或任一页 QA 失败都阻止组装。组装复验时逐页核对合同约定的版面
固定件（页码/页脚位置与字号一致），页内文本引用与实际页码核对存在。用户要求高保障
档位时，启用 [视觉质检规范](references/visual-qa.md) 第六节多轮审查协议（镜头池轮换，
连续两轮无 P1/P2 才收敛；台账记录，驳回须给依据）与交付双评审官可选档
（见 [执行合同](references/execution-contract.md)，分歧 ≥2 分复议，不替代三证）。

### direct-editable

读取 [可编辑工作流](references/editable-workflow.md)、
[Manifest Schema](references/manifest-schema.md) 和
[Page Decision Tree](references/page-decision-tree.md)。

图片/PDF 可直接 prepare；PPT/PPTX 必须先通过可信确认与 preflight。真实 worker 可用
后才读取 [page worker prompt](prompts/page-worker.md)。不得以整页截图叠少量文本冒充
对象级可编辑，也不得在真实 spawn 前记录 dispatch。

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
