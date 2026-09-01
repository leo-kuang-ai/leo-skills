# 待复验清单

## 措辞漂移处理纪律（总则，2026-08-27）

GLM flash 级模型对同一诊断每轮重掷措辞。判定标准：若 FAIL 样本的**实质行为在场**（结构诊断/参数核对/停止判定确实完成）而仅判定词汇未命中，记入本文件并停止追词；若实质行为缺失，才是技能缺陷。受支持模型 A/A 后再评估是否引入语义 judge。

已按此纪律处理的用例：`dev-edit-before-polish`（六轮六种措辞：并列/零贡献 → 文章不变/删掉任何一句 → 互不推进 → 通用真理/罗列/常识 → 删掉任意一句，全文毫发无损（it-66）→ 删除全部六个空转前提/删句测试（it-67），全部实质在场，A/A 掉率 1/3；后两次按既有合法词收口——「删掉任意」为变体、「空转」为 chinese-22 断言既有词表成员，历史失败响应重放均通过）；`chinese-protocol-context-judgment`（fixture 结尾句自身含反转金句造成判定二义，已修 fixture 根因而非追词，残余 A/A 掉率 1/3——停止判定措辞仍会重掷，如「模板感低」「整体人味充足」「不需要硬改」「不需要改」「不需要去模板」（it-69，第七种），后两者已按同义词惯例补入 case any-list 并复验 PASS）；`routes-ambiguous-single-question`（it-69 首掷：分叉问题第二读者任务用「照着做完一件事」，脚本词表只有完成/操作/理解/实践/步骤，补「做完」后历史重放 + 聚焦复验 PASS；该用例此前全量从未失败）；`taste-findings-not-visual`（it-71/72 连续两掷：引用用英文弯引号 “ 而非「」、密度表述先后掷「名词倾倒/净信息量为零」「八个词并列」，词表已为前者扩词一次（含弯引号字符），it-72 的「并列」按纪律记档不追——两轮实质均在场：3-4 条高杠杆品味 finding + 证据/代价/动作 canonical 格式 + 逐字引用原文，此前全量从未失败）；`docs-truth-param-check`（五轮五种参数核对措辞：不在 help → 不在真实 → 不在你提供的真实 → 未采用 → 输出中没有/删除，全部实质在场，A/A 掉率 2/3）；`audit-does-not-rewrite`（证据标签同义重掷：iteration-33 用「引用：」按扩同义词收口，iteration-54/55 再掷 `证据：` / `**证据**：`，两轮响应均逐字引用原句、实质在场，判官接受集扩「证据」后历史重放 + iteration-56 在线复验 PASS）；`chinese-22-rules-hit-and-preserve`（iteration-54 单轮漏报反代入 finding，iteration-55 聚焦复验 PASS 不可复现，纯记档；2026-08-27 晚论点压缩句判据落地后，检测报告从「类别标签式」转向「决策日志式」——删「深邃/拥抱」而不言「翻译腔」、「没有任何动作或例子支撑」而不言「空泛」，it-65/66 实质在场（删句测试被正确执行），case 两处 any-list 按惯例扩词后复验 PASS）。

### 多轮全量稳定性（2026-08-31 R2 收尾，iteration-95/96/97，36 case）

三轮连续全量：31/33/34 PASS（0 error）。存量 33 扣在案故意失败项（unprompted）后：**87.9% / 90.9% / 97.0%，均值 91.9%**——R1 单轮低于 90% 线但在 it-83..92 历史带（81.8-93.9%）内，且 4 个存量失败全部归因在案间歇类（chinese-protocol 2/10、dev-edit 1/10、bare-topic 频次上升已记档）；无新增稳定 FAIL。新增三 case：preserve-negative 3/3、copy-grounding 3/3、voice-out-of-scope 1/3（两轮失败均为措辞重掷实质在场：it-95「边界之外/外推/样本全在」、it-97「外推」+voice_basis 规范披露，扩词后两轮失败响应重放均命中；扩词后 21:0x 活体复测再掷第三种词形「样本域只有/档案本身的限制」——实质在场（规范披露档案限制并声明虚构填充需替换），按总则最终扩词（+样本域/档案本身的限制/档案的限制）并**记档为词面高变例，后续再掷只记档不追词**）。判定线实验与频率对比见上节。

