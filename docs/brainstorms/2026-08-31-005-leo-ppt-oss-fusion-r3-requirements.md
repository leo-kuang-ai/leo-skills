---
spec_id: 2026-08-31-005-leo-ppt-oss-fusion-r3
artifact_kind: prd-requirements
target_surface: generic
status: ready-for-planning
evidence_grade: mixed
source_authority: mixed
readiness_authority: engineering-owned
created: 2026-08-31
source_inputs:
  - docs/file-github-expert-reports/expert-1-content-research.md
  - docs/file-github-expert-reports/expert-2-copy-quality.md
  - docs/file-github-expert-reports/expert-3-visual-style.md
  - docs/file-github-expert-reports/expert-4-consistency.md
  - docs/file-github-expert-reports/expert-5-material-delivery.md
  - docs/file-github-expert-reports/expert-6-engineering.md
readiness_verified_by: check-prd-artifact.js
readiness_verified_at: 2026-08-31T08:55:59.631Z
readiness_checker_schema: spec-prd-artifact-check.v1
readiness_finding_count: 1
readiness_blocking_count: 0
readiness_prd_hash: sha256:d46fc98ff92610918779f295438005e13def84a549e764331f929481607eca58
readiness_inputs_hash: sha256:c0e59d1a5f467ce13cba91923dced5cf42fbedf16fd5a1a2f48cec9b6d0dd0f7
---

# leo-ppt-generator 开源借鉴优化(R3 融合轮)增量需求文档

> 调研底座:`/Users/kuang/knowledge/file-github/`(仓库外,152 个 AI 写作/内容生态开源项目,用户已线下确认全部上游授权,许可证不构成集成阻断)
> 与 `docs/plans/2026-08-30-file-github-integration.md`(R2,19 项目)和 `docs/plans/2026-08-30-001` 能力融合 M0/M1(PPT 类项目)衔接,本轮为第三轮融合(R3)。

## PRD 元数据

| 项 | 内容 |
| --- | --- |
| 需求名称 | leo-ppt-generator 开源借鉴优化(R3:152 个写作/内容生态项目全量借鉴) |
| 需求编号 / spec_id | 2026-08-31-005-leo-ppt-oss-fusion-r3 |
| 业务域 | leo-ppt-generator 技能包(内容引擎/内容质量/文案/视觉/一致性/交付/治理七域) |
| 目标 surface | CLI/DevTool(Agent skill 包;单 SKILL.md + references/scripts 分层) |
| 目标地区 / 市场 / tenant | 不涉及 |
| 目标用户 / 客户类型 | 在 Agent 宿主中使用 leo-ppt-generator 的演示文稿制作者(政务/金融/学术/营销/教学等垂直) |
| 是否触及付费、资金或交易 | 否 |
| 是否触及个人信息或敏感数据 | 部分触及:R-53 敏感文本扫描服务于既有 data_classification 分级门;不新增数据收集 |
| 是否需要外部规则或专业意见 | 否;上游许可已由用户线下确认(user-stated) |
| 相关文档 | 六份专家报告(source_inputs);`/Users/kuang/knowledge/file-github/分析报告/组0-7.md` 与 `调研报告.md`(仓库外);`docs/plans/2026-08-31-001/002/003`(P0/P1/P2 已落地批);`leo-ppt-generator/evals/known-issues.md` |

## Summary

以 6 位"PPT 产品专家 + 技术架构师"对 152 个开源写作/内容生态项目的机制级调研为基础,把其中约 60 条经源码验证的借鉴点转化为 leo-ppt-generator 的产品需求:把技能从"材料→PPTX 转换器"升级为"可选代采材料的内容引擎",为母版真值补上"承诺账本 + 影响面推导"两块内容层确定性核对,建立 deck 文案/讲稿的语言质量纪律与图上文字合成协议,打通确定性导出族与风格缩略图可发现性,并用统计判据收口评测三大在案债务——全部增量不削弱任何既有治理门禁(人在回路、收据、分级、凭据边界)。

## Problem Frame

- **不做风险**:leo 的交付纪律(收据/分级/三级标注)领先同侪,但对比 152 项目所代表的生态存在六类结构缺口——①输入端只认用户自备材料,材料缺失即 blocked,天花板=用户材料质量;②内容层(母版要点/断言)是全链路唯一没有独立机审的环节;③文案/讲稿质量只有结构性约束(条数/字数),无语言质量纪律,讲稿是 AI 腔最易暴露的交付面;④图像 lane 全出血页面的图上文字无排版协议,是高废片页型;⑤长 deck(50-200 页)的术语/承诺漂移检查是报告级,多轮改稿影响面靠人工推导;⑥评测"多轮采样后定论"是定性纪律,M1 17 例判官校准债收口缺统计工具。
- **业务价值**:世界级 skill 的判定标准不只是"生成得出",而是证据链全程机器可验、语言质量可感知、状态可恢复、评测可统计;本轮补齐的正是这些"交付级"维度。
- **时机**:M1 渲染 lane(Playwright 确定性渲染、零 token)已合入,P1 期搁置 handout 导出与风格缩略图的两条"渲染依赖"理由已消除(external-research:专家5/专家3 一致确认)。

## Current System Snapshot

| 现状项 | 当前行为 | 证据 tag |
| --- | --- | --- |
| 四 Route + 全门禁体系 | generate/direct-editable/upgrade-full/upgrade-selected;Gate 0 信任门、advise/execute、CONFIRM-GATE、DELIVERY-GATE、PARTIAL-GATE、控制面五字段块 | confirmed-source: leo-ppt-generator/SKILL.md |
| 母版真值与三级标注 | deck-master 四段结构;引用/估算/示意三级 + unknown 求证;check_master_contract 校验 v2 语法 | confirmed-source: references/deck-master.md、scripts/check_master_contract.py |
| M1 能力面 | 渲染 lane(render-contract、lint_render_templates、双跑像素 diff)、版式工程(layout-dispatch、suggest_layout、check_layout_reuse)、来源保真(sources-manifest strict)、社交卡片规格(social-card-specs.md)、测量质检(validate_visual_measure.py) | confirmed-source: references/ 清单、known-issues M1 批条目 |
| P0/P1/P2 产品批 | 表面合同 block-early、确认门回合合并、成本预估;交付档案、学术垂直入口、讲稿导出、风格画廊(目录级);leo-ppt-bench(8 维)、EN README | confirmed-source: docs/plans/2026-08-31-001/002/003(status: completed) |
| 输入端边界 | 材料缺失→input_material_missing blocked;素材须过 validate_assets;编造链接禁止 | confirmed-source: SKILL.md 三级标注节/红灯清单 |
| 评测面 | 83 case + judge 脚本(否定感知);五条治理 lint;known-issues 登记三大债:M1 17 例判官校准、金样 HEX 2 例、判官词表债;M1.1 教训=新能力"入口可见性缺口"致 19 case 团灭 | confirmed-source: evals/eval.yaml、evals/known-issues.md(iteration-90/94/96) |
| 长度一致性 | 200+ 页 deck 的一致性检查为报告级(术语"同实体异写即报告"非阻断);断点续跑在 R2 列为二阶段非目标未做 | confirmed-source: references/image-deck-workflow.md 步骤 7、file-github-integration.md §7 |

## Change Delta

