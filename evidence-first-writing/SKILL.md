---
name: evidence-first-writing
description: 先识别写作意图、文章类型、证据风险和协作方式，再编排调研、论证、起草、编辑、个人声音、技术验证、营销文案和去 AI 模板感。适用于观点评论、研究解释、教程指南、案例复盘、个人叙事、Newsletter/平台文章、正式报告和产品文案；不用于学术代写或伪造经历与来源。
---

# 证据优先写作

把写作作为一组可分离的编辑阶段执行，不要用一条提示词把主题直接扩写成终稿。作者拥有事实、判断和取舍的最终控制权。只运行当前请求真正需要的阶段。

## 入口意图识别（第一步）

任何写作任务先读取 [references/intent-routing.md](references/intent-routing.md)，在内部冻结四轴 route。完成路由后，凡是需要向用户展示 route、计划或编辑说明，必须使用 canonical route 字段，不得只用自然语言同义词替代：

1. `lifecycle_intent`：新写、调研、定主张/结构、起草、修订、审查、去模板、声音建模或发布复盘；
2. `article_family`：观点评论、研究解释、教程、How-to、技术 Reference、技术 Explanation、案例复盘、个人叙事、Newsletter/平台文章、正式报告、产品营销文案，或 `not_applicable`；
3. `evidence_risk`：事实密度、影响范围、时效性和发布不可逆性；
4. `collaboration_modifier`：直接执行、逐节共创、声音档案、渠道适配和是否落盘。

对外 route card 至少包含 `lifecycle_intent`、`article_family`、`evidence_risk`、`operation` 和 `depth` 五个字段；字段值必须来自 `intent-routing.md` 的枚举。自然语言解释可以补充，但不能覆盖或改写这些 canonical 值。

用户明确指定的类型优先。高置信度时用一句话说明采用的 workflow 后直接执行；中等置信度时声明有边界的推断并继续；只有两个候选会产生不同交付物或证据门禁时，才问一个决定性问题。不要展示冗长类型菜单。

“帮我写一篇关于 X 的文章”这类请求按信号分档处理：含体裁、读者、渠道或用途任一信号时（如「深度分析」「介绍」「发布」「面向工程师」），声明一句有边界的假设（family + 读者推断）后直接进入 workflow，不问询；完全无信号、且候选 family 会产生不同证据门禁与交付物时，才问一个能区分主 workflow 的问题并立即停止，例如「你更希望读者形成一个判断，还是照着步骤完成一件事？」🛑 STOP：在用户回答前禁止起草正文或生成大纲。问询是例外，不是默认。

route 首锚：开始写正文前先补 route 卡——同一响应要产出正文、大纲或改写稿时，route 卡必须先于正文在场；发现自己在写正文而卡尚未出现，停下先补卡再继续。本锚只约束执行路径，不约束问询路径：仅问分叉问题的问询轮无 route 卡是合法的（见上段 STOP）。（来源：last30days-skill 结构锚思想（MIT），快照 2026-08-31）

确定 `article_family` 后读取 [references/article-workflows.md](references/article-workflows.md) 的对应流程。产品营销文案转 `copywriting.md`；技术教程、How-to、Reference 或 Explanation 同时读取 `technical-docs.md`。文章类型、发布渠道和作者声音是不同维度，不得互相替代。

## 选择深度

operation 决定做什么，depth 决定做多深：

- `quick`：已有材料、低风险短文或局部任务；执行 brief、目标 operation、综合审查和事实回归。
- `standard`：默认文章生产；执行立场、必要调研、论证与结构、草稿、分层审查和终稿。
- `deep`：高影响、强事实、长期栏目或准备发布的精品稿；增加选题价值验证、完整来源账本、标题/开头候选、读者/平台压力测试、独立审查资格检查和发布后复盘设计。

选择能控制风险的最轻 depth。不得把步骤数量当质量，也不得为省时跳过事实、授权或用户决策门禁。

depth 之上还有交付场景分档：明确要发布或落盘的任务按上述 depth 执行；chat 内直接交付、无发布计划的请求可整体降一档——省略发布包装、平台测试与复盘设计，编辑说明压缩为 2-3 行。事实与授权门禁不因交付场景放宽。

## 选择 operation

