# 图片式 PPT 工作流

## 读取顺序

执行中的确认与等待统一遵守 SKILL.md 的协作方式。委托执行下 Agent 完成可逆工件的
内部审查并记录 `decision_source: user-delegated` 与依据；共创时按约定里程碑等待。
视觉方向与样张是 🔶 SAMPLE-GATE 默认人工呈现点：内部质检通过后、逐页派发前必须
同轮呈用户认可，用户显式豁免呈现时记录豁免原话后按 user-delegated 继续（见步骤 6）。
不得填写虚假的人工确认或跳过实际质量检查。最小目标和交付范围明确后，先核对低成本
runtime/worker 能力、已有配置与费用范围，再投入完整母版；不自动增加付费探针，
Provider 的真实可用性由首张业务样张验证。多页能力不足时保留已完成内容工件并说明阻塞。

1. 冻结内容合同：主题、受众、使用场景、演讲时长、行动目标、页数、素材来源、
   必须出现的事实与不可杜撰项,以及两项叙事必填——**`one_thing`**(整套 deck 能压成
   的一句话主线;暂不能给出时标 `unknown` 求证,不得为空)与**哇点登记**(S.T.A.R.
   时刻:一个听众一周后仍记得的瞬间——一个数字/一个人物/一次揭晓,登记其所在页;
   发布会与路演场景强制,登记位不强制新增页面)。另设**反方与边界登记**:
   `strongest_objection`(最可能推翻 `one_thing` 的最强反方及其证据锚点;受众为
   评审机构/委员会时须含一条**程序性反方**——决策权归属、委员会角色或被
   架空的感知)与 `invalidation_triggers`(`one_thing` 失效的可观测触发条件,
   带阈值或事件,并附一句分支预案);材料确无反方证据时写「无已知反方+检索
   依据」,不得为空;靠隐藏反证获得的结论按内容事实层失败处理,母版须在收束
   页前以页面角色「边界」或 `argument_role`「反方」承载(见 deck-master.md)。
   **金额测算纪律**:行动目标与收束页请求中的任何金额(预算/分期/gate 余额/
   分配额)须满足其一——登记表含测算行(拆到可核参数或引用报价),或显式
   `unknown`+补齐时限与 owner;裸估算金额不得进入请求页。**护栏最小完备**:
   收束页与认错/失效线的每个动作项必须携带 owner 与时限,验证类动作必须附
   交付物定义(可核实输出物)及**验收标准**(样本量/覆盖率/阈值类可核条件)
   与验收人;多个动作项共享执行资源时须核对并行冲突;「持续加强」「保持关注」
   类无交付物表述不得充当动作项(`check_master_contract` ⑪⑫ WARN 判据为其
   机器子集)。**给定结论冲突处置**:用户结论与材料证据冲突时,结论按证据
   适用域限定继承、不擅改;冲突以显式页呈现;出路三选(修改结论/补充未见
   证据/书面留痕),留痕类动作优先会前单独沟通,不当众处置;对证/证伪页的
   连续否定语调先缓冲——把「结论哪里仍然成立」的辩护价值一句前置到对证
   开头,当结论可能被两个口径同时支持时(如口述数字实为加权口径)预埋和解
   表述(两种口径都可能对,先按可复核口径行动),要求结论提出者签署留痕
   文件的场合改设会前单独签署环节,不放进会议现场。数字与因果断言按**四级标注**：
   有出处的事实为「引用」；本仓或经验推算为「估算」（页面必须括注"估算"或"经验值"）；
   修辞性对比为「示意」（必须标"示意"，且不得使用图表版式呈现）；用户口述数据为
   「用户确认」（可溯源到会话轮，语法见 deck-master 数字登记表节）。四级之外、来源不足的
   数字、引用、客户名、结论或因果关系标记为 `unknown` 并向用户确认，不得为了页面
   完整而补写；断言强度不得超出其来源等级。图片素材声明来源三级
   （实拍 / 生成-氛围 / 生成-示意,见通用设计规范图像铁律）。**学术场景合同三字段
   （必填）**：合同含论文/答辩/组会/文献汇报信号或选用科研答辩风格时,冻结合同
   必须声明 `math_load`（light/medium/heavy,公式密度与推导深度,heavy=页均含公式
   或含推导链）、`figure_orientation`（figure-first/balanced/text-first,图表取向,
   驱动版式与页数倾向）与 `section_priority`（节级表 `| 节 | 优先级 H/M/L |
   建议页数 |`,高优先节多页、低优先节压缩或并入;Σ建议页数与内容页数对账,不等即
   警告）;三字段随母版头部 deck-contract 块落盘（见 deck-master.md）,并作为后续
   视觉审查的 rubric 锚点。通用 deck 可选声明,未声明不阻断。**页数口径**（仅约束
   generate 路线）：用户给出的页数默认指**成品总页数**，封面与收尾从该总数内分配。
   “做 X 页 PPT”直接按总数 X 拟定并说明拆解，不为默认口径额外询问；明确
   “X 页正文 / 内容”才按成品 X+2 执行。明确“不超过 X 页”以 X 为上限。
   只有既有合同与新请求冲突、或材料无法在范围内合理表达时才澄清实际差异。
   去尾页口径在合同呈现中必须显式声明:成品 = 封面 1 + 内容 N,末页承担收束
   职能（回扣 `one_thing`）。
   数字 ≤2 且未明示要结构页时按卡片
   处理：不加结构页、按字面总数交付并附一句话说明。目录、章节隔断、附录计入
   内容页,不额外增加。内容合同经用户确认后，
   立即冻结独立 `<project-root>` 并建立 `content/` 内容子目录（仅 execute 模式；
   advise 不创建任何文件）。
   **协作里程碑**：合同、大纲、母版各自落盘并核查。委托执行中在授权范围内推进，
   共创时可同轮呈现合同与大纲、视觉方向与样张，修订只展示差异；用户明确只确认
   某工件时不扩展到其他工件。记录决策来源和范围，事实缺口只阻塞依赖动作。
   **交付档案预填**：用户保存过交付档案（`${LEO_PPT_HOME}/profiles/<名称>.md`，
   与 `styles/`、`brands/` 同构的用户档案通道）时,合同草案按档案预填并在每个
   预填字段后标注「来自交付档案 <名称>」;用户只需确认或改写差异项,逐项覆盖
   均合法。档案只存偏好字段（audience / scenario / page_count_policy /
   duration / data_classification_default / density / preferred_style 可选）,
   **绝不存业务数据**（材料数字、客户名、项目名）;保存动作本身需用户明示
   （"存为我的交付档案"）,保存前过 `scripts/check_delivery_profile.py` 结构
   校验。档案是偏好而非本次材料事实，分级和答辩档位据本次材料重新核对；只有
   无法可靠推断且影响可用范围时询问，不因已保存偏好伪造本轮确认。
