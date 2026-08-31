# ppt-github 90 项目 × 6 专家源码评审会：leo-ppt-generator 能力补充集成路线图

- **日期**：2026-08-30
- **形式**：6 位产品专家并行源码深度评审（每人 13–17 个项目，逐仓 ls → README 通读 → 核心源码实读，禁止抽查）→ 主持人交叉核验 → 跨组会议裁决 → 本路线图
- **评审对象**：`/Users/kuang/knowledge/ppt-github` 顶层 85 项目 + `gitee-mirrors/` 独有 5 项目（deckjs、nodePPT、remark、unioffice、webslides），合计 **90 个，全覆盖**
- **专家分报告**：`docs/ppt-github-expert-reports/专家{1..6}-*.md`（共 1493 行，每项目均附 ≥2 个真实读过的源码文件路径证据）
- **集成目标**：`leo-ppt-generator`（已 vendor codex-ppt-skill 与 image-to-editable-ppt-skill 两个 MIT 上游，共 60 项能力登记于 `upstream-capabilities.yaml`；风格库 137 可加载风格 + 145 分节轴规范）

---

## 一、主持人交叉核验记录（会议前置事实核验）

对六份报告中影响裁决的关键断言做了独立核验，全部属实：

| 断言 | 核验结果 |
|---|---|
| 专家6：editable 内核为手写 XML | ✅ `build_pptx_from_manifest.py` 实测 1002 行，`import pptx` 0 处，zipfile 3 处 |
| 专家5：11_图表语法已是 mermaid 方言 | ✅ 18 个文件中 15 个含 mermaid 语法（`xychart-beta`/mindmap/时序图等），是"写于图像路线时代的现成确定性渲染输入" |
| 专家1/2：guizang-ppt-skill、banana-slides 为 AGPL-3.0 | ✅ 两仓 LICENSE 均为 AGPL-3.0——文本/代码不可搬，机制只可思想改写 |
| 专家4：ppt-agent-skill（MIT）visual_qa.py 可搬 | ✅ MIT（sunbigfly），`scripts/visual_qa.py` 616 行存在 |
| 专家1：gpt-image2-ppt-skills（Apache-2.0）layouts.json 可搬 | ✅ Apache-2.0，`styles/initial/*.layouts.json` 三个 sidecar 实在 |
| 专家4：slides-grab（MIT）design-gate 可搬 | ✅ MIT，`src/design-gate-state.js`、`design-gate-report.js` 存在 |

---

## 二、基线共识：leo-ppt-generator 的水位定位（六专家独立交叉确认）

**处于全场第一梯队，且是 90 项目中唯一同时具备"治理协议 + 可评测 + 双路线（图像式/对象级可编辑）"的技能包。** 独有优势（多专家独立得出，非单一来源）：

1. **Gate 0 Office 信任门禁**：15 个端到端产品无一对外来 Office 输入做信任拦截（专家2 实证）。
2. **评测体系**：`evals/eval.yaml` + skill-up 门禁 + judge fixture 是 90 项目中独一份；对比项目最多只有单测/冒烟（专家1、专家4 独立得出同一结论）。
3. **三级标注事实纪律**（引用/估算/示意）：反幻觉粒度超出所有对比项目（OpenCanvas 只到"不编数字"）（专家2、专家3）。
4. **版式/风格资产厚度**：137 风格 + 145 分节轴全场最厚；产品的"接近 100% 还原"是营销话术，leo 的 `validation.passed` + 再检要求才是可验证承诺（专家2）。
5. **manifest IR 理念**：与业界收敛方向一致且更严格（box_px 缺失即违规、asset_provenance 枚举、notes 冻结）（专家6）。

**相对短板（会议聚焦的五项，按危害排序）**：

| # | 短板 | 证据 | 来源专家 |
|---|---|---|---|
| S1 | 门禁缺机器可执行凭证：`delivery_readiness` 是状态字段而非内容指纹，审后静默漂移检不出 | slides-grab design-gate 对照 | 专家4 |
| S2 | 图维度证据治理缺失：三级标注只管"数字来源"，不管"图怎么处理、是否可回溯" | scholar-ppt-cn 图表证据规则对照 | 专家3 |
| S3 | 文字保真缺降级链：文字错只能整页重生，无"压预算→留白贴字"分级处置 | ian-handdrawn 四件套对照 | 专家1 |
| S4 | 确定性渲染 lane 缺位：backend-selection.md 自认"密集表格页图像路线持续低通过"却无第三条出路 | frontend-slides/OfficeCLI/presenton 三处生产验证的截图管线 | 专家5 |
| S5 | OOXML 对象面纵深不足：手写 XML 1002 行仅支持 4 类形状，无原生表格/图表/母版/主题继承 | python-pptx 全对象面对照 | 专家6 |

