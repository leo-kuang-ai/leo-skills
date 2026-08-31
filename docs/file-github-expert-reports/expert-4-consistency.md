# 专家4:长篇一致性与记忆系统赛道 → leo-ppt-generator 长deck/多run 一致性借鉴报告

调研范围:webnovel-writer、QMAI、neuro-book、chinese-longnovel-skill 四项目机制级深读;inkos、MaliangAINovalWriter、NovelClaw、AI-Novel-Writing-Assistant、gpt-author 佐证扫描。视角:50–200 页企业/学术 deck 的术语/口径/版式/交叉引用漂移防护、断点续跑、多轮改稿影响面。

---

## 一、赛道优势总结(按流派)

### 1. 状态仓库流派(可验证真值 + 派生投影)
- **chinese-longnovel-skill** 是本流派工程极限:git 式事务链(每章 `prepare_transaction` 冻结正文/增量/状态回证哈希 → 项目写锁下复核 base head → **CAS 推进 commit-head** → 物化投影);每个 state delta 带 `source_anchor + source_excerpt_sha256`(状态变更必须锚定真实正文);仓库与正文冲突时**从 committed 正文重建投影,不用投影覆盖正文**;`validate_project.py` 失败则项目保持可恢复。证据:`references/状态与总结.md`、`scripts/项目事务.py`(WriteLock 类含 lease/stale recovery,CAS 函数族)。
- **webnovel-writer v6 Story System**:`.story-system/` 合同为唯一事实源,accepted `CHAPTER_COMMIT` 入账;state.json/index.db/summaries/memory/vector 全是**只读派生投影**,`projection_log.jsonl` 定位哪路未同步,`projections retry` 可只补投影不重跑前序阶段。证据:`README.md` 系统架构图、`scripts/chapter_commit.py`。
- **inkos**:章节工作区原子落盘("不出现状态已推进正文未落盘");Zod schema 校验 runtime state delta,坏数据直接拒绝不滚雪球。证据:`README.md` L63/L416。
- 共同原则:**存储态最小化+派生态计算**(neuro-book PromiseService 注释明言"存储态仅 open/fulfilled/abandoned,planted/echoed 等中间态从 beats 派生")。

### 2. 记忆系统流派(上下文不随篇幅膨胀)
- **chinese-longnovel-skill 七层组装**:项目配置→状态仓库→50 章阶段计划→最近 3 章正文→20 章总结→200 章长期摘要→伏笔档案;长期摘要"只保留仍影响后文的事实,已失效信息记录结束 node ID"。证据:`references/长篇上下文与一致性.md` 组装顺序节。
- **QMAI 上下文引擎**:12 级优先级组装(用户指定>细纲>上章结尾>Canon 正史>人物状态>伏笔>摘要>正文片段>图谱>向量>关键词)+token 预算三域换算(token/字符/CJK 密度防双算);`DependencyStamp`(源文件 md5/sha256+revision)驱动上下文缓存失效。证据:`src/lib/context-budget.ts`、`context-hub/{composer,source-registry,types}.ts`。
- **webnovel-writer 按章节类型动态权重**:plot/battle/emotion/transition 四模板 × early/mid/late 三阶段的核心/场景/全局权重矩阵。证据:`data_modules/context_weights.py`。

### 3. 提交链与版本流派(断点续跑/恢复语义)
- **webnovel-writer run ledger**:`WRITE_STEPS=(draft,review,data,commit,projection,backup)` 每步 `record-write-step`(step/status/输入输出路径/problems/duration_ms);`write-resume` **只给续跑建议不自动覆盖**,检测三种冲突态(正文被手改、章纲更新晚于正文、已 accepted 重跑)即停下给 2–3 个有限选项;文件签名含 sha256。证据:`skills/webnovel-write/SKILL.md` L277–312、`data_modules/run_ledger.py`。
- **chinese-longnovel-skill**:文件名即审查状态(`（草稿）.md` 后缀 = review_pending 的用户可见标识);审查报告绑定正文哈希,正文修订后旧报告自动失效;**事实性修复从第一处受影响节点重建 current generation**(maintenance rebase 影子链原子切换),纯表达修复只更新哈希不重算总结。证据:`SKILL.md` 工作流组合节、`长篇上下文与一致性.md` 待审节点节。

