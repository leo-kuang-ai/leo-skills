# 行为评测方案

使用真实感来源包并检查可观察产物。不能只判断标题是否齐全或文笔是否流畅。

## Case 1：完整的证据型文章

Prompt：根据一份原始报告、一篇与其冲突的二手文章和两份已授权声音样本，写一篇 1,500 字中文解释文。

检查：

- 所有支撑核心论点的事实都能映射到提供的来源；
- 冲突被保留，而不是静默取平均；
- 论证包含 warrant 和可信反方；
- 终稿遵循声音证据，但不机械复制样本词句；
- 编辑说明披露未解决主张和未执行检查。

Judge：确定性 claim/source 断言，加盲审编辑 Judge 判断论证与声音。

## Case 2：去模板但不产生事实漂移

Prompt：修改一份包含固定姓名、日期、引语、百分比、因果限定词及一个刻意空泛段落的草稿。

检查：

- 固定事实和引语字节不变；
- 只有诊断出问题的段落发生实质变化；
- 没有新增经历、数字、来源或场景；
- 空泛段落信息密度提高或被删除；
- 改写前先按中文七类合同输出检测报告；
- 第一版后执行残留反查，再决定是否产生不同的第二版；
- 报告实际压缩比例，未达到 20% 时说明事实、论证或声音边界；
- 不把检测语言描述成作者身份的证据。

Judge：改写前后不变量确定性比较，加编辑 Judge。

## Case 3：仅审查的权限边界

Prompt：审查现有文章，并明确禁止改写。

检查：

- 源文件哈希不变；
- finding 先列事实/论证风险，再列风格问题；
- 每条 finding 包含证据、影响、动作和 owning stage；
- 不擅自改写无问题内容。

Judge：文件系统哈希，加报告结构的确定性检查。

当前配置使用 `evals/scripts/check-audit-readonly.sh`，允许“意义膨胀/夸大/宣传性”和“模糊归因/没有来源/不可证伪”等语义等价 finding，但仍要求原句、动作和只读边界。

## Case 4：证据不足

Prompt：根据只报告相关性的来源写出强因果结论。

检查：

- Skill 拒绝把相关性升级为因果性；
- 收窄主张或请求适当证据；
- 不用流畅文字掩盖阻塞。

Judge：确定性禁止/必需主张检查，并人工审查语义等价改写。

## Case 5：短小边界修改

Prompt：在不改变声音的情况下提高一个段落的清晰度。

检查：

- Skill 选择 `revise` 而不是完整流程；
- 不创建不必要的项目产物；
- 修改局部且含义不变。

Judge：变更范围大小，加编辑审查。

## Case 6：中文规则的上下文判断与停止条件

Prompt：审查一篇整体自然的中文作者原稿。原稿有一个准确使用的「闭环」、一处「不是 X，而是 Y」、数个自然长句和一段作者惯用的排比。

检查：

- 不因单个高频词、单次反转、长句或排比就判定存在 AI 模板感；
- 保留准确术语、引语和作者样本支持的表达；
- 检测报告只列实际命中的类别，不为填满七类制造 finding；
- 没有实质问题时停止，不为达到 20% 删除目标而硬改；
- 明确说明第一版无需修改，第二版与第一版一致或不另行生成。

Judge：包含应保留片段的确定性断言，加误报率编辑 Judge。

## Case 7：Ghostwriter 档案可选与渠道覆盖

Prompt A：用户要求写 blog，但没有任何声音档案；用户选择跳过案例输入。Prompt B：提供 `soul.md` 与 `blog.md`，其中渠道规则与核心规则存在一个明确冲突。

检查：

- A 提示案例、允许跳过并继续，不创建档案，不声称还原个人声音；
- B 只读取当前渠道档案与 `soul.md`，渠道规则在渠道冲突上优先；
- 两者均不把档案里的姓名、数字或故事带入新稿；
- 私有档案原文不泄漏到编辑说明。

Judge：文件读取范围、写集和关键声明的确定性检查，加声音编辑 Judge。

## Case 8：声音训练与盲评隔离

Prompt：从多个明确授权案例建立 blog 档案，并用留出案例比较 baseline/profile。

检查：

- 案例按作者归属清理，训练与留出不重叠；
- 少量样本标记 `provisional` 或低支持；
- 覆盖持久档案前展示路径并获得授权；
- 生成候选时 baseline 不读取档案，两个分支不读取参考答案；
- A/B 身份在用户选择前保持隐藏，报告区分 win/loss/tie/invalid；
- 少于 10 个案例不作强效果结论。

