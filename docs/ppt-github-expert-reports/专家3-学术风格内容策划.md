# 专家 3 报告：学术演示与设计风格/内容策划视角的 16 项目源码评审

- 评审人角色：学术演示与设计风格/内容策划产品专家（论文→幻灯片管线、叙事结构算法、风格系统与模板设计语言）
- 评审对象：`/Users/kuang/knowledge/ppt-github/` 下 16 个项目（全部逐一深读源码，无抽查）
- 集成目标：`/Users/kuang/knowledge/leo-skills/leo-ppt-generator`（只读参考，未修改）
- 日期：2026-08-30

## 总览

16 个项目覆盖了学术 PPT 生成链路的几乎所有流派：纯图像式论文→PPTX（Paper2Slides）、多 agent 叙事驱动（ArcDeck）、RST 话语结构分页（ArcDeck）、LaTeX/Beamer 母版路线（beamer-academic）、HTML→可编辑 PPTX（huashu-design、Paper2Any）、可验证美学奖励（aeslides）、图片→对象级可编辑重建（yixueAIganhuo-PPT）、学术风格预设层（academic-ppt-master）、医学垂直域风格 JSON（yixueAIganhuo-PPT）、咨询图表语法（slides_maker、mckinsey-pptx）。

与 leo-ppt-generator 对照后的总体判断：**leo 的治理骨架（CONFIRM-GATE、deck-master 四段、三级标注、DELIVERY-GATE）在 16 个项目中处于第一梯队，唯一明显弱于对手的是三块：叙事结构算法的"话语级"依据（RST/commitment）、学术证据（图表/公式/引用）的领域规则密度、以及可验证美学度量（QA 目前偏合同校验而非几何/视觉度量）。**

---

## 逐项目评审

### 1. Paper2Slides
- 一句话定位：HKUDS 出品的论文→图片式幻灯片/海报生成器（RAG→摘要→规划→图像生成四阶段，全图像输出）。
- 架构与核心机制：
  - `paper2slides/core/pipeline.py`：`rag → summary → plan → generate` 四阶段状态机，带 checkpoint 与断点续跑（state.json 每阶段落盘）。
  - `paper2slides/prompts/content_planning.py`：分页提示词是学术五段式叙事骨架（Title/Cover → Background/Problem → Method（可多页，必须含 1–2 个 LaTeX 公式+变量解释） → Results（数据集精确数字、指标、消融） → Conclusion），每页绑定 `tables[]`/`figures[]`（`table_id`/`figure_id`/`focus`，表格可 `extract` 部分 HTML 且必须带真实数值）。另有 poster 三档密度提示词（sparse/medium/dense）。
  - `paper2slides/prompts/image_generation.py`：风格系统 = 自定义风格解析提示词（`STYLE_PROCESS_PROMPT` 输出 `style_name/color_tone/special_elements/decorations` 四字段 JSON，默认 Morandi 色板+浅底）+ 预置 academic/doraemon 两套风格 hint + 按 `opening/content/ending` 三段页面语义的版式规则（`SLIDE_LAYOUTS_*`）。
- 可搬运资产：五段式学术分页提示词与"公式/精确数字/表格真实值"保真条款；`opening/content/ending` 版式语义三元组；自定义风格四字段 schema；poster 密度三档。
- License：MIT（HKUDS，2025）。
- 对 leo-ppt-generator 的判定：**可借鉴机制**——leo 已有页面语义（13_页面语义）与风格 brief schema，但"公式必须保留 1–2 个 LaTeX + 变量解释""表格 extract 必须含真实数值"这类**学术保真条款**在 leo 的科研答辩风 brief 里未见同等密度的硬约束，值得移植进 deck-master 的证据层规则。

### 2. Paper2Any
- 一句话定位：OpenDCAI 的论文多模态工作流平台（Apache-2.0），47 个 agent 覆盖大纲、drawio 图、图表代码、图标、技术路线图、PPT/PPTX/视频/rebuttal。
- 架构与核心机制：
  - `dataflow_agent/agentroles/paper2any_agents/`（47 个 agent）：`outline_agent` / `diagram_planner` / `drawio_xml_generator` / `diagram_vlm_validator`（VLM 校验图表）/ `chart_type_recommender` / `technical_route_bw_svg_generator` + `technical_route_colorize_svg_agent`（技术路线图黑白生成→上色两阶段）/ `p2v_*`（PDF→beamer 代码）等。
  - `dataflow_agent/promptstemplates/resources/pt_paper2ppt_outline_repo.py`：论文→大纲提示词，schema 为 `title/layout_description/key_points/asset_ref`；**图片 catalog 白名单机制**——"只允许从论文图片 catalog 中选择真实存在的 ref，禁止编造图片路径"；另有 edit-planner 提示词把自然语言反馈转为结构化编辑计划（`update/delete/insert_after/move` + `apply_global_rewrite`），页数守恒。
  - `dataflow_agent/promptstemplates/paperbanana.md`：**学术方法图美学风格指南**（"NeurIPS Look"：分区色策略 10–15% 透明度浅底、圆角矩形=过程/圆柱=存储的形状语义、实线=数据流/虚线=辅助流的线型语义、标签 Sans/变量 Serif Italic 的字体分离、"Amateur 反模式"清单）+ 按论文类型分支的领域风格（Agent/LLM 论文→友好叙事卡通风、CV/3D→几何密集、理论→极简灰度+单高亮）+ 统计图美学指南（纹理+形状区分数据支持黑白打印与色盲）。
  - `dataflow_agent/promptstemplates/drawio_system_prompt.py`：结构约束 drawio XML 生成（软色板、网格对齐、默认 ≤12 节点、单视口 800×600 内、三种风格变体 default/minimal/sketch）。
