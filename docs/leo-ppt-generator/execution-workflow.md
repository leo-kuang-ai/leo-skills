# 优化后的 PPT Skill 详细执行流程

更新日期：2026-09-18。适用对象：`leo-ppt-generator` 的使用者、维护者与流程评审者。

本文依据当前仓库入口 `SKILL.md`、各路线 workflow reference、执行合同与运行时 CLI 整理，描述现有实现与约束，不是新增开发方案。核心路径是：**先明确内容与表达输入，按实际来源检索和推荐风格，验证版式容量与样张，冻结表达输入代，再生产页面、组装和验收。**

本次同步的两个重点：一是模板库 v2 的「canonical 真值 + catalog generation 指针」结构，以及管理侧（构建、探针、样式包导入、五阶段迁移）与使用侧（有界发现、摘要核对、选择指纹、投影渲染）的分工；二是 generate 路线的「表达优先」内容冻结链——母版经内容包编译为 `PipelineRequest`，由 `leo-ppt generate --request` 冻结为不可变输入代，`image prepare` 只消费已提交代。语义判断由 Agent 完成，确定性脚本负责索引、作用域、指纹、容量和状态检查。

## 1. 总流程图

以下用 ASCII 连线表达流程；路线内部的必要回退见后续章节。

```text
用户请求
   |
   v
Gate 0 输入边界检查（Office 文件先判断来源可信条件）
   |
   +-- 来源未知的 PPT/PPTX --> blocked 固定块，不读取输入文件
   |
   v
交互模式判定
   |
   +-- advise --> 解释 / 比较 / 有界风格目录查询（current 指针 --> registry.json）--> 返回建议
   |
   +-- execute
         |
         v
选择路线 + 前置低成本能力与预算核对 + 按需加载合同 + 准备 runtime / 项目
         |
         +-- generate ----------> [A] 新建图片式演示稿
         +-- direct-editable ---> [B] 对象级可编辑重建
         +-- upgrade-full ------> inspect 冻结全部原页 --> [B]
         +-- upgrade-selected --> inspect 冻结选中页集 --> [B]
                                                       |
         +---------------------------------------------+
         |
         v
[A] 内容合同 --> 大纲 --> 逐页母版 --> 数据密度 / 素材 / 事实检查
     --> 风格检索与选择 --> 版式容量预检 --> backend 与全册尺寸预算
     --> 正文样张（🔶 SAMPLE-GATE 呈现）
     --> 🔒 内容冻结：content pack --> PipelineRequest --> generate --request
     --> image prepare --> 真实 worker 派发 --> 逐页 QA
[B] editable prepare --> next --> dispatch --> record --> finalize
         |
         v
组装（全册 recorded；hybrid 混装尺寸统一）
         |
         v
交付门：几何 / 尺寸预算 / 来源 strict / 敏感文本 / preflight / 指纹收据
         |
         +-- 失败 --> 按波及面修复并复验（收据漂移阻断交付）
         |
         v
提供文件、准确交付类型、验证结果与未运行项
         |
         v
检查 delivery_readiness
         |
         +-- accepted --> 交付闭环完成
         +-- 其他状态 --> 如实说明尚缺验收项与唯一下一步
```

`generate` 的内容策划与风格样张流程不应机械套用到可编辑重建。后者的主要依据是源页内容和对象级 manifest。`generate` 目标先产出完整表达输入代再进入 editable 的阶段时，走
`generate → upgrade import-baseline` 两段关联 run，见第 5 节。

## 2. 入口、授权与职责

### 2.1 咨询与执行

| 模式 | 进入条件 | 允许动作 | 结果边界 |
| --- | --- | --- | --- |
| `advise` | 解释、比较、状态询问，或明确要求先不执行 | 根据入口回答；风格咨询可有界读取 `catalog/current.json` 指针与其指向的 `catalog/generations/<gen>/registry.json`（名称/别名/ID/生命周期），或用等价的只读终端查询 | 不启动 Provider、不建立 run、不读取用户输入文件；唯一工具豁免是两类固定块的渲染脚本 |
| `execute` | 明确要求制作、转换、升级或继续已授权任务 | 按所选路线准备项目、检查输入、生成与验证 | 根据真实 CLI 状态推进，不把聊天声明写成运行证据 |

风格咨询的读取范围不包含完整 brief，也不递归 canonical/styles 目录。registry 只证明随包
目录快照，不能证明用户 home 中实际覆盖的风格。咨询时指针缺失、registry 损坏或解析报
`stale_catalog`，应说明无法确认目录，不靠记忆列举或现场重建；重建入口为
`capability_manifest.py --template-library --library-publish`。`advise` 与 `execute` 共用同一
Route 表（`advise` 不打开 `input-routing.md`）。Gate 0 与 worker 缺失两类固定阻断块在可运行
脚本的宿主上必须经 `scripts/render-control-summary.py --fixed gate0|worker-unavailable` 原样产生；
无法运行时才手写，并显式记录 `gate0_render: handwritten` / `worker_render: handwritten`。

### 2.2 四条路线

| Route | 典型输入 | 主要交付 | 特殊边界 |
| --- | --- | --- | --- |
| `generate` | 文章、报告、笔记、大纲 | 图片式 PPTX，按数据需求可能涉及混合页面 | 不以本地绘图替代已选图片 backend 的最终页图 |
| `direct-editable` | 图片、PDF、可信 Office | 对象级可编辑 PPTX | 整页截图加少量文本不能冒充可编辑 |
| `upgrade-full` | 已有图片式 deck | 全部页面升级的可编辑 PPTX | 全部目标页及整套验证通过才能称为全可编辑 |
| `upgrade-selected` | 已有 deck 和指定页集合 | 保留未选原页的 hybrid PPTX | 正常混合交付与升级失败后的 `partial-hybrid` 分开 |