2. 把大纲写入 `<project-root>/content/outline-v<N>.md`（文档头部含内容合同
   快照与 `confirmation: pending`）。**结构页显式成页**：大纲以封面页开篇
   （必选;合同按卡片口径(≤2 页)执行时除外——唯一卡片兼任开场,不设独立
   结构页）、默认以收尾页收束,均以页面角色「开场/收束」
   显式列出;合同口径为去尾页时,末页承担收束职能（回扣 `one_thing`）。
   **论断式要点**：内容页大纲的第一条要点必须是**完整论断句**——主谓宾齐备、
   独立成句、不听讲解也能读懂的判断句;其后 1–2 条要点为**证据跟随**（数字/图/
   引用,逐条带三级短标）,不得只是论断的同义复述。开场（封面）、目录、章节隔断、
   收束页豁免（第一条要点可为陈述/金句/呼应,角色词表对齐 `styles/13_页面语义`）;
   零要点页（陈述/氛围档）合法跳过。此规则随大纲延续到母版要点段,并由母版校验器
   输出要点连读稿（TAKEAWAY-READTHROUGH）复核——连读不成故事线即打回。
   **RST 分页启发式（advisory）**：材料多段/结构复杂/学术长文时,大纲分页可按
   [`rst-paging.md`](rst-paging.md) 的 8 关系词表标注分组边界（大纲页行可选
   `rst: 与前页关系`;母版页首元信息可选 `rst_relation` 字段）——禅档位管
   "一页装多少",RST 关系管"哪些内容必须同页/必须拆页"（same-unit 绝不拆页）;
   两判据冲突时按学术图表证据规则的降级顺序处理,不得拆 same-unit。两者均为
   advisory,不进母版硬校验,确认摘要中呈现"分页依据"一句即可。
   在聊天中引用文档路径与变更摘要；按协作方式完成审查后
   更新标记为 `confirmed`，并记录决策来源与依据；反馈则修订产出 vN+1
   （旧版保留）。聊天不得整篇复述大纲。落盘失败即阻断该确认门并以控制面块
   报告，不得退回聊天整篇确认。