- 可搬运资产：paperbanana.md 整份学术图表风格指南（改写为 leo 的 references/styles/ 图表规范）；图片 catalog 白名单约束；edit-planner 结构化编辑计划；drawio 版式约束规则。
- License：Apache 2.0。
- 对 leo-ppt-generator 的判定：**可直接集成资产**——paperbanana.md 是本次评审中学术视觉语言密度最高的单文件，与 leo 的 11_图表语法/统计图标注.md 完全互补（leo 有"图型选择"，缺"学术方法图怎么画好看"的视觉语言）；Apache-2.0 允许改编保留声明后集成。

### 3. academic-ppt-master
- 一句话定位：ppt-master 引擎的学术分叉（ATTRIBUTION.md 明确：MIT 引擎 + 新增学术层），SVG→DrawingML 原生可编辑 PPTX。
- 架构与核心机制：
  - `references/modes/academic.md`：**五模块叙事骨架**（研究背景与目的→技术路径→研讨成果⭐（页数最多）→研究结论与讨论（连接到自己课题）→展望与借鉴），断言式标题（Assertion-Evidence, Michael Alley）、一页一信息、3 秒规则、能画图绝不打字；**密度双档**：minimal（会议报告）vs dense-defense（答辩档：左栏 TOC 导航轨、2–4 编号面板、4 列 substance block、真实数字/重绘表格/原图嵌入）。
  - `references/visual-styles/academic-defense.md`：答辩视觉风格的完整规格（chrome 两选一：页眉页脚带 / 左侧 TOC 侧栏；`3.2 复杂度分析：O(1) 路径`式编号断言标题；4 列 substance block = icon+headline+2–3 行事实+粗体 mini-stat；"Numbers, not adjectives"实质纪律；10–16 页规模律）。
  - `templates/layouts/academic_paper_report/`（10 页 SVG 母版）与 `academic_defense_deck/`（12 页）；`templates/brands/` 3 个学术品牌（academic-blue/graphite/navy）。
  - `references/strategist.md`：八确认流程 + design_spec 11 节模板（含 spec_lock 机制），与 leo 的 CONFIRM-GATE 同构。
- 可搬运资产：academic.md 五模块叙事 + 双密度档（可直接改写为 leo 的 06_论证模式新成员"学术五拍"）；academic-defense.md 的答辩 chrome 规格（左侧 TOC 侧栏是中国答辩 deck 的签名元素，leo 科研答辩风 brief 可吸收）；"Numbers, not adjectives"实质纪律条款。
- License：MIT（学术层原创，M1n-n9）。
- 对 leo-ppt-generator 的判定：**可直接集成资产**——学术层文件全部 MIT 且是本评审中最贴 leo 形态（风格/模式/母版三层分离）的项目；其"dense-defense 答辩档"是 leo 风格库缺的一档。

### 4. ArcDeck
- 一句话定位：UIUC Rehg Lab 的叙事驱动论文→PPTX 框架（arXiv:2604.11969），以 RST 修辞结构理论做分页决策，commitment 合同 + critic/judge 迭代闭环。
- 架构与核心机制：
  - `arcdeck-skill/agents/`（14 agent 流水线）：pdf-preprocessor → asset-extractor → **commitment-builder** → **discourse-parser** → slide-planner → narrative-critic → slide-reviser → narrative-judge → image-table-filter → slide-composer → design-critic → design-refiner → pptx-builder。
  - `arcdeck-skill/reference/RST-RELATIONS.md`：**RST 8 关系闭集**（elaboration/explanation/context/purpose/evaluation/organization + joint/same-unit）+ 二叉树规则（N 段落→N-1 组）+ 每关系的分页启发式（elaboration→同页、evaluation→可独立成页、same-unit→绝不拆页）。
  - `arcdeck-skill/prompts/outline/commitment_builder_lite.txt`：**全局合同 commitments.md**——Snapshot / Talk contract（受众、前置知识、目标 inform/persuade/teach/pitch、时长、目标页数、figure-first/balanced/text-first、数学量级 light/medium/heavy、must-include/must-avoid）/ Core content（论点一句、3 takeaways、贡献排序、out-of-scope）/ Narrative spine（5–7 步）/ Section plan 表（H/M/L 优先级+建议页数），250–500 词，"不确定写 UNKNOWN，禁止编造数字"。
  - `arcdeck-skill/prompts/outline/narrative_critic.txt`：critic 以 commitment 为主 rubric，输出 `priority_fixes`（含 `commitment_refs` 指向被违反的合同条目）。
  - 渲染层：8 个 PPTX 模板（`utils/slides_template/`）+ js_design/js_theme 参考图，design-critic/refiner 闭环。
- 可搬运资产：RST 关系→分页规则表（可并入 leo deck-master 的分页决策）；commitments.md 合同 schema（与 leo 合同互补的是"数学量级/风格三选/优先级页数分配"三个学术专用字段）；narrative-critic 的 commitment 对齐评分维度。
- License：MIT。
- 对 leo-ppt-generator 的判定：**可借鉴机制**——RST 分页给 leo 的"母版分页"提供了可解释的算法依据（目前 leo 分页主要靠论证模式+禅档位经验规则）；commitment 的"数学量级"字段是学术合同缺失的一问。