### 4. 大纲层次流派
- **MaliangAINovalWriter 三层大纲**:小说/卷/章三级生成 + 作品→卷→章节→场景四级管理,"设定树支持增量式修改并保存为历史快照(版本对比恢复)"。证据:`README.md` L47/L72/L97。
- **neuro-book 承载树/因果树分离**:承载树(卷→章)管"在哪讲",因果树(剧情线→场景)管"为什么发生",倒叙插叙不破坏因果链。证据:`README.md` Plot Workbench 节。
- **chinese-longnovel-skill 每 50 章分阶段细纲**:防"剧情抢跑"(后段按早期假设写死);写前闸门"本章细纲与 committed 事实冲突时停止,不顺着计划改写历史"。证据:`长篇上下文与一致性.md` 写前闸门节。

### 5. 一致性审查流派
- **neuro-book 承诺系统(伏笔账本)**:伏笔=对读者的承诺,埋下/推进/兑现全程记账;`deadlineChapterId` 锚定截止章、`cadenceChapters` 节奏承诺("三十章没发糖"提醒);账本排序 open 优先;payoff beat 打点自动 fulfilled,全部有效 payoff 消失才回退 open。证据:`server/plot/services/promise.service.ts`。
- **QMAI 章节计划履约检查**:对照已确认计划检查最终正文,10 维(场景序列/戏剧功能/期待兑现/信息流/伏笔动作/边界禁忌…),输出 status 四档+deviations≤5 条(point/evidence/suggestion);另有伏笔清理三分类(duplicate/noise/**stale**:埋设超 20 章未推进)。证据:`src/lib/novel/chapter-plan-compliance.ts`、`foreshadowing-cleanup.ts`。
- **inkos**:37 维连续性审计员;剧情多线推演 2–5 条隔离分支,采纳只存候选计划不改正史,**正史变化后旧推演自动标记过期**。证据:`README.md` L78/L355/L597。
- **webnovel-writer override ledger**:章节事实偏离母合同(world_rule_broken 等 10 类触发)时生成 AmendProposal 升级 master 合同,而非静默容忍漂移。证据:`data_modules/override_ledger_service.py`。

---

## 二、重点项目深读纪要

### 1. webnovel-writer(6.9k,Claude Code 插件)
与 leo 形态最接近(技能包+确定性脚本+CLI 子命令)。核心:①`.story-system` 合同(题材 CSV 驱动 master_setting + 每章 runtime contract);②写章九步流水线,`write-gate` 在 prewrite/precommit/postcommit 三个自然边界校验;③CHAPTER_COMMIT 驱动五路投影,失败可单独 retry;④run ledger 六步记账+write-resume 建议式恢复;⑤充分性闸门七条(正文非空/审查落库/blocking 修复/anti-AI 终检/五投影 done/committed/write-gate 三过)。**对 leo 最有价值**:run ledger 的阶段粒度、write-resume 的"建议不覆盖+手改检测+有限选项"恢复礼仪、投影单独重放。

### 2. QMAI(0.7k,Tauri 桌面,200–300 万字连载)
记忆型系统标杆:①章节保存即摄取(实体/事件/伏笔/时间线/图谱,队列+缓存+sanitize);②上下文包 12 级优先组装+三域预算换算(CJK 1 char=1 token 防双算);③角色认知 knows/does_not_know/信息差三态;④拆书库从成品提取 9 维文风宪法+角色 Skill 沉淀复用;⑤六维审查+角色命中记忆库报告(长章>8000 字分段并行,返修后 5.5 复审闭环);⑥伏笔清理 duplicate/noise/stale 规则预筛+LLM。**对 leo 最有价值**:计划履约检查的"计划 vs 成品"结构化偏差报告、伏笔/承诺的 stale 检测思路。

### 3. neuro-book(0.6k,写作 IDE)
软件工程隐喻最彻底:①World Engine 事件溯源(时间线+切面,任意时刻状态推算,历法可自定义,变更带时间戳可审计);②承诺账本(派生优先原则、deadline/cadence 字段、payoff 自动兑现);③创作决策记录(当场记档+**风险必填**+推翻留痕,ADR 化);④ChapterWriterBrief 双模式:autonomous(writer 自查引擎,brief 只给"查哪些 subject/哪个时间窗")vs curated(brief 展开状态,leader 按 mustHide 删减);信息控制四字段(读者已知/主角已知/必须隐藏/可暗示)全空则 status 降级**阻断 handoff**;⑤Agent 读写分权(leader 可写 world,writer 只读)。**对 leo 最有价值**:决策账本、brief 的状态阶梯阻断、承诺账本字段设计。

### 4. chinese-longnovel-skill(0.07k,Codex/Claude Code 协议)
一致性做到哈希级可验证:①有效节点判定四条件(稳定 node_id+沿 parent_transaction_id 可达 tx-genesis+四哈希校验+current generation);②七层上下文(上文);③事实锁(硬事实/时间锚/认知/资源/因果债/后文禁止误写,每条带来源路径+原文锚点+SHA-256,**来源改变旧 attempt 失效**);④提交流程七步(CAS 头推进+物化+validate);⑤写前闸门+一致性检查输出四分类(硬伤/风险/伏笔状态/通过项,硬伤给证据位置)。**对 leo 最有价值**:CAS/写锁、事实锁的"来源指纹绑定失效"原则、四分类审查输出。

---

## 三、借鉴点清单

| # | 来源项目+机制 | leo 现状 | 建议 | 价值论证 | 优先级 | 验证方式 |
|---|---|---|---|---|---|---|
| 1 | neuro-book PromiseService + QMAI 伏笔追踪:**承诺账本**(open/fulfilled/deadline 锚定) | 部分:cross-ref-page-exists 查页码引用存在,但目录页声称章节 vs 实际页面、agenda 承诺 vs 交付无账本(证据:deck-master.md 仅"交叉引用页码存在"判据) | 新增:deck-master deck-contract 块附 `deck-promises` 表(承诺文本/锚页/兑现页/状态),assemble 复验核对未兑现承诺非 0 退出 | 长 deck 目录页漂移是高频真实缺陷;账本数据全在母版内,零新增状态源;与既有 cross-ref 判据同构易挂载 | **P0** | check_master_contract.py 新判据+单测(伪造目录多宣称一章必须 FAIL)+eval case |
| 2 | chinese-longnovel 数字登记表思想已互相印证;其"事实性修复自动重建受影响投影" + webnovel override ledger:**影响面自动计算** | 部分:数字登记表含页码、术语表含首现页、收据 verify 有五类波及面定性规则,但"改一行→哪些页重建"需人工推导(证据:image-deck-workflow.md 步骤7、execution-contract.md 收据节) | 新增 `scripts/compute_impact.py`:输入母版 v<N>→v<N+1> diff,输出受影响页清单(命中数字/术语页+交叉引用传递闭包),接入"改母版再重建受影响页"合同 | 登记表/术语表已含全部指针,只差确定性推导;多轮改稿(改第3页波及其他页)是已知-issues 在案工作面;防漏改与过度重建两向收益 | **P0** | 单测:改登记表一个数字→清单恰含引用页;eval case 展示波及面结论引用该清单 |
| 3 | chinese-longnovel 项目事务 WriteLock(lease/stale recovery)+head CAS | 部分:run 层有 lease+file lock+generation 冲突拒绝,但 content/ 母版/outline 无并发保护——M1 批发生过并行会话共享文件事故(证据:known-issues.md"多会话并行时 CHANGELOG 应作为第一取证点";lifecycle.py 锁仅覆盖 run 内 jobs) | 新增:content/ 头部 base-hash 复核+CAS——post-confirm 写回与 QA 修订登记前重读基线哈希,不匹配即停并报告冲突 | 多会话并行是 leo 实际发生过的事故模式;run 层方案(generation/lease)已有成熟先例可平移到内容层;成本极低(一个哈希字段+复核逻辑) | **P1** | 单测模拟两会话并发修订后写者 CAS 失败;eval case 并发改稿询问而非覆盖 |
| 4 | webnovel run ledger(WRITE_STEPS 六步+record-write-step+write-resume 建议式) | 部分:三层容错(阶段分层重试/清扫/rendered 跳过)+from-failed-pages 为页粒度;页内阶段历史与跨会话人话恢复建议无持久化账本(证据:execution-contract.md Worker 节) | 增强:`<run>/reports/run-ledger.jsonl` 记每页 prompt/backend/QA/record/收据各阶段(时间/尝试/问题/产物),`leo-ppt run status` 附"从哪继续"建议;重新评估第二阶段"断点续跑/每页即落库"非目标 | 已 rendered 跳过已有,缺的是**可审计的阶段账本**与恢复建议——429 限流/超时中断(it-96 实测)后人工判断成本高;jsonl 追加写无锁竞争 | **P1** | 单测:伪造中断 run,status 输出正确续点;eval case 中断后续跑不重做已 record 页 |
| 5 | webnovel `projections retry` + chinese-longnovel "从 committed 正文重建投影" | 部分:slides.json/术语表/sources-manifest 从 confirmed 母版生成,但散在各步骤,无"从基线一键重投影+漂移核对"(证据:image-deck-workflow.md 步骤7 各自生成) | 新增 `leo-ppt deck reproject <project-root>`:从最高 confirmed 基线(含 post-confirm 链)重导出全部派生物并 diff 报告 | 收据 verify 检测漂移后需重建路径;派生物静默漂移(如术语表过期)目前无收敛命令;与 #3 CAS 配套形成"事件链→投影"完整语义 | **P1** | 单测:篡改派生物→reproject 恢复一致;CLI 冒烟 |
| 6 | webnovel write-resume 手改检测(sha256 签名+有限选项询问) | 无:恢复以 content/ 版本化为真值,但不检测会话外手改;QA 写回可能覆盖用户手改(证据:execution-contract.md 恢复节无手改分支) | 增强:恢复与 3a 写回前对 content/ 基线计算哈希对比,发现外部改动即停,给有限选项(采纳为新版本/丢弃/只查看) | 用户在确认间隙手改母版是真实场景;leo 已承诺"不覆盖作者手改"精神(SKILL 再检要求)但无机制;webnovel 同款礼仪已验证 | **P1** | 单测+eval case:预置手改后恢复,回复必须询问而非继续写回 |
| 7 | chinese-longnovel 一致性输出四分类(硬伤/风险/伏笔状态/通过项) + assemble 术语"同实体异写即报告"升级 | 部分:assemble 复验术语一致为**报告级**非阻断(证据:image-deck-workflow.md 步骤7"同实体异写即报告") | 增强:长 deck(>30 页)把跨页术语/编号/固定件漂移升为非 0 退出阻断,输出按四分类(阻断/风险/承诺状态/通过) | 10–30 页报告级足够人读;50–200 页漂移项淹没在日志里等于没查;收据门已示范"非 0 退出阻断交付"模式 | **P1** | 单测:构造同实体异写 deck→assemble 退出非 0;eval case |
| 8 | QMAI rendered 摄取 + webnovel data-agent 五投影:**渲染事实账本** | 部分:image record 有 attempts/tokens/page-type;check_table_values 做了值级比对但结果不沉淀为 deck 状态(证据:backend report 聚合;无逐页呈现事实文件) | 新增 `<run>/reports/rendered-ledger.json`:每页 OCR 文本摘要+关键数值+图表计数,收据 verify 与多轮改稿时对照"重生成后口径是否悄悄变了" | 多轮改稿(#2 影响面)需要"上一轮实际呈现了什么"作对照基线;否则重建页与未重建页的口径一致性无证据;OCR 已在链路内,只差落账 | **P1** | 单测:重建一页后 ledger diff 显示数值变化;eval case 波及面复查引用 ledger |
| 9 | chinese-longnovel 每 50 章分阶段细纲 + Maliang 三层大纲:**分节分批母版确认** | 部分:全册母版一次确认;post-confirm revision_kind 机制已支持增量修订继承 confirmed 状态(证据:execution-contract.md content/ 节) | 增强:>40 页 deck 母版按节分批落盘确认(大纲全册一次),每节附节摘要(本节结论/新增术语/新增数字/未决承诺) | 200 页母版单文档确认负担重且抢跑风险(后节按前节早期假设写死);节摘要是后续节组装与 #1/#2 的中间层;复用既有 post-confirm 机制不新增门 | **P2** | eval case 长deck 分批确认路径;判官核对每节独立确认 |
| 10 | QMAI chapter-plan-compliance(计划 vs 成品 10 维偏差报告) | 部分:required_text 白名单逐字核对+视觉 QA 容器落位;缺母版要点→渲染呈现的语义履约汇总(证据:visual-qa.md 判据为视觉向) | 增强:`scripts/check_plan_compliance.py`:OCR 回读 vs 母版要点,输出 status 四档+偏差≤N 条(point/evidence/suggestion) | 三级标注/数字登记管住了"数字对不对",履约报告管"该说的说了没";QMAI 同款结构证明可 LLM 化;作为 QA 线索级非门禁 | **P2** | 单测 fixture(丢一条要点的页→partial_deviation);eval case |
| 11 | neuro-book Decision(决策当场记档+风险必填+推翻留痕) | 部分:style 合同记录用户选择依据、prompts/registry.yaml 记提示词变更;视觉/叙事决策无统一账本(证据:SKILL.md 模版推荐节) | 新增 `<project-root>/content/decision-log.md`:风格选择/版式取舍/结构决策各记(决策/理由/风险/替代/状态),多轮改稿时可引用 | 多轮迭代"为什么当时这么定"丢失导致反复改稿;与交付档案互补(档案存偏好,账本存本 deck 决策);纯 markdown 零机制成本 | **P2** | eval case:改稿回复引用既有决策而非重新论证;文档 lint |
| 12 | inkos forecast 过期标记(正史变化旧推演失效) | 部分:样张双生"二选一落选即弃";大纲/风格候选阶段无过期标记(证据:SKILL.md 样张双生节) | 增强:风格/大纲候选(含双样张)落盘时记录所属基线版本,基线 confirmed 后旧候选标 expired 防误引 | 候选方案文件残留易被后续会话误读为当前方案;一行版本字段+复核即可;低成本防状态混淆 | **P2** | 单测:基线推进后候选文件状态翻转;文档说明 |
| 13 | QMAI 拆书库(从成品提取文风宪法/角色 Skill 沉淀复用) | 部分:extract_pptx_theme.py(可信 PPT 提取主题)+参考图反演三组判读;无"从成品 deck 蒸馏版式/密度画像存为可复用资产"(证据:README 质量闭环节) | 增强:extract 扩展为版式画像(密度档/图表频率/页面角色分布/字体层级),存 `${LEO_PPT_HOME}/profiles/` 供后续 deck 引用 | 企业用户常有"照着我们上一份 deck 的样子"诉求;现有 extract 只取色板;与 brand VI 同管道 | **P2** | 单测 fixture deck→画像字段齐;eval case 点名沿用旧 deck 风格 |
| 14 | neuro-book ChapterWriterBrief 状态阶梯(信息控制缺填→降级阻断 handoff) | 部分:check_sources_manifest --check-job-prompts 已检 job prompt 静默丢失(证据:image-deck-workflow.md C1 节) | 增强:worker 简报完备性阶梯扩展到全部关键块(style lock/required text/术语注入/数字行),缺任一→阻断派发并给缺块清单 | 既有检查只覆盖两块;长 deck 派发量大,缺块静默生成=整页白做;状态阶梯比事后 QA 便宜一个数量级 | **P2** | 单测:删一块→派发阻断;eval case |

## 四、明确排除项及理由

1. **向量 RAG/混合检索(三路 RRF)**——QMAI LanceDB、webnovel Embedding+Rerank、inkos SQLite FTS5:leo 的 deck 状态全在结构化清单(术语表/登记表/母版四段),≤200 页确定性查表即覆盖;引入向量库违背"CLI 真值/确定性推进"不变边界,徒增 runtime 依赖与不可解释召回。
2. **World Engine 完整事件溯源(subject/切面/自定义历法/任意时刻状态推算)**——PPT 无时间演化世界状态,deck 是版本快照而非时间线;母版版本化+post-confirm 修订链已等价覆盖;倒叙推算无对应场景。
3. **角色认知 knows/does_not_know 三态系统**——无角色概念;"什么能上页面"已由 data_classification 分级+三级标注+notes 双栏覆盖。
4. **伏笔超期/变义/cadence 评分**(QMAI STALE_PLANTED_CHAPTERS=20、neuro-book cadenceChapters)——deck 无"章节推进"时间轴;承诺账本只需 open/fulfilled 与锚页核对,超期评分无意义。
5. **llmlint 360 条规则/文风宪法蒸馏**——去 AI 味子集已由 human-writing/avoid-ai-writing 吸收(2026-08-30 方案 L1/L4);且 leo 页面文本受 required_text 白名单逐字控制,生成后改写空间为零,事后 lint 无处着力。
6. **gpt-author 一次性链式流水线**——无状态生成器恰是 leo 反面教材;其 EPUB 编译、成本标杆无机制增量。
7. **inkos 37 维连续性审计员全量移植**——leo 已有 visual-qa 判据表+多轮协议+双评审官 8 维 rubric;把确定性跨页扫描(术语/数字/编号/固定件)做硬(借鉴点 7)比维度堆料价值高。
8. **Maliang 多租户 RBAC/计费/LLM 可观测后台**——平台运营功能,与技能形态无关;token 计量 leo 已有 backend_stats 对账。
9. **webnovel context_weights 章型动态权重矩阵**——leo worker 上下文已按页裁剪注入,页型差异由 page role lock 禅档位承担,双机制重叠。
10. **chinese-longnovel 有效节点四条件/tx-genesis 全链可达性证明**——其复杂度服务于"数百章、无人值守连续创作";leo 每册 10–200 页、确认门密集,母版版本化+收据五指纹已提供同等可审计性,全事务链属过度工程(仅取其 CAS 与写锁思想,见借鉴点 3)。

---

## 五、一句话结论

本赛道对 leo 的最大增量不是"记忆"(leo 的结构化清单已优于小说界),而是**账本与礼仪**:deck 承诺账本(#1)、影响面推导(#2)补齐"内容层确定性核对"最后两块;run ledger+CAS+手改保护(#3/#4/#6)把 run 层已验证的租约纪律平移到内容层与恢复礼仪——四者共同把"母版真值"从文档约定升级为可验证状态机。