3. 把完整逐页内容稿（全部页汇总为单一文档）写入
   `<project-root>/content/deck-master-v<N>.md`（头部 `confirmation: pending`）
   并按协作方式完成内容审查，稿式为**逐页母版**（结构见
   [`deck-master.md`](deck-master.md)）：每页固定四段——结论句标题（按论证模式
   条件化）、要点（按页面角色禅档位,零要点合法）、视觉行（容器清单 + 每个要点的
   落位声明 + 图像来源三级）、备注（`speaker_script` 与 `engineering` 分栏）；
   页面角色（开场、问题、证据、解释、方案、行动或收束）、`argument_role`、`beat`、
   `audience_takeaway`、核心结论、事实来源、讲述衔接和预计用时沿用页首元信息；
   总时长必须与内容密度相容。母版确认前对文档执行**减法审计**（逐页「删掉哪条仍
   成立」、deck 级「哪些页可合并」）。母版确认后成为内容真值工件：四段完整性以
   文档为判定载体，聊天只引用路径与变更摘要；后续内容层修复先改母版再重建受影响
   页，母版变更触发受影响页重验。**影响面清单确定性推导**（R-35）：受影响页由
   `python3 scripts/compute_impact.py <旧母版> <新母版>` 从母版 diff 推导
   （页块变化、增删/顺序、数字/术语和交叉引用闭包），回复的波及面结论引用该清单。
   `affected_pages` 是复核范围，删除页按 `removed_pages` 移除旧产物，不能再派发；
   仅讲稿或工程备注变化核对 notes/证据投影，无需机械重生图片；可见内容变化更新
   `required_text` 和对应页图，不得凭空把纯文案改动视为零影响。
3a. **数据密度路由**（母版确认后、视觉方向前）：全 deck 数据点计数并按
   [`../template-library/governance/authoring/index/图表样式规范.md`](../template-library/governance/authoring/index/图表样式规范.md) 第五节判路——
   任一页 ≥6 个数据点或含估算级数值序列,该页改走可编辑/混合路线原生图表;4–5 点可留
   图片式但强制置信度形状语法;≤4 个巨数推荐数字海报页。无论点数，依赖精确几何比较、
   多轴或微小差异、复杂标签，或明确需要编辑/持续更新的图表也走原生图表。
   点数只是默认预警，不能证明低点数图表保真。路线或交付类型变化须在合同中明示。
   判定结果写回母版视觉行：
   产出母版新版本文件并登记 `revision_kind: post-confirm`（继承 confirmed 状态，
   不重新走完整确认）；若因此改变页数或结构，退回 pending 重新确认。