---

## 三、六大能力支柱（主题收敛：26 条专家建议 → 6 支柱）

### 支柱 A：证据与来源治理（对应 S2）——"三级标注"从生成端自觉变交付审计

| 动作 | 来源与证据 | 许可证 | 成本 |
|---|---|---|---|
| A1 新增《学术图表证据规则》references：6 种图处理模式（preserve/overview+detail/split/cross-slide/not-use/request-higher-resolution）+ 图视觉审查 5 级状态 + 原图裸上纪律 + 降级顺序 + 母版视觉行每图绑定 figure_id/focus | scholar-ppt-cn `references/evidence_asset_rules.md`；辅 Paper2Slides `content_planning.py` 公式/数值保真条款 | 思想改写 | 低 |
| A2 新增 `sources_manifest.json`：generate 记每页视觉来源（用户素材/AI 生成/示意）+哈希；upgrade 记对象来源（原图裁剪/AI 重绘/原生重建）；DELIVERY-GATE 增 `--strict-sources`（引用级必须回溯用户输入文件） | ai-paper2slide-skill `validate_visual_sources.py`（思想） | 思想改写 | 中 |
| A3 素材存在性/URL 可达性校验闭环（编造图片链接→校验→替换→缓存），堵"图片引用真实性"交付事故 | OpenCanvas `src/opencanvas/image_validation/` | MIT | 中 |
| A4 母版增强：每图加"承载元素\|服务的比较\|要避免的误读"行；数字登记表加 `verified?`/`as-of` 列；减法审计加"不读原文能否写出这页"第二问 | slides_maker `content-plan-spec.md`、note-slides `SKILL.md` | 思想改写 | 低 |

### 支柱 B：风格 × 版式资产工程——把全场最厚的资产变成可调度、可确认、可继承的结构

| 动作 | 来源与证据 | 许可证 | 成本 |
|---|---|---|---|
| B1 layout bank sidecar：为 11 内置风格与 36 版式骨架补 `.layouts.json`（五字段封顶：visual_signature/content_capacity/best_for/avoid_for/reuse_friendly）；`lint_layout_grid.py` 增配对检查；deck-master 消费 `reuse_friendly` 实现"强视觉版式一 deck 一次"机器执行 | gpt-image2-ppt-skills `runtime_profile.py` + `*.layouts.json` | **Apache-2.0 可直搬** | 中 |
| B2 "模板调度师"逐页版式匹配规则：角色对齐→结构匹配（layout_hint×content_density 对 content_capacity×visual_density）→节奏感（避免连续 5 页同版式）→置信度 <0.5 返回 undecided 交人工、禁止编造版式 id；结果进母版确认，寄生既有 CONFIRM-GATE | banana-slides `prompts.py` `get_template_auto_match_prompt` | **AGPL：只借思想改写** | 低 |
| B3 vw 视觉宽度容量模型（CJK=1.0/ASCII=0.5/空格=0.35）进 `check_deck_geometry.py`；36 版式骨架补 chars_per_line/max_lines/max_chars；要点禅档位定稿前跑容量预检（超容量→降档/换版式而非缩字号） | GordenPPTSkill `scripts/compute_capacity.py` | MIT 可搬 | 低-中 |
| B4 PPTX 主题提取器：JSZip 解析 theme1.xml + Office→Web 字体映射 16 条 + 亮度/色距推导角色色，令 direct-editable 的"可信 PPTX 风格提取"从 Agent 肉眼判读变确定性解析 | presentation-ai `pptx-theme-extractor.ts` | MIT 可移植（TS→Py） | 低 |
| B5 风格 brief 头部内嵌主题元数据（画布比例 + size/colors/fonts/fontSizes/space 五段令牌），page-worker 与 runtime 从同一主题源解析，消除字段两处漂移；远期打通"brief → theme1.xml"单一上游 | marpit `meta.js`、spectacle `default-theme.ts` | MIT | 低 |
| B6 学术视觉语言与答辩档：paperbanana"NeurIPS Look"方法图规范（分区色 10–15% 透明/圆角=过程/实虚线语义/变量 Serif Italic/领域三分支/Amateur 反模式）并入图表样式规范；06_论证模式加"学术五拍"；科研答辩风加 dense-defense 档（左 TOC 侧栏+编号面板） | Paper2Any `paperbanana.md`（Apache-2.0）、academic-ppt-master（MIT） | 可改编 | 低 |
| B7 风格确认升级：样张点从"单张"升级为"正文页样张（必选）+目录或封面页（可选）"；选定后锁 spec 前执行一次"风格反演"（读回样张总结该方向实际样子、稳定可继承 vs 偶然效果），反演结论随 spec 落 manifest | ppt-image-first `workflow.md` Stage 2/2.5 | Apache-2.0 | 低-中 |

