# 专家6:技术架构师(skill 工程与治理)——开源 Agent 技能包生态 / 治理与评测工程调研

- 被增强对象:`/Users/kuang/knowledge/leo-skills/leo-ppt-generator/`
- 调研输入:8 组分析报告(组0/1/2/3/5/7)+ 源码深读 5 项目(marketingskills、claude-blog、ai-marketing-skills、yuwen-publish-precheck、AcademicForge)+ 辅证项目(60s、XHSSpec、blogger-distiller)
- 已吸收边界:`docs/plans/2026-08-30-file-github-integration.md`(marketingskills 11 页销售 deck、geekai 分镜四规则等)与 2026-08-31-001/002/003 计划,本报告不重复。

---

## 一、赛道优势总结(分类分模块)

### 1.1 技能组织架构:文件为媒介的共享上下文

- **marketingskills(46.1k,48 skill)的互引基座不是技能间依赖,而是落盘工件契约**:基座 skill `product-marketing` 生成用户工作区的 `.agents/product-marketing.md`,其余 47 个 skill 的 SKILL.md 开头统一内置同一段约定——"If `.agents/product-marketing.md` exists, read it before asking questions"(源码验证:`skills/copywriting/SKILL.md` L15、`skills/ab-testing/SKILL.md` L15 逐字一致)。技能目录之间零 import、零路径引用,全部共享都经数据文件间接完成,且带 legacy 路径回退(`.claude/` 旧位置、旧文件名均自动识别)与迁移命令表。
- **入口治理是显式契约+脚本校验**:`validate-skills.sh` 按 agentskills.io 规范逐 skill 校验 frontmatter(name 1-64 字符且必须匹配目录名、description 1-1024 字符须含触发短语)、SKILL.md ≤500 行、可选目录白名单(references/scripts/assets);`VERSIONS.md` 集中登记 48 skill 的版本与更新日期表,供 agent 比对检测更新。
- **claude-blog(2.0k,32 skill)采用 orchestrator 路由**:入口 `skills/blog/SKILL.md` 解析命令→按需加载 22 个 references("load only what the task needs")→路由 sub-skill→agents 派发→5-Gate 收口,与 leo 的"单 SKILL.md+references 分阶段读取"同型,多出的只是 sub-skill 目录层。
- **XHSSpec 的"知识外置"原则**:SKILL.md 明文 "Do not store brand knowledge inside the skill"——品牌/策略/规范全部落用户 repo 的 `.xhsspec/`(brand 五文件:profile/audience/offer/tone/taboo;specs 五文件;knowledge 双文件 winning-patterns/failed-patterns),skill 只装流程,Required Repo Files 强制先读后动。与 leo 合同驱动一致;差异在长期上下文跨会话资产化程度。
- **启示**:AGENTS.md"兄弟技能不建立运行时依赖"约束下,marketingskills 展示了唯一合法的强共享模式——共享契约落用户工作区文件,而非技能目录互引。

### 1.2 交付契约工程:分值门禁 + 迭代预算 + 报告落盘

- **claude-blog 5-Gate 全部代码强制**(源码验证 `scripts/blog_preflight.py`):Gate 1 能力预检→Gate 2 格式完整→Gate 3 三视口(375/768/1280)截图+JSON-LD 视觉验证→Gate 4 reviewer agent 100 分制 **<90 或任一 P0 即阻断**→Gate 5 资产/外链完整性(`--gate N` 可单跑,`--strict` exit 1,结果机器可读落盘 `<draft>/preflight-report.json`)。
- **迭代预算显式化**:被门禁拦截的 draft 最多自动迭代 3 次,超限升级(escalation)而非无限重试;另有分层阈值——交付门 90 分,pre-commit 门(`quality_gate.py`)70 分,两道门阈值解耦。
- **对比 leo**:leo 的 Gate 0/CONFIRM-GATE/DELIVERY-GATE/PARTIAL-GATE + 指纹收据门在"人在回路确认"维度远强于 claude-blog;确定性脚本(check_deck_geometry/check_sources_manifest --strict)同型。leo 缺两个件:①**多判据合成单一可比分数的 rubric**(visual-qa 是逐项判据清单,双评审官有"分歧 ≥2 分复议"但无总分拦截);②**失败重试的预算上限**(文字保真降级链 TF-1→TF-2 有链序,多轮审查协议有"连续两轮无 P1/P2 收敛",但无"最多 N 轮后升级人工"的硬预算)。