3b. **素材校验闭环**（母版视觉行冻结素材清单后、`image prepare` 前）：运行
   `python3 scripts/validate_assets.py <project-root>/content/sources-manifest.json`
   （在技能目录内执行；或对 slides.json 的 `required_images`/`input_images` 列表）。
   本地素材查存在/可读/是图片/sha256 一致；URL 只接受 `https://` 并以 HEAD 探活
   （405 降级 GET+Range，超时 10s，不下载整文件）。**闭环合同**：校验失败 →
   该素材标 `unknown`（**禁止入页**）→ 二选一：用户提供真实素材 / 改为 AI 生成
   并标示意 → 重跑校验 → 缓存 diff 展示替换前后状态。`--offline` 模式完全不联网
   （URL 记 skipped，交付前须联网重验全绿）；缓存（`sources/.asset-validation.json`）
   只作报告 diff，永不作为"通过"的替代。编造素材链接直接出图 = 红灯（红灯清单）。
   退出码 0/1/2：1 存在不可达素材（阻断入页）；2 仅缓存过期/慢端/offline 跳过警告。
3c. **内容核查官**（高保障档，R-06）：母版冻结后、`image prepare` 前运行
   `python3 scripts/check_content_facts.py <母版> <材料/research-pack.md...> [--json]`
   （确定性，纯 stdlib）——抽取标题与要点的数字断言与材料文本回读比对（容忍
   千分位/百分号/万·亿单位换算；估算/示意/用户确认级要点豁免），差异清单
   有界 2 轮返母版（改数/补出处/降级标注后重跑），第 2 轮仍有差异不再返工——
   逐项向用户确认或降级 unknown；退出码 0 无差异 / 1 有差异 / 2 用法。
4. 模版推荐与选择：先按 [`style-recommendation.md`](style-recommendation.md) 的源摘要流程核对实际 user/builtin
   作用域与选择指纹；索引失败用独立 summary 查询，不重建安装目录。用户选择后才读取全文，
   render 使用同一 home 与 expected-selection。再按该合同执行——
   合同信号 → 可行集合内通常 2–3 个候选（允许单一合格方向；每方向四行）+ 带归因
   的默认推荐 → 用户回字母锁定、点名风格直行、给参考图"照图做"、或要求浏览三视图
   摘要。指定优先序：显式点名 > 参考图 > 推荐；错配劝阻一次后尊重。
5. 按 `backend-selection.md` 确认固定 backend。
6. 默认生成一个代表性样张，内部质检通过后进入 🔶 SAMPLE-GATE：同轮向用户呈现
   视觉方向归因、样张图与反演三组判读，取得认可后锁定并进入逐页派发；用户显式
   豁免呈现（原话记录）时按 user-delegated 继续。样张锚定**正文页角色**——在"最典型难页"
   中优先选信息承载最重的一页（正文页的信息密度与图文配比是风格是否成立的
   最强判据）；默认仍恰好 1 张，成本不变。结构页（目录 / 封面）加样为可选：
   agent 提议样张时**同一句内**告知"另出一张目录或封面页样张会多花一张图片
   成本，需要吗？"，用户点头才加，不点头不出、不默认出；多页样张共用同一
   `sample_generation_method` 与 backend（见下文冻结合同）。用户对候选方向纠结
   时，按 `style-recommendation.md` 第六节提议样张双生：披露额外费用并核对已有授权
   → 默认与最强备选各出一张
   同内容样张 → 二选一，落选即弃；二选一计入本步骤确认，不新增确认点。双生与
   结构页加样不叠加：双生时每方向仍 1 张正文页样张，胜出方向选定后才可（同样
   成本先告知、点头才出）补结构页样张。样张尺寸档是硬合同：PNG 实际像素（读图片头，
   不是 CLI 参数）必须为交付画布宽高比——默认 16:9、基准 2560×1440；backend 对自由
   尺寸的支持以 backend contract / registry 校验为准，不得在提示词或文档里写死模型名
   或假设某模型的尺寸档。非 16:9 的样张不得提交用户确认。样张选定后、锁定
   `deck_spec.style` 前，按 `style-recommendation.md` 第七节执行样张反演（三组
   判读随样张确认同一轮呈现，反演结论随 spec 落盘）。