| 变化类型 | 内容 | 涉及现有能力 | 用户/数据/运营影响 | 证据 tag |
| --- | --- | --- | --- | --- |
| keep(保持不动) | 全部治理门禁(Gate 0/CONFIRM-GATE/DELIVERY-GATE/PARTIAL-GATE/收据/分级/凭据边界)不削弱;四 Route 与控制面响应合同不变 | 全部 | 无 | confirmed-source: SKILL.md |
| extend | 输入端:可选"研究代采"分支、音视频材料路线、用户素材库;母版:要点级溯源、四级标注、证据密度、承诺账本;文案:确定性检测+讲稿纪律;视觉:负面提示词、token sidecar、渲染模板扩面;一致性:CAS 写锁、run ledger、影响面推导;交付:导出子命令族;治理:统计评测、rubric 分数门禁 | generate 路线输入节、deck-master 合同、image-deck-workflow 素材/交付节、visual-qa、execution-contract | 确认序列回合数不增加(新能力寄生既有确认门或属交付动作) | external-research(六份专家报告) |
| add(新增) | LEO_PPT_HOME 下 library/ 素材库、decks-styles/ 蒸馏档案、export 子命令族、eval_stats 统计工具、敏感文本扫描、图上文字合成协议 reference | 与 profiles/、brands/ 同构的第三/四用户档案通道 | 新增本地数据目录(仅存素材指纹与元数据,不存业务正文) | external-research |
| replace | 大于 30 页 deck 的术语/编号/固定件漂移从报告级升为非 0 退出阻断 | image-deck-workflow 组装复验"同实体异写即报告" | 长 deck 交付前多一道硬门;误报需四分类输出缓解 | external-research: 专家4 借鉴点 7 |
| remove | 无 | - | - | - |

## Requirements

编号规则:R-01 至 R-60(连续编号;域小节仅为组织视图)。优先级 P0(首批,世界级门槛)/P1(次批)/P2(择优后置)。来源列格式:专家N-编号(详见 source_inputs 专家报告)。

### 域 A:内容引擎(输入端,R-01~R-05)

| 编号 | 触发条件 | 角色 | 系统行为(EARS:应…) | 用户可见结果 | 来源 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | 用户无自备材料、宿主具备联网检索且用户明示授权代采 | 系统 | 先产出研究问题清单并经用户确认(寄生合同确认门),再执行采集,把每条 learning 与来源 URL 绑定落盘为材料包(content/research-pack.md,逐条可回指),然后按 generate 既有流程消化 | 从"被 blocked 要材料"变为"确认问题清单后获得带引用的材料包";未授权/无能力时维持既有 input_material_missing 语义(降级先例:Provider 三态/worker 缺失固定块) | 专家1-#1(gpt-researcher learnings 原子引用) | P0 |
| R-02 | 材料为超长文档(整书/超长报告) | 系统 | 按与 deck 主题及节标题的相关性产出材料摘要(content/material-digest.md),保留原文锚点,母版制作只读摘要并按需回原文 | 长材料的制作成本与上下文占用受控;引用级事实仍可回溯原文 | 专家1-#12 | P2 |
| R-03 | 用户提供音视频材料 | 系统 | 经登记的转写通道(宿主能力或用户自备转写稿)接受带时间戳的转写文本为合法材料,转写段落带时间戳前缀;引用级事实可回溯到录音时间点;数据分级询问照常 | "会议录音→汇报 PPT"可进入 generate 路线;无转写通道时如实说明并按材料缺失处理 | 专家5-E5-04(AI-Media2Doc ASR 时间戳协议) | P1 |
| R-04 | 用户把图片/图表/数据表/引用存入素材库(LEO_PPT_HOME/library/) | 系统 | 以 sha256 + 来源元数据 + 标签登记素材;母版视觉行引用库内素材时自动携带出处,sources-manifest 从库登记派生 | logo/产品照/历史图表跨 run 复用且出处自动完备;库外编造链接仍被 strict 校验拒绝 | 专家5-E5-01(Beav 目录式素材库) | P1 |
| R-05 | 用户需要市场/行业数据且经登记数据通道获取 | 系统 | 只经 references/data-sources.md 登记的公共只读通道获取,来源 URL 与抓取时间戳写入 manifest;抓取不到如实标 unknown 求证,不做研究综合 | 行业汇报的数据来源有确定答案与回溯格式;不做采集执行(爬虫/登录态) | 专家5-E5-06 | P2 |

### 域 B:内容质量(论证与证据,R-06~R-14)

| 编号 | 触发条件 | 角色 | 系统行为(EARS:应…) | 用户可见结果 | 来源 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| R-06 | 高保障档位母版冻结后、逐页派发前 | 系统 | 执行内容核查官:逐页断言/数字与材料(或 research-pack)回读比对,差异清单有界 2 轮返母版(复用再检要求:目标判据+波及面) | 内容层首次获得独立机审;材料含错误数字时被拦截并给出差异清单 | 专家1-#2(gpt-researcher fact_checker 有界环) | P1 |
| R-07 | 大纲制作时 | 系统 | 为大纲每节标注证据计数(evidence_count),过密(默认大于 6)提示拆页或升台账版式、过疏(默认小于 2)提示并入邻节(advisory,寄生大纲确认) | 页数分配从经验判断变为可解释决策;与禅档位(容量)+RST(结构)形成三判据 | 专家1-#4(Co-STORM 证据密度裂变) | P1 |
| R-08 | 母版要点行声明"引用"级 | 系统 | 要求该要点携带 source_ref(材料段落锚点或 research-pack learning id)并可回指;估算/示意级豁免(check_master_contract 校验) | 溯源从页级下沉到要点级,证据链全程机器可验 | 专家1-#5 | P1 |
| R-09 | 用户在合同/澄清轮口头给出数据 | 系统 | 将该数据标注为第四级"用户确认"(不引材料、可溯源到会话轮),词表与校验脚本同步扩展 | 消除"用户口述数据只能错误挂引用或降级 unknown"的语义失真 | 专家1-#6(codex-academic 四级溯源) | P1 |
| R-10 | 学术场景选择答辩档 | 系统 | 按材料归纳 3-5 个评审 persona 及各自最可能的追问,映射到 Q&A/backup 页配额建议 | 答辩 deck 获得预演追问的结构化准备 | 专家1-#3(storm persona 从同类文章 TOC 归纳) | P1 |
| R-11 | 高保障档位大纲制作时 | 系统 | 为每节附可选 verify_standard(该节讲完听众应能回答的问题),母版完成后逐节自检 | "这节为什么存在"从隐式变显式 | 专家1-#10(WriteHERE 任务四元约束) | P2 |
| R-12 | 材料充足且大纲制作时 | 系统 | 可先落"结构先验"(同类 deck 常见骨架)再落"证据精炼版",确认摘要附两版差异一句 | 大纲结构决策可解释 | 专家1-#11(storm 大纲两段式) | P2 |
| R-13 | 学术 deck 含文献页 | 系统 | 做文献元数据一致性校验(DOI/标题在材料内交叉核对,联网时对 CrossRef/arXiv)并支持 GB/T 7714 格式化;strict 档并入交付披露 | 文献错误在交付前被拦截 | 专家1-#7 | P2 |
| R-14 | 学术场景 figure_orientation=figure-first | 系统 | 注入学术图表规范(色盲安全调色板、误差表示必填判据、多面板网格对齐)入风格分节轴 | 学术审美公约数补齐 | 专家1-#8 | P2 |

### 域 C:文案语言质量(R-15~R-23)