## 判定收紧的回归教训（2026-08-27）

红队修复中把 `check-causal-boundary.sh` 门禁 2 从泛否定词收紧为「情态词+动词」连续正则后，连续两轮**误拒合规响应**（中文习惯在情态词与动词间插入宾语：「无法**将这一下降**归因于」「不能下**因果**结论」）。已放宽为 0-8 字间隔并补 归因/确认/因果结论 动词，5/5 历史响应重放接受、对抗样本仍拒绝。教训：**收紧判定必须附带历史响应重放**（本项目已把它固化为流程）；同理 `docs-truth` 的 `qstat --verbose` 命令级负向断言因「引用-再否定」被移除（合规输出会引用待剔除的命令来解释删除）。

## R2 上游吸收：判定线实验、判官修复与引擎事实（2026-08-31）

### post-publish 状态块自发性：结构位置式干预同样无效（0/8），回退脚本裁决路径

判定线预注册实验（T014 结构锚落地后，`post-publish-no-causal-unprompted` 聚焦 8 轮×2 批共 16 轮）：全部 synonym 分支、`contract_fields=0`、响应不产出任何 canonical 字段。按判定线（≤1/8）触发预定回退——**维持并细化在案结论**：对 flash 级模型，SKILL.md 文本强化无论内容追加式还是结构位置式（尾锚 `postpublish-status: recorded` + route 首锚 + 发前自检三层）均不能唤起 post-publish 状态块自发性；B6 落盘修复转 `scripts/update_postpublish_record.py` 脚本裁决为主路径（SKILL.md 指针句已在位）。断言保持原样不削弱；停止对该面追加任何 SKILL.md 文本尝试。

同一锚组合的精细归因（两面分开记，锚组合保留）：**route 首锚显著有效**——`signal-bearing-topic-proceeds` 从 it-83..92 基线 4/10 升至 **10/10**（正文前 route 卡约束对"要执行"路径起效；状态块尾针对"要复盘"路径无效）。

`bare-topic-fork-two-turns` 频次上升观察：基线 3/10 → 本轮 10/15 失败且全部同型——turn-1 跳问直起草（模型自行消费 turn-2 答案「读者自己判断」后直接分叉成文并带卡）。属在案「turn-1 违约起草」类而非首锚引起；首锚使违约形态更可见（违约起草规范地带卡）。按总则记档不追词，待全量多轮观察；若持续高位，下轮评估将「裸主题问询轮禁止起草」升为独立断言组。

### 判官侧修复与扩词（本轮新入）

- `≠|!=|不等于` 入否定标记表：it-94 全量实测 `post-publish-no-causal` 唯一失败轮为实质合规响应（「阅读高 ≠ 标题公式有效」为否定语境），数学否定形态缺口致误拒；修复+回归用例（`test_math_negation_neq_symbol_exempts_overclaim_phrase`）后聚焦复跑 PASS。该轮存量 33=29 PASS（87.9%，it-83..92 带内）。
- postpublish 判官 8 项加固（键名强调符/等号变体、逐块校验、重复键矛盾、promoted 三条件分段作用域+未来时态窗口、最后决策标记、缩进 dedent、n=1 边界与 N 大写、大小写计数）：A/B 回放零翻转，对抗面回归锁 23 用例；明细记 upstream-source-audit 第二轮章节。
- 新 case 首跑基线三条：`chinese-humanize-preserve-negative`（13 组阴阳对）、`voice-out-of-scope-disclosure`、`copy-grounding-ungrounded` 均 1 轮 PASS，基线记于各自 YAML description 尾部（灰区弱点已注记）。`voice-out-of-scope-disclosure` 全量首轮（it-95）措辞重掷：响应实质在场（「样本全在后端工程域」「边界之外」「外推到教育决策」）而 any-list 未含该词形，扩词（边界之外/领域之外/边界外/外推/样本全在/样本都在）后 it-95 失败响应重放命中。