7. 从 `content/` 最高 confirmed 基线（含其 `post-confirm` 修订链）的母版文档
   生成 slides.json 与全 deck 术语表（canonical 实体名 + 缩写 + 首现页），
   `image prepare` 时按该页实际命中的术语**裁剪注入**（不全表复制），
   `assemble` 复验增加跨页术语一致性检查（同实体异写即报告）；deck 超过 30 页
   时另跑 `python3 scripts/check_cross_page_consistency.py <母版>`（R-40）：同实体
   异写/页码跳号重复/固定件声明冲突升非 0 退出阻断，输出四分类（阻断/风险/
   承诺状态/通过），≤30 页降为风险报告（向后兼容）；**承诺表核对**
   （R-34）：目录/agenda 承诺与实际页面经 `check_master_contract` 的
   deck-promises 判据核对（承诺文本/锚页/兑现页/状态，语法见
   [`deck-master.md`](deck-master.md)），未兑现（open 项缺兑现页或兑现页
   不存在，含目录多宣称一章）非 0 退出阻断；把 confirmed 版
   outline 与 master 复制进 run input 归档。**slides.json 合同字段（C1）**：deck 级
   `style_lock: {shell: "...", constants: [...]}`——样张确认后从已确认风格 brief 与
   样张方法派生的跨页常量锁（外层壳：纸色/背景、页码位置与形态、标题处理与光学
   字号档、网格/角标、人物政策、表情档）；每页 `required_text: [...]`——该页允许
   出现的全部内容性可见文字白名单（标题/要点/标签/图注/固定件文案，逐字）。两者经
   vendor patch（`patches/0007`）渲染为 job prompt 的 `## Deck Style Lock` 与
   `## Required Text Only` 独立块（逐字）；派发前可运行
   `python3 scripts/check_sources_manifest.py --check-job-prompts <deck-dir>` 检出
   "slides.json 声明了 required_text/style_lock 而 job prompt 缺块"的静默丢失。
   **sources manifest 冻结（A2）**：从 confirmed 母版视觉行派生
   `<project-root>/content/sources-manifest.json`（schema 见
   [`sources-manifest-schema.md`](sources-manifest-schema.md)；母版是人确认的内容
   真值，manifest 只是机器投影）。**用户素材库（R-04）**：母版视觉行引用库内
   素材（`${LEO_PPT_HOME}/library/`，见 [`library-schema.md`](library-schema.md)）
   时自动携带出处（sha256+来源），sources-manifest 可由
   `python3 scripts/library_catalog.py --root <library/> export-manifest` 从库登记
   派生（page_id 占位与绝对路径按 WARN 提示改写后再冻结）；库外编造链接仍被
   `--strict` 拒绝。市场/行业数据只经 [`data-sources.md`](data-sources.md) 登记
   通道获取，来源 URL+抓取时间戳入 manifest，抓不到如实标 unknown 求证（R-05）。
   按执行合同先 `image sample-record` 保存有依据的样张决策；以下 prepare 调用还必须
   带 `--sample-binding <binding.json>`（六字段定义见执行合同），再调用顶层
   `"$LEO_PPT" image prepare <run> --slides <slides.json> --sources <sources-manifest.json>`。该 run 必须已通过 `leo-ppt generate --request <request.json>` 提交完整表达输入代；prepare 只核对页身份、页序并登记补充输入，改版须建新 run，详见 execution-contract.md「内容冻结绑定」。
   runtime 校验后把 manifest 冻结进 `<run>/input/sources-manifest.json`，其
   `contents_sha256` 并入 `prepare_fingerprint`；这一步创建唯一 `image-deck/slide_jobs.json` canonical
   state。vendor prompt 工具只能作为无状态能力被 bridge 调用，不直接拥有 run 真值。