### 支柱 C：文字保真与内容合同（对应 S3）——图片式 PPT 第一痛点的分级处置

| 动作 | 来源与证据 | 许可证 | 成本 |
|---|---|---|---|
| C1 提示词四件套并入 slide-worker 合同：deck style lock（一次锁定逐页逐字复用）/ page role lock（短标题不放大）/ **Required text only 白名单** / Avoid+一致性自检；visual-qa 增白名单对照核对 | ian-handdrawn `references/prompt-patterns.md` | MIT（署名） | 低 |
| C2 Text Fidelity Fallback 降级链：文字错 → 先压文本预算重生成 → 仍错则留白版式生成 + 确定性贴字，填补"错一字重生一页"的粒度空缺 | ian-handdrawn | MIT（署名） | 中 |
| C3 论断式大纲规则：内容页第一条要点必须是完整论断句 + 1–2 条证据跟随；封面/目录/章节页豁免；全部 takeaway 连读成故事线——与既有"结论句标题"形成大纲-标题两段贯通 | banana-slides `prompts.py` takeaway 规则 | **AGPL：思想改写** | 极低 |
| C4 母版合同学术字段：数学量级（light/medium/heavy）、图表取向（figure-first/balanced/text-first）、section 优先级页数分配（H/M/L→页数），并作为后续审查 rubric 锚点 | ArcDeck `commitment_builder_lite.txt`、`RST-RELATIONS.md` | 思想改写 | 中 |
| C5 RST 8 关系分页启发式作禅档位之外第二判据（elaboration/explanation 同页、evaluation 可独立成页、same-unit 绝不拆页） | ArcDeck `RST-RELATIONS.md` | 思想改写 | 中 |

### 支柱 D：确定性渲染 lane（对应 S4）——页型路由的两条 lane，而非替代图像模型

**技术裁决（采纳专家5 双层组合）**：页面级（整页版式、文字密集页、表格页）→ 无头浏览器截图为主；图表级（数据可视化、结构图解）→ SVG 管线（mermaid/echarts → resvg）为确定性主干；canvas 序列化（konva/fabric）不引入；foreignObject 系（html2canvas/dom-to-image/html-to-image）仅限浏览器内预览，永不进 CLI 成图管线。

| 动作 | 来源与证据 | 许可证 | 成本 |
|---|---|---|---|
| D1 Playwright 页面渲染 backend：`"$LEO_PPT" render page --template <id> --data slide.json --out slide_N.png --size 2560x1440`；HTML 模板合同必须含 deterministic 模式（禁动画、显式 ready 信号、`document.fonts.ready` + 分段等待）；字体经 HTTP 注入（非 file://）；2560×1440 用 deviceScaleFactor 2 | frontend-slides `export-pdf.sh` 420 行生产管线、playwright `page.ts` | Apache-2.0 | 中 |
| D2 图表页确定性渲染：`11_图表语法` 15/18 个 mermaid 方言文件在浏览器实例内 render → SVG → PNG，零改写升级为可执行资产；数值/单位/标签 100% 逐字保真，直接消灭"数值不一致""无数据授权 chart-like 形状"两类高频质检失败 | mermaid `mermaid.ts` render + themeVariables 注入 | MIT | 低-中 |
| D3 SVG→PNG 栅格化：resvg（fontDirs 离线中文字体 + fitTo.width=2560 像素档一等公民），同输入位级一致，评测可做像素 diff 回归 | resvg-js `index.d.ts` | MPL-2.0（NOTICE 登记） | 低 |
| D4 统计图表 lane（后置）：echarts `renderToSVGString` 补对数轴/双轴/堆叠百分比（mermaid xychart 无此能力），LLM 生成 option 即可渲染 | echarts、PPTist ChartElement 生产验证 | Apache-2.0 | 中 |
| D5 像素档后处理：交付档 2560×1440 与 web 预览档 1280×720 一键切换 + PPTX 体积治理（Python 侧以 Pillow 等价实现） | sharp、presenton `start.js` | Apache-2.0 | 低 |

### 支柱 E：质量闭环机器化（对应 S1）——"已审"变成不可伪造、不会静默过期的事实