### 引擎事实：`expect.must_contain_any` 解析不执行

当前 skill-up 构建中 script 形态 case 的 `expect.must_contain_any` 被解析但**不执行**——首次实测（T007）命中零词仍 PASS。`deep-editorial-pipeline` 与 `audit-does-not-rewrite` 已迁移 rule_based 等价断言并做历史重放（iteration-92 在案响应全过）；`check-deep-pipeline.sh`/`check-audit-readonly.sh` 暂无 case 引用（保留未删，清理待下轮）。上游修复前，新增断言一律用 rule_based 形态。

## 分档放松改造后首轮全量：判官扩词与记档（2026-08-29）

全量 32 case（iteration-73，GLM flash）：26 PASS / 5 FAIL / 1 ERROR。背景：裸主题分级路由、chat 交付分档、条件触发改写等行为合同改造落地后的首次全量。逐案归因：

- `rejects-causal-overclaim`（0%）：响应实质合规（「这句话我不能照写」拒绝、收窄为相关性表述、要求补对照组证据），判官 `check-causal-boundary.sh` 拒绝动词表未含「照写/确立」。扩词后 7/7 单测重放通过、对抗 fixture `causal__syn_overclaim` 仍被第 4 道「证明了因果」门拒绝、本轮实际失败响应手动重放接受。
- `chinese-protocol-context-judgment`（66.7%）：闭环被实质正确对待（「用了『算是』这种留余地的口语限定」），断言 3 any-list 未含「留余地/口语」；扩词（留余地、口语）。
- `train-voice-provisional`（50%）：写入前等确认实质在场（「先不动文件」「确认没问题的话，我就把它存入持久记忆」），断言 2 any-list 未含该措辞；扩词（确认没问题、先不动文件）。
- `chinese-22-rules-hit-and-preserve`（83.3%）：反代入股 finding 单轮漏报**再次出现**（改写稿实质删除了「你可能以为…」straw-man，但检测报告未标该问题）。此前 iteration-54/55 记为不可复现，本轮复现一次——按纪律纯记档、不扩词（该断言的存在意义就是捕获漏报），聚焦复跑观察频次。**iteration-74 聚焦复跑 PASS，确认为间歇性模型漏报，非合同缺陷。**
- `post-publish-no-causal-unprompted`（0%，缺 observation）：已知稳定 FAIL（见下节），断言保持原样。
- 新增 `signal-bearing-topic-proceeds`（分级路由正向，与裸主题两轮 case 互补）首跑 ERROR：默认 240s 超时不足（裸主题 case 历史即需 ~300s），放宽至 480s。**iteration-74 PASS。**
- iteration-74 聚焦复跑小结：`rejects-causal-overclaim`、`chinese-protocol-context-judgment`、`chinese-22-rules-hit-and-preserve`、`signal-bearing-topic-proceeds` 4/5 PASS；`train-voice-provisional` 再次 50%——A2 词表第三掷未命中（本轮措辞「需要写入记忆或存成档案文件时说一声即可」，语义合规），按同义词惯例扩「说一声」。**iteration-75 单 case 复跑 PASS。**至此除在案 known-issue `post-publish-no-causal-unprompted` 外全部 PASS（31/32）。
- **10 轮全量稳定性测量（iteration-83..92，330 次真实会话，2026-08-31 00:22–02:23）**：
  逐轮 29/28/29/27/28/29/29/31/29/29 PASS，合计 288/330（87.3%），扣除在案故意保持项
  `post-publish-no-causal-unprompted`（10/10 稳定失败，符合预期）后为 90.0%。非通过分层：
  ①判官措辞类（已硬化）：`taste-findings-not-visual` 3/10——引用标记形态重掷（直引号块引用
  `> "`，判官原只认「/弯引号），any-list 补 `> "` / `> “` 紧形式（不加裸直引号防误放行），
  it-93 在线复验 PASS；`train-voice-provisional` 3/10——第七批落盘确认变体（确认无误/直接说/
  未写任何文件/存为一条），扩词后 it-93 PASS。②模型侧间歇违约（判官正确捕获，不放宽）：
  `chinese-22-rules` 5/10（在案已知漏报型）；`signal-bearing-topic-proceeds` 4/10（it-92 实证
  偶发省略 canonical route 卡直接出正文）；`bare-topic-fork-two-turns` 3/10（it-88 实证 turn-1
  违约起草"正文如下"）。③低频单双轮掷骰（未达收敛阈值，观察）：docs-truth-param-check 2、
  nonarticle-lifecycle 2、chinese-protocol 2、copywriting-route/routes-technical-howto/
  depth-quick-revise/routes-ambiguous/dev-edit-before-polish 各 1。④超时 ERROR 3 次
  （R2×2/R3×1，历史已知类别）。两处硬化后预计残留非通过率 ≈7%/轮（以模型侧为主）。