8. 多页时按 `prompts/slide-worker.md` 派发 worker（前提：样张门已过——用户认可或
   显式豁免记录在案），并为每次执行使用顶层 run lease。
   先派发已计划中与样张差异最大的页面，复核对应风险后再展开余页；这是生产顺序，
   不默认新增页、图片调用或用户确认。实际 provider 验证和成本估算随业务样张更新。
   派发前 `python3 scripts/check_worker_brief.py <deck 目录|slides.json>` 过 worker
   简报四块完备阶梯（R-46，合同与豁免口径见执行合同 Worker 节）。
9. worker 返回后调用顶层 `"$LEO_PPT" image record <run>`；image lane 使用冻结合同中的
   Provider 名作为 `--backend`，同时传入该页的 `--provider-receipt`。CLI 从 `image`
   lane 读取绑定，重核 Provider、run、input generation、双层摘要和页图字节，
   provenance 随页记录原子写入。HTML lane 则使用 `--backend render:html` 和
   `--render-receipt`，两类收据不能混用，均在同一次页事务保存。image 的 OCR 门读取
   冻结内容包的必现文字，缺少可选来源清单或 overlay 标记不会豁免该门。失败保留在同一
   canonical state。聊天回复不改变状态，取消后的迟到 lease 会被拒绝。
10. 对每页分别关闭文字准确性、可读性/对比度、遮挡/截断、required asset、
    图表数据/单位/标签/排序和样张风格继承；任一失败都阻止该页 accepted，其他检查
    通过不能补偿。视觉质检按 [`visual-qa.md`](visual-qa.md) 执行：worker 正向自查 →
    父 Agent 独立复核 → 对抗式审查 → 任一失败打回重做，而非正向打勾。数据页判据
    按 [`../template-library/governance/authoring/index/图表样式规范.md`](../template-library/governance/authoring/index/图表样式规范.md)（形状授权、
    置信度形状语法、零基线/截断轴）。
11. 用 `"$LEO_PPT" run status <run> --json` 和 `"$LEO_PPT" image assemble <run>`
    确认全部页 recorded 后组装。缺页不得进入组装。PPTX notes **只承载
    `speaker_script`**（口播稿/预期疑问/停顿/用时）；`engineering` 备注留在 run
    工件不进 notes。`speech.md` 定义为 run 工件内全部页 `speaker_script` 的连播
    汇总（组装时生成,worker 禁改,见 slide-worker 禁改清单）。用户要求讲稿/
    演讲稿交付物时,用 `scripts/export_speaker_notes.py` 导出（`--pptx` 成品或
    `--master` 母版二选一;确定性输出,缺备注页如实列出并提示回母版补
    speaker_script,不得编造口播稿）。
12. 重新打开 PPTX，核对页数（基准 = 内容合同按页数口径换算的成品总页数）、
    notes、结构和交付类型。若母版或合同约定了版面固定件
    （页码/页脚/署名位），逐页核对位置与字号一致；页内文本引用（「见第 X 页」「见
    附录」）必须与实际页码核对存在。**叙事三查**（母版确认门首次执行关闭,
    此处为组装前复核）：①首页与收尾页是否
    回扣 `one_thing`（承诺-兑现闭环;合同去尾页时由末页承担,闭环不豁免）；
    ②关键点与合同决策任务一一对应，三点是短说服型演讲的建议，不强迫四项独立决策合并；
    ③Σ各页预计用时（含结构页）对照合同预算，超时提示减法；预计时长不是试讲证据。
    有实测试讲且超出硬性时长上限时再阻断定稿，调整内容或合同。最终任一 slide 图片 hash 变化后，必须创建新的
    artifact revision，重新组装、渲染并复验整套 PPTX；旧验证不得沿用。交付前必须
    运行 `python3 scripts/check_deck_geometry.py <final-pptx>`（在技能目录内执行；
    确定性断言画布 16:9、页图满幅无 contain 留白、无拉伸；非 0 退出阻止交付）。
    **strict-sources 交付门**：含图片证据的交付（generate 全部；upgrade 路线先
    `python3 scripts/check_sources_manifest.py --compile <run> [--out <path>]` 聚合）
    交付前必须运行 `python3 scripts/check_sources_manifest.py <run> --strict`（在
    技能目录内执行）：退出 1（含引用级不可回溯 `source_unverifiable`、AI 图冒充
    引用）阻断交付；退出 2（低审查状态图等 WARN）可交付但必须在交付披露中列明。
    交付披露同时逐页列明 TF-2 fallback 页清单（见文字保真降级链）。