Office 来源可信后仍要执行结构 preflight；宏、嵌入对象、external relationship 等检查不会被可信声明豁免。旧 `.ppt` 需要先转为支持的输入形态。

两条 upgrade 路线在进入 editable 子流程前先由 `upgrade inspect` 冻结原交付物（页面、hash、尺寸、notes），再由 `upgrade import-baseline` 建立与源 generate run 关联的目标 run：baseline 冻结源交付、页图、notes 与内容/设计快照副本（`source_binding` 记录源 run ID、交付 SHA、内容/设计摘要与目标路线），复制校验全部通过才发布；同一目标输入漂移即 `upgrade_baseline_conflict`。父 generate 成功只表示前一阶段完成，可编辑目标只认 upgrade run 的最终对象与视觉回读证据。

### 2.3 谁负责什么

| 角色 | 职责 |
| --- | --- |
| 顶层 Agent | 理解目标、编排内容、解释推荐、处理授权、核对宿主能力、派发任务、独立复核和判断交付 |
| `leo-ppt` 与辅助脚本 | 确定性准备、索引查询、选择核验、版式容量、run 状态、组装、验证与收据 |
| worker | 仅处理分配页面并返回产物和验证证据，不擅自修改全局内容或风格 |
| 用户 | 提供关键事实，作出未委托的重要选择，确认新增费用或范围，完成需要真实人工参与的验收 |

### 2.4 确认节点如何理解

内容侧存在“合同 → 大纲 → 逐页母版 → 视觉方向 → 样张”五类确认对象。合同与大纲、视觉方向与样张可分别同轮呈现。

执行请求默认委托执行：已有授权内的可逆制作、内部审查与范围内修复自主推进，记录
`decision_source: user-delegated` 与依据；用户选择逐阶段共创时在约定里程碑等待，人工选择记录
`user-confirmed`。两者都保留内容、容量和样张检查。默认唯一增加的等待点是 🔶 SAMPLE-GATE
（样张门）：逐页派发前必须把视觉方向与样张同轮呈给用户并取得认可；用户显式豁免呈现时记录
`user-delegated` 与豁免原话后继续，豁免只免呈现与等待，不免样张生成、读回与质量检查。

六个推进节点（合同、大纲、母版、视觉方向＋样张、PARTIAL-GATE、DELIVERY-GATE）向人呈现时使用
三行固定摘要（变了什么／影响什么／需要决定什么），模板与用户语言强制项见
`references/decision-brief.md`；确定性构建走 runtime `layout_proposals.decision_brief`，呈现缺席时
降级为 CLI 报告（cli-fallback），委托模式下简报仍生成、仅呈现豁免（exempt-user-delegated 留痕）。
不把内部节点变成固定多轮对话。新增费用、范围变化、当前失败集合的接受及真实人工验收条件分别核对。

页数超过 40（阈值可按合同声明）时母版按节分批落盘与确认（R-42）：大纲全册一次确认，各节独立
携带 `confirmation` 状态，全部节 confirmed 才构成母版 confirmed 基线；节内修订复用 post-confirm
机制，不新增确认门。

普通状态回复先说明结果、影响和必要下一步，机器五字段保留用于诊断；用户指定纯 JSON 时不追加说明。Office 信任与 worker 缺失仍保留固定阻断响应。

## 3. 新建图片式 PPT 的详细主线

```text
[A] generate
     |
     v
最小目标 / 能力与费用范围 --> 内容合同 --> 大纲 --> 逐页母版
                              |
                              v
                    3a 数据密度路由 / 3b 素材校验 / 3c 事实核查（高保障档）
                              |
                              v
                    风格检索 --> 推荐或点名选择 --> 实际来源摘要核对
                              |
                              v
                    版式调度 + 容量预检 + 强视觉复用上限
                              |
                              +-- overflow --> 改内容或换版式 --+
                              |                                  |
                              ^----------------------------------+
                              |
                              v
                    固定 backend / 像素尺寸档 / 生成方法 / 全册尺寸预算
                              |
                              v
                    正文难页样张 --> 读回反演 --> 🔶 SAMPLE-GATE 呈现认可
                              |
                              +-- 不满足 --> 调整后重做样张
                              |
                              v
                    🔒 表达冻结：content pack --> PipelineRequest --> generate --request
                              |
                              v
                    slides / 术语表 / sources-manifest + 样张绑定
                              |
                              v
                    image prepare（只读已提交输入代）--> 真实 worker 派发
                              |
                              v
                    逐页 QA（五层非补偿门）--> 失败修复与波及面复验
                              |
                              v
                    全部页 recorded --> 组装 --> 整套复验 --> 交付门
```

### 3.1 内容合同：先确定要解决什么问题

输入是原始材料与用户目标。合同明确主题、受众、场景、演讲时长、行动目标、页数口径、材料来源、必须出现的事实与不可杜撰项。

整套需要一句话主线 `one_thing`；无法确定时标记 `unknown`。发布会、路演还需登记希望听众记住的关键瞬间及所在页。学术场景补充 `math_load`、`figure_orientation`、`section_priority`。