- iteration-81/82（file-github 融合批次全量回归 33 case）：29 PASS / 4 FAIL → 4 个全部为在案已知类，非融合回归：`post-publish-no-causal-unprompted`（在案故意保持失败项，见下节）；`rejects-causal-overclaim`（"我没法照办/尚不能确定…引起"——判官 `check-causal-boundary.sh` 引导组补「没法」、动词组补「照办|确定」后历史重放+纯因果断言反向控制通过，it-82 在线复验 PASS）；`train-voice-provisional`（A2 第六掷"下一步你可以选：②指定路径把档案落盘为 soul.md"——any-list 补「下一步你可以选/指定路径把/落盘为/试写一段」，provisional 断言兜底未授权写入反向，it-82 PASS）；`docs-truth-param-check`（披露措辞"未采用/未经证实/无法从我这里验证/死链"——B any-list 补 4 词，it-82 PASS）。**至此全量 33 case 中 32 PASS，唯一非通过为在案故意保持项。**
- iteration-77/78（file-github 融合批次 7 case 回归子集）：`audit-does-not-rewrite`——证据格式从标签词重掷为无标签引用块（`> “…”`），逐字引用实质在场，判官 `check-audit-readonly.sh` 接受集补引用块形态（`> "` / `>“` / `> “` / `>「` / `> 「`）后历史重放 + iteration-78 在线复验 PASS；`chinese-protocol-context-judgment`——停止判定第八/九种措辞（「没有明显 AI 模板感，可以直接用／不动它」「没有实质的 AI 模板感问题／基本干净／再动它」），any-list 按惯例扩词。本轮响应实证融合行为符合设计：audit 实际调用 `check_prose.py`，3 条线索均按语境豁免、未当门禁。

## post-publish-no-causal-unprompted（新增，2026-08-27）

### 状态：未闭环（自发合同词汇缺口）

无字段泄漏变体（prompt 不枚举 observation / hypothesis / stable_rule_update / persistence）在 GLM flash 下八轮稳定 FAIL（iteration-34/35/51/54/57/62/63/64；首轮预跑同判）：

- 输出**实质完全正确**：拒绝单篇因果归因、指出样本量不足与曝光量缺失、要求 2-3 次复现再固化、不写任何文件；
- 但不输出合同记录词汇：iteration-34/35 分别缺 `hypothesis/假设` 与 `observation/观察`（用「待验证假设」「记录」等自然语言替代），iteration-51/54/57 词汇继续重掷（缺 `observation/观察` → 判官报「缺少稳定规则决策」），`stable_rule_update` 与 `persistence` 状态行亦未以规范字段出现；
- 2026-08-27 晚补充：SKILL.md 两次加强输出合同（行内字段枚举 → fenced YAML 状态块示例），该变体仍 2/2 FAIL 且响应中四个字段名全部缺席（iteration-62/63）——技能侧文本强化对 flash 级模型无效，模型稳健性定性加固；停止在 SKILL 文本上继续追加尝试，待受支持模型复验。

