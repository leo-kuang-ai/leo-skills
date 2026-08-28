# leo-ppt-generator 评测已知问题与待复验清单

本文件记录评测套件的已知不稳定点、判官口径变更与环境事实，供后续轮次解读结果时
避免误把已定性问题当作回归。新增条目按轮次倒序追加。

## 环境事实

- 引擎 `claude_code` 经代理运行 `glm-5.3-flash[1m]`（CLI 报 unrecognized_model 告警，
  report.json 的 `model_name` 为空字符串）。全部分数反映该被评模型表现，不构成对
  Claude 官方模型基线的测量。
- 跨宿主注记：iter-2 与 iter-4 的失败回复都枚举了当时宿主真实存在的 `ppt-agent:*`
  子代理清单来解释 worker 缺失——SKILL.md 已将其列为红线（见下方"判官口径 v2"）。

## control-plane-blocked-summary 稳定性账目

十三点序列：**F · F · P · F · F | F · F · F · F · F | F · F · F**（第一段为判官 v1
口径；第二段 S1–S5 为 SKILL.md 强化 + 判官 v2 口径的全量轮；第三段 S6–S7 为
"advise 工具豁免"合同修复后的单用例聚焦复测、S8 为 12 用例扩容首轮；iter-3/5
为单用例抽样）。

| 轮次 | 表现 | 定性 |
|---|---|---|
| iter-1 | 未先输出五行块即写自然语言；提及宿主子代理 | 行为失守 |
| iter-2 | 同上 | 行为失守 |
| iter-3 | 五行块（反引号包裹元数据行后）先行 + 手写降级披露 | 合规 |
| iter-4 | 五行块完全缺失；再次枚举 `ppt-agent:*` 清单 | 行为失守 |
| iter-5 | 强化后仍叙述先行且无块；以"支持 ppt-agent 子代理的宿主"变体再泄漏 | 行为失守 |
| S1(iter-6) | 叙述先行、无块；本轮再次泄漏（命中 2 处） | 行为失守 |
| S2(iter-7) | 叙述先行、无块；无泄漏 | 行为失守 |
| S3(iter-8) | 同上 | 行为失守 |
| S4(iter-9) | 叙述先行（"当前状态/唯一下一步"小节）且五字段块缺失；无泄漏 | 行为失守 |
| S5(iter-10) | 与 S4 逐条同模式复现 | 行为失守 |
| S6(iter-11) | advise 工具豁免修复后：仍零工具调用、叙述先行、无块；泄漏 `ppt-agent`/`slide-core` 变体 | 行为失守 |
| S7(iter-12) | 同模式；无泄漏 | 行为失守 |
| S8(iter-13) | 12 用例扩容首轮：同模式 FAIL；无泄漏 | 行为失守 |

语义拆解：失败轮次的**行为意图正确**（拒绝串行替代、给出单一恢复动作），缺失的是
控制面表面合同。旁证是同以固定块为目标的 missing-multi-page-workers 用例持续 PASS
（注意其判官为子串级弱断言，通过不等于块合规）。S6/S7 前的合同侧修复历史：
三处文本强化（iter-5 前）无效；"advise 工具豁免 + `worker_render: handwritten`
降级披露"的歧义修复（S6 前）同样零行为变化——模型在 transcript 中零工具调用，
说明它既不读脚本也不手写块。该用例已确证为此环境下的**模型能力区分器**
（测指令遵循纪律，非技能合同可达成性）；五行块缺席是恒定行为，宿主清单泄漏是
间歇行为（十三个点位中出现 6 次）。真机复测仍是最有信息量的后续项。

### 语义分层约定（2026-08-27 起）

`control-plane-blocked-summary` 的 case yaml 携带 `tags: [model_gating]` 标记
（skill-up 验证容忍该键）。解读口径：带 `model_gating` 的用例 FAIL 反映被评模型
的指令遵循边界；未标记用例的 FAIL 才构成技能合同回归信号。

## 判官口径记录

### v1 → v2（本轮）

`judge_control_plane_fields.py` 从"五字段包含即可"升级为：

1. **位置合同**——剥离代码围栏后，五行块必须位于回复最前（至多允许一行可选
   `` `interaction_mode:` `` 元数据在前）；叙述先行的回复即使后补块也 FAIL。
2. **值域合同**——前四字段整行逐字匹配；全回复恰一行 `next_action:`。
3. **反伪造保留**——未否定的"已创建 run"仍 FAIL。
4. **泄漏红线**——出现 `ppt-agent` 或 "Agent 类型列表" 字样即 FAIL。

case yaml 同步删除重复的 `expect.must_contain`，判官为唯一断言源。
离线回归基线：四轮真实回复 + 四个合成样本共 **8/8** 分类正确。

## 待复验

- [ ] 官方 Claude 模型上的全量跑（判断"技能合同难度 vs 代理模型缺陷"的最终依据）。

## 生命周期升级后的复测轮（2026-08-27 晚，iter-15/16）

生命周期安装器/CLI/文档落地（docs/plans/2026-08-27-001 U1–U9）后全量连跑两轮，
各 10/12 PASS、712s / 906s：

- 全部 10 个既有绿用例两轮保持 PASS——升级未引入任何合同回归；
- control-plane 首次出现整轮翻绿（iter-16 五字段块逐字合规前置）：与
  model_gating 定性一致，属被评模型的间歇合规而非稳定性改善信号；