### 5. GenSlide
- 一句话定位：LangGraph + GPT-4o 的极简 agentic PPTX 生成器（orchestrator 规划标题 → content agent 并行写页 → python-pptx 组装 → Streamlit 人审循环）。
- 架构与核心机制：
  - `agents/orchestrator.py`：单页数组大纲提示词（5–10 个标题、3–8 词、有叙事弧、禁用 Introduction/Agenda/Thank You/Q&A 占位标题）+ 4 策略回退解析链。
  - `agents/content_agent.py`：单页三键 JSON（title/bullets 3–5 条每条 ≤15 词/speaker_notes 2–4 句不复读 bullets）+ 修订后缀注入用户反馈做"外科手术式修改"。
  - `tools/pptx_builder.py`：确定性渲染——深色首尾页夹浅色内容页的三明治结构、布局网格常量、页脚条。
- 可搬运资产："禁用占位标题"黑名单；human-in-the-loop 的"定向修订而非重写"话术模式。
- License：MIT。
- 对 leo-ppt-generator 的判定：**已覆盖**——leo 的母版+CONFIRM-GATE+revision 机制全面强于此项目；仅"占位标题黑名单"小到不值得单独立项，可并入母版纪律一句话。

### 6. aeslides
- 一句话定位：智谱 GLM 团队的 RL 美学框架（arXiv:2604.22840），用**可编程验证的美学指标**（而非 VLM 评分）做 GRPO 奖励，修布局四病：比例失真/留白过量/元素碰撞/视觉失衡。
- 架构与核心机制：
  - `src/reward.py`：非对称二次惩罚的纵横比奖励（对数域 `exp(-α·e² - β·tall_excess²)`，高瘦惩罚重于扁宽）+ smoothstep 奖励（0.8–0.995 区间平滑映射）。
  - `src/whitespace.py`：**局部方差图留白检测**——box filter 求局部均值/方差 → clip 归一化 → 二值化分内容/空白 → 全图与裁剪（去 15%/10% 边）两个 content_ratio。
  - `src/centroid.py`：富语义 bbox 树加权视觉质心 vs 视口中心的偏移（图标 0.5 权重、背景剔除、文本/原子节点特判）。
  - `src/gdpo.py`：reward-decoupled 归一化（多目标奖励的组内解耦，防某一奖励支配）。
  - README 明确论证：VLM 评分有系统性盲点（测不出纵横比失真）、判别力弱、易被 reward hacking——**可验证指标优于 VLM 打分**。
- 可搬运资产：四个美学度量的算法思想与阈值（纵横比 ±4% 平坦区、留白 content_ratio 阈值、质心容差）；"VLM 不可作为美学唯一裁判"的论点可直接支撑 leo 的 visual-qa 设计。
- License：**无 LICENSE 文件**（README 声明因专有约束只放核心机制片段；已集成进 GLM-5）。代码不可直接搬运，算法思想可引用论文（arXiv:2604.22840）自行实现。
- 对 leo-ppt-generator 的判定：**可借鉴机制**——leo 的 visual-qa.md 若增加"局部方差留白率/质心偏移/纵横比"三个可编程指标（自行实现，约百余行 OpenCV/NumPy），就从"合同校验"升级为"几何度量门禁"，直接命中答辩 deck 最常见的空版式与偏版式问题。

### 7. beamer-academic
- 一句话定位：论文→Beamer 答辩 PDF 的 Claude Code 技能（16 个 LaTeX 版式母版 + slots + 选型注册表 + 反 AI 味写作指南）。
- 架构与核心机制：
  - `references/layouts.md` + `references/layout-registry.yaml`：16 版式（cover/toc/section-divider/text-only/左右图文/formula/table/full-image/conclusion-box/transition/list/thanks/statement 金句/stats 三个数/hypothesis 三列短句），每个版式含 LaTeX 骨架 + slots 定义 + 字数约束（纯文段每段 80–120 字总 ≤300 字）；registry 定义 `when/max_per_presentation/position/slots` 选型规则。
  - `references/writing-style.md`：**Anti-AI 标题与内容检查**（标题红旗："深入探讨/全面分析/系统研究"；内容红旗："值得注意的是/本研究具有重要意义"→"像答辩学生写的还是 AI 写的"）+ 从真实答辩 PPT 提炼的页面组合模式（段落+keybox 核心问题框）。
  - `assets/beamerthemeAcademic.sty` + `config.yaml`：主题与 5 色板；`scripts/extract_figures.py` 从论文 PDF 提图；`examples/transformer/defense.tex` 全量样例。
  - `SKILL.md`：三遍大纲（结构→每节→终确认）+ 节奏约束（版式重复控制）。
- 可搬运资产：**writing-style.md 的反 AI 味检查清单**（学术中文场景立即可用）；layout-registry 的 `max_per_presentation/position` 选型字段设计；statement/stats/hypothesis 三个版式语义（金句页/三数字页/三列假说页）。
- License：MIT。
- 对 leo-ppt-generator 的判定：**可借鉴机制**——LaTeX 母版与 leo 路线不同，但"反 AI 味写作检查"与"版式出现频次上限字段"两件东西可以低成本并入 leo 的母版纪律与版式库 schema。