### 1.3 评测方法论:从定性分层到统计检验

- **ai-marketing-skills `growth-engine/experiment-engine.py`(Karpathy autoresearch 模式)**:实验=假设+变体+指标→逐数据点 log→score 阶段做真实统计检验——**bootstrap lift 95% CI**(重抽样,种子固定 42 保证可重复)+ **Mann-Whitney U 非参数检验**(不假设正态);判定五态 keep/crash/discard/**trending**/running,双门槛(p<P_WINNER 且 lift≥LIFT_WIN 才晋升)、最小样本门槛(min_samples)、trending 中间态(p<P_TREND 且 n≥15,"needs more samples to confirm")。赢家自动晋升 living playbook。
- **评测基建**:`eval/` 通用 runner 支持 chat/content/classifier/summarizer/custom 五型,--baseline 保存基线做回归检测。
- **直接命中 leo 债务**:known-issues 的三大债(M1 17 例判官校准、判官词表债、80-case 轮归因)当前全部靠**定性纪律**收口——"多轮采样后定论""单轮红绿不作回归结论""稳定性 4 轮分层""10 轮终版矩阵"都是人工读数。统计化后:"某 case 是否稳定绿"= 多轮 PASS 率的 Wilson 95% CI 下界>0.5;"judge 修复是否有效"= 修复前后历史重放 PASS 序列的 Mann-Whitney U 显著性;"间歇翻绿"(在案 9/10、2/10、1/10、0/10 矩阵)= 样本不足的 trending 态而非硬结论。bench README 的"≥3 轮采样"口径可升级为带置信区间的判据。

### 1.4 预审 gate:两层检测 + 场景门控 + 出处锚定