| 动作 | 来源与证据 | 许可证 | 成本 |
|---|---|---|---|
| E1 DELIVERY-GATE 指纹收据：通过时写收据 JSON（五类 sha256：每页产物/本地资产/QA 报告/渲染预览/模板样式源）；交付/导出前校验新鲜度，指纹漂移即硬阻断；再检要求可用指纹 diff 自动给出波及页；judge fixture 直接断言收据文件 | slides-grab `design-gate-state.js`（collectSlideFingerprints/diffFingerprints/assertGateFresh） | **MIT 可直搬** | 低-中 |
| E2 确定性像素 QA 前置闸门：非 LLM 像素断言族（画幅/留白上限/边缘截断/对比度分区/文件大小/策划卡与视觉块对账），退出码 0=过/1=FAIL 打回/2=WARN 可交付；FAIL 页不进 LLM 审——与 check_deck_geometry 划清职责 | ppt-agent-skill `visual_qa.py` 616 行 | **MIT 可直搬** | 中 |
| E3 美学度量三件套（自研）：局部方差留白率（内容占比 40–60% 带）、bbox 加权质心偏移、元素纵横比平坦区检测——aeslides 实证 VLM 有系统性盲区，三指标便宜确定 | aeslides 论文（arXiv:2604.22840）思想；**代码无 LICENSE 不可搬，须自研** | 自研 | 中 |
| E4 worker 逐页三层容错协议：按阶段分层重试（布局/渲染/导出各自计数 ≤3）→ 全册完成后 ≤2 轮验证清扫（复位非 rendered 页重派）→ 已 rendered 页无条件跳过；evals 增"注入一页失败→断言全册完整"用例 | codex-slides `pipeline.ts`（PAGE_MAX_ATTEMPTS=3/VERIFY_MAX_ROUNDS=2） | 思想改写 | 低 |
| E5 渲染器感知 lint：规则-渲染器映射（按 provider 声明每条 lint 规则适用范围与跳过集，读 app.xml 判定产物来源），消除双后端误报 | presentation-skill `layout_lint.py` | MIT 可移植 | 低 |
| E6 提示词进化记账：PROMPTS_REGISTRY 式 yaml 记录每次提示词改动（name/improvement/dimension/lesson），适配 lint baseline 收敛纪律 | OpenCanvas `PROMPTS_REGISTRY.md` | MIT | 低 |

### 支柱 F：对象级内核与 IR 升级（对应 S5）——补 OOXML 纵深，不动 IR 理念

**技术裁决（采纳专家6）**：python-pptx 深耕为主、manifest 保持唯一 IR 并加厚、不采用多内核并用；unioffice 商业 EULA 一票否决；PptxGenJS 引入 Node 运行时对技能包形态是净负担，不引入。

| 动作 | 来源与证据 | 许可证 | 成本 |
|---|---|---|---|
| F1 对象级生成内核迁移 python-pptx 对象 API：补齐全 MSO 形状库、原生表格、原生图表、母版/版式继承、notes 母版接线；shape id/relationship/content-type 由库负责；`oxml/xmlchemy` 逃生舱承接 custom polygon；以现有 validator 兜底回归 | python-pptx `autoshape.py`/`freeform.py`/`util.py`（EMU）对照现状 1002 行手写 XML | MIT（已在依赖树） | 中 |
| F2 notes 全链路 + 主题最小合同：theme1.xml 字体双槽（headFontFace/bodyFontFace→`a:latin typeface`），"全 deck 统一字体主题"让字体替代记录在主题层表达，升级换字体不再逐页改 run | PptxGenJS `gen-xml.ts` makeXmlTheme、python-pptx `templates/theme.xml` | MIT | 低 |
| F3 upgrade 路线对象级 spec：可信 Office 输入 prepare 即 dump 结构化 JSON（与 manifest 同构），提供对象级 ground truth；finalize 后"源 vs 产物"对象级 diff 验收（位置/文本/notes 三轴）；选择器语义 `/slide[N]/shape[@name=X]` | OfficeCLI `PptxBatchEmitter.cs`（思想移植，不引 C# 二进制） | Apache-2.0（思想） | 中高 |
| F4 字节保真 OOXML 补丁原则 + 单页合并降级：upgrade-selected 只重做选中页时"母本字节保留、仅补丁页替换"，避免整库重写样式漂移；页面级失败原位重插不废整 deck | genoffice `generate.ts` 头注、`landGeneratedPages` | Apache-2.0（思想） | 中 |
| F5 manifest IR v2（后置）：向"坐标无关 + 稳定对象 ID + 证据链接 + 阅读顺序 + 可编辑性元数据"对齐，坐标归后端执行层；稳定 ID 改善 upgrade-selected 对象级指代精度 | presentation-skill `deck_ir.schema.json` | MIT | 中 |
| F6 复杂度计分决策树 + 授权省略：page-decision-tree"复杂视觉保留位图"改为 6 项条件计分触发器；upgrade 引入 `authorized_omissions` 字段（省略/合并/重排显式登记并与三级标注联动）；自纠按固定优先级序 + 轮次上限 | xiaobei-skill `rebuild-image-in-powerpoint/SKILL.md` | 思想改写 | 中 |
| F7（远期备选）SVG→OOXML 矢量可编辑子路线：html2svg→svg2pptx 生成原生可编辑 SVG 对象（PPT365），为 direct-editable 增"矢量保真可编辑"子路线 | ppt-agent-skill `html2svg.py`+`svg2pptx.py`、make-slide `pptx-spec.md` | MIT | 中-高 |