### 8. scholar-ppt-cn
- 一句话定位：中文学术 PPT 技能（v3.4），与 leo-ppt-generator 架构高度同构：生产规划表→mockup family→生图样板/全稿逐页/模板直出三路线→视觉系统锁定→可编辑重建→montage QA。
- 架构与核心机制：
  - `references/evidence_asset_rules.md`：**科研图表证据规则**——选图先于版式（"每张图必须回答一个明确的演示问题"）；原图默认不加边框/卡片/圆角容器/阴影直接上版面；轴/图例/单位/比例尺/panel 标签必须可见；6 种处理模式（preserve / overview+detail / split / cross-slide / not-use / request-higher-resolution）；**视觉审查状态 5 级**（vision-reviewed/metadata-reviewed/caption-inferred/user-described/not-reviewed，只有 vision-reviewed 才允许基于图内位置的标注）；"图过多过小时的降级顺序"（删图→减结构→放大关键图→拆页→overview+detail→省略）。
  - `references/hidden_narrative_presets.md`：4 类叙事预设（文献汇报 10 拍/学位答辩 11 拍/科研进展 8 拍/一般主题 8 拍）+ 页数规模（10–15 分钟 14–18 页）。
  - `references/pptx_qa_rules.md` + `scripts/qa_pptx.py`：**QA 场景 profile**（group-meeting/defense/conference/classroom/template-preserve）+ 交付阻断错误清单 + montage 对比 + 最终哈希验证（任何 PPTX 修改使旧 QA 报告失效）。
  - `references/layout_repetition_control.md`：连续 ≤2 页同骨架、同任务多页轮换 archetype、重复视为 QA 失败。
  - 生图路线约束：每次调用重复注入短约束（不依赖长上下文记忆）；禁止编造科学节点/因果/数值；可编辑重建不继承商业课件图标（灯泡/书本/显微镜/烧瓶/靶心/emoji）。
- 可搬运资产：evidence_asset_rules 的 6 处理模式 + 5 级审查状态（与 leo 三级标注形成完整证据治理栈）；QA profile 按"投影场景"分档；版式重复控制三条。
- License：MIT。
- 对 leo-ppt-generator 的判定：**可借鉴机制**——leo 已有三级标注（引用/估算/示意，管数字与断言），但**没有"图怎么处理"的证据规则**（preserve/split/cross-slide 等模式与 vision-reviewed 状态）；这是 leo 学术路线最大的单点缺口之一。