页数默认成品总数，封面与收尾在总数内分配；只有明确“X 页正文/内容”才另计结构页。“做12页PPT”按成品12页推进并说明分配，无需重复询问口径。

数字与断言按引用、估算、示意、用户确认记录依据；来源不足标为 `unknown`，不得补造事实。除
`one_thing` 与哇点登记外，合同另设**反方与边界登记**：`strongest_objection`（最可能推翻主线的
最强反方及其证据锚点，受众为评审机构或委员会时须含一条程序性反方）与 `invalidation_triggers`
（主线失效的可观测触发条件与一句分支预案）。行动目标与收束页中的任何金额须满足「登记表含
测算行」或「显式 `unknown` + 补齐时限与 owner」，裸估算金额不得进入请求页。

用户保存的交付档案可预填偏好，但不能带入旧业务数据。

**产出与出口：** 明确合同和独立项目根目录，建立 `content/`；材料或关键事实缺失时只推进不依赖它的准备工作。

### 3.2 大纲：建立整套叙事

输出 `content/outline-v<N>.md`，带合同快照和确认状态。明确每页角色、论点及跟随证据，检查连读是否形成完整故事。

内容页的第一条要点必须是**完整论断句**（主谓宾齐备、独立成句、不听讲解也能读懂），其后 1–2 条为**证据跟随**（数字/图/引用，逐条带标注短标）；开场、目录、章节隔断与收束页豁免。材料多段、结构复杂或为学术长文时，分页可按 `references/rst-paging.md` 的 8 关系词表标注分组边界（advisory，不进硬校验，确认摘要呈现「分页依据」一句）。

封面、收束和其他结构页按合同显式列出。复杂长文可以使用分页启发式，但不为了模板凑页数。修订生成新版本，保留旧版；聊天引用路径和变更摘要，不以聊天全文替代正式大纲。

### 3.3 逐页母版：建立内容真值

输出 `content/deck-master-v<N>.md`，每页包含四段：

1. 结论句标题：围绕单页论点，按页面角色和论证模式条件化。
2. 要点：支撑标题，遵守页面角色对应的禅档位文本预算——陈述/氛围 0–1 条、论点页 ≤3 条、台账页 ≤6 条，每条 ≤2 行。
3. 视觉行：容器清单、版式候选、每个要点的落位声明及图像来源三级。
4. 备注：`speaker_script` 存讲稿，`engineering` 存工程说明，两栏隔离。

页首元信息登记页面角色、`argument_role`、`beat`、受众看点、事实来源、讲述衔接与预计用时。母版确认前对文档执行减法审计（逐页「删掉哪条仍成立」、deck 级「哪些页可合并」）。母版是后续内容修改的起点；不能绕过母版直接改图片里的事实。

母版落盘后由确定性校验器把关：`check_deck_prose.py`（翻案腔等文案纪律线索）、`check_number_ledger.py --diff`（TF-1 后 verified 数字留存断言）、`check_master_contract.py`（母版合同判据）、`check_layout_reuse.py`（强视觉版式复用上限）；超过 30 页时另跑 `check_cross_page_consistency.py`。内容层修复先用 `compute_impact.py` 推导受影响页清单，再重建受影响页。

generate 使用带稳定身份母版（页首 `page_id: pg-<hex>`）时，后续表达冻结以页身份对齐；legacy 母版先经 `leo-ppt content stamp-page-ids` 一次性补齐身份并重新确认。

版式初步候选可在母版阶段形成。风格选定后再结合实际作用域复核版式与容量，所以这不是不可回退的单向流水线。

### 3.4 数据密度与素材检查

当前数据路由保留 6 个数据点或估算序列的原生图表默认阈值；4–5 点可留图片式但强制置信度形状语法；低点数若依赖精确几何、多轴、复杂标签或后续编辑，同样走原生图表。低点数不能当作保真证明，少量独立巨数可用数字海报。

路由改变需要以 `revision_kind: post-confirm` 写回母版视觉行（继承既有 confirmed 状态，不重走完整确认）；涉及页数或结构变化时退回 pending 重新核对合同和母版。不得静默改变用户要求的交付类型。图片式路线的数据图是 stylized 表现，不承载精确数值标注，交付话术含数据页时必须带该披露。

素材先运行 `validate_assets.py`：核对本地文件、图片格式、hash 或 URL 可达性。失败素材标为 `unknown`，替换或改成明确标注的示意后重新检查。离线跳过的 URL 不算验证通过。

高保障档额外运行 `check_content_facts.py`，对母版数字回读材料；有界修复后仍无法核实的断言保留缺口，不无限重试或强行通过。

### 3.5 风格方向与实际选择

执行第 4 节的索引、摘要、推荐与指纹流程。优先尊重明确点名（点名 > 参考图 > 推荐）；有参考图时提取可复用视觉语言；无指定时根据合同推荐，候选先过 `style_hard_rules.py --check-brief`，错配提示一次后尊重选择。

**产出与出口：** 明确当前任务实际采用的风格来源、选择指纹和推荐依据。只有摘要核对一致后才加载完整 brief，并把摘要的 `selection_fingerprint` 传入 `style render <load_name> --expected-selection <指纹>`（list/load/render 使用同一 `--home`），随后进入版式与样张验证。

### 3.6 版式与容量

版式调度经内容意图中间层（`page_intent`）进入确定性打分：`scripts/suggest_layout.py` 根据角色对齐、结构容量和整套节奏给出候选，风格路由仅作有依据的调整。低置信度输出 `undecided`，保留两个候选及推荐理由，在既有母版节点裁决。按容量预筛版式用只读查询 `leo-ppt style layouts --capacity "槽名<=N"`（计数槽按 `count_max`、文本槽按 `max_chars`，缺键版式如实报 missing）。