---

## 四、冲突与裁决记录（会议真实分歧及处理）

| # | 分歧 | 裁决 |
|---|---|---|
| 1 | **Node 边界之争**：专家6 明确反对 JS 栈进 Python 技能包（针对 PptxGenJS）；专家5 的渲染 lane 需要 Playwright/echarts/resvg-js/sharp（Node 系） | 分层裁决：**格式内核层绝不引入 Node**（python-pptx 深耕，F1）；**渲染 lane 优先 Python 官方等价物**——playwright-python（官方维护）+ mermaid/echarts 在浏览器实例内渲染出 SVG + 栅格化独立子进程隔离。原则一句话："Node 只许出现在渲染叶子节点且以子进程隔离，永不进 PPTX 组装路径。" |
| 2 | **确认门治理冲突**：专家4 建议的"三页实图预览"与 skill 既有治理原则"全部寄生既有确认点，不新增确认门"冲突 | 裁决：寄生样张点执行——样张升级为"正文页（必选）+目录或封面（可选）"，风格反演作为样张确认前置读回动作；不新增暂停点，多图成本先告知（沿用样张双生的成本告知纪律） |
| 3 | **sidecar 复杂度张力**：专家1 既建议 layout bank sidecar，又警告 dashi"巨型 schema 防御性堆积"反面教训 | 裁决：sidecar 五字段封顶（visual_signature/content_capacity/best_for/avoid_for/reuse_friendly），不学 dashi 全量 schema；合同分层原则——提示词层管语义，数据层只管可验证事实 |
| 4 | **AGPL 红线**：banana-slides（模板调度师、论断式大纲）、guizang-ppt-skill（版式锁）、PPTist（元素 schema）均为 AGPL-3.0 | 裁决：机制可学、思想可改写、**文本与代码绝不搬运**；PPTist 仅 schema 语义参考。同时发现 **leo 自身 `04_来源_guizang` 从 AGPL 项目提取规则文本属许可证灰色地带**——列为 P0 自审项：补来源与许可证标注，或按思想重写文案 |
| 5 | **渲染 lane 与图像模型的关系**：是否意味着放弃图像模型路线 | 裁决（采纳专家5）：两条 lane 是页型路由关系——图像模型继续管视觉创意页（封面/概念/氛围），确定性渲染接管正确性合同最重的页型（图表/表格/文字密集）；backend-selection 已有 `chart|text-heavy|image` 页型路由与 backend_stats 通过率统计，架构天生预留了插槽，路由边际收益最大 |
| 6 | **评测自证风险**：aeslides 美学度量代码质量高但无 LICENSE | 裁决：依论文自研并引用（arXiv:2604.22840），代码一行不搬；visual_qa.py（MIT）可直接搬但需保留署名与 NOTICE |

---

## 五、分期路线图

### P0：快赢包（提示词/文档/小脚本，1–2 周量级）

1. **C1+C3+C4+C1 附带**：slide-worker/deck-master 提示词合同增强（四件套 + 论断式大纲 + 学术字段）——纯文档，六专家中三位的最优先项
2. **E1 指纹收据**：DELIVERY-GATE 机器凭证化——治理收益/工程成本比全场最高（1 脚本 + 1 子命令 + 2 处合同文档）
3. **A1+A4 图表证据规则 + 母版增强四件**：补图维度证据治理（S2）——纯 references 文档
4. **B7 风格反演 + 样张升级**：寄生既有确认点，直击图片式 PPT 最大返工源
5. **许可证自审**：`04_来源_guizang` 补 AGPL 来源标注或重写；顺带全仓 NOTICE 纪律检查

### P1：结构工程（2–6 周量级，按依赖排序）

