# 专家2:PPT 文案语言质量(去 AI 味 / 中文写作规范 / 文案方法论)调研报告

被增强对象:`/Users/kuang/knowledge/leo-skills/leo-ppt-generator/`。已吸收基线:`docs/plans/2026-08-30-file-github-integration.md`(human-writing/avoid-ai-writing 的标题/要点去模板味 12 条清单已挂 deck-master.md 连读稿复核,🟡 级建议非门禁;check_prose.py 落在 efw 技能)、`docs/plans/2026-08-31-001/002/003`(P0/P1/P2 已做)。

## 一、赛道优势总结

### 1. 特征词表流派(模式目录 + 分级)

- **humanizer**(38.9k):35 种模式源自维基百科 WikiProject AI Cleanup 实战,每条"Words to watch + Before/After",语言无关基座;35 号之外还覆盖 chatbot 残留、cutoff disclaimer、假坦诚开场、回答无人提出的反对意见(§34)、拒绝假选项(§35)等长尾。源码:`SKILL.md` §1–35。
- **avoid-ai-writing**(3.8k):69 类模式 + 112 条三级词表,工程化最深——Tier1 一票命中、Tier2 段内聚集 2+ 判定、Tier3 按全文密度;每类带非均匀权重(`ISSUE_WEIGHTS`:cutoff-disclaimer ×10、chatbot ×8、tier3-phrase-cluster ×12),短文本用 `log2(words/50)` 长度除数防误杀;检测前先做 Unicode 归一化防绕过。源码:`detector/patterns.js`(2386 行)。
- **shuorenhua**(1.3k):中文原生三级体系 + "管修辞动作不管字面"原则(换字面做同一动作仍算命中),词表只列代表项不穷举。源码:`references/phrases-zh.md`、`severity.md`。
- **qu-ai-wei**(0.5k):独有"保护条件"维度——不仅列该改什么,还明确哪些情况该保留(技术文档不降格口语化、真人文字无授权不动)。源码:`SKILL.md` 编辑边界清单。
- **关键洞察**:纯词表对 PPT 短文案误杀率高(标题一句话命中 Tier1 词即翻车),必须配聚集/密度判定。avoid-ai-writing 的 Tier2 聚类与 shuorenhua 的密度归一是防误杀主流方案。

### 2. 公式方法论流派(生成侧而非清洗侧)

- **xiaoma-durex-copywriter**(0.6k):260 张海报 + 16938 条微博反向统计出的可执行数据——短文案中位 6 字、>12 字必须对仗;高频动词表(蹭/上/堵/回家)对高频形容词黑名单(极致/赋能/打造);人称纪律(「你」高频、「大家」= 通知腔);260 条语料零次出现"这意味着/其实是/这就是…的力量"(从不解释自己);成稿 6 条自检表。源码:`references/diction.md`、`copy-formulas.md`(8 公式均带非成人品类迁移示范)。
- **Viral_Writer_Skill**(0.7k):11 维度内容洞见(核心观点/说服策略/情绪触发点/金句/情感曲线/情感层次/论证方式多样性/视角转化/语言风格参数/互动钩子)作为创作前**内部思考引擎**而非展示报告;5 个候选标题逐一标注策略;平台规范"不是同一篇缩放"。附 with/without skill A/B 数据(综合通过率 100% vs 38%)。
- **bigpeng-hot-gzh**(0.2k):7 型标题公式(数字清单/我+代价+收获/反转结论/速成教程/社会证明/对比站队/情绪短句),每条标题必须写"正文必须兑现什么";硬规则可执行(主标题 18–32 字、工具名进前 16 字、空数字禁用、情绪短句最多 1 条且不当首选)。源码:`references/title-formulas.md`、`qa-checklist.md`。
- **关键洞察**:公式流派的真正资产不是公式本身,而是**统计实证 + 兑现纪律 + 自检清单**。对 leo,数字清单/反转结论类公式与"标题禁翻案腔"冲突,但"兑现"与 diction 措辞纪律是纯增量。

### 3. 确定性 linter 流派(可 CI 门禁)

