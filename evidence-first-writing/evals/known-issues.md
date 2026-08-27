# 待复验清单

## 措辞漂移处理纪律（总则，2026-08-27）

GLM flash 级模型对同一诊断每轮重掷措辞。判定标准：若 FAIL 样本的**实质行为在场**（结构诊断/参数核对/停止判定确实完成）而仅判定词汇未命中，记入本文件并停止追词；若实质行为缺失，才是技能缺陷。受支持模型 A/A 后再评估是否引入语义 judge。

已按此纪律处理的用例：`dev-edit-before-polish`（六轮六种措辞：并列/零贡献 → 文章不变/删掉任何一句 → 互不推进 → 通用真理/罗列/常识 → 删掉任意一句，全文毫发无损（it-66）→ 删除全部六个空转前提/删句测试（it-67），全部实质在场，A/A 掉率 1/3；后两次按既有合法词收口——「删掉任意」为变体、「空转」为 chinese-22 断言既有词表成员，历史失败响应重放均通过）；`chinese-protocol-context-judgment`（fixture 结尾句自身含反转金句造成判定二义，已修 fixture 根因而非追词，残余 A/A 掉率 1/3——停止判定措辞仍会重掷，如「模板感低」「整体人味充足」「不需要硬改」「不需要改」「不需要去模板」（it-69，第七种），后两者已按同义词惯例补入 case any-list 并复验 PASS）；`routes-ambiguous-single-question`（it-69 首掷：分叉问题第二读者任务用「照着做完一件事」，脚本词表只有完成/操作/理解/实践/步骤，补「做完」后历史重放 + 聚焦复验 PASS；该用例此前全量从未失败）；`taste-findings-not-visual`（it-71/72 连续两掷：引用用英文弯引号 “ 而非「」、密度表述先后掷「名词倾倒/净信息量为零」「八个词并列」，词表已为前者扩词一次（含弯引号字符），it-72 的「并列」按纪律记档不追——两轮实质均在场：3-4 条高杠杆品味 finding + 证据/代价/动作 canonical 格式 + 逐字引用原文，此前全量从未失败）；`docs-truth-param-check`（五轮五种参数核对措辞：不在 help → 不在真实 → 不在你提供的真实 → 未采用 → 输出中没有/删除，全部实质在场，A/A 掉率 2/3）；`audit-does-not-rewrite`（证据标签同义重掷：iteration-33 用「引用：」按扩同义词收口，iteration-54/55 再掷 `证据：` / `**证据**：`，两轮响应均逐字引用原句、实质在场，判官接受集扩「证据」后历史重放 + iteration-56 在线复验 PASS）；`chinese-22-rules-hit-and-preserve`（iteration-54 单轮漏报反代入 finding，iteration-55 聚焦复验 PASS 不可复现，纯记档；2026-08-27 晚论点压缩句判据落地后，检测报告从「类别标签式」转向「决策日志式」——删「深邃/拥抱」而不言「翻译腔」、「没有任何动作或例子支撑」而不言「空泛」，it-65/66 实质在场（删句测试被正确执行），case 两处 any-list 按惯例扩词后复验 PASS）。

## 判定收紧的回归教训（2026-08-27）

红队修复中把 `check-causal-boundary.sh` 门禁 2 从泛否定词收紧为「情态词+动词」连续正则后，连续两轮**误拒合规响应**（中文习惯在情态词与动词间插入宾语：「无法**将这一下降**归因于」「不能下**因果**结论」）。已放宽为 0-8 字间隔并补 归因/确认/因果结论 动词，5/5 历史响应重放接受、对抗样本仍拒绝。教训：**收紧判定必须附带历史响应重放**（本项目已把它固化为流程）；同理 `docs-truth` 的 `qstat --verbose` 命令级负向断言因「引用-再否定」被移除（合规输出会引用待剔除的命令来解释删除）。

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