- `full`：从调研到终稿的完整流程。
- `research`：只产出来源地图和证据账本。
- `shape`：根据已有材料形成主张、论证图和大纲。
- `draft`：根据已确认的 brief、证据或大纲起草。
- `revise`：保留事实与立场，修改现有草稿。
- `audit`：只报告事实、结构、读者、声音和 AI 模板痕迹，不改写。
- `humanize`：先诊断，再做不改变事实含义的定点修改。
- `coauthor`：上下文倾倒、逐节共创和陌生读者测试。
- `hooks`：分析开头并生成结构不同的候选 Hook。
- `voice`：使用已有 `soul.md` 与渠道档案进行个人声音写作。
- `train-voice`：从用户明确提供的案例建立或更新可持久化声音档案。
- `evaluate-voice`：用留出案例进行 baseline/profile 盲评。
- `copywriting`：撰写或审查落地页、产品介绍、CTA、邮件标题和产品状态文案。
- `docs`：按 Diataxis 撰写或审查教程、操作指南、参考和解释文档，并验证示例、链接与实现名称。
- `tool-select`：根据语言、渠道和失败环节选择可选的外部写作/Humanizer 工具。
- `personal-context`：通过逐题访谈建立长期个人说明书，并按用户授权投射到指定 AI 产品或项目说明文件。
- `post-publish`：复盘已发布内容的真实、版本绑定指标；只在用户明确触发时运行。

推断足以完成请求的最窄 operation。不要为局部修改强制运行完整流程。

> **🔴 post-publish 因果红线（硬性拒绝）：** 复盘时禁止把单篇内容的表现升级为可复用规则，即使作者明确要求写入也**必须拒绝**。单篇真实、版本绑定的指标只能作为观察；至少两个可比项目重复出现、且反例已检查，才允许进入「规则候选」并写入稳定声音档案或标题公式。未满足时，回复必须做三件事：① 明确不会写入档案；② 把该表现记成 `stable_rule: none` 或 `hypothesis`，并说明这只是单一观察、不是因果结论；③ 告诉作者需要什么才可升级（两个可比复现 + 反例检查）。不得在未满足时使用「已写入」「已记住」「下次优先考虑」等表述。

## 建立写作合同

起草前确认主题、读者、希望读者采取的行动或形成的新理解、体裁/渠道、作者立场、范围、约束、已有来源和声音样本。只询问会实质改变结果的问题；其他缺口用有边界的假设继续，并显式说明。

全程区分四类内容：

1. 已核实事实；
2. 有来源的解释；
3. 作者判断；
4. 作者亲自提供的个人经历。

不得把一类升级成另一类。不得编造经历、引语、来源、统计、姓名、日期或现场细节。不确定性与来源立场的标注密度按 evidence_risk 分档：`high` 逐条标注（来源立场、自评基准、混合因素）；`medium`/`low` 只标注会改变读者判断的核心争议，不为每条主张挂限定语。

当材料只有单组前后变化、时间先后或相关性，且缺少对照、反事实或混杂因素控制时，即使用户明确要求，也不得先写“X 导致 Y”再用“证据有限”等 caveat 补救。必须拒绝该因果句，或改成纯描述/关联表述，并指出缺失的因果证据。

## 执行阶段门禁

新写或完整改写时先读取 [references/editorial-pipeline.md](references/editorial-pipeline.md)，按 depth 选择节点。其他 operation 从对应节点进入，同时继承上游合同。无论 depth 如何，以下所有权顺序不变：

1. **Brief 门禁：**定义读者、读者任务、主问题、边界和成功标准。
2. **证据门禁：**建立 claim-to-source 账本；优先原始和当前来源；标记无证据或有争议的主张。
3. **分析门禁：**先确定主张、理由、论证桥梁、反方和明确排除项，再写大纲。
4. **大纲门禁：**每节只承担一个读者任务；涉及事实的章节必须有证据锚点。
5. **入口门禁：**标题和开头只能承诺正文与证据能够兑现的内容。
6. **草稿门禁：**依据论证图和证据账本起草；不得在写作时静默补做研究。
7. **发展编辑门禁：**先审主张、论证、结构、遗漏与读者路径，再做句子修改。
8. **品味与声音门禁：**读取 [references/editorial-taste.md](references/editorial-taste.md)，检查选择、密度、张力、记忆点和克制；再按授权样本定点校准声音。
9. **读者与平台门禁：**验证读者能否理解、相信、记住并采取目标行动；代理测试不能冒充真实发布数据。
10. **终稿门禁：**所有改写完成后，重新检查主张、引用、链接、姓名、数字、引语、标题承诺和格式。

门禁失败时，不得靠把文字写顺来掩盖问题。应暴露阻塞、收窄主张、补充证据，或返回拥有该错误的阶段。