### 9. note-slides
- 一句话定位：访谈/播客/长文→横向翻页 HTML 笔记幻灯片技能，核心方法论是**来源锚点**（每页必须指回原问题/原判断/例子/数字/概念原词）。
- 架构与核心机制：
  - `SKILL.md`：通读后强制产出**现场清单**（真正推动回答的原问题、改变方向的小标题/转折句）作为每页来源候选池；候选页 5 字段（来源位置/页面重点/支撑锚点/推荐布局/**自检"不读原文能不能写出这一页？能则重写"**）；核心总结候选（6–12 条，只选材料里明确说过的判断）。
  - `references/styles.md`：设计系统——一页一想法、默认垂直居中、**内容占画面 40–60% 视觉面积**（挤过 80% 即密度超标）、"Jobs 式原则"七条、"One thousand no's for every yes"。
  - `references/layouts-notes.md`：笔记型骨架 Layout 23–32（界面证据/原文摘录加侧注/段落拆解/线索词追踪/观点加例证/一句原话多层注解/文章脉络/双张力/未解问题/核心总结）。
  - `scripts/check_plan.py` / `check_deck.py`：写 HTML 前查每页来源锚点、交付前机械 P0（标点纪律、data-source 属性）。
  - `references/content-extraction.md`：好坏对照的锚点细则。
- 可搬运资产：现场清单→候选页→静默自检的三步内容工作流；"不读原文能不能写出这一页"的自检问句；内容面积 40–60% 的可量化密度带；Layout 23–32 的笔记型版式语义（尤其"双张力""未解问题"两页型对学术研讨 deck 有用）。
- License：MIT。
- 对 leo-ppt-generator 的判定：**可借鉴机制**——"来源锚点"与 leo 三级标注互补（三级标注射数字，锚点管每页可回溯性）；"不读原文能否写出这页"可加进 deck-master 的减法审计作为第二问。

### 10. slides_maker
- 一句话定位：Addsum 的原生可编辑 PPTX 技能（45+ references、5 agents），卖点是"读真实材料、绝不编数字、独立 critic 审查、按内容设计"，12 方向双语模板库。
- 架构与核心机制：
  - `skills/slide-maker/references/critic-panel.md`：**CONTRACT CARD** 评审分发卡片——deck 记忆句+情绪曲线、逐页 takeaway/role/question/beat 表、claim ledger、每图 carrying-element 行、signature_proof token（签名页/最密页/数据页三锚点）、用户反馈 user-dials 中性记录；**trace_composed.py 把已交付文本拆为"源引用 vs 作者撰写"**——实测三大内容缺陷全在后者，这是评审瞄准镜。
  - `references/content-plan-spec.md`：comprehension brief 必填字段——一句话信息+其来源原句、贡献（用作者的话）、方法本质（含那一个关键公式）、**每图每表一行：`id | 它为哪个比较服务 | 哪个确切元素承载它 | 强调什么 | 要避免的误读`**（"说不出承载元素的图就是没看懂的图"）；**claim ledger**（每个数字/日期/名字/引用/最高级断言一行：source+verbatim value+verified?+as-of date，不可验证要么删要么标 open 绝不上稿）；长源模式（分类→映射→分诊→深读承重 20%，CJK 字数校正）。
  - `references/data-viz.md`：**按论证选图**的图表语法库——donut+KPI/dumbbell/slope/dual-axis/bubble+趋势线/Pareto/KPI scorecard/leaderboard/hub-spoke/waterfall/radar（含"雷达图必然夸大领先、面积平方增长、轴序改变形状"的诚实性限制）/distribution（引 Nature Methods *Kick the bar chart habit*：n≥5 箱线、3–4 均值±误差、n<3 拒画）/marimekko/small multiples/sparkline/标注层（CAGR 箭头/差值括号/参考线）/football field/choropleth/IBCS 记法/色盲安全；每型都有反模式段。
  - `evals/evals.json`：评测哲学——`reference_reached` 断言（参考文件在运行中真的被读了吗？只能从 transcript 回答）；场景按盲点选择不凑数；明拒 LLM 美学评分（reference 相似度奖励模仿，闭式美学分与多样性门自相矛盾）。
- 可搬运资产：claim ledger（与 leo 数字登记表同构但多了 verified?/as-of date 与"不可验证不上稿"硬规则）；每图 carrying-element 行；data-viz.md 的 distribution/雷达限制等学术向条目；evals 的 reference_reached 断言思路。
- License：MIT。
- 对 leo-ppt-generator 的判定：**可借鉴机制**——leo 数字登记表已覆盖 claim ledger 的大部分；delta 是 (a) 每图 carrying-element 行（"这张表为哪个比较服务、哪行承载它、要避免什么误读"——对答辩实验表页是杀器），(b) reference_reached 式评测断言。

### 11. mckinsey-pptx
- 一句话定位：麦肯锡风格 40 个确定性 Python 模板的 Claude 插件（LLM 读 CATALOG 选模板→python-pptx 渲染）。
- 架构与核心机制：
  - `mckinsey_pptx/agent/CATALOG.md`：**模板目录即 agent 接口**——每模板给 Use when / Don't use when（指向更合适的相邻模板）/ Required inputs / Optional inputs / 最小调用示例；如 executive_summary_takeaways（2–4 个粗体 takeaway 各带 2–4 bullet + final_conclusion）、dark_navy_summary（单一 impact statement 满版深蓝页）、assessment_table（KPI×红绿灯状态）。
  - `mckinsey_pptx/slides/*.py`：13 个渲染模块 40 模板（执行摘要/对比/时间线/组织图/趋势/气泡/流程）。
  - `mckinsey_pptx/theme.py`：深蓝系色板 dataclass（dark_navy/bright_blue/status_green…）。
- 可搬运资产：CATALOG.md 的"Use when/Don't use when + 最小示例"模板卡格式（leo 的 12_版式库/13_页面语义 可采用此格式让 agent 选版式更准）；dark_navy_summary 式"单一结论满版页"。
- License：MIT。
- 对 leo-ppt-generator 的判定：**可借鉴机制**——leo 的版式库目前是描述式的；给每个版式补 Don't-use-when 与最小示例字段，选型准确率会明显提升（ArcDeck/beamer-academic 的 registry 也是同方向证据）。

### 12. huashu-design
- 一句话定位：花叔的"打字回车出设计"大杂烩技能（PPT/动画/视频/原型），60 种 HTML 原生风格库 + HTML→可编辑 PPTX 导出链。
- 架构与核心机制：
  - `references/design-styles.md`：网页 20 + PPT 20 + 信息图 20 风格库，按大胆/中性/安静三派组织；**色彩推导三步协议（采样→收敛→论证）** + "低饱和比纯屏幕色高级"的印刷质感论证 + 同色相不同文化语境速查。
  - `references/editable-pptx.md` + `scripts/html2pptx.js`（1177 行）：HTML 逐元素翻译为可编辑 PPTX 的 4 条硬约束（div 不直接写文字必须 p/h1-h6 包裹等）+ 画布 960×540pt=LAYOUT_WIDE 的尺寸决策（"HTML 尺寸决定物理尺寸不是分辨率"）+ "视觉保真与可编辑不可兼得是 PPTX 物理约束"的路线裁决（复杂视觉走 PDF 路径）。
  - `references/typography.md`、`tweaks-system.md`、`critique-guide.md` 等支撑文件。
- 可搬运资产：色彩推导三步协议（采样→收敛→论证）可并入 leo 风格推荐；"视觉保真 vs 可编辑"的路线裁决表述；60 风格库的组织法（三派 × 三媒介）。
- License：MIT（2026-05-14 起完全开源）。
- 对 leo-ppt-generator 的判定：**可借鉴机制**——学术关联弱，但色彩三步协议与路线裁决两段方法论对 leo 的 style-recommendation 与 input-routing 有直接补强。

### 13. humanize-ppt
- 一句话定位：LearnPrompt 的"为演讲而生"系统：AST（Audience-State-Transfer 观众状态转移）大纲理论 + 演讲体检（揪出"只能看、不能讲"的页）+ 下游多渲染器适配。
- 架构与核心机制：
  - `docs/AST-theory.md` + `contracts/ast-outline.schema.md`：大纲必答 6 问（谁在听/初始状态/期望状态/核心张力/每页如何推进状态/哪个渲染器完成）；transfer_path 五角色（hook→conflict→method→proof→takeaway）；经验源（Karpathy 结构/Jobs 呈现/Musk 传播/YC office hours）。
  - `references/qa-failure-modes.md`：**失败模式目录纪律**——"只列代码里真实存在的规则，不写愿望清单"；两层失败类（渲染器无关 + 渲染器专属）；"静态扫描测不出的失败类"诚实单列（字重降级、视口截断、图文错位需真渲染；WebGL 封面截图时机问题）；每模式给症状/观众视角/检测函数名/修复方向。
  - `scripts/humanize_ppt_v2.py` 的 FAILURE_MODES 字典是代码侧唯一事实来源；体检产出 fix_prompt.md 让下游重渲。
- 可搬运资产：AST 六问与五角色（可与 leo 的 beat/audience_takeaway 字段融合成"演讲适配"合同段）；失败模式目录的"真实存在才入册"纪律与两层划分法。
- License：MIT。
- 对 leo-ppt-generator 的判定：**可借鉴机制**——leo 母版已有 beat/audience_takeaway，AST 的增量是"核心张力"字段与"每页完成一次状态转移"的体检判据；失败模式目录纪律适合 leo 的 visual-qa 演进。

### 14. Awesome-PPT-Design-Skills
- 一句话定位：6 个 ppt-master 风格皮肤技能（7 种 house style：日式生活杂志/和纸柔光/3D 黏土/未来科技编辑/极简奢华品牌/现代插画编辑/日式手绘编辑），每个含完整风格系统 + 版式词汇 + QA 清单。
- 架构与核心机制：
  - `japanese-style-ppt-skill/SKILL.md`：不可协商风格规则（禁纯白纯黑、每 deck 唯一活动 accent 默认 indigo #2C3E50、禁霓虹/玻璃拟态/SaaS 蓝紫）+ 默认色值表 + 60–75% 安静面/20–30% 内容/5–10% accent 的面积配比。
  - `references/style-system.md`：调色板角色表（paper base/indigo accent/charcoal text/divider gray/五个 reserve 色标注"rare"）+ 材质规则（和纸纹理模拟法、soft glow 仅限局部低透明洗）。
  - `references/slide-patterns.md`：**版式词汇表**——Quiet Editorial Cover / Asymmetric Thesis / Thin-Line Matrix / Paper Bento / Process Thread / Framed Evidence / Reflective Quote，每型给适用场景与构成要素；"不要每页重复同一布局"。
  - `references/qa-checklist.md` + `ppt-master-integration.md`：风格层 QA 与引擎挂接。
- 可搬运资产：风格技能的文件组织范式（SKILL 硬规则 + style-system 色彩角色表标 "rare" + slide-patterns 版式词汇 + qa-checklist）；面积配比（60/30/10）作为风格参数。
- License：**无 LICENSE 文件**（README 仅繁中说明与 Limits 段）。资产不可直接搬入 MIT 仓库，机制可借鉴。
- 对 leo-ppt-generator 的判定：**不适用**（美学方向与学术赛道不重合且无许可证）；仅"色彩角色表 + rare 标注 + 版式词汇命名"的组织法值得看一眼。

### 15. yixueAIganhuo-PPT
- 一句话定位：医学学术 PPT 技能：父 agent 编排医学理解 + GPT Image 2 逐页生图 + page worker 逐页对象级可编辑重建，19 种医学风格 JSON，默认双交付（图片 PPTX + 可编辑 PPTX + 中文讲稿）。
- 架构与核心机制：
  - `references/00X_*.json`（19 个风格提示词）：**七段 schema**——metadata / global（medical_academic_slide 全局风格 + layout_geometry 版式几何 + typography_and_evidence 排版与证据）/ continuity（跨页连续性）/ illustration（科研插图）/ asset_embedding（原图嵌入规则）/ closing / negative_constraints（负面约束）。每段是可直接拼装为生图 prompt 的成品文案（如 003 深蓝灰：#152A36 主色+#F2A900 高亮黄、黑白医学影像底、黄色六边形编号）。
  - `references/page-decision-tree.md`：**页面对象决策树**——三步强制顺序（背景识别与修复→前景资产分离→原生元素重建），"先定背景/前景/原生边界再写 manifest"；公式单列（目标函数/约束/矩阵/分式/根式/cases/多行方程组，绝不与普通文本混编）；"虚假进展"失败模式警示（重建文字布局但裁剪近似前景资产=未通过对象来源合同）。
  - `prompts/page-worker.md`：强制先读三参考再动手、OCR text-hints 与图像任务并行、manifest 为唯一构建真值、上一次失败工件视为不可信。
  - `scripts/`：风格选择器、PDF 资产推断、OCR（PaddleOCR/PP-OCRv5）、slide prompt 校验器等 15 个脚本。
- 可搬运资产：19 风格 JSON 的七段 schema（ Leo 的风格 brief 可吸收 continuity/asset_embedding/negative_constraints 三段）；公式单列与 LaTeX 渲染规则；"虚假进展"失败模式。
- License：**非商业许可**（Non-Commercial Use License：个人/学术/教育/研究可用，商业需书面授权）。资产不可搬入 leo（MIT 仓库），机制与 schema 结构可借鉴。
- 对 leo-ppt-generator 的判定：**可借鉴机制**——leo 的 page-decision-tree.md 与它思路同源（leo 已有）；真正的新东西是**风格 JSON 里的 continuity/asset_embedding/negative_constraints 三段**，leo 风格 brief 补这三段能显著提升跨页一致性与原图嵌入纪律。

### 16. ppt-master
- 一句话定位：Hugo He 的原生可编辑 PPTX 引擎（SVG→DrawingML，79 脚本，6 模式，20 风格，模板/品牌/图表/图标四库），是 academic-ppt-master 与 Awesome-PPT-Design-Skills 的共同上游。
- 架构与核心机制：
  - `skills/ppt-master/references/strategist.md` + `templates/design_spec_reference.md`：八确认 + design_spec 11 节 + spec_lock（双层锁：mode 层叙事骨架 + visual style 层美学）。
  - `references/native-formula.md`：**原生公式规格**——LaTeX 精确作者契约，inline marker（`data-pptx-inline-formula` tspan）与 block marker 两形态，"公式结构而非平面预览是垂直布局真值"、native 高度预留（分式/根式/n 元极限的上下伸）、导出为可编辑 Office Math（a14:m > m:oMath）。
  - `templates/charts/`：20+ SVG 图表模板（含 box_plot/butterfly/dumbbell/funnel/gantt/heatmap）+ `chart-vocabulary.md` + charts_index.json。
  - `references/modes/`（pyramid/narrative/instructional/showcase/briefing）与 executor 家族（executor-chart/table/visualization/structured）。
- 可搬运资产：native-formula 的"公式结构是布局真值 + 高度预留"规则（leo 图像路线公式是画进图里的，但 direct-editable 路线会用到）；chart-vocabulary 组织法。
- License：MIT。
- 对 leo-ppt-generator 的判定：**已覆盖**——leo 的四路线/风格库/母版治理已同等级或更强（leo 有 deck-master 四段与三级标注这套 ppt-master 没有的证据治理）；公式高度预留规则在 leo 做 direct-editable 学术页时可回来查。

---

## Top 5 集成建议（按 ROI 排序）

### 建议 1：为学术路线补"科研图表证据规则"（evidence asset rules）
- 来源：scholar-ppt-cn（`references/evidence_asset_rules.md`）、Paper2Slides（`paper2slides/prompts/content_planning.py` 的 tables/figures 绑定）
- 内容：新增 leo `references/` 层的《学术图表证据规则》：6 种处理模式（preserve / overview+detail / split / cross-slide / not-use / request-higher-resolution）+ 图的视觉审查 5 级状态（仅 vision-reviewed 允许基于图内结构标注）+ "原图裸上版面、不加卡片圆角阴影"纪律 + 图过多过小时的降级顺序 + 母版视觉行每图绑定 `figure_id/focus`。同时把 Paper2Slides 的学术保真条款（方法页 1–2 个 LaTeX 公式+变量解释、表格必须真实数值）写进科研答辩风的母版纪律。
- 预期收益：学术场景（答辩/组会/文献汇报）的图页是差评重灾区；这是把 leo 的"数字三级标注"扩展为"数字+图双维证据治理"，直接决定学术线口碑。
- 集成成本：低——纯 references 文档 + deck-master 视觉行字段扩展（加 figure 处理模式列），无 runtime 改动。

### 建议 2：引入 RST 话语关系作为分页算法依据 + commitment 合同的学术字段
- 来源：ArcDeck（`arcdeck-skill/reference/RST-RELATIONS.md`、`prompts/outline/commitment_builder_lite.txt`、`prompts/outline/narrative_critic.txt`）
- 内容：在 deck-master 分页决策中引入 RST 8 关系启发式（elaboration/explanation 同页、evaluation 可独立成页、same-unit 绝不拆页），作为"禅档位"之外的第二判据；合同模板增加三个学术字段：数学量级（light/medium/heavy）、图表风格（figure-first/balanced/text-first）、section 优先级页数分配表（H/M/L→建议页数）。
- 预期收益：分页决策从经验规则升级为有论文依据的可解释算法；数学量级字段避免"理论论文被做成图少文多"的常见错配。
- 集成成本：中——需要把 RST 树作为母版生成的中间产物（可选轻量版：只借分页启发式表，不做完整树解析）。

### 建议 3：visual-qa 增加三个可编程美学度量（留白率/质心偏移/纵横比）
- 来源：aeslides（`src/whitespace.py`、`src/centroid.py`、`src/reward.py`，arXiv:2604.22840）
- 内容：在 leo 的 visual-qa/D ELIVERY-GATE 门前增加三个自研指标（参照论文算法，不搬代码）：(a) 局部方差留白检测得 content_ratio（内容占比带 40–60% 参考 note-slides 阈值）；(b) bbox 加权质心 vs 版心偏移；(c) 图像元素纵横比平坦区检测。产出可视化 debug 图供样张评审。
- 预期收益：aeslides 实证 VLM 有系统性盲点且判别力弱；这三个指标便宜、确定、可直接阻断"空版式/偏版式/变形图"三类学术 deck 高频缺陷，把 QA 从合同校验升级为几何度量。
- 集成成本：中——约百余行 Python（OpenCV/NumPy），挂进现有 DELIVERY-GATE 流程；注意 aeslides 无 LICENSE，须自行实现并引用论文。

### 建议 4：集成"NeurIPS Look"学术方法图视觉语言 + 答辩 dense 档风格
- 来源：Paper2Any（`dataflow_agent/promptstemplates/paperbanana.md`，Apache-2.0）；academic-ppt-master（`references/modes/academic.md`、`references/visual-styles/academic-defense.md`，MIT）
- 内容：(a) 把 paperbanana.md 改写并入 leo `references/styles/00_索引/图表样式规范.md` 或新建《学术方法图视觉语言》：分区色 10–15% 透明度、圆角=过程/圆柱=存储、实线=数据流/虚线=辅助流、变量 Serif Italic/标签 Sans 的字体分离、按论文类型（Agent/CV/理论）的三分支、Amateur 反模式清单。(b) 以 academic.md 五模块叙事 + academic-defense.md 答辩 chrome（左侧 TOC 侧栏、2–4 编号面板、"Numbers, not adjectives"）为蓝本，给 leo 的 06_论证模式 增加"学术五拍"模式、给科研答辩风 brief 增加 dense-defense 档（当前 leo 禅档位没有面向答辩的"证据密集档"）。
- 预期收益：方法示意图是学术 deck 的门面页；paperbanana 是本评审视觉语言密度最高的资产；答辩 dense 档补上"组会简报档"与"答辩证据档"的分野。
- 集成成本：低——均为 MIT/Apache 文档资产改写；风格 brief 与模式文件是 leo 现有格式。

### 建议 5：母版与版式库的小型高价值增强包
- 来源：slides_maker（`skills/slide-maker/references/content-plan-spec.md` 每图 carrying-element 行、`evals/evals.json` reference_reached）；beamer-academic（`references/writing-style.md` 反 AI 味清单、`references/layout-registry.yaml` 的 max_per_presentation/position 字段）；note-slides（`SKILL.md` 的"不读原文能否写出这页"自检、40–60% 内容面积带）；mckinsey-pptx（`mckinsey_pptx/agent/CATALOG.md` 的 Use/Don't-use/最小示例卡格式）；GenSlide（`agents/orchestrator.py` 占位标题黑名单）
- 内容：一次性小改：(a) 母版视觉行每图加一行 `承载元素 | 服务的比较 | 要避免的误读`；(b) 数字登记表加 `verified?/as-of` 两列（不可验证→删或标 open）；(c) 减法审计加第二问"不读原文能否写出这页"；(d) 风格/版式文件统一补 Use-when/Don't-use-when/示例三字段；(e) 母版标题纪律并入反 AI 味红旗清单与占位标题黑名单；(f) 评测增加 reference_reached 式断言（参考文件是否真被读过，从 transcript 断言）。
- 预期收益：六件小改动各自独立生效、合计显著提升内容可信度与版式选型准确率，且几乎全部落在 leo 已有的文件格式内。
- 集成成本：低——均为文档与校验器的小增量。

## 专家观点（署名立场）

**学术赛道成熟度判断**：这条赛道已从"论文摘要填充模板"（GenSlide 一代）进化到"叙事驱动 + 证据治理"两轴竞争。叙事轴的代表是 ArcDeck（RST 分页 + commitment 合同 + critic 闭环）和 humanize-ppt（AST 观众状态转移），证据轴的代表是 scholar-ppt-cn（图表处理模式 + 审查状态）、slides_maker（claim ledger + carrying-element）和 Paper2Slides（公式/数值保真条款）。**两轴都做且做成产品级闭环的，16 个项目里一个都没有**——ArcDeck 的证据层薄，scholar-ppt-cn 的叙事层弱。leo-ppt-generator 恰好两块骨架都有（论证模式+beat 管叙事，三级标注+数字登记表管证据），这是最大的结构性机会：补上"图维度的证据规则"（建议 1）后，leo 将是唯一双轴闭环的学术 PPT 技能。

**风格库最缺什么**：缺的不是风格数量（136 个已足够多），而是**三个维度的纵深**：(1) **密度分档**——目前禅档位是"内容多少"的档，没有"证据密度"的档（学术答辩需要的 dense-defense 档：左 TOC 侧栏+编号面板+KPI+重绘表格，与组会简报档是两种生物）；(2) **图内视觉语言**——13 类风格管页面皮肤，不管"方法示意图内部怎么画"（分区色策略、形状语义、线型语义、变量字体规范），这正是 Paper2Any paperbanana.md 的领地；(3) **风格的跨页连续性与负面约束段**——yixueAIganhuo 的 19 风格 JSON 证明 continuity/asset_embedding/negative_constraints 三段能显著稳住逐页生图的一致性，leo 的 brief 多数只有正向描述。

**最值得引入的 1 个设计**：**ArcDeck 的 commitment 合同（commitments.md）**。它用一个 250–500 词的 Markdown 文件回答了学术演示的全部前置问题——受众与前置知识、inform/persuade/teach/pitch 目标、数学量级、figure-first 风格、must-include/must-avoid、叙事脊柱 5–7 步、每节 H/M/L 优先级与页数——并且成为下游 critic 的唯一评分依据。leo 的合同有受众/场景/口径，但没有"数学量级、图表风格取向、优先级页数分配"这三个学术决定性字段，更没有把它用作后续审查的 rubric 锚点。引入它等于给 CONFIRM-GATE 装上学术大脑：确认的东西从此可以被逐条核对（narrative-critic 的 `commitment_refs` 机制），而不是确认完就散在聊天记录里。

## 反面教训（明确不该学的做法）

1. **不要学 aeslides 用 RL/VLM 打分当美学唯一裁判的替代品，也不要反向迷信 VLM**——aeslides 的价值在"可验证指标"；但它的完整系统（渲染基建、系统提示词、工具实现）因专有约束不开源，仓库只放片段。学算法思想（引用论文），不搬代码（无 LICENSE）。
2. **不要学 Paper2Any 的"agent 数量军备竞赛"**——47 个 agent、20+ 顶层目录、商业版不开源的混合形态，维护成本与认知成本极高；leo 的 slide-worker/page-worker 双 worker + 母版治理是更收敛的设计。搬它的单点资产（paperbanana.md），不搬架构。
3. **不要学 huashu-design 追求"打字回车出一切"（PPT+动画+视频+原型+音频）**——战线过长导致 references 泛而不深；学术赛道的价值在证据与叙事纵深，不在媒介广度。
4. **不要学 mckinsey-pptx 的"模板即终点"思维**——40 个确定性模板快而稳，但对学术内容（公式推导、跨页大图、消融表）表达力不足；它值得学的是 CATALOG 的接口格式，不是产品形态。
5. **警惕 yixueAIganhuo-PPT 的许可陷阱**——非商业 License 的风格 JSON 质量很高，最容易顺手复制；在 MIT 的 leo 仓库里这样做是侵权。只借鉴 schema 结构（七段式），文案必须重写。
6. **不要学 Awesome-PPT-Design-Skills 无 LICENSE 发布**——六个完整技能没有许可证文件，法律上默认保留所有权利；这本身是治理反面教材（leo 自己的 LICENSE 纪律是对的）。

## 附：License 一览

| 项目 | License |
|---|---|
| Paper2Slides | MIT |
| Paper2Any | Apache 2.0 |
| academic-ppt-master | MIT |
| ArcDeck | MIT |
| GenSlide | MIT |
| aeslides | 无 LICENSE 文件（仅论文 arXiv:2604.22840） |
| beamer-academic | MIT |
| scholar-ppt-cn | MIT |
| note-slides | MIT |
| slides_maker | MIT |
| mckinsey-pptx | MIT |
| huashu-design | MIT |
| humanize-ppt | MIT |
| Awesome-PPT-Design-Skills | 无 LICENSE 文件 |
| yixueAIganhuo-PPT | 非商业（Non-Commercial Use License） |
| ppt-master | MIT |