| 编号 | 触发条件 | 角色 | 系统行为(EARS:应…) | 用户可见结果 | 来源 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| R-15 | 母版落盘后 | 系统 | 运行 deck 文案确定性检测(新增检查脚本):对标题连读稿+要点跑可正则化检测(翻案腔及变体、黑话词表、名词化信号、三连同构开头、连词密度、抒情词),输出采用密度阈值+豁免上限框架(deck 级翻案腔至多 1 处且须为真实论证骨架;不超过 3 条要点的短文案孤立命中不计;行业既定词豁免),WARN 级挂母版合同检查输出;含中英空格/全角标点/数字单位格式 WARN 子集 | 去模板味从 12 条 agent 自检清单升级为"脚本可查+密度防误杀";格式统一直接提高 OCR 回读命中率 | 专家2-#1/#2/#7(humanizer 误报保护 × shuorenhua 密度框架 × autocorrect 规则思想) | P0 |
| R-16 | speaker_script 写入母版时 | 系统 | 执行讲稿口语化纪律(短句、第二人称直说、禁"接下来我将为大家介绍"式套话、数字与结论与母版一致不得口头加码);讲稿导出时可带 WARN 扫描 | 逐字被念出来的交付面不再有 AI 腔 | 专家2-#5(shuorenhua Tier1 套话 × xiaoma 人称纪律) | P0 |
| R-17 | 母版要点措辞检查时 | 系统 | 执行要点措辞纪律:动词句优先;禁自我解释连接词("这说明/这意味着/由此可见"不入要点);数字裸用不加"高达/多达";金句/氛围页禁通知腔 | 要点措辞有可执行判据,来源为 260 条真实爆款语料反向统计 | 专家2-#3(xiaoma diction.md) | P1 |
| R-18 | 连读稿复核时 | 系统 | 做标题兑现对账:结论句标题中的每个数字性断言在本页要点或数字登记表有对应行(脚本可查),无对应即回母版 | 防"标题说得满、要点撑不起" | 专家2-#4(bigpeng 兑现纪律) | P1 |
| R-19 | TF-1 压文本预算减法重生成时 | 系统 | 断言 verified 标记为 yes 的数字登记表行不得在母版修订 diff 中静默消失;数字性证据删移须显式降级(示意)或经确认 | 唯一"改写"场景(TF-1)获得信息点留存机器断言 | 专家2-#6(shuorenhua 双向回读+留存率) | P1 |
| R-20 | 交付档案含用户文风样本字段 | 系统 | 使母版措辞向样本靠拢,文案检测对样本高频词豁免 | 文案检查闭环"用户声音"而非仅通用规范 | 专家2-#8(humanizer voice sample 优先) | P2 |
| R-21 | 连读稿复核时 | 系统 | 检查论证媒介多样性:连续 3 个及以上内容页同为纯数据或纯定性论证时提示换媒介(类比/案例/反例) | 防"数据页连排/口号页连排"的单调 | 专家2-#9(Viral 维度 8) | P2 |
| R-22 | 金句页/收束页制作时 | 系统 | 执行金句判据:脱离本页上下文可独立成立、含具体洞见非口号、全 deck 反向克制型至多 1 处 | 金句页从数量约束升级为质量约束 | 专家2-#10 | P2 |
| R-23 | 学术场景要点检查时 | 系统 | 对要点模糊强度词("显著/先进/有效/鲁棒")且无量化条件者 WARN,提示替换为测量条件(引号内与示意级豁免) | Numbers-not-adjectives 从标题延伸到要点谓语 | 专家1-#9 | P2 |

### 域 D:视觉系统(R-24~R-33)

| 编号 | 触发条件 | 角色 | 系统行为(EARS:应…) | 用户可见结果 | 来源 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| R-24 | generate 路线产出全出血封面/大图井页面 | 系统 | 执行图上文字合成协议:安静区测试(画布不低于 30% 低细节带)→无蒙版优先→失败才允许局部图像色调蒙版(限定标题区、取图内色调、峰值透明度约束)→缩略图终检;母版视觉行支持主体映射(标注人脸/主体位置,文字只进安全区) | 图像 lane 高废片页型获得前置决策协议而非事后补丁 | 专家3-V1(guizang image-overlay 四步阶梯) | P0 |
| R-25 | 风格 brief 定义时 | 系统 | 支持可选 negative_prompt 字段(反模式铁律),并入 style render 注入链;治理 lint 增字段校验(存量白名单) | 扩散模型废片率下降;同类 skill 标配能力 | 专家3-V2(xhs-visual-director 负面提示词) | P1 |
| R-26 | 生成风格画廊时 | 系统 | 用确定性渲染(M1 渲染 lane)为 11 套内置风格各产出代表版式缩略图(固定示例数据、双跑 sha256 或像素一致),嵌入风格画廊;126 参考风格维持目录级 | 选风格从"读文字"变为"看图";P1 搁置理由(图像 API 成本/确定性)已被 M1 消除 | 专家3-V3 | P1 |
| R-27 | 用户微调风格参数时 | 系统 | 支持风格 token sidecar(调色/字体/密度键名对齐 social-card 8 token 扩展)与 --var key=value 覆盖,复用对比度硬校验;不带覆盖时渲染字节不变 | 换主色/字号不必改整篇 brief;token 为缩略图/图表色映射提供统一输入 | 专家3-V4(md 七参数 CSS 变量 + xiaohu JSON 主题) | P1 |
| R-28 | 版式路由命中正确性敏感高频版式(规格表/时间线/对比/大引语/台账) | 系统 | 将其逐批 HTML 化纳入确定性渲染模板,复用渲染模板治理 lint 合同 | "逐字保真零 token"覆盖面扩大;表格/台账是图像 lane 最易错页型 | 专家3-V5(guizang 28 版式骨架 × html-anything 模板面) | P1 |
| R-29 | 用户手工新增风格 | 系统 | 提供风格扩展模板(定义/视觉系统/负面提示词/构图规则/区分性)与合格判断门,新增统一过模板与 lint | 137 静态 brief 之外的用户侧扩展通道 | 专家3-V6 | P2 |
| R-30 | 发布会/路演类场景选风格 | 系统 | 可提供分角色风格组合推荐(封面更冲击/内页更理性/主辅搭配),默认关,呈现时一句话说明 | 封面与内页气质分化需求 | 专家3-V7 | P2 |
| R-31 | anchor 注入开启版式锚 | 系统 | 支持版式系统锁定(网格 token/安全边距/页码位/圆角线重)逐页注入;默认输出字节不变 | "网格页码不漂"与"颜色字体不漂"分层锁定 | 专家3-V8(母版锁定前缀) | P2 |
| R-32 | 页面含证据截图 | 系统 | 提供确定性截图框架组件(比例/圆角/阴影/背景/内边距参数化,禁透视倾斜),截图页优先路由渲染 lane | 截图页(Demo/看板/代码证据)废片率下降 | 专家3-V9(guizang frame-shot) | P2 |
| R-33 | 用户迁移/分享风格 | 系统 | 支持风格包目录约定(brief + token sidecar + 缩略图 + 样张)与导入校验(过四条治理 lint 后入位);不做中心化市场 | 团队/跨机风格迁移 | 专家3-V10 | P2 |

### 域 E:长程一致性与状态(R-34~R-46)