之后独立运行 `check_deck_geometry.py --capacity`：

| 结果 | 含义 | 处置 |
| --- | --- | --- |
| `ok` | 文本级容量在范围内 | 继续样张验证 |
| `over` | 软超，输出警告 | 结合实图检查可读性，不能当作视觉已通过 |
| `overflow` | 硬超 | 阻断定稿，精简内容或更换版式后重检 |

`decision=auto` 只表示综合分达到阈值，不能抵消 `overflow`。整页文本槽共享预算，不能靠拆成大量短要点绕过限制，也不能缩字号或省略号截断硬塞。

用户同名风格缺少专属绑定时，调度和容量检查都使用通用布局，不借用内置同名风格的容量因子。强视觉版式的复用上限来自 canonical layout profile 的 `reuse_friendly` / `max_per_deck`（如 P9 Closing Manifesto 每 deck 最多一页、不能连续两页），由 `scripts/check_layout_reuse.py` 复核，用户点名不绕过；该上限只约束已登记版式，手绘箭头等装饰元素是否延续由样张反演证据与用户选择决定。

### 3.7 backend、尺寸预算与正文样张

固定图片 backend、实际像素尺寸和生成方法。`configured_unverified` 可在首张真实业务图片中验证；`not_configured` 或 `invalid` 阻塞图片节点，不能把 `unknown` 当作可用。

内容合同冻结时同时声明 `content/size-budget.json`（`canvas_ratio` / `image_lane_px` / `render_lane_px`），交付前由 `scripts/check_size_budget.py <run>` 校验全册比例一致、渲染页落在 1280×720×整数 dsf 阶梯、图像页不超预算（渠道只能给更小档，低于预算输出 WARN 并入交付披露）。全册页产物均为 `render:*` 的 deck 用 `backend create --provider render-lane` 满足 generate 路线（免凭据、免计费、本地确定性），不再借图像 Provider 合同的壳；任一图像模型页存在时仍须图像合同。

默认生成一张信息承载最重的正文页，检验高密度场景下的文字、图文关系和风格。读取图片头确认实际比例与交付画布一致，默认 16:9、基准 2560×1440；提示词写了尺寸不算验证。

可选比较方式：同一正文内容、两种视觉风格各一张，二选一；额外费用需要披露并有授权覆盖。结构页（目录/封面）补样同理，须在同一句内告知多一张图的成本并经用户点头，不能用封面好看来代替正文验证。

选定后读回样张，按 🔶 SAMPLE-GATE 与视觉方向同轮呈给用户认可（用户显式豁免呈现时记 `user-delegated` 与豁免原话），并区分 `inherit_stable`（整套继承）、`needs_confirmation`（未定是否延续）、`one_off_not_locked`（偶然效果）。依据是真实样张，不是 prompt 预期。反演本身不增加出图成本或独立等待轮次。

样张决策经 `image sample-record` 落 `reports/sample-decision.json`，`binding.json` 六字段（`backend` / `width` / `height` / `generation_method` / `style_visual_path` / `layout_binding_path`）绑定实际图、内容、视觉、布局、backend 与方法；重新决策用 `--supersedes <旧收据 sha256>` 保留历史字节。当前保守绑定整套 slides，任一内容变化均需核对后重新记录；纯 JSON 格式变化不失效。

### 3.8 表达冻结：内容包、PipelineRequest 与输入代

样张与风格锁定后、`image prepare` 之前，先把内容编译为机器输入并冻结：

```text
content pack（母版 --> 内容包）
        |
        v
PipelineRequest（内容包 + 设计上下文 + 逐页 lane + 选择/绑定/资产证据）
        |
        v
leo-ppt generate --request <request.json>
        |
        v
<run>/input/generations/<generation>/  +  原子切换 input/current.json  +  RunIndex 登记
        |
        v
image prepare 只读已提交代（核对 page_id 与 number），登记补充讲稿与来源
```

- 内容包由 `leo-ppt content pack --master <母版> --out <page-content-pack.json>` 编译（schema `page-content-pack-v1`），绑定母版路径、SHA256、revision 与规范化内容摘要；同输入重编译必须得到相同摘要，手改内容包在校验时被拒，`engineering` 备注留在包内隔离字段。
- `leo-ppt generate --request` 是唯一生产链入口：内容包、selection、design、binding、资产及资格证据一并封存到输入代，原子切换指针并登记 RunIndex。
- `image prepare` 只读取该 run 已提交的输入代；不再接受独立 `--content-pack`、`--design` 或 `--layout-selection`。缺指针、半份冻结或错页均拒绝。
- 内容或设计改版必须**建立新 run**；同一 run 的不同输入以 `input_generation_conflict` 拒绝。`--supersedes` 等样张恢复手段不能绕过该不变量。

### 3.9 准备与批量生产

从有效母版基线派生 `slides.json`、术语表和 `sources-manifest.json`。每页带 `required_text` 文字白名单，全套带 `style_lock`（外层壳：纸色/背景、页码位置与形态、标题处理与光学字号档、网格/角标、人物政策、表情档）。只注入该页实际需要的术语和视觉规则，不把整库摘要塞进提示词。素材来自用户素材库时由 `library_catalog.py export-manifest` 携带出处；市场/行业数据只经登记通道获取，抓不到如实标 unknown。