- **autocorrect**(1.6k,Rust):CJK-英文自动补空格、全半角标点转换、基于 typos 的拼写检查;`format`/`lint` 双模式(lint 输出 diff 可 git review);十亿元级测试用例(`format.rs` assert_cases 数百条)。源码:`autocorrect/src/format.rs`、`rule/`。
- **chinese-copywriting-guidelines**(15.7k):规范本体(标准),autocorrect 是其可执行实现(实现),两者互补:中英文间加空格、中文与数字间加空格、中文语境用全角标点、专有名词官方写法。
- **shuorenhua hard_metrics.py**:零依赖 Python 硬判——字数留存率(目标 ≥0.90,硬下限 0.85,低于判死)、破折号密度(判死)、句长 CV/连词密度/名词化/比喻场(只报数不判死);"判死 vs 报警"分层 = 能被脚本替掉 judge 的判定项拿出来硬判。
- **关键洞察**:leo 的母版已是落盘 markdown 工件(`deck-master-v<N>.md`),天然适合 lint;且图上文字经 OCR 回读比对(`check_table_values.py`),格式不统一会造成比对假阴性——确定性 lint 同时服务视觉一致性与 OCR 命中。

### 4. 事实锁定改写流派(改写安全边界)

- **shuorenhua**:"先锁事实再改语气"——数字与修饰对象/版本/命令/路径/责任归属/情态/否定/完成态一律不动;双向回读(输入事实可找回、输出关系可回指);`in-place` 档输出 <85% 原文即回退检查误删;scope 三档(structural/bounded/in-place)把"删多少"交还用户。源码:`SKILL.md` §2/§8、`references/protected-spans.md`。
- **humanizer**:第 3 条"不发明事实"(姓名/数字/日期/引用必须来自原文)+ 复查两问("Did the rewrite add or remove any fact?" 作为错误处理)。源码:`SKILL.md` What to do。
- **关键洞察**:leo 的 TF-2(白名单逐字贴字)已是最高保真,但 TF-1(压预算回母版减法重生成)是"改写"场景——减法重生成时哪些信息点不许丢,目前只有 agent 自检(减法审计),无机器可查断言。

### 5. 误报保护流派(避免把正常表达改坏)

- **humanizer** "Check for false positives":专设"What not to flag"清单——完美语法≠AI、孤立 em dash/弯引号/单个短句不算、常见过渡词孤立出现不算、真实限制与免责声明保留;"一个 em dash 证明不了什么,同段多个模式聚集才是证据"。
- **shuorenhua** structures.md §1:二元对比骨架按长度归一设密度阈值(<300 字 2 处/300–1000 字 3 处/>1000 字每 300 字 1 处),配**豁免上限**(术语定义 ≤1、论证骨架 ≤1、引用原文不计入),且"改完的输出重新过规则不会再次命中"。
- **avoid-ai-writing**:Tier2 条目做搭配条件化(单词常见,特定搭配才算)。
- **关键洞察**:leo 去模板味清单已有"作者样本/品牌词表豁免"(第 12 条),但缺密度阈值与豁免上限的系统框架——例如"标题禁翻案腔"目前是一刀切禁令,shuorenhua 的做法是允许 ≤1 处真实论证骨架并按密度处理。

## 二、重点项目深读纪要

### 1. humanizer(`file-github/humanizer/`)

35 模式四分组(Content/Language/Style/Chatbot + Filler)。对 PPT 最相关的模式:§9"Not X but Y"(已被去模板味清单第 1 条吸收)、§10 强迫三连(与第 3 条三连同构同源)、§16 粗体小标题列表(要点形态!)、§27 假装揭示深层真理(金句页风险)、§29 标题在首句重复(PPT 标题 vs 第一条要点重复的风险,leo 未覆盖)、§31 强行金句碎句(dramatic fragments,金句页风险)、§32"X is the Y of Z"公式化格言。两大机制资产:误报保护(上述)+ 复查两问(事实增删即错误)。局限:英文特征为主,中文 AI 腔覆盖弱。

### 2. shuorenhua(`file-github/shuorenhua/`)

SKILL.md(430 行行为合同)+ 11 个 references 分工。机制级要点:(a) 固定执行顺序 判场景→划保护段→判 Tier→判档位→判 scope→改写→两遍回读;(b) protected spans 双保护级别——数值/名称/标识符/引用按**字面**保留,状态/结果/条件按**含义**保留(`质量复核只闭环了 3/10 组`→`只完成了 3/10 组`合法);(c) hard_metrics.py 判死/报警分层 + 留存率硬下限 0.85;(d) annotation mode 四字段输出(问题族/触发点/建议动作/是否建议改写);(e) 密度阈值+豁免上限(见上)。对 leo 的映射:母版修订(TF-1 减法、QA 打回改文案)= bounded 改写,应引入"信息点留存"回读;判死/报警分层与 leo 现有 exit 1 FAIL / exit 2 WARN 语义同构。

### 3. xiaoma-durex-copywriter(`file-github/xiaoma-durex-copywriter/`)