| 编号 | 触发条件 | 角色 | 系统行为(EARS:应…) | 用户可见结果 | 来源 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| R-34 | 母版含目录页/agenda/章节承诺 | 系统 | 维护 deck 承诺表(承诺文本/锚页/兑现页/状态)于母版工件,组装复验核对未兑现承诺,非 0 退出阻断 | 目录页漂移(声称章节 vs 实际页面)被硬拦截 | 专家4-#1(neuro-book 承诺账本) | P0 |
| R-35 | 母版发生 post-confirm 修订 | 系统 | 从母版 diff 确定性推导受影响页清单(命中数字/术语页+交叉引用传递闭包),接入"改母版再重建受影响页"合同 | 多轮改稿影响面由机器推导,防漏改与过度重建 | 专家4-#2(chinese-longnovel 事实修复重建投影) | P0 |
| R-36 | 母版/大纲 post-confirm 写回前 | 系统 | 复核基线哈希(CAS 语义),不匹配即停并报告冲突(并行会话场景) | 多会话并行改稿不再互相覆盖(M1 在案事故模式) | 专家4-#3(WriteLock + head CAS) | P1 |
| R-37 | run 执行中每页各阶段(派发/生成/质检/记录)完成 | 系统 | 追加持久化阶段账本(run 的 reports/run-ledger.jsonl);恢复时输出"从哪继续"建议 | 中断(限流/超时)后续跑不重做已完成阶段 | 专家4-#4(webnovel run ledger;重新评估 R2 二阶段"断点续跑"非目标) | P1 |
| R-38 | 派生物(slides/术语表/manifest)疑似漂移 | 系统 | 支持从最高 confirmed 基线一键重投影全部派生物并 diff 报告 | 派生物静默漂移有收敛命令 | 专家4-#5(projections retry) | P1 |
| R-39 | 恢复或写回前检测到 content 目录被会话外手改 | 系统 | 停止并给有限选项(采纳为新版本/丢弃/只查看),不覆盖 | 用户手改不被 QA 写回吞掉 | 专家4-#6(write-resume 手改检测) | P1 |
| R-40 | deck 超过 30 页组装复验 | 系统 | 把跨页术语/编号/固定件漂移从报告级升为非 0 退出阻断,输出四分类(阻断/风险/承诺状态/通过) | 长 deck 漂移项不再淹没于日志 | 专家4-#7 | P1 |
| R-41 | 每页图像记录完成 | 系统 | 沉淀渲染事实账本(每页 OCR 文本摘要+关键数值+图表计数);多轮改稿与收据核对时对照口径变化 | "上一轮实际呈现了什么"有对照基线 | 专家4-#8 | P1 |
| R-42 | 母版页数超过 40 | 系统 | 支持按节分批落盘确认(大纲全册一次),每节附节摘要(结论/新增术语/新增数字/未决承诺) | 200 页母版确认负担下降;防后节按前节早期假设写死 | 专家4-#9 | P2 |
| R-43 | 视觉质检完成 | 系统 | 可输出计划履约报告(OCR 回读 vs 母版要点,status 四档+偏差至多 N 条,线索级非门禁) | "该说的说了没"有结构化核对 | 专家4-#10 | P2 |
| R-44 | 风格/版式/结构决策发生 | 系统 | 把决策记档(决策/理由/风险/替代/状态)于项目 content 目录;多轮改稿可引用 | "为什么当时这么定"不再丢失 | 专家4-#11(ADR 化) | P2 |
| R-45 | 基线 confirmed 后 | 系统 | 把基线之前的候选文件(含双样张落选方向)标记 expired,防误引 | 候选残留不再被误读为当前方案 | 专家4-#12 | P2 |
| R-46 | worker 派发前 | 系统 | 校验 worker 简报关键块完备性(style lock/required text/术语注入/数字行),缺任一阻断派发并给缺块清单 | 缺块静默生成=整页白做的前置防线 | 专家4-#14 | P2 |

### 域 F:交付与分发(R-47~R-50)

| 编号 | 触发条件 | 角色 | 系统行为(EARS:应…) | 用户可见结果 | 来源 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| R-47 | 用户要求 handout-PDF / 长图 / 轮播卡片等衍生形态 | 系统 | 提供 export 子命令族:全部走 M1 渲染 lane 确定性渲染,导出物并入交付收据指纹,导出属交付动作、经 DELIVERY-GATE 披露;carousel 正式接入既有社交卡片规格(解除其实验性状态) | 一份 deck 多形态交付;确定性渲染保证同输入同输出 | 专家5-E5-07(elog 多目标导出架构;P1 搁置理由已消除) | P0 |
| R-48 | 用户要求 leo 代为发布到平台 | 系统 | 拒绝代发、不请求/不存储平台凭据,指路已登记的外部工具(Wechatsync 等);leo 交付止于文件与导出形态 | 分发边界明确(与 DELIVERY-GATE 同构的防范围蠕变声明) | 专家5-E5-08 | P1 |
| R-49 | 导出/衍生动作执行 | 系统 | 输出三态回执(started/completed/failed + 产物路径 + 失败页清单),与收据 verify 衔接 | "导出了吗"不再含糊 | 专家5-E5-11 | P1 |
| R-50 | 用户把已确认 deck 存为模板并用于下期 | 系统 | 支持结构资产复用(母版骨架+风格+页数合同),下期走 diff 式确认(只确认变化项);确认门数量不减,样张与数据分级每期照常;模板实例登记数据点指纹,自动 diff 沿用/新增/缺失,缺失项进材料确认清单 | 周报/月报高频场景往返减少而确认语义不变 | 专家5-E5-09/E5-10 | P2 |

### 域 G:治理与评测(R-51~R-60)

| 编号 | 触发条件 | 角色 | 系统行为(EARS:应…) | 用户可见结果 | 来源 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| R-51 | 多轮评测报告存在 | 系统 | 提供评测统计工具:输入多轮结果,输出每 case PASS 率置信区间(Wilson 95% CI)、判官修复前后重放序列显著性检验(Mann-Whitney U/Fisher),置信区间跨 0.5 或样本不足标 trending;bench"至少 3 轮采样"口径升级为置信区间判据 | M1 17 例判官校准/词表债/80-case 轮归因三大债的收敛判据去主观化;统计显著不自动晋升 judge(人在回路修复协议保留) | 专家6-E6-1(ai-marketing-skills 统计检验引擎) | P0 |
| R-52 | 高保障档 visual-qa 多轮审查 | 系统 | 支持判据加权合成 100 分 rubric,低于阈值(默认 90)阻止组装;审查协议加"最多 N 轮(默认 3)后升级用户"硬预算 | 门禁从逐项布尔升级为可比分数;迭代预算防无限重试烧 token | 专家6-E6-2(claude-blog Gate 4) | P1 |
| R-53 | 材料含未公开/涉密样貌数据、分级确认前 | 系统 | 运行确定性敏感文本扫描(模式:未脱敏手机号/证件号/用户词表内部代号),输出候选页+命中位置供 agent 语境复核;按分级门控规则集;候选不等于结论(两层检测) | 分级确认获得"哪里值得看"的机读证据;误杀由语境层把关 | 专家6-E6-3(yuwen 两层检测) | P1 |
| R-54 | 用户提供可信的优秀标杆 deck(多页) | 系统 | 蒸馏其论证模式/页面节奏/版式偏好/标题风格为 LEO_PPT_HOME/decks-styles/ 档案(与 brands/profiles 同构),条目带页码出处+反演三组标注+样本局限声明;硬规则:不把通用版式包装成"该 deck 独有";档案可作为点名资产参与风格优先序;并可从成品 deck 提取版式画像(密度档/图表频率/页面角色分布) | "照着我们上一份 deck 的样子"成为一等入口;蒸馏档案跨 deck 复用 | 专家6-E6-4 + 专家4-#13(blogger-distiller 蒸馏 schema + QMAI 拆书库) | P1 |
| R-55 | 评测套件运行 | 系统 | 含负触发用例组(纯文档排版/单张配图请求应礼貌指路不进入四 Route),其中 1 例 holdout 不参与判官调参 | frontmatter 负触发边界首次获得行为评测覆盖 | 专家6-E6-5 | P1 |
| R-56 | 交付档案保存 | 系统 | 可在项目工作区 .agents/ 落只读镜像副本并显式登记该工件契约为跨技能共享面(AGENTS.md 允许"显式声明的共享契约") | leo 与兄弟技能(如 evidence-first-writing)共享受众/场景偏好免重复问答 | 专家6-E6-6(marketingskills 工件为媒介) | P2 |
| R-57 | 提交前检查 | 系统 | 运行技能结构 lint(SKILL.md 行数上限、引用文件存在性、frontmatter 契约) | 防"入口可见性缺口"与断链复发 | 专家6-E6-7(validate-skills.sh 思想) | P2 |
| R-58 | 分级/Gate 0 advise 回复 | 系统 | 附常见过度规避误区澄清(如"内部数据不等于涉密,未公开经营数据定级为内部即可继续") | 降低误拦摩擦,"该放行的放行" | 专家6-E6-8(辟谣提示) | P2 |
| R-59 | 交付声明前 | 系统 | 聚合各预检门(geometry/sources/sensitive/receipt)结果为单一机器可读预检报告,交付披露引用该文件 | 验证分报告有单一真值;bench 可加"预检报告存在且全过"维度 | 专家6-E6-9(preflight-report.json) | P2 |
| R-60 | doctor 自检 | 系统 | 输出技能能力清单版本(styles/scripts/references 计数与 hash 摘要)并比对提示更新 | 安装器更新后的能力级 diff 可见 | 专家6-E6-10 | P2 |