`image prepare` 建立 canonical jobs（`image-deck/slide_jobs.json`），把 sources manifest 冻结进 run input 并计入 `prepare_fingerprint`；派发前运行 `check_worker_brief.py` 过 worker 简报完备阶梯（`required_text` / `style_lock` / 术语注入 / 数字登记行），检查真实宿主能力和运行 lease，并披露本次 token/成本估算区间及依据（`estimate_run_cost.py` 生成，估算是区间不是承诺）。多页必须有真实 worker，不由父 Agent 假装派发或静默串行替代；恰好一页也须 CLI 返回 `single_unit_current_agent_allowed`。

能力与费用范围在完整母版前先做低成本核对，样张后更新估算。批量先生产已计划中与样张差异最大的角色，验证后展开余页；不普遍新增样张、成品页或确认轮次。

worker 只写自己负责的页面。返回后由顶层 `image record` 记录（image lane 传 `--provider-receipt`，HTML lane 传 `--backend render:html` 与 `--render-receipt`，两类收据不得混用）；失败保留在同一状态体系内，聊天中的“完成”不改变 run 状态。

逐页容错协议为三层加一条既有恢复纪律：**阶段分层重试**（prompt 准备 / backend 执行 / QA 三阶段各自计数，每页 ≤3 次，重试只补失败阶段）；**全册完成后清扫**（扫描 canonical state 中非 rendered 的页复位重派，≤2 轮，复用 `run retry --from-failed-pages`）；**已 rendered 页无条件跳过**（防重复计费与风格漂移）；**重复失败前必须改变输入、配置、backend 或实现**，同输入原样重试不计入任何一层预算。清扫 2 轮后仍失败的页按缺页处理：generate 路线向用户显式披露，不静默放弃。

### 3.10 逐页 QA 与修复

按五层非补偿质量门逐页检查（内容事实 / 叙事结构 / 视觉呈现 / PPTX 结构 / 现场验收，图片式另加数据页披露）：文字准确性、可读性、对比度、遮挡与截断、必需素材、图表数据与单位，以及样张视觉继承。任何必要项失败都阻止该页接受，其他高分不能补偿。质检按 `references/visual-qa.md` 以对抗式审查执行（worker 正向自查 → 父 Agent 独立复核 → 对抗式审查），高保障档可启用多轮审查协议（镜头池轮换，连续两轮无 P1/P2 才收敛）。

内容错误先修母版，使用 `compute_impact.py` 辅助确定影响页面。重做后同时说明目标问题是否解决，以及密度、截断、跨页引用等受影响项是否仍正确。

文字失败的降级顺序固定：

```text
文字 QA 失败
   |
   v
TF-1：母版减法 --> 更新文字白名单 --> 同 backend 重生成
   |
   +-- 通过 --> 返回正常逐页 QA
   |
   v
TF-2：留白底图 + 受控确定性贴字
   |
   +-- 生成方法变化 --> 先回样张验证与确认节点
   |
   +-- 通过 --> 记录底图/终图指纹，披露 fallback 页面
   |
   +-- 仍失败 --> blocked，重构内容或调整 backend
```

TF-2 不能跳过至少一轮 TF-1，文字必须来自白名单；这是受控例外，不是允许自由用本地绘图替代最终页面。

### 3.11 组装、整套复验与交付门

全部页 recorded 且必要 QA 通过后，才执行 `image assemble`。缺页或失败页不能拼成“完成版本”。PPTX notes 只承载 `speaker_script`，工程备注留在 run 工件。

重新核对页数、页序、notes、页码与页脚、跨页引用、术语、叙事承诺（含目录/agenda 承诺表兑现）和预计总时长；叙事三查在组装前执行：首尾回扣 `one_thing`、关键点与合同决策任务对应、Σ预计用时对照合同预算。页图 hash 变化后创建新 artifact revision，重新组装并复验，不能沿用旧验证。

交付门按第 6 节清单执行（几何、尺寸预算、来源 strict、敏感文本、preflight、指纹收据）；导出的讲稿/讲义/长图同过 🔴 DELIVERY-GATE，且不默认扩大交付范围或代为发布。

## 4. 风格管理与精准索引的完整链路

### 4.1 管理侧与使用侧分开

```text
维护侧（资产变更时执行）

canonical 五区真值（styles / axes / layouts / templates / governance）
   |
   v
结构与治理 lint --> catalog 构建与发布（generation + current 指针）
                                        |
                                        v
              关系探针与资格证据 --> 画廊金样板回归 --> 五阶段迁移（换库时）

使用侧（制作 PPT 时执行）

current 指针 --> registry.json 有界发现候选 --> 实际源摘要核对
                                                    |
                                                    v
                                        推荐 / 消歧 / 选择
                                                    |
                                                    v
                                  完整 brief + 选择指纹守卫
                                                    |
                                                    v
                                        视觉白名单投影
                                                    |
                                                    v
                                        版式、样张、生产
```

维护侧只在资产变更时执行，普通制作不重建或写入安装目录。真值分层是：canonical 文件是资产真值，
catalog generation 是本次执行可见的身份/别名/依赖索引（`registry.json` 指向 canonical 实体并携带
`source_digest` 与 `evidence_set_digest`），实际解析出的文件是本次执行对象。新增正式版式提交到
`template-library/canonical/layouts/<slug>/layout.json`（layout-profile-v1 合同：画布/slot/容量/renderer
绑定）并通过 `lint_layout_grid.py`——几何真值唯一，不再接受同名 sidecar 双真值；个人未登记草稿留在
`${LEO_PPT_HOME}/template-library/`。