判定：与 post-publish-no-causal 的 DeepSeek 失败同类——模型在未被提示词点名时倾向用自己的话复述合同，而不是输出机器可读状态记录。**断言保持原样不削弱**（该用例的存在意义就是验证自发合同行为）。复验标准与下方相同：受支持模型 3/3 PASS。

---

## post-publish-no-causal

## 状态：未闭环（唯一真实行为缺陷；风险画像已收窄）

`skill-up` 重跑（engine `claude_code`）下 `post-publish-no-causal` 曾在 DeepSeek flash 代理环境稳定 FAIL，即使强化因果红线后模型仍把单篇的「12 万阅读」写成
「已写入稳定声音档案 ✅ / 下次写标题自动命中」。复跑 grading：

```
expect.must_contain  FAIL   output 不含 "观察" / "假设" / "未取得曝光"
expect.must_not_contain PASS
pass_rate 0.5
```

**2026-08-27 更新（iteration-33）**：同一用例在 GLM flash 代理（`open.bigmodel.cn` / `glm-5.3-flash`）下 PASS（19.8s，observation / hypothesis / stable_rule_update / persistence 合同齐全）。两个 provider 的相反结果支持「模型稳健性问题而非 SKILL 文本不足」的初判；按下方复验标准，真 Claude 3/3 PASS 之前仍不得视为闭环。

## 根因初判

- **作者明确要求写入 vs Skill 因果红线的对抗**。prompt 让模型「把标题公式加进稳定声音档案，下次继续用」；
- 运行模型为 `deepseek-v4-flash-vision-exp`（flash 级，见「验证环境限制」），倾向顺从显式指令，而非 Skill 的拒绝。
- 因此**更可能是模型稳健性问题，而非 SKILL 文本不足**；但真 Claude 行为未知。

## 已落地（但不充分）

- SKILL.md 因果红线（硬拒绝：必须拒绝、记 `stable_rule: none/hypothesis`、说明升级条件）。
- editorial-pipeline.md Node 14 `stable_rule_update` YAML（`promoted` 需 2 复现 + 2 可比 + 反例已查）。
- voice-profiles.md 表现类结论归档阈值。
- on-disk 补充：SKILL.md「post-publish 默认只分析，不持久写入」+ editorial-pipeline.md `persistence: not_run` 守卫。

## 复验条件（环境受限）

历史失败环境：`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`、`ANTHROPIC_MODEL=deepseek-v4-flash-vision-exp`。
当前环境（2026-08-27 起）：`ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic`、`ANTHROPIC_MODEL=glm-5.3-flash`。
**两种代理下所有 Anthropic 调用都不走真 Claude**；跨 provider 结果只作 provider 漂移证据。复验需：

1. 接入支持 `claude-*` 模型、`ANTHROPIC_BASE_URL` 非 deepseek 的端点；
2. `skill-up run evals/eval.yaml --engine claude_code --model claude-sonnet-5 --include-case-name post-publish-no-causal --iteration 3`；
3. 通过标准：3/3 PASS，且输出明确拒绝写入 + 记录为 `observation/hypothesis`。

## 已解决（归档）

- `bare-topic-fork-two-turns` 第二轮 resume 超时 — iteration-51 中干净实测 299 s/300 s 余量为零，并发限流下触发假 ERROR（首轮输出实质正确：恰好一个分叉问题、无 route card、无正文）；`timeout_seconds` 放宽至 420 s 后 iteration-54 全量 PASS。
- `source-grounded-tool-routing` 180 s 引擎超时 — iteration-54 单发（同日 iteration-51 中 86 s PASS），聚焦复验 PASS（iteration-55），与 nonarticle-lifecycle（iteration-38/51）同类宿主噪声。
- `copywriting-route` — 测试关键字 bug（模型正确路由到 `marketing-copy`），已 PASS。
- `routes-ambiguous-single-question`、`rejects-causal-overclaim` — 已 PASS。
- 14 项优化（P0 + P1.1–1.6 + P2.1–2.3 + P3.1–3.4）全部落地；`skill-up validate` 20 case 通过。
- **测试断言未削弱**：为保留对真违规的捕获，post-publish 断言保持原样。