6. **D1+D2+D3 渲染 lane MVP**：playwright-python 页面渲染 backend + mermaid 图表确定性渲染 + resvg 栅格化；产物走既有 check_deck_geometry + image record 闭环
7. **B1+B2+B3 版式工程**：layout bank sidecar（Apache-2.0 直搬适配）+ 模板调度师规则 + vw 容量预检——三者咬合成"风格×版式双层库"
8. **E2+E5 质检机器化**：visual_qa 像素断言前置闸门 + 渲染器感知 lint
9. **F1+F2 内核迁移**：build_pptx_from_manifest 迁 python-pptx 对象 API + theme/notes 合同
10. **C2 文字保真降级链** + **E4 三层容错协议** + **F6 复杂度计分决策树**
11. **A2+A3 来源 manifest + 素材校验闭环**；**B4 主题提取器**；**B6 学术视觉语言包**

### P2：战略投资（季度级）

12. **F3+F5**：OfficeCLI 式 dump/diff 对象级验收 + manifest IR v2（坐标无关 + 稳定 ID）
13. **D4+D5**：echarts 统计图表 lane + 像素档后处理
14. **E3 美学度量自研** + **B5 主题元数据内嵌** + **F4 字节保真补丁原则落地**
15. **F7 SVG→OOXML 矢量可编辑子路线**（direct-editable 的差异化纵深）

---

## 六、明确不做清单（六专家反面教训合并）

1. **不引入 Node 进 PPTX 组装路径**（PptxGenJS/unioffice 一票否决；unioffice 另有商业 EULA + 混淆源码双重否决）
2. **不搬 AGPL/无 LICENSE 项目的任何文本与代码**（banana-slides、guizang 系、PPTist、awesome-ppt-skills、chatppt、aeslides 代码、Awesome-PPT-Design-Skills、yixueAIganhuo 非商业）
3. **不用 LibreOffice PDF→PPTX 当重建主路径**（marp-cli 官方自认 EXPERIMENTAL 不保证可复现；转换器不能当重建器用）
4. **不做 foreignObject 系 CLI 成图**（html2canvas/dom-to-image/html-to-image 字体策略在真实世界不可靠，PPTist 被迫 `fontEmbedCSS=''` 是实证）
5. **不做 canvas 序列化路线**（konva/fabric 的场景图 JSON 对"内容合同→页面图"无表达优势）
6. **不学 47-agent 军备竞赛**（Paper2Any）、**不学模板=固定元素计数**（ai-to-pptx"结构绑架内容"）、**不学无环单发架构**（slide-deck-ai）
7. **不做"启用即 git pull 自动更新"**（guizang/Gorden 破坏确定性与供应链安全）
8. **不做可空转门禁**（PPTAgent inspect_slide 非反思模式直接返回 "This slide is valid."——任何 gate 须"未执行≠通过"）
9. **不承诺"接近 100% 还原"式不可验证营销话术**（用 validation.passed + 指纹收据说话）
10. **不把默认设计偏好硬编码进提示词**（SlideBot 教训：默认值必须外置为可选资产）

---

## 七、许可证与集成纪律（沿既有 upstreams.yaml 治理延伸）

- **可直接搬代码/资产**（保留署名 + NOTICE/UPSTREAM 登记）：ppt-agent-skill（MIT）、slides-grab（MIT）、image-to-editable-ppt-skill（MIT，已 vendor）、gpt-image2-ppt-skills（Apache-2.0）、presentation-ai（MIT）、frontend-slides（MIT）、GordenPPTSkill 代码（MIT，模板除外）、Paper2Any paperbanana.md（Apache-2.0）、academic-ppt-master（MIT）、ppt-image-first（Apache-2.0）、presentation-skill（MIT）、ian-handdrawn（MIT）、make-slide、OpenCanvas（MIT）、oh-my-ppt（Apache-2.0）、genoffice/LandPPT/ArcDeck 思想层（Apache-2.0/MIT）
- **只借思想、文本重写**：banana-slides、guizang-ppt-skill、guizang-social-card-skill（AGPL）；xiaobei-skill、beamer-academic、scholar-ppt-cn、slides_maker、note-slides、humanize-ppt、mckinsey-pptx、codex-slides、ArcDeck 承诺合同（无 LICENSE 或未确认处从严）
- **不可用**：unioffice（商业 EULA）、yixueAIganhuo（非商业）、Awesome-PPT-Design-Skills / awesome-ppt-skills / chatppt（无 LICENSE，默认保留所有权利）
- 每次集成沿用既有纪律：pinned commit、import_set、patch 登记、capability 回归清单（`upstreams.yaml` / `upstream-capabilities.yaml` 模式）

---

## 附录 1：90 项目判定总表（按专家分组，详细证据见各分报告）

**专家1 · Skill 提示词工程（14）**