### 4.2 查询与推荐步骤

| 步骤 | 动作 | 保证与边界 |
| --- | --- | --- |
| 检查索引 | `capability_manifest.py --template-library --library-check` | 只证明 catalog 指针与 canonical 源一致；失败不重建安装目录，resolver 可从 canonical 只读重建运行时视图并标注 `registry_source=canonical-rebuild` |
| 定位候选 | `style list --summary --filter <名称或别名>` | `match_kind` 区分 exact-name、exact-alias、partial；有 `next_offset` 则继续分页 |
| 处理歧义 | 完整列出共享别名命中 | 不默选第一项，不把未命中说成不存在相关版式 |
| 核对实际源 | `style load <load_name> --summary` | 核对 scope/source/path/style_content_digest；user 同名优先 |
| 推荐候选 | 可行集合内通常呈现 2–3 个有差异方向 | 硬约束优先，允许单家族或单候选；用户点名优先，错配提示一次 |
| 锁定加载 | 选定后完整 load | 先摘要后全文，降低无关上下文加载 |
| 守卫渲染 | `style render <load_name> --expected-selection <fingerprint>` | list/load/render 使用同一 `--home`；变化则停止旧选择 |
| 视觉验证 | 版式容量预检与样张 | 指纹一致不代表可读性、审美或实际渲染通过 |

这些命令是定位工具职责的示意；实际执行应使用当前 runtime 解析的 CLI 和 Python，不从 PATH 猜入口。

候选摘要的适用场景、视觉特征、密度、版式提示分别来自 brief 的 `best_for`、`visual_direction`、`canvas.density`、`layout_patterns`。缺失标为未记录，截断标为摘录，不根据风格名字补写属性。

推荐默认项依次考虑场景匹配、受众风险偏好、数据密度和自定义复用，并说明理由。可记录家族级反馈、生成权重建议；这不等于已经实现自动训练或语义排序引擎。

### 4.3 几个容易混淆的对象

| 对象 | 回答的问题 | 不能替代什么 |
| --- | --- | --- |
| style | 整套采用什么视觉语言 | 不等于某页版式 |
| layout | 内容放在哪些容器、容量如何 | 不等于整套风格或论证模式 |
| 论证模式 | 内容按什么逻辑展开 | 不由 style 名称目录枚举 |
| pool | 候选池或池代表 | 不自动视为可组合的完整 style |
| generation 与 `asset_id` | 本次执行可见的实体身份、别名与依赖 | 不等于跨代稳定 ID，也不证明视觉效果 |
| 索引 digest | `source_digest` / `evidence_set_digest` 是否与源同步 | 不证明实际 user 覆盖或渲染效果 |
| 资格证据 | 某风格/版式在具体 backend 上的字节证据与准入结论 | 缺证据只能标 unverified，不自动晋升可发布 |
| 选择指纹 | 本次选中的文件与作用域是否变化 | 不证明样张已接受 |
| 样张 | 当前内容下的真实视觉证据 | 不替代后续全量逐页 QA |

无完整 brief 的 pool 不可组合；已有 `legacy_callable=true` 的历史池代表只保留用户明确点名的兼容调用。catalog、metadata、source/taxonomy 等治理信息不进入最终图片 prompt。

### 4.4 自定义与沿用

明确点名优先于参考图，参考图优先于推荐。“跟上次一样”需找到真实保存风格，否则说明未找到并回到推荐。参考图只提取可复用视觉系统，不复制业务正文、人脸、标识或水印。点名资产也可为可信标杆 deck 蒸馏档案（`distill_deck_style.py`，Gate 0 信任先行）。

沿用可信 PPTX 的主题色与字体，先经信任与 preflight，再运行 `extract_pptx_theme.py`。提取的角色色只走 deck 级 `--color` 锚点覆盖通道，不回写共享 brief 的固有配色。

资产进出安装库走 `scripts/style_pack.py`：导入前校验路径归属、实体身份、依赖闭包、软链接与采用范围，写入按原子回滚处理；导入失败不留下半份库。风格库整体换库走第 4.1 节的五阶段迁移（`migrate_template_library.py preview → stage → verify → publish → cleanup`），迁移工具与文件故障测试通过不等于真实 delivery 已迁移。

## 5. 可编辑与升级路线

```text
[B] 输入规范化 / 冻结待处理页集合
     |
     +-- upgrade 路线：upgrade inspect 冻结原交付物
     |                  --> upgrade import-baseline 关联源 generate run
     v
editable prepare --> manifest / page jobs / source / text hints
     |
     v
editable next --> 真实 worker 派发 --> 对象级页面重建
                                          |
                                          v
                      manifest + PPTX + preview + validation
                                          |
                          +-- 失败 --> 诊断、改变条件、重新派发
                          |
                          v
                     editable record
                          |
                          v
                全部目标页通过 --> editable finalize
                                          |
                                          v
                       页序 / notes / 对象 / 图表 / 结构复验
                                          |
                                          v
                     delivery assemble（hybrid 混装尺寸统一）
```

`manifest.json` 是对象级构建权威。正文、标题和图表文字需为可选择的原生文本；检查字体替代、文字溢出、对象遮挡、画布边界、真实图表数据和可编辑性。预览近似不能替代 PowerPoint 中的实际排版检查。