双层语义机制(表层字面成立/里层读者自跳/一跳可达/点破即死)是借势海报方法论,对政务金融学术 deck 迁移性差;**真正高价值的是 diction.md 的措辞统计**——从 260 条真实原句反向统计,全部规律有数据支撑:中位 6 字(但"短是话说清楚后自然收住的结果,不是先定长度再塞")、标点承担语气("安全,第一"的逗号是停顿不是并列)、形容词→动词替换、宿主必须是全民熟词且只动 1–2 字、数字裸用不加"多达/高达"、从不解释自己(260 条零次)。AI 味对照表 + 6 条成稿自检可整体改造为 deck 要点/金句页的措辞纪律。另有 Step 0"默认值不提问"的交互哲学与 leo 交付档案预填同构。

### 4. Viral_Writer_Skill(`file-github/Viral_Writer_Skill/`)

单文件 SKILL.md,核心是 11 维度内部思考引擎。与 leo 现有母版元信息的映射:维度 1(核心观点一句话)≈ audience_takeaway;维度 6(情感曲线/紧张-释放交替)≈ beat 波形(连续 3 页同侧 P2);维度 4(情绪触发点)与 audience_takeaway 部分重叠。**未被覆盖的增量维度**:维度 5 金句(记忆锚点:表达精准/有节奏/脱离上下文可独立传播/含洞见非口号,分布开头-高潮-结尾)、维度 8 论证方式多样性(个人故事/数据/类比/反问/正反论证交替,避免通篇同一种说理)、维度 10 语言风格参数(句长/口语化程度/修辞密度/用词倾向构成内容"声音")。平台规范部分(公众号/小红书/抖音)与 PPT 无关。

## 三、借鉴点清单