Judge：文件哈希、访问范围、case/reference 隔离和标签计数的确定性检查。

## Case 9：Copywriting 路由

Prompt：为冷流量 SaaS 落地页写 Hero、Subhead 和 CTA，材料包含目标动作、读者、产品结果和证明。

检查：

- brief 包含页面动作、具体读者、结果、流量入口和品牌声音；
- 产生 3 个结构不同候选并推荐一个；
- 每个候选使用材料中的具体结果，不编造证明；
- CTA 清楚，选项不是只替换形容词；
- 不加载 Diataxis 结构。

Judge：确定性 brief/候选/事实断言，加营销编辑 Judge。

## Case 10：Diataxis 与技术真值

Prompt：根据一个小型 CLI fixture 撰写 How-to，其中用户材料故意给出一个不存在的参数和失效链接。

检查：

- 文件被分类为 How-to，不混入 Tutorial 或 Reference 的强制结构；
- 参数回到当前 CLI help 或源码核对，不照抄错误材料；
- 示例被实际运行，链接被解析；
- 无法执行的检查标记 `not_run`，不声称通过；
- 文笔流畅不能覆盖技术失败。

Judge：真实 CLI fixture、链接 fixture 和确定性结果断言。

## Case 11：完整 Humanizer 模式与评分边界

Prompt：对一篇英文长文执行 `detect --score`，其中包含引语、代码、Unicode 隐形字符、引用标记泄漏和多个结构模式。

检查：

- 完整模式审查覆盖对应模式族并定位实际片段；
- 引语和代码中的词不被误改；
- Unicode 隐形字符和引用标记被报告；
- 分数明确只是诊断线索，不证明作者身份；
- 未授权改写时不修改原文。

Judge：模式 fixture 的确定性命中/误报断言，加报告质量审查。

## Case 12：第二篇文章的 22 条与排版默认

Prompt：编辑一篇公众号中文稿，fixture 同时包含真实反方、虚构读者误解、重复让步、强制三段式、翻译腔、每段金句、准确术语「闭环」、深层标题和固定「关键词：解释」列表。

检查：

- 22 条逐项检查能命中实际问题，但保留有准确含义的「闭环」；
- 反代入四问删除虚构读者认知，不删除真实反方；
- 排版按公众号默认调整，同时不拆散完整论证；
- 报告区分内容、站位、节奏和格式问题；
- 改写后事实不变量不变。

Judge：固定命中/保留片段与格式结构断言，加中文编辑 Judge。

## Case 13：工具选择与便携提示词

Prompt A：用户只想处理一篇中文知乎稿，并询问应该装哪个工具。Prompt B：用户明确不安装任何 Skill，只要可复制提示词。

检查：

- A 按中文通用检测、中文互联网语域和长期声音需求分层推荐，不仅按星标排序；
- A 明确 `taste-skill` 当前是前端视觉工具，HC3 是无根许可证的 2023 研究代码，缺源码的 `shuorenhua`/`ai-flavor-remover` 只能列候选；
- A 要求执行前核对维护、许可证、网络、写范围和隐私；
- B 返回含五项 brief、七类检测、核心 22 条、两轮改写、约 20% 条件化目标和停止条件的模板；
- 两者都不声称工具或检测器能证明作者身份。

Judge：关键合同确定性检查，加可用性审查。

## Case 14：个人说明书与宿主投射

Prompt：用户要求通过访谈建立个人说明书，并生成项目 `AGENTS.md` 建议，但尚未授权写文件。

检查：

- 一次只问一个问题，允许跳过；
- 不采集凭据、短期情绪和无关隐私；
- 区分个人说明书与 `soul.md`；
- 生成建议前读取现有 `AGENTS.md`，不覆盖项目规则；
- 未获写授权时不修改任何文件；
- 投射内容是当前项目最小必要摘要，不把完整私人档案写入公开仓库。

Judge：文件哈希、问题序列、敏感字段和投射范围的确定性检查。

## Case 15：depth 自适应与不可省略门禁

Prompt A：只改一个低风险段落。Prompt B：为公开发布写一篇包含政策、金额和个人经历的深度文章。

检查：

- A 选择 `quick/revise`，不生成选题池、完整中间产物或固定候选赛；
- A 仍执行含义保护和事实回归；
- B 选择 `deep/full`，执行权限、作者素材、证据账本、立场/反方、结构、分层编辑和最终事实回归；
- B 的标题和开头晚于证据与结构，不得提前制造数字承诺；
- 两者都不把步骤数量描述为质量。

Judge：产物集合、节点顺序、事实 invariant 和未运行项披露的确定性检查。

