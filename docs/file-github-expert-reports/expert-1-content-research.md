# 专家1:Deep Research / 学术写作赛道 → leo-ppt-generator 可借鉴能力清单

调研范围:8 组报告中本赛道约 20 个项目;机制级深读 4 个(gpt-researcher、storm、WriteHERE、dexter)+ 1 个补充(codex-claude-academic-skills)。视角:PPT 内容研究与证据流。

## 一、赛道优势总结(分模块)

### 1. Agent 编排模式
- **gpt-researcher(29.2k)**:Chief Editor 多角色编排 `browser→planner→human(plan 审)→researcher(逐节并行)→writer→fact_checker→visualizer→publisher`,三个有界修订环(plan 审、draft 审、fact-check 审)均有 `max_*_revisions` 上限,超限优雅放行而非死循环(`multi_agents/agents/orchestrator.py` L92-135、`editor.py` L131-149)。核心优势:人审与机审各占其位、修订次数可配置、并发按 section 粒度。
- **dexter(27.6k)**:`spawn_subagent` 单轮并行派发独立子任务、SOUL.md 身份层+RULES.md 用户研究规则层、append-only JSONL scratchpad 为唯一事实源,含工具调用计数与**查询相似度≥0.7 的重试环检测**(`src/agent/prompts.py` L246-251、`src/agent/scratchpad.ts` L50-53)。
- **优势本质**:内容生产的质量不靠单次生成,靠"规划→执行→机审→有界返工"的环结构。

### 2. 引用与证据管理
- **gpt-researcher**:`deep_research.py` 的 learnings 以**原子级携带引用**(每条 learning 绑 sourceUrl,正则双路径解析 `Learning: [url]`,L41-44、L143-205);References 段排序保证确定性(注释明言 set 迭代序曾导致不可复现);embedding 相似度过滤压缩上下文(`context/compression.py`)。
- **storm**:`DialogueTurn` 保留 question/queries/snippets/answer 全链;`ArticleTextProcessing.remove_uncompleted_sentences_with_citations` 专门裁掉带引用的残句防幻觉;成文时引用编号全树重排(`storm_dataclass.py reorder_reference_index`)。
- **dexter**:scratchpad JSONL 逐工具调用落盘,"每次查询可完整回放调试";大结果持久化磁盘只注入预览。
- **优势本质**:证据在**采集瞬间**就与陈述绑定,而非成稿后补挂;全过程可回放。