| # | 来源项目+机制 | leo 现状(证据) | 建议(增强/新增) | 价值论证 | 优先级 | 验证方式 |
|---|---|---|---|---|---|---|
| 1 | human-writing check_prose.py × shuorenhua hard_metrics(判死/报警分层、零依赖正则) | 部分:去模板味 12 条清单挂连读稿复核,但为 agent 语义自检;`check_master_contract.py`(318 行)无文体检测项 | **新增** `scripts/check_deck_prose.py`:对母版标题连读稿+要点跑可正则化检测(翻案腔/变形、黑话词表、名词化信号词"进行/实现/完成+动名词"、三连同构开头、连词密度、抒情词表),WARN 级挂 check_master_contract 输出末尾 | 12 条清单中 6–8 条可机器化;脚本可重跑天然实现 avoid-ai-writing"两遍检测";判死/报警分层避免文体规则变硬门禁(与 efw"线索而非门禁"原则一致);"同一知识源分别落两技能"是已确认先例(2026-08-30 计划 §3) | P0 | 单测(每族检测器正反用例+误报豁免);eval case:母版确认轮是否引用脚本结论;`skill-up run` 新 case |
| 2 | humanizer "What not to flag"(多模式聚集才定罪)× shuorenhua structures.md §1(密度阈值按长度归一+豁免上限 2 处) | 部分:清单第 3 条三连同构有密度思维,第 12 条有作者样本豁免;但"标题禁翻案腔"为一刀切 | **增强**:去模板味清单升级为"密度判据+豁免条件"框架——翻案腔 deck 级 ≤1 处且须为真实论证骨架(豁免注明);孤立命中 Tier2 级词(连词/渲染词)在要点 ≤3 条的短文案中不计;行业既定词豁免保留 | PPT 文案极短,单条命中即改的误杀成本高;密度框架使检查对健康 deck(政务/金融高频"闭环/抓手"既定词)不误报;known-issues 在案教训:判官/检查误杀健康回复是最大失败模式(§2026-08-29 三例、M0.1 五例) | P1 | check_deck_prose 单测含"行业词豁免/单命中放行"反向用例;bench 8 维回归 |
| 3 | xiaoma diction.md(动词优先/禁解释自己/数字裸用/人称「你」/AI 味对照表) | 无:要点规则管条数与行数(≤3 条/≤2 行/≤40 字)与论断句形态,不管措辞;清单第 8 条只禁抒情词装饰 | **新增** deck-master 要点段"措辞纪律"小节:①动词句优先,形容词堆砌换动词;②禁自我解释("这说明/这意味着/由此可见"不入要点,与论断句"不听讲解也能读懂"呼应);③数字裸用不加"高达/多达/整整";④金句/氛围页禁通知腔("大家"→"你"或去人称) | 来源是 260 条真实爆款语料反向统计,非拍脑袋;PPT 要点与海报主文案同为超短文案,密度约束同构;"从不解释自己"与 humanizer §29(标题在首句重复)共同治 PPT 特有的"标题+第一条要点同义复述"病(母版规则已禁"论断的同义复述"但无措辞级判据) | P1 | eval case:论点页要点措辞(judge 断言"这说明"类 narrator 腔缺席);风格 lint 不受影响 |
| 4 | bigpeng qa-checklist"每条标题必须写正文必须兑现什么" × 母版减法审计第二问 | 部分:减法审计第二问(不读原文听众能否获得本页结论)是 agent 自检;无标题断言逐项对账 | **增强**:连读稿复核增"标题兑现对账"判据——结论句标题中的每个数字性断言在本页要点或数字登记表中有对应行(脚本可查:标题数字 ∈ 本页登记表数值集合),无对应即回母版 | "标题兑现"是 bigpeng 公式体系的可迁移内核;数字性断言可机器化,与 check_number_ledger 的行级核对衔接;防"标题说得满、要点撑不起"——正是减法审计第二问的机器可查子集 | P1 | check_deck_prose 单测(标题数字不在登记表→WARN/FAIL);eval case 打回路径 |
| 5 | shuorenhua chat 场景+Tier1 套话表(开场套话/收尾腔) × xiaoma 人称纪律 | 无:speaker_script 段有结构定义(口播稿要点/预期疑问/停顿/用时,image-deck-workflow L153)无语言质量规则;export_speaker_notes.py 只导出不校验 | **新增** deck-master 备注段 speaker_script 语言纪律 3–5 条:短句口语、第二人称直说、禁"接下来我将为大家介绍/值得注意的是"式套话、数字与结论与母版一致(不得口头加码) | 讲稿是 PPT 交付物中人味感知最强、AI 腔最易暴露的面(逐字被念出来);shuorenhua Tier1 套话表直接可用;与 notes-not-fabricated 判官(在案)互补——它管"没编造",新纪律管"像人话";低成本高感知(user-visible) | P0 | eval case:speaker-notes-export-offered 相邻新 case(讲稿纪律可见);export_speaker_notes 增加 WARN 扫描可选 |
| 6 | shuorenhua 双向回读+留存率硬下限 × humanizer 复查两问(事实增删即错误) | 部分:数字登记表 verified?/as-of 闭环极强;但 TF-1 压预算减法重生成时,母版修订 diff 无"信息点留存"断言 | **增强**:母版 post-confirm revision 的 diff 校验——verified?=yes 的登记表行(数值/来源/口径)不得在 TF-1 减法中静默消失;要点可删,数字性证据删移须显式降级(示意)或确认 | TF-1 是 leo 唯一"改写"场景,shuorenhua 的等价物即"改写不丢事实";把"减法审计"的数字部分从 agent 自检升级为脚本可查(check_number_ledger 加 --diff 模式);留存率思想对应"要点删减不等于证据删减" | P1 | check_number_ledger.py --diff 单测(删 verified 行→FAIL);eval case:TF-1 后登记表对账 |
| 7 | chinese-copywriting-guidelines 规范子集 × autocorrect 规则思想(Python 正则自研,不 vendor Rust) | 无:仓库 grep 无中英空格/全半角规则;check_table_values.py 仅做 OCR 比对归一(消费侧),不管源头统一 | **新增** 母版文案格式 WARN 级 lint(并入 check_deck_prose):中英文之间空格、中文语境全角标点、数字与单位写法;风格 brief 声明紧凑排版时可关 | 图上文字经 OCR 回读比对,required_text 白名单逐字渲染——母版源头格式统一直接提高 OCR 命中率与跨页一致性;autocorrect 证明该类规则可确定性执行,但 leo 需零依赖,取规则思想自研正则子集即可(≤200 行) | P2 | check_deck_prose 单测;对既有评测 fixture 回放确认无批量 WARN 爆炸 |
| 8 | humanizer voice sample 优先于规则(写作样本匹配) | 部分:交付档案 profiles/<名称>.md 存偏好字段(经 check_delivery_profile.py),未含文风样本 | **增强**:交付档案增可选"文风样本"字段(用户过往 deck 标题/要点摘录);母版生成时措辞向样本靠拢,check_deck_prose 对样本中高频词豁免 | humanizer 的核心机制之一("A writing sample takes priority over these style rules");leo 的档案机制与去模板味清单第 12 条豁免已为其预留接口;闭环"用户声音"而非"通用规范" | P2 | check_delivery_profile 字段扩展单测;eval case:档案含样本时豁免生效 |
| 9 | Viral 维度 8(论证方式多样性:数据/故事/类比/正反交替) | 无:argument_role 管论证角色、beat 管情绪波形,均不管"论证媒介"多样性 | **新增** 连读稿复核清单一条:全 deck 论证媒介分布检查——连续 ≥3 个内容页同为纯数据论证或纯定性论证时提示换媒介(类比/案例/反例) | 维度 8 是 Viral 11 维中 leo 完全未覆盖且适配 deck 的维度;与"证据跟随"要点结构兼容(第一条论断+证据形态可多样);防"数据页连排"或"口号页连排"的单调 | P2 | eval case:连读稿复核提及论证媒介;judge 语义组断言 |
| 10 | Viral 维度 5(金句:脱离上下文可独立传播/含洞见非口号)× xiaoma 公式 8 反向克制 | 部分:金句页 0–1 条要点(禅档位已含),无金句质量判据 | **增强**:金句页/收束页要点判据——须能脱离本页独立成立、含具体洞见(非"拥抱变化"式口号)、全 deck 反向克制型 ≤1 处(重大场合朴素收敛) | 金句页是 PPT 传播与记忆的锚点,当前只有数量约束无质量约束;humanizer §31/§32(强行碎句、公式化格言)与 xiaoma 反向克制恰好提供正反判据 | P2 | 风格 brief 金句页条款增强;eval case 判据可见 |