### 横切业务规则(适用全部新增能力)

- **BR-001(入口锚点纪律)**:任何新增能力落地时,必须同步在 SKILL.md 对应章节/按需读取表写入入口锚点行,并按 M0.1 协议(历史重放+反向陷阱+在线复测)校准 judge 词表——M1.1 教训:19 个新 case 团灭主因是入口可见性缺口,不是代码回归(confirmed-source: known-issues iteration-90)。
- **BR-002(确认序列不增回合)**:新能力寄生既有确认门(合同/大纲/母版/视觉方向/样张)或属于交付后动作;不新增确认回合,不因 execute 授权豁免确认。
- **BR-003(降级响亮)**:研究代采/导出/素材库等依赖宿主或外部通道的能力,能力缺失时按既有固定块/降级语义处理(如 input_material_missing),不得静默模拟。
- **BR-004(确定性优先)**:新增检查/账本/导出一律确定性可重跑(同输入同输出),LLM 只做语义判定层;判官/检查器的误报保护(密度阈值+豁免)是设计要求而非可选优化。
- **BR-005(署名与证据)**:上游授权已由用户线下确认;署名按 `NOTICE` 法定最小集处理(现行治理已移除 per-borrow 借源登记,见 CHANGELOG Unreleased"移除借源登记"条),借鉴机制与来源证据由 `docs/file-github-expert-reports/` 六份报告承载,不新增借源登记面。

## 优先级分级

| 编号 | 优先级 | 可降级方案 | 是否阻塞"世界级门槛" |
| --- | --- | --- | --- |
| R-01 | P0 | 不可降级(可按宿主能力条件启用,但能力本身必须存在) | 是 |
| R-15 | P0 | 检测规则集可分期,框架不可降 | 是 |
| R-16 | P0 | 同 R-15 | 是 |
| R-24 | P0 | 协议可先覆盖封面+大图井两类版式 | 是 |
| R-34 | P0 | 不可降级 | 是 |
| R-35 | P0 | 不可降级 | 是 |
| R-47 | P0 | 可先做 handout-PDF+长图,轮播随后 | 是 |
| R-51 | P0 | 不可降级(三大债收口依赖) | 是 |
| R-03/R-04/R-06~R-10/R-17~R-19/R-25~R-28/R-36~R-41/R-48/R-49/R-52~R-55 | P1 | 域内可再排序 | 否(但合计决定次批价值) |
| R-02/R-05/R-11~R-14/R-20~R-23/R-29~R-33/R-42~R-46/R-50/R-56~R-60 | P2 | 可整体延后或择优 | 否 |

## Scope Boundaries

### 本期做

- 上述 7 域 60 条需求的全量 WHAT 定义、验收与分期建议(执行分批落地,见 Feature Slices)。
- 与既有 P0/P1/P2 批和 M1 能力面的接缝声明(解除 social-card-specs 实验性状态等)。

### 本期不做(Non-Goals)

- **不做自动发布/平台代发**:发布动作属外部工具(已登记 Wechatsync 等);不引入平台凭据、账号管理、爬虫采集执行(专家5 排除项 1/4/6)。
- **不做选题判断/流量预测/热点雷达**:leo 最多消费带时间戳的已获取数据(专家5 排除项 3)。
- **不做向量 RAG/事件溯源引擎/角色认知系统**:deck 状态用结构化清单+确定性查表即覆盖(专家4 排除项 1-4)。
- **不做检测对抗/去 AI 味规避引擎**(AIWriteX 朱雀对抗):与交付质量导向相反(专家2 排除项 4)。
- **不做中心化主题市场**:风格包只定义目录约定与导入校验(专家3-V10)。
- **不做统计显著自动晋升 judge**:判官修复保留人在回路协议(专家6 排除项 9)。
- **不做 48-skill 拆分与目录级互引**:违反仓库 AGENTS.md 兄弟技能边界;跨技能共享只走显式声明的工作区工件(专家6 排除项 1)。
- **不做 Live Photo/动态卡、PSD/编辑器架构移植**(专家3 排除项 9/10)。
- **不新增确认回合、不削弱任何既有门禁**(BR-002)。

### 与其它模块/需求的关系

- 依赖 M1 已合入的渲染 lane 与渲染模板合同(R-26/R-28/R-47/R-32 的前提);依赖既有 sources-manifest(R-04/R-05)、数字登记表(R-18/R-19/R-35)、收据门(R-47/R-49/R-59)。
- `docs/plans/2026-08-30-file-github-integration.md` §7 二阶段路线图中"断点续跑"由 R-37 重新立项(前提变化:M1 后 run 结构成熟);"STORM pip 桥/公众号导出自建管线"维持不做(前者属 efw 侧,后者被 R-47 渲染 lane 方案取代)。
- 兄弟技能 evidence-first-writing 的共享面仅 R-56 显式声明工件。

## Acceptance Examples

正向与异常均覆盖;P0 逐条正/异配对,其余每条至少一行可观察验收。