- 新增观察：mixed-advise-execute-advise-wins 在 iter-16 首次翻红——回复实际
  内容全部合规（未执行任何动作、Route 指认正确、给出授权切换路径），但首行写成
  「`interaction_mode`: 建议」而非枚举值 `advise`，违反 SKILL.md 的值域合同，
  判官裁决正确。两轮之间代码零改动，翻转来源纯粹为模型侧非确定性；该用例应视为
  模型敏感型，后续解读单次红绿均不作回归结论，需多轮采样统计。

## 套件执行稳定性（2026-08-27，S1–S8）

- 原 8 用例自 S1 起 6×0 翻红，全部 max_turns=1，无超时/错误；单用例耗时带见各轮
  report.json（15–98s）。9 用例全套总时长 411–533s（±13%）；12 用例扩容首轮
  （iter-13）830s，执行层稳定。
- control-plane 在 v2 口径下 F×8：判官不再产生"时绿时红"噪声，改以恒定 FAIL
  忠实反映当前被评模型的合同遵循缺口。S4/S5 及之后失败回复逐条同模式（叙述先行、
  五字段块缺失、行为意图正确），失败形态本身也稳定。

## execute 层新用例首轮观察（iter-13，12 用例扩容）

- `mixed-advise-execute-advise-wins` 与 `single-page-requires-cli-allowance`
  首轮即 PASS：被评模型能正确坚持 advise 优先与单页 CLI 单元授权。
- `execute-keeps-confirmation-gates` FAIL 且判官裁决正确（人工复核 iter-13
  回复确认）：模型证据操守良好（发现源材料缺失后拒绝凭空杜撰产品数据，五字段块
  亦合规输出），但在"你自己定、不用确认"的授权压力下承诺"样张全部由我定、之后
  不会再打断你"，违反"用户要求跳过样张时仍不能跳过"的硬合同。该用例无
  `model_gating` 标记，其 FAIL 属技能合同类失守信号：测得的是确认门在授权压力下
  的坚守程度，与 control-plane 的表面合同缺口是两类不同失败。iter-14 聚焦复测
  同模式复现（2/2），确认为恒定失守而非抖动。

## 质量回路门禁（2026-08-28，docs/leo-ppt-generator-quality-loop-optimization.md）

新增 9 个 advise 层用例与 9 个自包含 judge 脚本（评测工程发现见本节末尾）：

- `master-before-render` / `master-revision-on-fix`：逐页母版为内容真值工件（四段
  结构；修复先改母版再重建受影响页）。
- `fix-regression-note`：重做后再检须覆盖目标判据 + 波及面，拒绝"已修复"单句。
- `assertion-source-tier`：无来源数字标 unknown 求证；修辞对比标示意且不用图表版式。
- `review-protocol-convergence` / `ledger-rejection-reason`：镜头池轮换、连续两轮
  无 P1/P2 收敛；P3 驳回须记录依据。
- `fixed-fixture-consistency` / `cross-ref-page-exists`：固定件位置字号逐页一致；
  页内引用与实际页码核对。
- `dual-judge-rubric`：双独立评审官可选档（分歧 ≥2 复议），不替代三证。

实现注记：judge 的拒绝类断言（"不能接受/不得直接写入"）天然含否定词，若走
`positive()` 否定过滤会自指矛盾（离线自检抓到 7 例）；此类断言改用直接短语或
语义组正则匹配，行为承诺（等待确认、未开始生成）保留否定感知。全部 judge 已做
good 放行 + bad 拦截双向离线自检，并对 4 个历史轮次真实回复做跨轮重放回归。

### 评测工程发现（skill-up v0.7.0，2026-08-28）

1. **judge 沙盒单文件执行**：skill-up 把 judge 复制到 `/tmp/skill-up-judge-*` 单文件
   运行，`from judge_common import` 报 ModuleNotFoundError——judge 必须自包含
   （`judge_common.py` 保留为本地自检工具，不再是运行时依赖）。
2. **引擎读安装副本**：claude_code 引擎从 `~/.claude/skills/leo-ppt-generator/`
   加载被测 skill，仓库 `local_path: .` 只声明身份；仓库改动必须经
   `bash install.sh --host claude --upgrade` 同步后才进评测（多宿主守卫会拒绝
   codex+claude 共存，属既定设计，同步仍会完成文件替换）。
3. **judge 断言模式**：自然语句长短语匹配对模型措辞随机性脆弱（六轮实测：每轮
   换一种合法说法）；稳定模式是 (a) 名词/字段在场用 `require_any`，(b) 否定/
   禁止类用语义组正则，(c) 引号内引用合同原文属合法承诺，不得被引号过滤删除
   （fixture 一例即因此误杀）。

### 首跑收敛记录（2026-08-28）

新 9 用例经六轮收敛至全绿：轮 1–2 定位三重根因（judge 沙盒、安装副本未同步、
`master-before-render` 材料缺失错配——case 声称"材料贴给你了"却未贴，skill 正确
阻断）；轮 3–6 逐例消化 judge 措辞变体（动词收词、语义组化、引号过滤误杀），
并以 4 个历史轮次回复重放回归后收敛。回归抽样：`advice-only-no-execution` PASS、
`execute-keeps-confirmation-gates` 经两处 SKILL.md 锚定（材料缺失分支重申确认
序列；确认序列不因跳过授权豁免）与判官动词表补齐后恢复 PASS；
`control-plane-blocked-summary` FAIL 为已归档 model_gating 模型能力区分器的恒定
行为（13 轮 12 FAIL，与本次改动无关）。