- **yuwen-publish-precheck 的两层检测**(源码验证 `scripts/scan.py`):脚本词面只负责"定位复核候选,不下违规结论"(docstring 明示),输出三类——风险候选/用户本地规则命中/**辟谣提示**(检出"赚米""S"式不必要的自我审查并主动告知官方已澄清);违规与否由 AI 语境判定("月入过万"在个人经历 vs 绑卖课链接结论不同)。
- **误报工程**:场景三层门控(commercial_only 规则在纯分享内容不启用、industry 规则需声明行业才启用);用 **38 篇平台实际放行的真实口播稿校准**,平均每篇仅 0.8 个词面候选;42 条规则全部锚定官方原文(72 条引文带链接与核验日期)。
- **修复闭环**:给可直接替换的句子并**自动复检**(复检 0 命中才交付),拒绝谐音/拆字绕审;本地 data/ 黑白名单越用越准且升级不覆盖。
- **评测侧**:`evals/trigger_cases.jsonl` 9 条正负触发用例(5 trigger/4 no,含 1 条 holdout);`test_scan.py` 16 测试专门覆盖误报保护(commercial gate 开关、share-style 零候选、词库文件惰性)。
- **对比 leo**:leo 的 data_classification 分级门(机密/绝密拒做)、PHI/国家秘密/私募门、数字登记表、来源清单 strict 校验是合同层(agent 行为约束),**无确定性敏感文本扫描**;再检要求("目标判据+波及面")与"自动复检"同型已有。

### 1.5 蒸馏入口:标杆 → 带出处的可复用资产

- **blogger-distiller 的蒸馏产物 schema**(源码验证 `references/张咋啦_创作指南.md`):五层结构——认知层(像 TA 一样思考)/策略层(像 TA 一样决策)/内容层(像 TA 一样写)/创作禁区/对比示例;每条方法带**出处笔记+互动数+验证状态**(核心信念须"≥2 条不同笔记验证")+**局限声明**("样本有限仅供参考");frontmatter 声明运行规则;硬性防编造规则四条(不能编造未表达过的观点、不能把通用建议包装成 TA 的方法、超出采样范围明确说没覆盖)。
- **对比 leo 参考图通道**:leo 的"参考图"是**单图视觉系统提取**(点名>参考图>推荐,提取后样张并排比对,风格反演三组判读——应延续/需确认/偶然成立)。"整份标杆 deck 的结构化蒸馏"(论证模式、页面节奏、版式偏好、标题风格→可复用档案)不存在;且反演三组的思想已具备,缺的是把它从"样张读回实证"推广到"整 deck 多页证据"+产物资产化(与 `brands/`、`profiles/` 同构的第四通道)。

### 1.6 分发与注册表工程

- **60s 多运行时**:核心逻辑一份(`src/router.ts`+`src/app.ts`),`deno.ts`/`bun.ts`/`node.ts`/`cf-worker.ts` 四个薄入口+各自 lockfile+wrangler.toml+Dockerfile。运行时差异全部收敛在入口层。
- **AcademicForge 注册表治理**(源码验证):`forge.yaml` 声明 source_of_truth(`registry/skills.json`)与本地维护集合;`validate-registry.mjs` 校验 id 去重、install.method 白名单、**sparse_path 必须真实存在于磁盘**(防注册表与实际内容漂移)、summary 中英未翻译检测;`build-skill-index.mjs --check` 防索引漂移;skills.json 支持主 skill+sub_skills 两层。
- **对比 leo**:lint_style_index(索引防漂移)+登记核对测试(双向)已同型覆盖核心;leo 的 `prompts/registry.yaml`(提示词进化记账,lint 强制"prompt 无条目即 FAIL")甚至比 AcademicForge 更严格。增量空间小。

---

## 二、重点项目深读纪要(5 个)

### 1. marketingskills(46.1k,/Users/kuang/knowledge/file-github/marketingskills)

48 skill、8 类目。机制级发现:(a) 互引基座经 `.agents/product-marketing.md` 工件完成,48 个 skill 靠同一段"If exists, read it"约定共享产品/受众/定位上下文,skill 目录间零依赖;(b) 基座 skill 自带版本化(Document version + Changelog 追加式),因"它是所有其他 skill 读的共享上下文,值得留 dated paper trail";(c) `validate-skills.sh` 是 Agent Skills spec 的完整 shell 实现(名称/长度/触发短语/目录白名单),CI 可跑;(d) `VERSIONS.md` 集中版本表 + README 迁移表(重命名 skill 旧名→新名)。**与 AGENTS.md 约束的兼容性判断:直接照搬 48-skill 互引基座违规,但"工件为媒介"模式合法。**

### 2. claude-blog(2.0k,/Users/kuang/knowledge/file-github/claude-blog)

32 skill+30 命令+agents+252 测试。核心是 5-Gate 交付契约:`blog_preflight.py --gate 1..5 --strict` 代码强制,preflight-report.json 机器可读;Gate 4 reviewer agent 100 分 rubric(Content 30/SEO 25/E-E-A-T 15/Technical 15/AI Citation 15)分数低于 90 或零 P0 拦截,最多迭代 3 次升级;交付门 90 与 pre-commit 门 70 双阈值分层;质量红线表直接写进 orchestrator SKILL.md(编造统计零容忍、标题不跳级、来源 Tier1-3);`tests/evaluations.json` 是触发用例集(命令→预期路由+预期行为);风格学习 `/blog style learn` 从 5-10 篇文章建作者 voice profile。

### 3. ai-marketing-skills(3.5k,/Users/kuang/knowledge/file-github/ai-marketing-skills)

37 个顶层能力目录(增长/销售/内容/SEO/视频),每个是"SKILL.md+可执行 Python 脚本"的完整工作流。深读 `growth-engine/experiment-engine.py`:实验对象模型(agent/hypothesis/variable/variants/metric/cycle-hours)→数据点 log→score 统计评估(bootstrap_lift_ci 函数 95% CI、mannwhitneyu 双侧+单侧、LIFT_WIN/P_WINNER/P_TREND 三阈值、min_samples 门槛)→keep/crash/discard/trending/running 五态→赢家自动晋升 living playbook 并建议下一实验。种子固定(rng default_rng(42))保证 bootstrap 可重复。`eval/` 目录是可移植通用评测 runner(chat/content/classifier/summarizer/custom 五型+baseline 回归)。

### 4. yuwen-publish-precheck(0.7k,/Users/kuang/knowledge/file-github/yuwen-publish-precheck)

单 skill+references 分层(平台三份/行业两份/judgment/repair/diagnose)+scripts(scan.py+terms.json)+data/(用户本地黑白名单,git 不跟踪)+evals。机制级发现:(a) scan.py 的职责边界极清晰——"词面命中只是哪里值得看,结论必须由语义判定得出",输出含**辟谣提示**(反向纠错:检出不必要的自我审查);(b) 三层场景门控函数 `rule_applies`(commercial_only/industries 别名归并)从源头降误报;(c) 误报校准用 38 篇真实放行稿;(d) 触发评测 JSONL 正负例+holdout;test_scan.py 有 `test_user_data_never_tracked_by_git` 这类数据边界测试。

### 5. AcademicForge(2.5k,/Users/kuang/knowledge/file-github/AcademicForge)

registry 驱动的技能分发层:forge.yaml(声明 source_of_truth/安装命令/update 命令)+registry/skills.json(主 skill+sub_skills 两层,含 install.method/sparse_path/双语 summary)+validate-registry.mjs(去重/方法白名单/**磁盘存在性**/翻译检测)+build-skill-index.mjs --check+site 选配站。治理要点:注册表条目宣称的一切资源必须真实存在(本地维护集合 sparse_path 逐一 existsSync 验证),索引与注册表双向防漂移。