| 编号 | 覆盖需求 | Given / When / Then(压缩) |
| --- | --- | --- |
| AE-01 | R-01 | Given 无自备材料+宿主联网+用户授权代采;When 进入 generate 首轮;Then 先呈现研究问题清单并请求确认(含剩余确认序列预告),不直接 blocked;材料包落盘路径与逐条引用在后续合同轮可查 |
| AE-02 | R-01 | Given 同上但宿主无联网或用户未授权;When 用户要求"帮我找材料";Then 维持 input_material_missing 固定块语义,如实说明能力边界,不静默模拟研究结果 |
| AE-03 | R-15 | Given 母版标题连读稿含 2 处以上"不是X而是Y"翻案腔;When 文案确定性检测运行;Then WARN 定位条目;单处真实论证骨架(带豁免注明)不告警 |
| AE-04 | R-16 | Given speaker_script 含"接下来我将为大家介绍"式套话或数字与母版登记表不一致;When 讲稿纪律检查/导出;Then 该页被列出并给改写方向,口头加码被拦截 |
| AE-05 | R-24 | Given 全出血封面含主标题且底图人脸位于画布中央;When 母版视觉行制作;Then 主体映射标注人脸位置、文字落位进安全区;无蒙版方案优先被尝试 |
| AE-06 | R-34 | Given 母版目录页声称 5 个章节而实际页面只覆盖 4 个;When 组装复验;Then 承诺账本核对失败,非 0 退出阻断交付,差异承诺被列出 |
| AE-07 | R-35 | Given post-confirm 修订改了登记表一个数字;When 影响面计算执行;Then 受影响页清单恰含引用页与传递闭包页;回复的波及面结论引用该清单 |
| AE-08 | R-47 | Given 已 accepted 的 deck,用户要求导出 handout-PDF;When export 执行;Then 同输入两次导出 sha256 一致;导出物入交付收据指纹;披露含导出三态回执 |
| AE-09 | R-47, R-49 | Given 导出过程中某页渲染失败;When export 结束;Then 三态回执标 failed 并列出失败页清单,不得声称全部导出 |
| AE-10 | R-51 | Given 某 case 历史 10 轮 9 绿 1 红,另一 case 2 绿 8 红;When 评测统计执行;Then 前者输出稳定绿(CI 下界大于 0.5),后者输出 trending,而非人工读数 |
| AE-11 | R-08 | Given 母版某要点标"引用"级但无 source_ref;When check_master_contract 校验;Then 该要点被拦截并提示补锚点;估算级不受影响 |
| AE-12 | R-54 | Given 用户提供可信优秀 deck 要求"照这个风格";When 蒸馏执行;Then 档案每条结论带页码出处与反演三组标注;超出采样范围的维度如实声明未覆盖 |
| AE-13 | R-04 | Given 母版引用素材库外编造的图片 URL;When 交付前 strict 来源校验;Then 仍然拒绝,提示入库或替换(素材库不放松 strict 门) |
| AE-14 | R-36 | Given 两个并行会话先后基于同一母版基线修订;When 后写者 post-confirm 写回;Then CAS 复核失败,写回被阻断并报告冲突,先写者修订不丢失 |
| AE-15 | R-48 | Given 用户要求把成品 deck 直接发布到公众号;When 交付对话;Then leo 拒绝代发、不请求凭据、指路外部工具,交付止于导出形态 |
| AE-16 | R-53 | Given 材料正文含 11 位手机号且尚未分级;When 敏感文本扫描执行;Then 输出候选页与命中位置供分级复核;候选不直接触发拒做 |
| AE-17 | R-02 | Given 整书级超长材料;When 材料预处理;Then digest 落盘且保留原文锚点,母版制作只读 digest |
| AE-18 | R-03 | Given 会议录音且宿主有转写能力;When 提交材料;Then 接受带时间戳转写稿为合法材料,分级询问照常;引用级事实可回溯时间点 |
| AE-19 | R-05 | Given 用户要求行业市场数据且登记通道可达;When 取数;Then manifest 含来源 URL 与抓取时间戳;不可达时标 unknown 求证 |
| AE-20 | R-06 | Given 材料中某数字与母版断言不一致;When 高保障档核查官运行;Then 差异清单产出并有界 2 轮返母版,超限如实报告 |
| AE-21 | R-07 | Given 大纲某节证据计数超过阈值;When 大纲确认呈现;Then 回复含拆页或升台账版式建议一句 |
| AE-22 | R-09 | Given 用户在澄清轮口述"转化率 37%";When 母版标注;Then 该数字标"用户确认"级并可溯源到会话轮,不挂"引用" |
| AE-23 | R-10 | Given 学术答辩档材料;When 学术模式执行;Then 回复含 3-5 个评审 persona 与追问映射及 Q&A/backup 页配额建议 |
| AE-24 | R-11 | Given 高保障档大纲;When 母版完成;Then 逐节 verify_standard 自检结论在场 |
| AE-25 | R-12 | Given 材料充足;When 大纲确认;Then 确认摘要附结构先验与证据精炼两版差异一句 |
| AE-26 | R-13 | Given 文献页 DOI 与标题在材料内不一致;When 文献校验;Then 该条被列出,strict 档阻断交付披露 |
| AE-27 | R-14 | Given 学术 figure-first 场景;When 风格注入;Then 图表规范(色盲安全/误差表示)在场 |
| AE-28 | R-17 | Given 论点页要点以"这说明"开头;When 措辞检查;Then 被提示改写,动词句优先建议在场 |
| AE-29 | R-18 | Given 结论句标题含数字断言但本页登记表无对应行;When 兑现对账;Then 回母版修订 |
| AE-30 | R-19 | Given TF-1 减法后 diff 中 verified 行消失;When 留存断言;Then FAIL 并要求显式降级或确认 |
| AE-31 | R-20 | Given 交付档案含文风样本;When 文案检测;Then 样本高频词豁免生效 |
| AE-32 | R-21 | Given 连续 3 个内容页同为纯数据论证;When 连读稿复核;Then 提示换媒介 |
| AE-33 | R-22 | Given 金句页要点为"拥抱变化"式口号;When 金句判据;Then 提示重写为具体洞见 |
| AE-34 | R-23 | Given 学术要点含"显著提升"且无量化条件;When 模糊词检查;Then WARN 提示测量条件 |
| AE-35 | R-25 | Given 风格 brief 声明负面提示词;When style render 注入;Then 提示词链包含负面清单(输出 diff 可断言) |
| AE-36 | R-26 | Given 生成风格画廊;When 缩略图渲染;Then 11 套内置风格各含代表版式缩略图,双跑 sha256 一致 |
| AE-37 | R-27 | Given 用户以 --var 覆盖主色;When 渲染;Then 输出反映覆盖且过对比度校验;不带覆盖时字节不变 |
| AE-38 | R-28 | Given 台账版式被路由;When 页面生成;When 确定性渲染模板接管;Then 表格文字逐字保真(零 token 渲染) |
| AE-39 | R-29 | Given 用户按模板手工新增风格;When 保存;Then 过四条治理 lint 后入位,不合格被拒并给清单 |
| AE-40 | R-30 | Given 科技发布场景;When 风格推荐;Then 可选呈现封面/内页分角色组合(默认关,一句话说明) |
| AE-41 | R-31 | Given 开启版式锚;When 多页渲染;Then 页码/边距/网格跨页一致;默认开启状态字节不变 |
| AE-42 | R-32 | Given 页面含证据截图;When 路由;Then 优先走渲染 lane 截图框架组件 |
| AE-43 | R-33 | Given 导入风格包缺 token sidecar 或缩略图;When 导入校验;Then 拒收并报缺失清单 |
| AE-44 | R-37 | Given run 在限流中断后恢复;When status 查询;Then 输出"从哪继续"建议,已记录页不重做 |
| AE-45 | R-38 | Given 派生物被篡改;When 重投影;Then 从 confirmed 基线恢复一致并输出 diff 报告 |
| AE-46 | R-39 | Given content 基线被会话外手改;When 恢复/写回;Then 停止并给有限选项,不覆盖 |
| AE-47 | R-40 | Given 50 页 deck 存在同实体异写;When 组装复验;Then 非 0 退出阻断,四分类输出 |
| AE-48 | R-41 | Given 重建一页后关键数值变化;When 渲染账本对照;Then diff 显示数值变化供复查 |
| AE-49 | R-42 | Given 母版 120 页;When 母版确认;Then 按节分批呈现与确认,每节附节摘要 |
| AE-50 | R-43 | Given 某页丢失母版一条要点;When 履约报告;Then 该页标 partial_deviation 并给偏差条目 |
| AE-51 | R-44 | Given 风格经用户在两个候选间裁决;When 记档;Then decision-log 含决策/理由/风险/替代;后续改稿引用而非重新论证 |
| AE-52 | R-45 | Given 基线推进;When 候选检查;Then 旧候选(含落选样张方向)标 expired |
| AE-53 | R-46 | Given worker 简报缺术语注入块;When 派发前校验;Then 阻断并给缺块清单 |
| AE-54 | R-50 | Given 周报模板下期数据到来;When 生成;Then diff 式确认只呈现变化项;样张与数据分级确认照常 |
| AE-55 | R-52 | Given 高保障档 rubric 合成分低于 90;When 组装;Then 阻止组装;连续 3 轮未达标升级用户 |
| AE-56 | R-55 | Given 请求"帮我把这段文字排版成文档";When 技能触发判定;Then 礼貌指路不进入四 Route(holdout 例不参与调参) |
| AE-57 | R-56 | Given 交付档案保存;When 工件镜像;Then 工作区 .agents/ 副本一致且契约已在两技能文档登记 |
| AE-58 | R-57 | Given SKILL.md 引用了不存在的 reference 文件;When 结构 lint;Then 非 0 退出并定位断链 |
| AE-59 | R-58 | Given 用户提交普通商务数据但 agent 欲升密级;When 分级交互;Then 误区澄清在场,未公开经营数据定级内部即可继续 |
| AE-60 | R-59 | Given 交付声明;When 预检聚合;Then delivery-preflight 单文件含各门结果,未过项如实列出 |
| AE-61 | R-60 | Given doctor 自检;When 版本比对;Then 能力清单(计数+hash)与安装副本差异被提示 |
| AE-62 | R-47 | Given 用户要求轮播卡片导出;When export carousel;Then 按既有社交卡片三画板规格产出,规格脱离"实验性"标注 |