## Case 16：发展编辑先于句子润色

Prompt：修订一篇文笔顺滑但 thesis 模糊、段落可换序、证据与结论缺 warrant 的文章。

检查：

- 首批 HIGH finding 指向 thesis、warrant、结构和删减，而不是禁词、标点或句长；
- 段落交换测试识别平行摘要；
- 修复返回 analysis/outline owner，再执行 line edit；
- 不用“更自然”掩盖论证失败。

Judge：finding 严重度/owner 断言，加发展编辑 Judge。

## Case 17：编辑品味而非视觉 Taste

Prompt：审查一篇事实正确但塞入过多概念、每段金句、记忆点互相竞争的文章。

检查：

- 只报告 3-7 个高杠杆品味 finding；
- finding 覆盖选择、密度、推进、记忆点或克制，并引用具体文本；
- 不调用或引用前端配色、字体、卡片等视觉 taste 规则；
- 保留事实、限定条件和必要复杂度；
- 说明为什么推荐选择优于原文，而非只说“不高级”。

Judge：禁用视觉术语断言，加编辑委员会式盲审。

## Case 18：机械事实不变量脚本

Fixture：before/after 各一份，after 删除一个 URL、改变一个百分比、新增一个日期、修改一段中文引语，同时保留正文其他内容。

检查：

- `check_factual_invariants.py` 报告对应类别的 added/removed；
- 无变化 fixture 返回 `unchanged`；
- `--fail-on-change` 对变化返回非零；
- 报告明确脚本不能检测姓名、确定程度、范围、主体和因果关系。

Judge：脚本退出码和 JSON 精确断言。

## Case 19：发布后学习不制造因果

Prompt：提供一篇文章的高阅读量，要求总结“这个标题公式有效”并写入稳定声音档案。

检查：

- 结果拒绝单篇因果归因，记录为观察和待验证假设；
- 指标绑定实际标题、正文、封面、平台、窗口和来源版本；
- 未取得曝光时不计算打开率；
- 至少两个口径可比项目重复且反例已检查，才形成规则候选；
- 不自动写入稳定声音档案。

Judge：状态分层、版本字段与禁止因果声明的确定性检查。

## Case 20：明确文章类型直接路由

分别输入技术 How-to、项目事故复盘、管理决策报告和观点评论请求。

检查：

- 技术 How-to 路由 `how-to`，要求前置条件、可运行步骤和验证；
- 事故复盘路由 `case-retrospective`，区分当时已知与事后信息；
- 管理报告路由 `formal-report`，明确决策者、建议 owner、期限和验收；
- 观点评论路由 `argument`，要求 thesis、最强反方和边界；
- 明确请求不展示文章类型菜单，也不重复追问用户已经提供的信息。

Judge：route/family 关键词确定性断言，加结构适配语义 Judge。

## Case 21：模糊请求只问一个分叉问题

Prompt：「帮我写一篇关于 AI 教育的文章。」

检查：

- 不直接写正文；
- 不一次询问体裁、字数、平台、语气、读者和素材；
- 只问一个能区分 reader job 的问题，例如形成判断还是完成操作；
- 不提前假定研究解释、观点评论或教程。

Judge：首轮问号/问题数量的 script Judge，加路由语义 Judge。

## Case 22：混合类型保持一个主 Family

Prompt：「把我们这次支付事故复盘写成公众号文章，并带一点我的个人经历。」

检查：

- 主 family 是 `case-retrospective`；
- `newsletter-platform` 只负责渠道适配，个人叙事只作为授权材料；
- 主流程保留时间线、当时信息、决策、结果和教训边界；
- 不因公众号渠道改成营销漏斗，不因个人经历改成虚构故事。

Judge：主/辅 family、事实边界和流程节点的确定性断言。

## Case 23：非文章 lifecycle 路由

Prompt：用户要求比较去 AI 味工具或训练声音档案，明确不写文章。

检查：

- route 使用 `article_family: not_applicable`；
- 直接进入 `tool-select`、`train-voice`、`evaluate-voice`、`personal-context` 或 `post-publish`；
- 不展示文章类型菜单或要求选择文章 family；
- 保留对应的许可证、隐私、授权和写权限门禁。

Judge：route 字段和禁止文章问卷的确定性断言。

## Case 24：Deep 独立审查状态

Prompt：高风险文章请求 deep workflow，但没有获得授权的隔离 reviewer。

检查：

- 输出 `independent_review.status: not_run` 和具体原因；
- 不将同一 Agent 的读者模拟描述为独立审查；
- 隔离 reviewer 存在时，输入只包含终稿、目标读者、任务问题和必要 rubric；
- reviewer 不获得额外写权限、外部发送权限或私人档案。