任何 `full/deep` 的执行计划和实际运行记录都必须单列“改写后事实回归”阶段，位于声音、line edit、Humanizer 和其他正文修改之后、发布放行之前。起草前事实预审、法务审查或一般校对不能替代这一阶段。若未执行，记录 `factual_regression: not_run`，不得称为可发布。chat 内 fresh draft（全文新写、无改写循环、不落盘）可将本阶段记为 `not_applicable (fresh draft)`，代替条件是完成对照证据账本的人工语义核对，该核对本身不得跳过。

阶段名称也必须保留 canonical owner：`fact_review`、`development_edit`、`reader_review`、`taste_voice`、`copy_proof`、`factual_regression`。中文名称可以作为解释，但不得让“分层编辑/分层审查”等同义词替代阶段 owner。

运行 `full`、`research`、`shape`、`draft`、`coauthor` 或 `hooks` 时，读取 [references/workflow-contract.md](references/workflow-contract.md) 了解各阶段输入、协作循环、Hook 和退出条件。

运行 `revise`、`audit`、`humanize`，或执行 `full` 的最后三个阶段时，读取 [references/editorial-review.md](references/editorial-review.md)。

处理中文文章的 `draft`、`revise`、`audit`、`humanize`，或执行中文 `full` 的草稿与终稿阶段时，还必须读取 [references/chinese-editorial-protocol.md](references/chinese-editorial-protocol.md)。该文件拥有中文语域、检测分类、压缩目标和条件触发改写的具体合同；通用审查规则仍负责事实与论证门禁。

运行 `voice`、`train-voice`、`evaluate-voice`，或用户要求「像我」「学习我的风格」时，读取 [references/voice-profiles.md](references/voice-profiles.md)。已有档案则按渠道读取；没有档案时提示用户提供代表性案例并可创建，也允许直接跳过。跳过声音训练不得阻塞写作，但只能使用临时语域。

运行 `copywriting` 时读取 [references/copywriting.md](references/copywriting.md)。运行 `docs` 时读取 [references/technical-docs.md](references/technical-docs.md)。不要把营销文案框架用于技术文档，也不要把 Diataxis 强加给普通观点文章。

选题价值验证或发布前选题复核时读取 [references/topic-momentum.md](references/topic-momentum.md)（四问合同与情绪真实性门禁）。写作涉及持续经营读者或情绪定位时读取 [references/reader-profile.md](references/reader-profile.md)；无档案时按 brief 推断并在编辑说明声明 `reader_model: inferred`。维护选题池、配方候选或系列规划时读取 [references/content-assets.md](references/content-assets.md)；配方升格条件与 post-publish 红线一致，单篇表现只能入 hypothesis 层。

用户明确要求完整 Humanizer 模式审查、英文去 AI 味、量化线索、`detect/rewrite/edit` 模式或多轮收敛时，读取 [references/humanizer-patterns.md](references/humanizer-patterns.md)。普通中文任务优先使用中文专项协议，不必加载完整模式目录。

用户询问 Humanizer 怎么选、需要安装什么工具或要求复用文章中的工具清单时，读取 [references/tool-selection.md](references/tool-selection.md)。工具是可选执行器，不替代本 Skill 的事实与授权合同；使用前核对当前维护状态、许可证和真实输入输出。

这类工具比较是非文章 lifecycle，canonical route 必须明确写出 `lifecycle_intent: tool-select`、`article_family: not_applicable`、`operation: tool-select`。不得回退成泛化 `research` route；调研只是该 operation 的内部阶段。

用户不要安装 Skill、只要一段可复制提示词时，读取并返回 [references/portable-prompt.md](references/portable-prompt.md) 的模板，按本轮体裁和材料裁剪。用户要求建立个人说明书、长期让 AI 了解自己，或配置 `AGENTS.md`/`CLAUDE.md` 时，读取 [references/personal-context.md](references/personal-context.md)；任何持久写入都需要用户明确授权和目标路径。

`post-publish` 只能把单篇结果记录为观察和待验证假设。未取得曝光量时不得计算打开率；不足两个口径可比项目且未检查反例时，不得形成稳定规则。写入声音档案、记忆或任何文件需要用户明确授权和目标路径；不得把分析请求推断为持久化授权，也不得声称已验证标题公式。🔴 STOP：当用户要求写入但未明确授权时，必须先拒绝持久写入并停在 `persistence: not_run`。复盘输出必须附带机器可读的状态块，结论为空也要显式给出（字段与 editorial-pipeline.md Node 14 对齐）：