最终 slide 图片必须来自确认的图片 backend。不得使用 Pillow、SVG、HTML、
canvas 或本地绘图生成“近似替代页”。required asset 无法正确进入页面时应
blocked，而不是省略后继续。**封闭例外共两条**：① 经样张确认的
text-fidelity-fallback 模式（TF-2，见下节）——底图仍须来自确认 backend，
叠加文字由 `scripts/overlay_text.py` 确定性产生并逐字来自该页
`required_text[]` 白名单；② R-70a/b 阶段的组合页合成路径——背景层带
确认 backend 的 render provenance，文字层由同一白名单机制主题化确定性
产生并经手改拒绝校验（合同与阶段门见
[`render-contract.md`](render-contract.md) 组合页合成节）。②仍是阶段实现：
`page_type_regime` 不因它扩展 composite lane 准入，默认路由、worker brief
与交付披露的转正属 R-70c，未过阶段门前合成命令只用于门禁证据与显式调用。

样张批准后，所有 slide job 继承同一 `sample_generation_method` 和 backend。
继承前必须核验该方法的像素尺寸档为交付画布比例（16:9）：比例不符（如历史 run
的 1536×1024 素材）不得继承，也不得由 worker/parent 私自降档回退，一律视为
generation method 变更，走样张重新生成与确认。
backend 切换需要用户重新确认并使旧 job fingerprint 失效。

### 文字保真降级链（Text Fidelity Fallback）

触发条件：视觉质检"文字准确性"失败（错字/漏字/白名单外文字），且视觉方向本身
已接受。处置顺序固定，不可跳步：

1. **TF-1 压文本预算重生成（优先，且至少尝试一轮）**：回母版做要点减法（禅档位
   降一档 / 每条压缩 / 标签数减半），登记 `revision_kind: post-confirm`（页数或
   结构变化才退回 pending，复用既有 3a 通道）→ 更新该页 `required_text[]` 白名单
   → 同 backend 同方法重生成该页。文本预算参考（与禅档位联动，非新档位）：标题
   ≤12 字、要点每条 ≤2 行、标签 ≤5 个、图注 ≤6 条每条 ≤12 字。
2. **TF-2 留白版式 + 确定性贴字**：TF-1 仍失败时——① 用确认的 backend 生成
   "留白版式页"（prompt 声明为每个白名单文字项预留空白区，禁止任何占位假字）；
   ② `python3 scripts/overlay_text.py <底图> <required_text 白名单 json> <out>`
   （在技能目录内执行）逐字贴字，输出恒为 2560×1440，非 16:9 底图或白名单外
   文字拒绝渲染；贴字后重验画幅。**治理对齐**：TF-2 = `sample_generation_method`
   变更——启用前必须重新生成并确认样张（寄生既有样张确认点，零新增确认门）；
   未经该确认，slide-worker 的"manually composited text overlays"禁令不变，
   不得静默贴字交付。③ 记录：sources manifest 该页加
   `{"visual_id": "text-overlay", "source_class": "deterministic-overlay"}`；
   slide job 记 `text_fallback: true`；收据按"底图 + 叠加后终图"双指纹记录；
   qa_note 写"TF-2 engaged + 白名单逐字 + 无残留生成假字复检"。