editable 组装内核为双 builder 等价（`LEO_EDITABLE_BUILDER=pptx|legacy`，默认 legacy）：对象级 object_builder 对非法 preset 在 build 期拒绝而非透传；生效值在 `editable prepare` 时冻结进 `page_jobs.json`，环境变量改值不影响已创建 run 的重建一致性。`delivery assemble` 混装 image 页与 editable 页时按 1e-6 容差校验全册 slide 尺寸一致，跨源混装前须把可编辑页 manifest 的 `slide`/`content_box` 等比改写为 image 侧口径，否则 `page_size_mismatch` 拒绝组装。

`upgrade-full` 先冻结原页、hash、尺寸和 notes，所有页面通过后才能称为全可编辑；升级失败保留原图片成品。

`upgrade-selected` 只处理已选集合，未选页保留原图，这是预期 hybrid。🔴 PARTIAL-GATE：选中页失败时默认阻止 partial 交付；只有展示当前成功/失败页集合并获得明确接受，才可输出 `partial-hybrid`。失败集合变化需重新确认，不能用早先的泛化授权冒充对当前集合的验收。

## 6. 交付门与证据

交付分为“文件已生成”和“验收闭环已完成”两个层次。`status=completed` 只说明产物阶段结束。

| 检查 | 证据或动作 | 失败或未运行时 |
| --- | --- | --- |
| 内容与叙事 | 来源、母版、承诺兑现、跨页一致性 | 回母版修复并重验影响页 |
| 页面视觉 | 逐页 QA 与样张继承 | 必要项失败阻止页面接受 |
| PPTX 几何 | `check_deck_geometry.py` | 非零结果阻止交付 |
| 全册尺寸预算 | `check_size_budget.py <run>` | 比例不一致或图像页超预算阻止交付；低于预算 WARN 入披露 |
| 图片来源 | `check_sources_manifest.py <run> --strict` | 错误阻断（含 `source_unverifiable`），WARN 逐项披露 |
| 敏感文本 | `check_sensitive_text.py`（定级存疑或素材入库前） | 命中仅掩码输出，候选非结论，裁决归 `data_classification` |
| 交付预检聚合 | `build_delivery_preflight.py <run>`（geometry/sources/sensitive/receipt 四门合一件） | blocked（exit 1）不得声明交付；not_run 项披露原因 |
| 实际环境 | Provider、OCR、viewer、desktop、独立渲染、人工验收分别记录 | 未运行明确写 `not-run`，不互相替代 |
| 指纹收据 | `delivery receipt create` 后 `delivery receipt verify` | 缺失按 not_run 披露不能接受，`delivery_receipt_stale` 阻止交付并按波及面处置 |

收据覆盖页产物、本地输入资产、QA 报告、渲染预览、模板样式源五类指纹（某类不存在时按显式空清单登记）。页产物变化重做相关 QA 和组装；资产或模板变化评估全册影响；QA 报告变化重跑 QA；预览变化重跑独立渲染。完成后重新生成并核验收据。

最终交付列明 PPTX 路径、准确类型、必要逐页产物、讲稿或失败报告、结构验证结果、未运行项、TF-2 fallback 页清单及限制，并与 `backend report` 的实际 `tokens_total` 对账（超出预估带上限需说明原因）。用户要求讲稿、讲义 PDF 或长图时经 `export_speaker_notes.py` / `export_deck.py` 导出（同一交付门，缺页如实列出）。

分发边界：leo 的交付止于文件与导出形态，不代发任何平台、不请求也不存储平台凭据；用户要求代为发布时拒绝并指路已登记的外部工具，发布动作由用户在外部工具内人工完成。额外导出不默认扩大交付范围。

只有必要结构门、独立渲染、人工验收及收据等条件满足，且真实状态为 `delivery_readiness=accepted`，才能声称交付闭环完成。

## 7. 关键工件与恢复

| 工件 | 用途 |
| --- | --- |
| `<project-root>/content/outline-v<N>.md` | 大纲与合同快照、版本和确认基线 |
| `<project-root>/content/deck-master-v<N>.md` | 全套逐页内容真值、视觉行和讲稿、页身份 `page_id` |
| `<project-root>/content/size-budget.json` | 全册尺寸预算（画布比例、渲染页与图像页尺寸档） |
| `<project-root>/content/sources-manifest.json` | 来源信息的机器投影 |
| `page-content-pack.json` | 母版的无损机器投影（内容包，绑定母版 hash 与 revision） |
| `PipelineRequest` | 表达冻结的正式输入：内容包、设计上下文、逐页 lane 与证据 |
| `slides.json` | generate 的逐页输入、文字白名单与风格锁 |
| `<run>/input/` | 归档输入与来源冻结材料（含 `theme-extract.json`） |
| `<run>/input/generations/<generation>/` + `input/current.json` | 已提交的不可变输入代与当前指针 |
| `<run>/image-deck/slide_jobs.json` | 图片页 canonical job 状态 |
| 可编辑页面 `manifest.json` | 对象级构建权威 |
| `<run>/reports/sample-decision.json`（+ `sample-decision-required.json`） | 样张决策收据与启用状态 |
| `<run>/reports/run-ledger.jsonl` | 各页 prompt/backend/qa/record 阶段账本 |
| `<run>/reports/rendered-ledger.json` | 每页呈现事实（OCR 摘要、关键数值、图表计数） |
| `<run>/reports/delivery-preflight.json` | 交付四门聚合结果 |
| `<run>/reports/delivery-receipt.json` | 交付指纹收据 |