## Goals / Success Metrics

| 目标类型 | 目标描述 | 衡量口径 | 数据来源 |
| --- | --- | --- | --- |
| 产品目标 | 材料缺失场景从 100% blocked 到可代采(授权+能力具备时) | R-01 落地后新 case 在线绿;advise/execute 回复含代采分支知识 | evals 在线轮 |
| 质量目标 | 内容层机审覆盖(核查官/承诺账本/影响面) | R-06/R-34/R-35 新 case + 单测全绿;构造缺陷 deck 被拦截 | 单测+eval |
| 质量目标 | 文案/讲稿 AI 腔可检测 | R-15/R-16 case:套话/翻案腔被定位且健康 deck 零误杀(密度框架) | check 脚本单测+bench 回归 |
| 效率目标 | 图像 lane 废片率(全出血/截图页)下降 | R-24/R-32 落地后对照同版式历史废片率(观察信号,无既有基线则记录首轮基线) | run 记录 |
| 工程目标 | 评测债务收口可统计 | R-51 上线后对 known-issues 在案 10 轮矩阵回放,输出 CI 结论 | eval_stats 输出 |
| 边界目标 | 门禁零削弱 | 全量 case 回归:既有 83 case 无行为回归;五 lint 全绿 | skill-up run |

## Evidence And Assumptions

| 主张 | 类型 | 证据来源 / 为何是假设 | 确认路径 |
| --- | --- | --- | --- |
| leo 当前能力面与三大评测债 | confirmed-source | SKILL.md/README/known-issues(iteration-90/94/96)逐条核对 | 已核 |
| 各借鉴点的上游机制存在且如描述 | external-research | 六份专家报告,每条带上游源码 file:line 证据(source_inputs) | 落地时按 BR-005 复核 |
| M1 渲染 lane 消除 P1 搁置导出/缩略图的理由 | confirmed-source | render-contract.md、known-issues(HTML 链路像素 diff 0.000%) | 已核 |
| 上游许可不构成阻断 | user-stated | 用户任务书("线下与作者沟通授权") | 已确认 |
| R-24 等视觉协议能降废片率 | assumption | 无量化基线;guizang 同协议在其场景有效 | 落地后建基线观察 |
| R-40 的 30 页阈值、R-52 的 90 分/3 轮预算、R-07 的 6/2 密度阈值 | assumption | 专家建议默认值,可调 | plan 阶段调参 |
| 借鉴点价值排序(P0 八条) | external-research | 六专家独立优先级交集;专家1/4/6 各自 P0 判定 | 用户审阅 PRD 时可否决 |

### Coverage Pack(工程澄清覆盖,中风险工具面)

| coverage_item | status | source_tag | evidence_ref | deferred_owner | deferred_unblock_condition |
| --- | --- | --- | --- | --- | --- |
| source_authority | filled | mixed | 专家报告(external)+ leo 源码(confirmed) | - | - |
| current_state | filled | confirmed-source | SKILL.md/README/known-issues/plans-001..003 | - | - |
| change_delta | filled | external-research | 六专家借鉴表 | - | - |
| requirements_acceptance | filled | - | 60 R / 62 AE,全覆盖 | - | - |
| owner_oq_trace | filled | user-stated | 用户任务书三要求 | - | - |
| scope_boundaries | filled | - | Non-Goals 九条 | - | - |
| interaction_exception | filled | - | AE-02/09/13/14/15/46 降级与异常路径 | - | - |
| data_compliance_security | filled | - | R-53/R-48/凭据边界;不新增数据收集 | - | - |
| nfr_operational | filled | - | NFR 节 | - | - |
| design_source | not-applicable | - | 无 UI 设计稿输入(空声明见 Design Source Coverage) | - | - |
| regression_guard | filled | - | Goals 最后一行+BR-001 | - | - |
| handoff_context_slice | filled | - | Planning Recheck + Feature Slices | - | - |

## Glossary

| 术语 | 定义 | 来源 |
| --- | --- | --- |
| 研究代采 | 宿主联网+用户授权时,先确认研究问题清单再采集并产出带引用材料包的前置分支 | 专家1 |
| 承诺账本 | 目录/agenda/章节承诺到兑现页的核对表,组装复验硬门 | 专家4 |
| 影响面计算 | 从母版 diff 确定性推导受影响页清单(数字/术语命中+交叉引用闭包) | 专家4 |
| 图上文字合成协议 | 安静区、无蒙版优先、局部色调蒙版、缩略图终检的四步决策阶梯 | 专家3 |
| 密度阈值+豁免框架 | 文案检测按 deck 长度归一设阈值并配豁免上限,防短文案误杀 | 专家2 |
| 两层检测 | 词面扫描只定位候选不下结论,违规判定由语义层作出 | 专家6 |
| 标杆蒸馏 | 从整份优秀 deck 提取带页码出处的可复用风格/版式档案 | 专家6/4 |

## Dependencies / Constraints / Risks

**约束(产品级,不可突破)**:
- 人在回路与安全门(CONFIRM-GATE/DELIVERY-GATE/Gate 0/分级/凭据边界)不可交易;任何"自动化"不得绕过(BR-002)。
- 仓库 AGENTS.md:兄弟技能不建立运行时依赖;跨技能共享仅 R-56 显式声明工件。
- 技能零依赖分发原则:新增检查脚本不引入编译型依赖(autocorrect 类只取规则思想自研)。

**交付风险与缓解**:

| 风险 | 影响 | 缓解 / 接受 |
| --- | --- | --- |
| 60 条范围过大导致落地失焦 | 分批拖长、半成品面增多 | Feature Slices 分四批+每批独立可验证(沿用 P0-P2 批纪律);P2 允许择优 |
| 新能力入口可见性缺口复发(M1.1 在案) | 新 case 团灭 | BR-001 强制入口锚点+judge 校准同批走 |
| 文案/敏感扫描误杀健康内容 | 用户摩擦、评测误判 | BR-004 密度阈值+豁免为设计要求;bench 8 维回归+负向用例 |
| 内容层新硬门(承诺账本/术语阻断)误伤合法 deck | 长 deck 交付受阻 | 四分类输出+先 WARN 后阻断灰度(首落地可先阻断+详单) |
| 上游项目停更/机制漂移 | 借鉴源失效 | 证据以 docs/file-github-expert-reports/ 报告为准;借鉴思想而非 vendor(除既有授权件) |
| 研究/导出依赖宿主能力差异大 | 各宿主行为不一致 | BR-003 降级语义与固定块;能力探测前置 |