| 项目 | 判定 | 要点 |
|---|---|---|
| gpt-image2-ppt-skills | 可直接集成资产 | RuntimeProfile + layouts.json sidecar（Apache-2.0） |
| ian-handdrawn-ppt | 可直接集成资产 | 提示词四件套 + 文字保真降级链（MIT） |
| GordenPPTSkill | 可直接集成资产 | vw 容量模型 + 铁律（代码 MIT） |
| guizang-ppt-skill | 可借鉴机制 | 版式锁 + 测量修正阶梯；AGPL 禁搬 |
| guizang-social-card-skill | 已覆盖 | 04_来源_guizang 已吸收，需补许可证标注 |
| NanoBanana-PPT-Skills | 可借鉴机制 | 仅转场元模板有增量 |
| html-ppt-skill | 可借鉴机制 | 同视口预览 + 渲染测量强化样张 QA |
| image-to-editable-ppt-skill | 已覆盖 | leo 已 vendor（E01–E31） |
| codex-ppt-skill | 已覆盖 | leo 已 vendor（C01–C25），是超集 |
| awesome-ppt-skills | 可借鉴机制(受阻) | rendered_text 双用思想好；无 LICENSE |
| nano-banana-slides-prompter | 可借鉴机制(选择性) | 版式词汇表可查；密度崇拜哲学不学 |
| dashi-ppt-skill | 可借鉴机制 | copyBudgets + 四方案对比；AGPL |
| xiaobei-skill | 可借鉴机制 | 复杂度计分 + authorized_omissions |
| ai-paper2slide-skill | 可借鉴机制 | visual_source_manifest + strict 校验 |

**专家2 · 端到端产品架构（15）**

| 项目 | 判定 | 要点 |
|---|---|---|
| banana-slides | 可借鉴机制 | 论断式大纲 + 模板调度师；AGPL 只借思想 |
| frontend-slides | 已覆盖+可借鉴 | selection-index 渐进加载纪律 |
| presentation-ai | 可借鉴机制 | PPTX 主题提取器（MIT 可搬） |
| oh-my-ppt | 可借鉴机制 | DesignContract 八字段 |
| genoffice | 可借鉴机制 | 字节保真补丁 + pageMarkers 降级 |
| LandPPT | 可借鉴机制 | 视觉宪法→创意简报两段式 |
| open-slide | 已覆盖+可借鉴 | design token 先生 + 动态美学选项 |
| AiPPT | 不适用 | 浏览器渲染引擎 + 后端闭源 |
| ai-to-pptx | 不适用 | 模板=元素计数，结构绑架内容 |
| SlideBot-AI | 可借鉴机制 | 母版结构化分析字段表 |
| OpenPPT | 不适用 | 编辑器形态不重合，AI 走闭源云 |
| chatppt | 不适用 | 教学级实现；FAKE_LLM 降级思路可用于 evals |
| langchat-slides | 已覆盖 | 模板分类命名可交叉校对 13_页面语义 |
| ChatPPT-MCP | 不适用 | 纯云 API 网关 |
| OpenCanvas | 可借鉴机制 | image_validation 闭环 + 提示词进化记账 |

**专家3 · 学术风格内容策划（16）**

| 项目 | 判定 | 要点 |
|---|---|---|
| Paper2Slides | 可借鉴机制 | 公式/数值保真条款 |
| Paper2Any | 可直接集成资产 | paperbanana.md 学术视觉语言（Apache-2.0） |
| academic-ppt-master | 可直接集成资产 | 学术五模块 + dense-defense 档（MIT） |
| ArcDeck | 可借鉴机制 | RST 分页 + commitment 合同 + critic 闭环 |
| GenSlide | 已覆盖 | 仅占位标题黑名单可吸收 |
| aeslides | 可借鉴机制 | 可验证美学四指标；代码无 LICENSE 须自研 |
| beamer-academic | 可借鉴机制 | 反 AI 味清单 + layout-registry 选型字段 |
| scholar-ppt-cn | 可借鉴机制 | 图表证据规则（本组最大单点增量） |
| note-slides | 可借鉴机制 | 来源锚点 + 40–60% 内容面积带 |
| slides_maker | 可借鉴机制 | claim ledger + carrying-element + reference_reached |
| mckinsey-pptx | 可借鉴机制 | CATALOG Use-when/Don't-use-when 模板卡 |
| huashu-design | 可借鉴机制 | 色彩三步协议 + 路线裁决 |
| humanize-ppt | 可借鉴机制 | AST 状态转移六问 + 失败模式目录纪律 |
| Awesome-PPT-Design-Skills | 不适用 | 无 LICENSE（治理反面教材） |
| yixueAIganhuo-PPT | 可借鉴机制 | 七段风格 schema；非商业 License 只借结构 |
| ppt-master | 已覆盖 | native-formula 高度预留规则可回查 |