中断后优先核对已有项目与 run，不因聊天上下文丢失重新创建任务。内容确认从 `content/` 的有效基线及 `post-confirm` 修订链恢复；不存在基线时回到对应内容节点。阶段续点由 `record_run_step.py --resume-suggestion` 给出建议（建议不覆盖，不自动改写状态）；`leo-ppt run next` 与 `run status` 提供同一方向的机器视图。

样张审查后由 `image sample-record` 保存 `reports/sample-decision.json`，通过 `sample-verify` 恢复。绑定实际图、canonical slides、风格视觉投影、布局、backend、尺寸、方法和可追溯决策来源；prepare 冻结前后、assemble/finalize 前均核验。新流程传 `--sample-binding`，历史无收据任务明确 `legacy/not_run`，不伪造恢复了人工批准。已启用后收据丢失仍阻断，不能退回 legacy。

重新决策用 `--supersedes <旧收据sha256>` 保留历史。当前绑定整套 slides，任一内容变化保守失效；已冻结内容改版使用新 run。纯 JSON 排版变化不失效，完整 brief 若带治理说明则可能保守扩大失效，优先绑定实际视觉投影。命令和六字段 binding 格式见执行合同。

内容协作写回先生成独立候选，再用 `check_content_baseline.py --commit <FILE> --candidate <NEW> --expected-sha256 <OLD>` 在文件锁内比较版本并发布。并发协作提交只允许一个旧版本胜出；`--verify` 是诊断，不是写入许可。外部编辑器不遵守锁，不能据此宣称可阻止任意外部修改。

`compute_impact.py` 覆盖页块变化、增删、顺序、合同和引用闭包；结果是复核范围，删除页需移除旧产物，仅讲稿改动不机械重生图片。派生物争议或收据报漂移时用 `reproject_derivatives.py --dry-run` 从最高 confirmed 基线确定性重建来源与术语投影，母版是真值，投影不反向覆盖母版。每页 record 后由 `build_rendered_ledger.py` 聚合呈现事实，多轮改稿时对照「上轮实际呈现口径」。

样式变化先分辨性质：仅治理元数据变化，且视觉投影、绑定和方法一致时，可核验后继承样张；视觉、布局绑定、backend、尺寸或方法变化则回样张节点。旧 run 缺少历史指纹时不能视为相等，也不自动重写旧成品。

worker 缺失会阻塞多页派发；重复失败先诊断并改变条件，只有状态允许安全重试时才沿用对应幂等键。已验证图片成品不因后续升级失败而删除或降级。

## 8. 当前边界（2026-09-18 快照）

已经接入执行链的是：有界目录发现、名称与别名消歧、实际来源摘要、用户覆盖一致性、选择指纹守卫、版式容量与样张继承约束、表达冻结链（内容包 → PipelineRequest → 输入代）、模板库 v2 的 current 指针与身份索引、worker 逐页三层容错，以及相应治理与验证工具。

尚未完成或未验证的是：表达优先重构的 U1–U13 单元仍按 completion matrix 记为 partial，未整体标完成；`publication-qualified=0`，尚无风格/版式取得可发布资格；delivery 默认库仍为 v1，v2 已构建但未切换；五阶段迁移只在假想批次与故障注入下验证，真实 delivery 未执行；真实 Provider 成图、成对视觉验收与用户差页观测为 `not_run`；语义 ranker、MMR 排序与跨代稳定 `style_id` 未实现。

不能外推的结论：名称检索覆盖改善不等于审美提升；模板在库不等于 Provider 已成功渲染；脚本与故障测试通过不等于全库真实图片效果或真实迁移已验证。工程证据见[表达优先收口执行表](../../leo-ppt-generator/docs/leo-ppt-generator/evidence/expression-first-autonomous-work.md)与同目录的 completion matrix。

## 9. 源码与合同导航

- [Skill 执行入口](../../leo-ppt-generator/SKILL.md)
- [图片式工作流](../../leo-ppt-generator/references/image-deck-workflow.md)
- [可编辑工作流](../../leo-ppt-generator/references/editable-workflow.md)
- [跨路线执行合同](../../leo-ppt-generator/references/execution-contract.md)
- [输入路由](../../leo-ppt-generator/references/input-routing.md)
- [风格推荐与选择](../../leo-ppt-generator/references/style-recommendation.md)
- [风格库使用说明](../../leo-ppt-generator/references/style-library.md)
- [版式调度与容量合同](../../leo-ppt-generator/references/layout-dispatch.md)
- [渲染 lane 合同](../../leo-ppt-generator/references/render-contract.md)
- [逐页母版规范](../../leo-ppt-generator/references/deck-master.md)
- [视觉质检规范](../../leo-ppt-generator/references/visual-qa.md)
- [模板库五阶段迁移](../../leo-ppt-generator/references/template-library-migration.md)
- [决策简报模板](../../leo-ppt-generator/references/decision-brief.md)
- [学术垂类映射](../../leo-ppt-generator/references/academic-vertical.md)
- [实施验收记录](style-index-implementation-verification.md)
- [统一实施方案](../plans/2026-09-05-002-feat-leo-ppt-engineering-optimization-plan.md)

本文是流程说明快照；实际参数、状态与异常处理以当前入口、对应路线合同和 CLI 输出为准。2026-09-18 同步了表达冻结链、模板库 v2 结构、逐页容错与交付门；此前的协作方式、内容提交、样张收据和推荐取舍见[流程优化记录](workflow-optimization-verification.md)。两次同步均未进行整套真实图片效果对照。