3. **终止**：TF-1 + TF-2 均失败 → 该页 `text_budget_exhausted`（blocked），回母版
   重构或换 backend，不得无限重试。`text_fallback_engaged` 为状态码非错误。

交付披露：最终回复逐页列明 fallback 页清单（TF-2 页与原因）；未披露的贴字页按
红灯处理。回滚：TF-2 未获样张确认即整链禁用（退回"整页重生"）。

中断恢复：会话中断后重新进入同一 generate 任务时，读取 `content/` 的版本化文档
与确认基线定位所处确认门（某门已过当且仅当存在 confirmed 基线或其 `post-confirm`
修订链）；`content/` 为空即从内容合同重新开始。视觉方向与样张决策使用
`image sample-verify` 核验收据，来源、具体图和生成条件一致时恢复；缺失或漂移时
按协作方式重新处理对应决策，不自动重问所有内容节点。命令与兼容边界见执行合同。

### 页面主题变体

同一套 deck 可以有封面、正文和收束等页面主题。遇到“深色封面 + 浅色正文”时，
必须在 `deck_spec.style_variants` 声明正文的 `canvas.background` 和硬性 `rules`，并在
正文 slide 设置 `style_variant: "body"`。如果正文引用深色封面样张，还必须通过
`reference_inheritance` 只继承线宽、网格密度或圆角等结构语言，并在
`reference_exclusions` 排除 `background`、`palette` 和前景色。页面主题优先于全局
风格与样张的冲突背景；不得只在自由文本里写“正文白底”。

## 五层非补偿质量门

- **内容事实：** 逐条对照来源与不可杜撰项；事实不明即阻断，不用视觉效果掩盖。
- **叙事结构：** 大纲有主线，每页只有一个任务，前后页能解释“为何此刻出现”。
- **视觉呈现：** 核心文字准确可读、对比充分、无截断遮挡，required asset 与图表真值
  完整，整套继承已批准样张而非逐页换风格。关键信息不得只靠颜色区分，必须同时有
  文字、标签、形状或位置等第二种线索；投屏距离下不可读的字号或低对比内容必须失败。
- **PPTX 结构：** 页数、页序、尺寸、notes、媒体引用和交付 hash 一致；画布与页图
  宽高比一致（页图满幅、无 contain 留白、无拉伸），由
  `scripts/check_deck_geometry.py` 确定性断言，非 0 退出阻止交付。
  母版冻结后同步运行 `python3 scripts/check_layout_reuse.py`（强视觉版式
  `reuse_friendly=false` 一 deck 一次、P36 至多 2 页；见 `references/deck-master.md`
  强视觉版式合同行与 `references/layout-dispatch.md`）。
- **数据页披露：** 图片式路线的数据图为 stylized 表现，不承载精确数值标注；真实数值
  以逐页母版 / direct-editable 版为准（`../template-library/governance/authoring/index/图表样式规范.md` §五、3a 步数据密度
  路由）。交付话术含数据页时必须带此披露。
- **现场验收：** 自动检查只证明确定性合同；真实 provider、PowerPoint 桌面打开、
  投屏可读性与人工审美必须分别实际执行和记录，未执行时写 `not-run`。

## 确定性工具映射

- prompt/state：顶层 `image prepare`、`image record`、`run status`；
- provider：`image generate|generate-batch|edit`；
- 图片处理：`remove-chroma-key`；
- 组装：`assemble`，包括页序、压缩和 speaker notes。

图片式交付的公开状态入口统一使用顶层 `leo-ppt`；固定上游 bridge 仅承担无状态
prompt/provider/格式能力。旧上游的
`codex_ppt_runtime.py bootstrap|config|doctor` 由当前 Skill 的
`runtime_manager.py ensure|doctor|print-cli` 与 backend contract 替代，不能创建
第二套 runtime 或配置入口。