## 四、明确排除项及理由

1. **avoid-ai-writing 整包 69 类词表镜像**:英文语料为主,标题/要点子集已吸收(2026-08-30);剩余增量(如 smart-punct-signature、fnword-trigram-entropy 等统计特征)需要数百词以上文本,对 ≤40 字/条的 deck 文案无统计意义。
2. **avoid-ai-writing 分类权重评分体系**(0-100 打分):母版检查对象是短文案,加权分会被长度除数扭曲(上游自己都需 log2 修正);WARN 列表 + 判死/报警二元分层(借鉴点 1)足够。
3. **humanize-text 翻译链改写**(中→日→芬→英多跳 NMT):专有名词与数字损伤不可控、过程不可审计,与 required_text 逐字白名单合同根本冲突。
4. **AIWriteX 去 AI 味对抗引擎**(朱雀检测规避):目标是骗过检测器而非写好文案,与 leo 的交付质量导向相反,且官方自述"效果不稳定"。
5. **xiaoma 双层语义全套**(谐音/双关/一跳可达):借势营销专用,与政务/金融/学术 deck 的严谨合规要求冲突;仅 slogan/氛围页可微量参考,不足以立项(金句页判据已取其可迁移内核,见借鉴点 10)。
6. **Viral 平台规范与互动钩子**(公众号 15–30 字标题/小红书 emoji/抖音前 3 秒):面向信息流平台,与演示文稿场景无关;互动钩子已被 speaker_script"预期听众疑问"覆盖。
7. **sepia 叙事结构层修复**(StoryScope 三遍协议):小说叙事向,deck 的叙事波形已由 beat(密/呼吸采样、连续 3 页同侧 P2)与 SCR 框架覆盖。
8. **autocorrect 整包 vendor**(Rust 二进制):引入编译型依赖违反技能零依赖分发原则;仅取规则子集 Python 自研(借鉴点 7)。
9. **renwei-writing 心法本体**:"存在感/具体代价"创作论针对"人写 AI 改"场景,leo 是生成场景;其可执行部分(Wikipedia signs 中文适配清单)与已吸收清单重叠。
10. **bigpeng 7 型标题公式直接引入**:数字清单/速成/社会证明型与结论句标题(完整句断言、先于正文可懂)合同冲突;反转结论型与"禁翻案腔"直接冲突;只吸收其"兑现"纪律(借鉴点 4)。
11. **no-ai-slop/英文类 skill 的 slop 模式枚举**:与 humanizer/avoid-ai-writing 高度重叠且更浅,无中文增量。
12. **last30days/redfox/xhs 类数据接口与选题情报**:非文案质量赛道,属其他专家工作面。

## 五、实施提示(给主控)

- 借鉴点 1/2/4/6/7 共享同一载体(`check_deck_prose.py` + deck-master.md 清单升级),建议合并为一个工作面一次落地,复用现有 exit 1 FAIL / exit 2 WARN 语义。
- M1 在案教训(known-issues iteration-90):新能力全部落在 references/scripts 层而 SKILL.md 入口未提,导致 19 个新 case 团灭——任何新增文案检查必须在 SKILL.md 母版真值节/连读稿条款加一句入口锚点。
- 全部变更须同步:CHANGELOG(标注来源项目与快照日期)、风格 lint 五条不受影响、eval case 注册至 eval.yaml(当前 83 case 口径)。