---

## 三、借鉴点清单

| # | 来源项目+机制 | leo 现状 | 建议 | 价值论证 | 优先级 | 验证方式 |
|---|---|---|---|---|---|---|
| E6-1 | ai-marketing-skills experiment-engine.py:bootstrap lift CI+Mann-Whitney U+trending 态+固定种子 | 部分:known-issues 有"≥3 轮采样""4 轮分层""10 轮矩阵"等定性纪律,无统计工具 | 新增 `scripts/eval_stats.py`:输入多轮 report.json,输出每 case PASS 率 Wilson 95% CI、judge 修复前后重放序列的显著性检验(Mann-Whitney U/Fisher),CI 跨 0.5 或 n 不足标 trending | 直接命中三大债:M1 17 例判官校准的收敛判据、判官词表修复有效性(重放 2/10→5/10 是否显著)、80-case 轮归因去主观化;bench README"≥3 轮"口径升级为置信区间判据 | P0 | 离线单测(已知序列构造期望区间);对 known-issues 在案 10 轮矩阵回放复核定性结论;新全量轮实测 |
| E6-2 | claude-blog Gate 4:100 分 rubric <90 拦截+最多 3 次迭代升级+交付/提交双阈值 | 部分:visual-qa 判据清单式+双评审官"分歧 ≥2 分复议",无总分拦截与重试预算 | 高保障档位可选:visual-qa 判据按 P1/P2/P3 加权合成 100 分,低于阈值(默认 90)阻止组装;多轮审查协议加"最多 N 轮(默认 3)后升级用户"硬预算 | 门禁从"逐项布尔"升级为"可比分数"后,轮间/风格间/回归对比可量化;迭代预算防无限重试烧 token,与成本预估前置合同呼应 | P1 | 新单测(分数合成/预算截断);新 eval case(rubric 低于阈值阻断交付+预算耗尽升级);在线复测 |
| E6-3 | yuwen scan.py 两层检测:词面只定位候选不下结论+场景门控降误报+复检闭环 | 部分:data_classification/PHI/国家秘密为 agent 合同层,无确定性敏感扫描 | 新增 `scripts/check_sensitive_text.py`:对母版/成品 deck 文本做模式扫描(未脱敏手机号/证件号/内部代号用户词表),输出候选页+命中位置供 agent 语境复核;按 data_classification 分级门控规则集 | 分级确认目前完全依赖 agent 阅读材料,词面初筛给"哪里值得看"的确定性证据,误杀由语境层把关(两层结构与既有"否定感知"判官哲学同构) | P1 | 单测(模式命中/分级门控/零候选路径);eval case(扫描候选触发分级复核而非直接拒做) |
| E6-4 | blogger-distiller 蒸馏指南:五层结构+每条带出处与验证状态(≥2 样本验证)+硬性防编造规则 | 部分:参考图通道=单图视觉系统提取+反演三组判读;无整 deck 蒸馏产物资产化 | 新增"标杆 deck 蒸馏"通道:用户提供可信优秀 deck(多页)→蒸馏论证模式/页面节奏/版式偏好/标题风格为 `${LEO_PPT_HOME}/decks-styles/` 档案(与 brands/profiles 同构),条目带页码出处+反演三组标注+样本局限声明;硬规则:不把通用版式包装成"该 deck 独有" | 参考图是单图提取,蒸馏是结构化多页证据;产物可复用跨 deck,与点名>参考图>推荐的优先序自然衔接(蒸馏档案=可点名资产);防编造规则防风格归因幻觉 | P1 | 单测(档案 schema/出处完整性 lint);eval case(蒸馏结论必须给页码出处+超出采样范围如实声明) |
| E6-5 | yuwen trigger_cases.jsonl:正负触发用例+holdout | 无:"纯文档排版/单张配图不触发"边界只在 description 声明,无用例 | eval.yaml 新增负触发用例组(2-3 例:纯文档排版请求、单张封面图请求应礼貌指路不进入四 Route),其中 1 例标 holdout 不参与判官调参 | frontmatter 负触发语义是 leo 安全边界(description 刻意超长保负触发),但该边界从未被行为评测覆盖;holdout 防判官过拟合 | P1 | judge 双向自检(应指路/不应启动 Route);在线复测;与 untrusted-office-sanitized-copy 同纪律试陷阱 |
| E6-6 | marketingskills `.agents/` 共享上下文工件+legacy 路径回退 | 部分:profiles 在 `${LEO_PPT_HOME}/profiles/`(技能数据目录,P1-A 已落地),无跨技能可见性 | 可选镜像:交付档案保存时同步在项目工作区 `.agents/` 落一份只读副本(或在 plans 文档显式声明该工件契约为跨技能共享面),evidence-first-writing 等兄弟技能可按声明读取 | AGENTS.md 禁兄弟运行时依赖但允许"显式声明的共享契约";工件文件是唯一合法媒介;leo+efw 常在同一文档工作流出现(报告→deck),共享受众/场景偏好免重复问答 | P2 | 单测(副本一致性与 legacy 回退);在两技能 SKILL/AGENTS 文档登记契约;eval case(工件在场时合同预填来源标注) |
| E6-7 | marketingskills validate-skills.sh:入口结构 spec 校验(SKILL.md ≤500 行/引用存在性) | 部分:五条内容向 lint(brief/网格/索引/治理/render-templates),无入口文件结构 lint | 新增 `scripts/lint_skill_structure.py`:SKILL.md 行数上限(当前 309/500)、SKILL.md 与 references 内引用的文件路径必须存在、frontmatter 契约(name/description 非空) | M1 教训:19 case 团灭主因是"新能力入口可见性缺口"(能力在 references/scripts 层但 SKILL.md 未提);结构 lint 强制引用-文件一致,防断链与入口漂移 | P2 | 新 lint 对当前树全绿;故意删一个被引用文件验证非 0 退出;纳入提交前检查清单 |
| E6-8 | yuwen 辟谣提示:主动澄清常见过度规避误区 | 无:分级与安全边界只有"拒做"方向,无"不该拒"方向纠偏 | 在分级门与 Gate 0 的 advise 回复中加误区澄清文案:如"内部数据≠涉密,未公开经营数据定级为内部即可继续""来源确认可信后仍会做 preflight 不代表不信任" | 过度阻断与漏放同属合同失守;yuwen 用 38 篇放行稿证明"该放行的放行"需要显式设计;降误拦即降用户摩擦 | P2 | eval case(通用商务数据请求被误升密级时应纠偏;分级问答不制造恐慌) |
| E6-9 | claude-blog preflight-report.json:五门结果聚合单文件落盘 | 部分:delivery-receipt.json(指纹)+各脚本独立退出码,无聚合报告 | 新增交付预检聚合报告 `<run>/reports/delivery-preflight.json`:geometry/sources/sensitive(E6-3)/receipt 各门结果+WARN 清单一处落盘,交付披露引用该文件 | 交付披露目前拼装多脚本输出,聚合报告让"验证分报告"原则有单一机器可读真值;bench 可加第 9 维"preflight 报告存在且全过" | P2 | 单测(聚合完整性);eval case(交付披露引用聚合报告且未过项如实列出) |
| E6-10 | marketingskills VERSIONS.md:集中机读版本表供 agent 自检更新 | 部分:UPDATES.md/CHANGELOG 人类可读,prompts/registry.yaml 只覆盖 prompt | 技能能力清单版本化(styles/scripts/references 三层数量与 hash 摘要表),`leo-ppt doctor` 输出版本比对提示 | npx skills add 通用安装器更新后无能力级 diff 可见性;版本表让"风格库 137 brief 是否同步"可机读核验,与 lint_style_index 计数口径互证 | P2 | doctor 冒烟(版本表生成与比对);变更时 CHANGELOG 同步纪律沿用 |