### 3. 结构规划
- **storm**:persona 生成器先检索**同类话题已有文章的 TOC**作为结构先例,再派生多视角编辑 persona(`persona_generator.py` L77-97);大纲两段式——先参数知识 draft outline,再用研究对话精炼,两版都可产出(`outline_generation.py` L108-125)。Co-STORM 的 KnowledgeBase 树有**证据密度驱动的节点裂变**:节点内信息数超 `node_expansion_trigger_count` 才展开子节(`information_insertion_module.py` L53-、L334-),信息插入走 insert/step/create 三选一的逐层导航。
- **WriteHERE(EMNLP 2025 Oral)**:异构任务图(PLAN_NODE/EXECUTE_NODE),每个节点携带 goal/inclusion/**exclusion/verify_standard** 四元任务约s束,生命周期含 **planning_post_reflect 与 execute_post_reflect 双反射**(`graph.py` L87-105、L551-595);BFS 拓扑排序决定执行波次;每步落盘 nodes.pkl+article.txt 可断点续跑(`engine.py` L49-72)。
- **优势本质**:结构由证据密度与任务约束共同塑形,而非一次性模板展开。

### 4. 迭代验证
- gpt-researcher fact_checker:对照 research_data 审 draft,发现错误返 writer,有界 N 轮;dzhng/deep-research 与 gpt-researcher deep_research 共用 breadth/depth 递归+learnings 反哺下一轮 query 生成;node-DeepResearch 的 gap 问题循环(报告组1)。WebThinker 的 Think-Search-and-Draft 让报告"边查边写、随新证据动态修订"(组7)。
- **优势本质**:迭代上限显式化(有界),learnings 是跨轮可累积的中间资产。

### 5. 学术工件(垂直资产)
- **codex-claude-academic-skills(3.3k)**:四级信息溯源标注 `原文/用户确认/推断/建议`;模糊词硬纪律("显著/先进/有效/鲁棒"必须替换为测量条件或删除);citation-management 子技能做 DOI→BibTeX 元数据**交叉校验**(CrossRef/PubMed/arXiv 多源);scientific-visualization 提供期刊级制图预设(Nature/Science/Cell 尺寸、色盲安全调色板、误差棒、多面板网格);thesis-defense-pptx 带模板克隆与**溢出巡检脚本**(`references/thesis-defense-pptx/scripts/`)。
- **academic-paper-skills**:大纲门控——7 维 35 分模拟评审,≥28 分才放行写作;每个 research gap 强制 3-5 篇引用支撑(组6)。
- **Research-Paper-Writing-Skills**:claim-evidence 对齐检查与审稿人视角投稿前自审(组0)。

## 二、重点项目深读纪要

### gpt-researcher(机制密度最高的编排范本)
单 agent 核 `agent.py`(conduct_research→write_report)与多 agent Chief Editor 双形态并存。关键机制:①初始研究产出 summary→planner 按其生成 section headers(JSON,`max_sections` 约束)→**人工 plan 审(可选)→逐 section 并行子图(researcher→reviewer→reviser 有界环)**→writer 汇编 intro/sections/conclusion→fact_checker 对照数据再审→publisher 落盘;②deep_research 技能:query+researchGoal 成对生成、并发信号量、learnings/citations/visited_urls 跨层递归传递、上下文 25k 词裁剪保尾部(近因优先);③全部中间产物(research_data/fact_check_notes/human_feedback)都在 State 中流转,可审计。对 leo 的启示:**deck 的"节"就是天然并行单元;每类返工必须有界;内容审与视觉审应分层**。

### storm(结构先例 + 证据生长)
两阶段管线的价值在大纲侧:persona 从**同类文章目录**归纳(不是凭空造视角——视角有结构先例支撑);ConvSimulator 每轮 WikiWriter 提问→TopicExpert 生成 query→检索→只用 top1 snippet(刻意压制上下文膨胀)→带引用作答;对话历史裁剪只保留近 4 轮完整问答。Co-STORM 的 InsertInformation 候选选择:embedding 先筛候选位置,LLM 三选一(insert/step/create),不合理则"无合理候选"——**结构与证据互相塑形的完整实现**。对 leo 的启示:**大纲可以从"同类 deck 的结构先例"获得先验;页/节的裂变应由证据量驱动**。

### WriteHERE(异构递归规划)
每个任务节点自带 exclusion(不做什么)与 verify_standard(怎么算完成)是**任务合同的最小完备形态**;规划节点与执行节点异构、可无限嵌套;每节点两段反射(规划后/执行后)分别修计划与修产出。工程上 nodes.json 每步重写、可人工介入后 load 续跑。对 leo 的启示:**大 deck 的母版制作可按节建 plan 节点(要点配额/证据预算)→逐页执行→节末验收(verify_standard 化的判据)**;leo 的确认门已是人审,缺的是节级机审。

### dexter(长会话工程纪律)
microcompact(轻量截断)与 LLM 摘要 compaction 双层上下文治理;大工具结果落盘换预览;overflow 自动降级重试;JSONL scratchpad 支撑回放与防循环。对 leo 的启示:**母版生成若引入研究工具,必须同步落"逐页取材台账"(JSONL),否则三级标注的"引用"级无法回溯到采集现场**。

### codex-claude-academic-skills(学术 PPT 直接同业)
三技能链(数据分析出图→写章节→答辩 PPT)与 leo 学术模式同构;其差异化资产:四级溯源、模糊词禁换、DOI 校验、期刊制图预设、PPTX 溢出巡检与模板克隆脚本。对 leo 学术垂直是**低成本高契合的补强来源**。

## 三、借鉴点清单

| # | 来源项目+机制 | leo 现状 | 建议 | 价值论证 | 优先级 | 验证方式 |
|---|---|---|---|---|---|---|
| 1 | gpt-researcher:初始研究→learnings(原子引用)→冻结为材料;dzhng 智能追问 | 无:材料缺失即 `input_material_missing` blocked,用户必须自备材料(SKILL.md 三级标注节) | 新增可选前置"研究代采"分支:用户无材料且授权联网时,先出**研究问题清单确认**(寄生合同确认门)→采集→learnings+逐条引用落盘 `<project-root>/content/research-pack.md`→按 generate 正常流程消化;不新增 Route | leo 当前是"转换器",天花板=用户材料质量;此分支把 leo 变成内容引擎,是"世界级"最大单点杠杆,且 learnings 原子引用天然对接三级标注"引用"级 | P0 | 新 eval case:无材料+授权→先出问题清单而非 blocked;含 research-pack 落盘路径断言 |
| 2 | gpt-researcher:fact_checker 有界修订环(对照 research_data 审 draft) | 部分:三级标注纪律+visual-qa 多轮审查,但**内容层无独立核查 pass**(known-issues 无此债) | 高保障档位增"内容核查官":母版冻结后、派发前,逐页断言/数字与材料(或 research-pack)回读比对,差异清单有界 2 轮返母版;复用再检要求(目标判据+波及面) | 视觉 QA 已达多轮协议水准,内容层是唯一没有独立机审的环节;学术 dense-defense 档尤其需要 | P1 | 新 case:材料含错误数字→核查官拦截并给出差异清单;单测核查比对脚本 |
| 3 | storm:persona 从同类文章 TOC 归纳视角;Co-STORM 专家追问 | 无:答辩档只有五拍骨架,无"评委会从哪些视角追问"的机制 | academic-vertical 增"评审视角矩阵"步骤:按材料归纳 3-5 个评审 persona 及各自最可能追问,映射到 Q&A/backup 页配额;不改确认序列 | 答辩 deck 的真实痛点是预演追问;结构先例驱动的 persona 比凭空生成的更可信;直接强化 leo 最独特的学术垂直 | P1 | 新 case:学术材料→回复含视角矩阵与 backup 页建议;判官断言 persona 数量与映射 |
| 4 | Co-STORM:节点证据密度超阈值裂变子节(ExpandNode) | 部分:RST 8 关系管"哪些必须同页/拆页",但页数分配只有 section_priority 口径,无密度反馈 | 大纲工件每节标 `evidence_count`(learnings/材料段计数),超阈值(如 >6)提示拆页或升台账版式、不足(如 <2)提示并入邻节——advisory 提示寄生大纲确认 | "证据预算"让页数分配从拍脑袋变成可解释决策;与禅档位(容量)+RST(结构)形成三判据闭环 | P1 | 单测密度计数脚本;case:材料某节证据过密→回复含拆页建议一句 |
| 5 | gpt-researcher deep_research:learning 原子携带 sourceUrl;storm DialogueTurn 全链留存 | 部分:三级标注是**页级**数字/断言纪律,sources-manifest 是**视觉级**(sources-manifest-schema.md) | 母版要点行支持可选 `source_ref` 字段(材料段落锚点或 research-pack learning id),check_master_contract 校验"引用"级要点必须可回指;估算/示意级豁免 | "引用"级目前只到"有出处"粒度,不到可点验粒度;原子溯源是引用管理赛道的共识做法,补齐后 leo 证据链全程机器可验 | P1 | check_master_contract 新校验+单测;case:引用级要点无 source_ref 被拦截 |
| 6 | codex-academic:四级溯源(原文/用户确认/推断/建议) | 部分:三级标注(引用/估算/示意)+unknown,"用户口头确认的数据"无专属档位(只能落引用或unknown) | 三级标注扩第四级"用户确认"(用户在合同/澄清轮口头给出的数据,标注不引材料但可溯源到会话轮),词表与 check 脚本同步 | 实际工作流中大量关键数字来自用户口述,现在只能错误地挂"引用"或降级 unknown,标注语义失真 | P1 | 词表与校验脚本更新+单测;case:用户口述数字→标"用户确认"而非"引用" |
| 7 | codex-academic:citation-management DOI→BibTeX 多源交叉校验 | 部分:学术模式有文献版式(P29)与图证据行,无文献元数据校验 | 新增 `scripts/check_references.py`:文献页逐条 DOI/标题元数据校验(可离线查材料内一致性,联网时交叉 CrossRef/arXiv)+GB/T 7714 格式化;strict 档并入交付披露 | 答辩场景文献错误是硬伤;与来源清单 strict 校验同构,成本低 | P2 | 脚本单测+case:文献页 DOI 不一致被拦截 |
| 8 | codex-academic/scientific-visualization:期刊制图预设(色盲安全/误差棒/多面板/Nature 尺寸) | 部分:diagram_render.py 确定性自绘+图表语法三份(瀑布桥/2×2/统计图标注契约) | academic 档 figure_orientation=figure-first 时注入"学术图表规范"参考:色盲安全调色板封闭枚举、误差表示(误差棒/置信带)必填判据、多面板网格对齐;落入 styles 图表分节轴 | 学术评委对图表规范敏感度极高;leo 已有统计图门槛,补齐的是"学术审美公约数"而非新渲染器 | P2 | 风格 brief lint 扩学术图表判据;case:figure-first 学术 deck 回复含色盲安全说明 |
| 9 | codex-academic:模糊词禁换(显著/先进/有效/鲁棒→测量条件) | 部分:断言式标题与"数字而非形容词"(Numbers-not-adjectives)管标题与数字,要点层模糊词无纪律 | deck-master 要点 lint 增模糊词检测:学术场景要点含模糊强度词且无量化条件→WARN(不阻断),提示替换为测量条件 | 与既有 Numbers-not-adjectives 同族,把它从标题/数字延伸到要点谓语,学术可信度直接受益 | P2 | lint 脚本+单测(含误报豁免:引号内、示意级) |
| 10 | WriteHERE:任务节点四元约束(goal/inclusion/exclusion/verify_standard)+节末双反射 | 部分:母版四段结构与再检要求已含"目标判据+波及面",但**deck 级与节级无显式验收判据工件** | 大纲工件每节增可选 `verify_standard` 一行(该节讲完听众应能回答的问题);高保障档母版完成后逐节自检该判据,不通过走再检流程 | 把"这页为什么存在"从隐式变显式;答辩档的"每节一个可检验命题"正是评委心智模型;增量小(一行字段+一次自检) | P2 | 大纲 schema 字段+case:高保障档回复含逐节判据自检结论 |
| 11 | storm:大纲两段式(先验 draft outline→证据精炼,两版留档可 diff) | 无:大纲一步成稿(outline-v<N>.md 版本化只发生在用户打回后) | 材料充足时大纲轮可先落"结构先验"(同类 deck 常见骨架+RST 预标注)再落"证据精炼版",确认摘要附两版差异一句话;不增确认回合 | 用户确认大纲时最缺的就是"改了什么、为什么";先验→精炼的差异本身就是结构决策的可解释性;与 #4 密度反馈同工件 | P2 | case:大纲确认摘要含结构依据句(先验 vs 证据) |
| 12 | gpt-researcher:embedding 相似度过滤压缩材料上下文 | 无显式机制:长材料(整书/超长报告)如何裁剪进母版制作未成文 | 材料预处理 advisory:超长材料按"与 deck 主题+节标题相关性"分节过滤并落 `content/material-digest.md`(保留原文锚点),母版制作只读 digest+按需回原文 | 长材料是 generate 路线真实场景;没有 digest,worker 上下文与成本都会失控;learnings 模式证明相关性过滤是成熟做法 | P2 | 单测 digest 生成;case:超长材料→回复含 digest 落盘与锚点说明 |

实施注记(来自 known-issues 最新债务):M1.1 的教训是"新能力入口可见性缺口"导致 19 个新 case 团灭——上述任何新增能力必须同步在 SKILL.md 入口表/不变边界留一句锚点行,评测注册与判官词表随实现同批走。

## 四、明确排除项及理由

- **storm 多视角方法论(efw 侧)**:已于 2026-08-30 批吸收进 `evidence-first-writing/references/source-analysis.md`(融合表 #9);"STORM pip 桥"亦在其二阶段路线图登记,不重复推荐。本清单只推荐 leo 侧未覆盖的视角矩阵(#3)与证据生长(#4)。
- **geekai 分镜四规则、marketingskills 销售 deck 框架**:已吸收(fusion 表 #12/#15)。
- **模型本体类**(MiroThinker、通义 DeepResearch、WebThinker):需自建 vLLM/专有权重,leo 是技能不是推理服务,形态不匹配;其 IterResearch/交互式扩展思想已由 learnings 递归(#1)覆盖。
- **AI-Scientist / FAROS 的实验执行闭环**:产出新实验数据,PPT 场景无实验环节;FAROS 的 PlanPackage 思想已由 #10 verify_standard 吸收。
- **SurveyX**:开源版仅支持离线喂 .md、联网检索锁商用站,机制被 gpt-researcher 覆盖;LaTeX 编译不在 leo 交付范围(academic-vertical 边界明示 Beamer/LaTeX 不做)。
- **去 AI 味赛道**(humanizer/qu-ai-wei/no-ai-slop 等):efw 工作面,与 PPT 证据流无关。
- **发布分发/热点数据源**(wenyan 系、60s/newsnow/last30days、Agent-Reach):属其他专家赛道;last30days 类舆情源对 deck 主题选择有价值但属选题层,非本技能边界。
- **node-DeepResearch/OpenDeepResearcher/dzhng 极简流派**:机制(递归 learnings、gap 追问、并发抓取)已由深读 gpt-researcher 的对应实现覆盖,无增量。
- **dexter 的 WhatsApp 网关/cron/memory 个性化**:产品形态差异,与 deck 生成无关;保留的只有 scratchpad 台账思想(已并入 #5/#12 论证)。
- **WebThinker 的 Think-Search-and-Draft**:需模型内生工具调用能力,宿主依赖强;"边查边修订"精神由 #2 内容核查环替代实现。