## 非功能需求(NFR)

| 类别 | 产品级要求 | 衡量口径 | 是否阻塞上线 |
| --- | --- | --- | --- |
| 确定性 | 新增检测/账本/导出同输入同输出 | 单测双跑断言(sha256/像素容差) | 是 |
| 性能 | 检测类脚本对 200 页母版运行时间可接受(秒级) | 单测计时 | 否(超标再优化) |
| 安全 | 敏感扫描本地执行;素材库不存业务正文;导出不泄露隐藏元数据 | 单测+审计 | 是 |
| 可观测 | run ledger/渲染账本/预检聚合报告可机读 | schema 单测 | 是 |
| 兼容 | 既有 83 case 零行为回归;五 lint 全绿;安装器/多宿主不破坏 | skill-up run + lint | 是 |

## 需求追溯矩阵(P0 与抽样)

| 需求编号 | 关联业务规则 | 验收编号 | 证据/规则依据 | 优先级 |
| --- | --- | --- | --- | --- |
| R-01 | BR-002/003 | AE-01/02 | 专家1-#1 | P0 |
| R-15 | BR-004 | AE-03 | 专家2-#1/2/7 | P0 |
| R-16 | BR-004 | AE-04 | 专家2-#5 | P0 |
| R-24 | BR-004 | AE-05 | 专家3-V1 | P0 |
| R-34 | BR-004 | AE-06 | 专家4-#1 | P0 |
| R-35 | BR-004 | AE-07 | 专家4-#2 | P0 |
| R-47 | BR-002/003 | AE-08/09/62 | 专家5-E5-07 | P0 |
| R-51 | BR-001 | AE-10 | 专家6-E6-1 | P0 |
| R-08 | BR-004 | AE-11 | 专家1-#5 | P1 |
| R-54 | BR-005 | AE-12 | 专家6-E6-4 | P1 |
| R-04 | BR-004 | AE-13 | 专家5-E5-01 | P1 |
| R-36 | BR-004 | AE-14 | 专家4-#3 | P1 |
| R-48 | - | AE-15 | 专家5-E5-08 | P1 |
| R-53 | BR-004 | AE-16 | 专家6-E6-3 | P1 |

## Feature Slices

<!-- prd:section=feature_slices -->
### 分期建议(plan 阶段定案)

- **R3-1 门面批(P0 八条)**:R-01 研究代采、R-15 文案检测框架、R-16 讲稿纪律、R-24 图上文字协议、R-34 承诺账本、R-35 影响面、R-47 导出族(先 handout-PDF+长图)、R-51 评测统计;随批 BR-001 入口锚点+judge 校准。
- **R3-2 内容批(P1)**:R-06~R-10、R-17~R-19、R-03/R-04、R-53/R-55。
- **R3-3 状态与视觉批(P1)**:R-36~R-41、R-25~R-28、R-48/R-49、R-52、R-54。
- **R3-4 择优批(P2)**:按使用信号择优,其余挂起并留接缝声明。

## Planning Recheck

| item | why recheck | required before | blocks planning? |
| --- | --- | --- | --- |
| 各 P0 项的宿主能力探测点(联网/转写/渲染) | 落地时需按宿主矩阵验证降级路径 | R3-1 动工 | 否(降级语义已定义) |
| 专家报告中上游源码 file:line 证据 | 落地时按报告复核机制仍在(证据载体为专家报告,非借源登记) | 借鉴实现前 | 否 |
| 阈值默认值(30 页/90 分/6-2 密度) | assumption 需按首批实测调参 | R3-2/3 验收 | 否 |

## Outstanding Questions

| id | question | PRD write target | owner_status | blocks_planning | closure_disposition | planning_would_invent_what | closure_state | recommended_default |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OQ-1 | 四批分期顺序是否照 Feature Slices 执行 | Feature Slices | not-asked | no | implementation-only-how-pushdown | no | deferred | 推荐照 R3-1 至 R3-4;执行顺序属 plan 职责,不改任何单条 WHAT |
| OQ-2 | R-01 研究代采默认启停 | R-01 | not-asked | no | source-resolved | no | closed | 默认条件启用,宿主能力与用户授权双具备才走代采;降级先例见 SKILL.md 不变边界(Provider 三态与 worker 缺失固定块) |
| OQ-3 | R-56 跨技能共享工件是否启用 | R-56 | not-asked | no | source-resolved | no | deferred | 默认做,但须在两技能 SKILL 与 AGENTS.md 显式登记该共享契约后才生效 |

## Owner Decision Trace

| question | owner_answer/source | chosen_answer | PRD write target | consequence | closure_state |
| --- | --- | --- | --- | --- | --- |
| 上游开源项目授权(任务书要求 1:"忽略开源协议,已线下授权") | user-stated(2026-08-31 任务书) | 许可不构成阻断,保留来源登记(BR-005) | 全文 | 融合按"学思想+必要时直接采用"双轨 | closed |
| 文档定位(任务书要求 3:"已存在增强、未存在补充,输出详细借鉴优化产品文档") | user-stated | 全量收录 60 条(增强+补充),分期落地 | Requirements/Feature Slices | 范围=全量 WHAT,顺序属 plan | closed |
| 目标(任务书:"打造成世界级顶尖 skill") | user-stated | P0 八条定为世界级门槛 | 优先级分级 | P0 不可降级 | closed |

## Design Source Coverage

design_source_inventory:
- source_or_node: none(本 PRD 无 UI 设计稿/Figma/截图类设计输入;视觉借鉴点均为机制协议,非设计视觉规格)
  read_status: read
  affected_prd_write_targets: -
  extracted_design_what: -
  evidence_level: not-applicable
  unread_or_degraded_reason: -
  readiness_consequence: -
  conflicts:
    - contradicts: none
      owner_authority_needed: no
      readiness_consequence: -

design_sources_read:
- none

design_sources_unread:
- none

design_source_coverage: read
design_degraded_owner_acceptance_ref: none

## Readiness Self-Check

write_mode: final-prd
clarification_evidence: source-proven-no-ask
preflight_sweep_closure: closed
decision_card_highest_risk_gap: 60 条借鉴点范围若不分期则落地失焦;以全量收录+Feature Slices 分期+Non-Goals 九条化解
decision_card_next_action: final-prd
decision_card_why_no_invention: 每条需求带 EARS 行为+用户可见结果+验收+默认参数;边界扩张项(研究代采/导出族)有条件启用与降级语义(既有合同先例);排期与阈值调参属 plan,不改变 WHAT
design_source_coverage: read
readiness_verified_by:
readiness_checker_schema:
readiness_prd_hash:
readiness_inputs_hash:
first_unclosed_owner_question: none
recommended default: 按 Feature Slices R3-1 起步
can_enter_spec_plan: yes
why_not:

## 变更记录

| 日期 | 修改人 | 变更内容 |
| --- | --- | --- |
| 2026-08-31 | ZCode(spec-prd) | 初稿:基于 6 专家×152 项目调研,7 域 60 条需求、62 验收、四批分期 |

## Handoff

- 本 PRD 语义闭合(P0 全验收覆盖、降级语义明确、Non-Goals 硬边界),可进入 spec-plan 做批次化实施计划(建议从 R3-1 门面批开始)。
- 需要独立评审 → spec-doc-review;对某条借鉴点有异议 → refine 本文档。
- 不要直接进入 spec-work。