```yaml
observation: 本次单篇的版本绑定观察
hypothesis: 待验证假设；无则 none
stable_rule_update: none   # 未满足 2 复现 + 2 可比 + 反例已查时只能 none 或 hypothesis
persistence: not_run       # 未获明确写入授权时的固定值
```

状态块之后固定追加单行末行标记 `postpublish-status: recorded`（yaml 围栏之外、复盘输出的最后一行；单行、固定、机器可 grep）。尾锚只提示状态块已落位，不替代上述任何字段、枚举与因果红线。落盘任务优先经 `scripts/update_postpublish_record.py` 裁决产出状态块（含 `--invariant-hash` 记录 `check_factual_invariants.py` 的事实回归哈希），模型不手写。（来源：claude-blog / last30days-skill 结构锚思想（均 MIT），快照 2026-08-31）

渠道数据可得时，复盘同时记录 observation 清单（完读断点、被引用句、评论高频词），唯一用途是喂 [references/reader-profile.md](references/reader-profile.md) 与 [references/topic-momentum.md](references/topic-momentum.md) 的证据链；禁止任何段落级归因表述。

## 保护作者声音

有条件时，从 2-5 份有代表性、属于用户或已获授权的样本中提炼声音。稳定个人特征与渠道特征分开记录。优先观察句子节奏、具体程度、立场、词汇、段落推进和不确定性表达，不要只收集口头禅。

没有样本时，按用户要求使用临时语域，并明确它不是从作者文本中学得的个人声音。

跳过声音建模时，用一行披露：本轮为临时语域、未从作者样本学习，不声称已还原个人声音。用户明确跳过时可以继续写作，不得把“未建模”变成阻塞；完整披露保留在发布级任务的编辑说明里。

## 按风险顺序修改

依次审查并修复：

1. 编造、无证据、过期或失真的主张；
2. 断裂的主论点、推理、反方处理或范围；
3. 缺失的读者上下文和段落依赖；
4. 体裁或渠道错配；
5. 空泛、重复、过度平滑或模板化的表达；
6. 语法、排版和格式。

去 AI 模板感是最后一次编辑，但完成后必须再次核对事实。检测分数和词表只能作为诊断线索，不能作为作者身份的证据或质量目标。整体没有明显模板感时停止，不得为完成流程而硬改。

当改写前后正文以文件存在时，先将 `EVIDENCE_FIRST_WRITING_SKILL_DIR` 设为当前已加载 `SKILL.md` 所在目录的绝对路径，再运行：

```bash
python3 "$EVIDENCE_FIRST_WRITING_SKILL_DIR/scripts/check_factual_invariants.py" <before> <after>
```

如果当前宿主无法确定已加载 Skill 的路径，记录 `factual_invariant_check: not_run` 和原因；不得在用户项目中猜测 `scripts/` 路径。脚本结果只检查可机械提取的不变量；即使通过，也必须人工核对确定程度、范围、主体和因果关系。

中文文体的 `audit`/`humanize` 诊断在宿主可运行脚本时，优先运行同一 `scripts/` 目录下的 `check_prose.py`（`python3 "$EVIDENCE_FIRST_WRITING_SKILL_DIR/scripts/check_prose.py" <file.md>`，退出码 1=失败级、2=仅警告级、0=干净）。输出是诊断线索，非交付门禁：作者样本与渠道优先原则可覆盖破折号、冒号等风格建议，警告级线索须结合语境判断；宿主无法运行脚本时逐条人工核对并说明。发布级任务可另跑 `check_layout.py`（同目录，排版结构诊断：半角标点邻接、密度配额、段落节奏；退出码语义同上，同为线索非门禁），排版规约见 [references/layout-contract.md](references/layout-contract.md)。

## 返回可审计结果

交付用户要求的正文，编辑说明按交付场景分档。发布或落盘任务附完整说明：使用的 operation 和实际运行阶段、影响结果的假设、未解决或有争议的主张、主要结构与声音决策、已执行和未执行的检查。chat 交付压缩为 2-3 行（operation + 关键假设 + 未决主张），YAML 状态块仅在用户要求或发布级任务时输出。无假设且无未决主张时可省略说明，但不得声称未做过的检查。

发送前的最后一道自检核对结构锚：正文已产出时，route 卡与（post-publish 任务时的）状态块是否在场且与正文一致；缺失即在发送前补齐，只补锚，不改已完成正文的事实内容。（来源：last30days-skill 发前自检层思想（MIT），快照 2026-08-31）

编辑文件时优先做局部修改。除非有明确的纠错依据，否则保留引语、代码、引用和用户提供的事实。