**专家4 · Agent 编排与质量闭环（13）**

| 项目 | 判定 | 要点 |
|---|---|---|
| slides-grab | 可直接借鉴机制(最高优先) | 五类 sha256 指纹设计门（MIT） |
| codex-slides | 可借鉴机制(高优先) | 三层容错 + design-qa 报告格式 |
| ppt-agent-skill | 可直接集成资产 | visual_qa 像素断言族 + svg2pptx（MIT） |
| presentation-skill | 可直接集成资产 | 渲染器感知 lint + deck IR（MIT） |
| make-slide | 可直接集成资产 | pptx-spec.md 转换约束清单 + 主题对 |
| ppt-image-first | 可借鉴机制 | 三页实图预览 + 风格反演（Apache-2.0） |
| ppt-agent-skills | 可借鉴机制 | 治理对照系：阶段型返工 + 密度机器合同 |
| MultiAgentPPT | 可借鉴机制 | Write-Check 逐页重写环；寄生 ADK 已停维护 |
| PPTAgent | 可借鉴机制 | v1 编辑式 + v2 sandbox 双轨标本 |
| PPTist | 可借鉴机制(仅语义) | textType/slideType 枚举；AGPL 代码禁搬 |
| bolt-slides | 可借鉴机制 | 布局准入条件 + 引擎锁定契约 |
| presenton | 可借鉴机制 | PreviewSlideTool 工具化自查 |
| slide-deck-ai | 不适用/已覆盖 | 无环单发基线 |

**专家5 · 渲染与图像管线基建（17）**

| 项目 | 判定 | 要点 |
|---|---|---|
| playwright | 可直接集成资产 | 无头截图 lane 主干（Python 官方包） |
| resvg-js | 可直接集成资产 | SVG→PNG 确定性天花板（MPL-2.0） |
| mermaid | 可直接集成资产 | 11_图表语法 15/18 文件即其方言 |
| echarts | 可直接集成资产 | renderToSVGString 统计图表 lane |
| sharp | 可直接集成资产 | 像素档降档 + 体积治理（Python 等价实现） |
| puppeteer | 可借鉴机制 | 能力对等，分发便利性逊 playwright |
| satori | 可借鉴机制 | JSX→SVG 范式，未来信息图 lane |
| html-to-image | 可借鉴机制 | 仅浏览器内超采样场景 |
| vega | 可借鉴机制 | spec+schema 校验范式 |
| canvg | 可借鉴机制 | resvg 全面占优，不值得双轨 |
| awesome-gpt-image-2 | 已覆盖 | 05_来源 已 vendored，保持同步 |
| dom-to-image | 不适用 | 停更 8 年 |
| html2canvas | 不适用 | 有真浏览器即无理由用 |
| konva | 不适用 | 编辑器画布生态位 |
| fabric.js | 不适用 | 同上 |
| G2 | 不适用 | 交互式渲染器架构，静态成图不如 echarts |
| nivo | 不适用 | React 组件树依赖过重 |

**专家6 · 幻灯片框架与格式内核（15）**

| 项目 | 判定 | 要点 |
|---|---|---|
| python-pptx | 可直接集成资产 | 内核迁移目标（已在依赖树） |
| OfficeCLI | 可借鉴机制 | dump/batch + 选择器 + 渲染闭环范本 |
| PptxGenJS | 可借鉴机制 | theme XML 配方可抄，JS 栈不引入 |
| marpit | 可借鉴机制 | @theme 元数据 + 注释即 notes |
| spectacle | 可借鉴机制 | 五段主题 token |
| slidev | 可借鉴机制 | 独立 parser + 画布合同同构 |
| react-pptx | 可借鉴机制 | 佐证 IR 独立于内核的分层 |
| marp-cli | 已覆盖 | soffice 兜底是反面教材 |
| nodePPT | 可借鉴机制(弱) | 代码块→对象映射思想 |
| impress.js / reveal.js / deckjs / remark / webslides | 不适用 | HTML 演示框架，无 OOXML 输出或已停维护 |
| unioffice | 不适用 | 商业 EULA 一票否决 |

## 附录 2：材料索引

- 专家分报告：`docs/ppt-github-expert-reports/`（专家1–专家6，共 1493 行）
- 前置目录级调研：`/Users/kuang/knowledge/ppt-github/AI-PPT开源项目调研报告-2026-08-30.md`
- leo 基线：`leo-ppt-generator/SKILL.md`、`upstreams.yaml`、`upstream-capabilities.yaml`、`references/style-library.md`