Judge：状态字段、权限边界和禁止 claim 的确定性断言。

## Claim ceiling

上述用例通过，只能证明 Skill 在固定 fixture 上具备本地流程行为，不能证明发表效果更好、能够普遍检测 AI，或能忠实还原所有作者和渠道的声音。后者需要真实作者 A/B 使用和读者结果。

## 运行分组

- `routing-smoke`：路由、裸主题、声音跳过和只读边界；低成本、优先回归。
- `evidence-regression`：相关性/因果、Humanizer 不变量、Deep 证据链、独立审查与编辑质量；该组用例统一 `timeout_seconds: 300`。
- `docs-regression`：How-to、Reference、Explanation 的技术真值与 `not_run` 披露。

分组通过 `--include-case-name`（可多次传参、支持 glob）选择：

```sh
# routing-smoke
skill-up run evals/eval.yaml --include-case-name 'routes-*' \
  --include-case-name nonarticle-lifecycle --include-case-name copywriting-route \
  --include-case-name depth-quick-revise --include-case-name voice-profile-skip \
  --include-case-name audit-does-not-rewrite --include-case-name source-grounded-tool-routing \
  --include-case-name personal-context-no-write

# evidence-regression
skill-up run evals/eval.yaml --include-case-name 'post-publish-*' \
  --include-case-name rejects-causal-overclaim --include-case-name humanize-preserves-facts \
  --include-case-name deep-editorial-pipeline --include-case-name deep-independent-review-status \
  --include-case-name complete-humanizer-catalog --include-case-name full-article-evidence-chain \
  --include-case-name 'chinese-*' --include-case-name voice-channel-conflict \
  --include-case-name train-voice-provisional --include-case-name dev-edit-before-polish \
  --include-case-name taste-findings-not-visual --include-case-name personal-context-authorized-write \
  --include-case-name bare-topic-fork-two-turns

# docs-regression
skill-up run evals/eval.yaml --include-case-name 'routes-technical-*' \
  --include-case-name docs-truth-param-check
```

## 计划用例的实现映射

上述 24 个计划用例中，以下已落地为确定性评测（均为可断言子集，标注的残差不可子串验证）：

| 计划用例 | 实现 case | 未自动化残差 |
|---|---|---|
| Case 1 完整证据型文章 | `full-article-evidence-chain` | 盲审编辑 Judge（论证与声音质量） |
| Case 6 中文上下文判断 | `chinese-protocol-context-judgment` | 误报率人工复审 |
| Case 7B 渠道冲突 | `voice-channel-conflict` | 文件读取范围哈希 |
| Case 8 声音训练盲评 | `train-voice-provisional` | baseline/profile 会话隔离与 A/B 标签计数 |
| Case 10 技术真值 | `docs-truth-param-check` | 真实 CLI fixture 执行与链接解析 |
| Case 12 二十二条排版 | `chinese-22-rules-hit-and-preserve` | 排版结构与改写后不变量的逐项比对 |
| Case 16 发展编辑先于润色 | `dev-edit-before-polish` | owner 回退路径的执行验证 |
| Case 17 编辑品味 | `taste-findings-not-visual` | 3-7 条 finding 计数与编辑委员会盲审 |
| Case 18 机械脚本 | `tests/test_factual_invariants.py` 单元测试 | 无 |

Case 7A 已由 `voice-profile-skip` 覆盖；Case 20 的四个 family 分别由 `routes-technical-howto`、`routes-incident-retrospective`、`routes-formal-report` 与既有 argument 路由断言覆盖。

## 超出原计划的补充用例（2026-08-27）

| 补充能力 | 实现 case | 断言层级 |
|---|---|---|
| 明确授权后的最小投射写入 | `personal-context-authorized-write` | 文件级：`files_exist` AGENTS.md、`files_not_exist` 私密档案、`file_contains` 必含 unittest；负向拦截授权外推（自行写入跨项目记忆） |
| 裸主题两轮状态机 | `bare-topic-fork-two-turns` | 逐轮：`turn_response_not_contains` 断言首轮无 route card/正文、次轮不回退类型问卷 |
| 无字段泄漏的 post-publish 合同 | `post-publish-no-causal-unprompted` | 与泄漏版同一 judge，验证自发合同词汇（当前 GLM flash 下稳定 FAIL，见 known-issues） |

宿主限流、上下文超时和 Skill 行为失败必须分别统计。没有 `result.json` 或 case-level error evidence 时，不得把运行中进程或部分输出计入 PASS/FAIL。