---

## 四、明确排除项及理由

1. **marketingskills 48-skill 互引基座直接照搬(目录级引用)**——违反仓库 AGENTS.md"兄弟技能不建立运行时依赖";且 leo 拆多 skill 会放大 M1 已实证的"入口可见性缺口"问题(能力藏在子目录导致 agent 读不到)。只吸收其"工件为媒介"模式(E6-6)。
2. **claude-seo 25 子技能+18 agent 并行编排**——leo 无全站审计类批量并行需求;多 agent 派发已有真实派发合同与 worker 缺失固定块,再拆 sub-skill 目录纯属组织开销。
3. **60s 四运行时薄入口打包(bun/deno/node/cf-worker)**——leo 是本地技能非 HTTP 服务,分发已由"受管 runtime+install.sh/ps1 多宿主+npx skills add"三层覆盖;引入 JS 运行时矩阵无增量。
4. **redfox-community/xiaohu 等付费数据 API 连接器模式**——引入外部付费依赖与凭据面,违反 leo"凭据只由宿主或 allowlist reference 管理"边界。
5. **marketing-os"一个 skill 装下市场部"的 14 模块路由架构**——与 PPT 单域技能定位不符;其"每输出带 0-100 评分+显式声明无法确定项"两点已被 E6-2(评分)与 leo 三级标注 unknown(无法确定项)分别覆盖。
6. **xiaobei/AIWriteX 的自动发布闭环、热点雷达**——属内容分发赛道,越出 leo"生成/重建/升级 PPTX"的 frontmatter 边界。
7. **AcademicForge 的中英双语 summary 校验、选配站**——leo references 无双语需求(EN README 已由 P2-B 覆盖),建站属分发营销非技能工程。
8. **yuwen 的平台规则原文引文库(72 条带链接)**——PPT 领域治理规则多为 leo 自定合同而非外部法规,无处锚定;其"误报校准用放行稿"方法论已转化为 E6-8 的误区澄清方向。
9. **ai-marketing-skills 的 living playbook 自动晋升**——评测判官修复必须走"历史重放+反向陷阱+在线复测"协议(M0.1 既定纪律),不能因统计显著就自动合入,人在回路不可省;只取统计判据(E6-1)不取自动晋升。
10. **VERSIONS.md 整表复制为独立治理仪式**——与 E6-10 合并实施,避免新增独立维护面。
