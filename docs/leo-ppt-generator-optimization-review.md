# leo-ppt-generator 优化建议（最终版）

- 日期：2026-08-27
- 范围：`leo-ppt-generator/` 技能包全量（SKILL.md、references、prompts、evals、tests、patches、runtime 声明面）
- 方法：三源证据交叉——(1) 本日 14 个 iteration 的 skill-up 实测（12 用例套件、判官 v2、单测 5/5）；(2) 全包内容一致性审查（矛盾/死引用/漂移/缺口/脱节五类，证据带 `文件:行号`）；(3) 全网调研（Anthropic 官方 Skill 编写最佳实践、PPTAgent/PPTEval 领域基线、Office 文档安全行业实践、Agent 评测方法学）。
- 结论速览：核心合同设计在业界对照下站得住甚至领先；剩余债务集中在**内容审查发现的合并遗留**（1 个[高]项）与**评测尚未回灌的新合同**；对被评模型（glm-5.3-flash 代理）的一切"继续加文本强化"类提案已被实测否决。

## 0. 优先级矩阵

| 档位 | 提案 | 一句话理由 |
|---|---|---|
| 立即采纳 | A1 判官-合同互斥修复（handwritten 披露行） | P1 修复引入的真 bug，两轮证据可验 |
| 立即采纳 | A2 upstream-capabilities 死引用清理 | 唯一[高]项：能力审计在包内不可复核 |
| 立即采纳 | A3 文档一致性修复包（矛盾+漂移+悬空指针） | 全部低风险纯文档修正，证据齐 |
| 建议采纳 | B1 Gate 0 块位置与歧义固定块判官断言 | 合同忠实原则的既有遗漏 |
| 建议采纳 | B2 轨迹级评测（transcript 工具调用断言） | 把 control-plane 失败根因变成可测信号 |
| 建议采纳 | B3 codex 侧 patch 0003/0005 聚焦回归落地 | 0004/0006 模式已验证可复制 |
| 待确认 | C1 SKILL.md description 精简 | 安全语义冗余 vs 官方 token 建议，需拍板 |
| 待确认 | C2 死引用 proof 的"标注 vs 落地"路线 | 成本差异大，需拍板 |
| 暂缓 | D1 execute 层深化评测（setup/backend create 链） | 模型基线未达标前性价比低 |
| 暂缓 | D2 PPTEval 式产出质量评测 | 依赖真实 provider，成本高 |
| 否决 | E1 任何继续加 SKILL.md 文本强化的提案 | iter-5 三处强化 + S6/S7 工具豁免均零行为变化 |
| 否决 | E2 放宽 Gate 0（引入沙箱/净化恢复路径） | 与微软 MOTW/ACSC 立场相悖，评测证明 fail-closed 正确 |
| 已排队 | F1 官方 Claude 模型全量跑 | 两类模型缺口的最终裁决，known-issues 待办第一位 |

## 1. 执行 workflow 节点图

```text
N1 Gate 0 Office 信任 ──blocked──> 终止（固定块）
N2 交互模式门禁 advise|execute
N3 控制面五字段合同（所有非纯内容回复）
N4 输入路由（generate | direct-editable | upgrade-full | upgrade-selected）
N5 首次准备（launcher → setup → config/Provider 三态）
N6 Backend 选择（registry contract、capability 过滤）
   ├── N7 generate 主链：内容合同→大纲→逐页稿→视觉方向→backend→样张
   │      →image prepare→worker 派发→image record→五层质量门→assemble→复验
   ├── N8 editable 主链：规范化→editable prepare→next 循环→dispatch→record
   │      →finalize→对象级质量门
   └── N9 upgrade 链：baseline 冻结→按 direct-editable 处理→partial-hybrid 确认门
N10 worker 派发纪律（多页必真 worker；单页需 CLI single_unit_current_agent_allowed）
N11 恢复（checkpoint / idempotency / cancel terminal / cleanup dry-run）
N12 交付合同（status=completed ≠ 交付；delivery_readiness=accepted 才闭环）
横切：N13 评测体系（12 用例 + 判官 + model_gating 分层）
      N14 确定性工具链（leo-ppt CLI、_vendor、patches、boundary 单测）
```

各节点实测状态：N1/N4/N9/N12 判定稳定 PASS；N3 是模型能力区分器（13 点 12F）；N7 的确认门存在恒定失守（confirmation-gates 2/2）；N5/N6/N11/N8 的 execute 段尚无 agent 层评测覆盖（CLI 确定性面有单测）。

## 2. 逐节点分析（现状 → 证据 → 提案 → 对抗性审查 → 裁决）

### N1 Gate 0 Office 信任

- **现状**：来源未确认的 PPT/PPTX 立即固定块阻断（`untrusted_office_input`），禁止读取/扫描/净化；"警告后继续""净化后继续"均不构成授权。
- **证据**：2 个用例恒 PASS（iter-1 起零失守）；`--fixed gate0` 模式不读文件，机器化输出。
- **行业对照**：微软对互联网来源宏默认阻断（MOTW），ACSC 建议组织级限制宏——本技能 fail-closed 与行业一致甚至更严；"拒绝净化即恢复"有依据（宏可藏于嵌入对象/external relationship，净化不重建信任）。
- **对抗性审查**：反方——行业存在"沙箱+扫描后继续"的服务端流水线，是否过于保守？正方——本技能运行于本地 agent 环境，威胁模型不同；且 2 用例证明模型执行良好，改动只会引入风险。
- **裁决**：维持现状，否决 E2。遗留小项见 B1（块位置合同未断言）。

### N2 交互模式门禁

- **现状**：advise 禁工具/禁读 reference/禁建 run；混合请求以 advise 为准；P1 已补 `--fixed` 渲染唯一工具豁免与 `worker_render: handwritten` 降级披露。
- **证据**：mixed-advise 用例首轮 PASS；但 S6/S7（iter-11/12）证明工具豁免修复零行为变化（transcript 零工具调用）。
- **对抗性审查**：反方——豁免文本是否白写？正方——合同正确性独立于当前模型是否遵守（换模型即生效），且修复成本已沉没。反方——是否还要加"advise 必须首行声明"到 advice-only 用例？正方——mixed 用例已断言该合同，advice-only 不必重复。
- **裁决**：文本侧封笔（E1）；豁免保留待官方模型验证。

### N3 控制面五字段合同

- **现状**：五字段块必须最前（至多 `interaction_mode:` 一行在前），固定块必须脚本渲染。
- **证据**：13 点序列 12F/1P，失败形态稳定（叙述先行、零工具调用、意图正确）；泄漏间歇（6/13）。
- **发现（审查）**：**P1 引入互斥**——若模型按合同把 `worker_render: handwritten` 披露行放在五字段块之前，判官 `judge_control_plane_fields.py:36` 只容忍 `interaction_mode:` 一行在前，会误判 FAIL。
- **提案 A1**：SKILL.md 明确披露行置于五字段块**之后**（判官无需放宽，值域合同不受影响）。
- **对抗性审查**：反方——为何不改判官容忍两行元数据？正方——位置合同越严越可测；披露行放块后不损失任何语义，改判官反而弱化合同。反方——会不会又有模型把披露放前面？正方——那本就该 FAIL（位置违约），判官行为正确。
- **裁决**：采纳 A1（一句话合同修正，立即）。

### N4 输入路由

- **现状**：四 route 有限枚举、扩展名白名单、内容+视觉稿并存必须单问。
- **证据**：ambiguous、mixed-advise 均 PASS；审查确认链接与命令树一致。
- **发现（审查）**：SKILL.md:70-73 要求歧义场景先原样输出两行固定块（`严格保留布局: direct-editable` / `仅作风格参考: generate`），但 `judge_ambiguous_route.py` 只查 route 名，未断言固定块。
- **裁决**：节点本身维持；断言缺口并入 B1。

### N5 首次准备与 Provider

- **现状**：launcher→setup→config 三态（`configured_unverified` 可开工）；凭据只走引用；首次流程最多两问。
- **证据**：configured-unverified 用例恒 PASS。
- **发现（审查）**：**两问上限口径冲突**——first-use.md:74 的"最多两个问题"与 image-deck-workflow 的五重确认（大纲/逐页稿/视觉方向/backend/样张）按字面冲突，未界定"首次流程"仅指 setup 阶段。
- **提案（并入 A3）**：first-use.md 澄清"两问上限仅覆盖 setup/config 阶段，内容与样张确认门不受此限"。
- **对抗性审查**：反方——是否该统一成一个确认模型？正方——过度设计；两个阶段语义本就不同，一句话划界即可。
- **裁决**：采纳（文档修正）。

### N6 Backend 选择

- **现状**：registry 唯一创建 contract、capability 过滤、mask 约束。
- **发现（审查）**：三处存放口径不一（`./backend.json` 示例 vs `contracts/` vs `<run>/input/backend-contract.json`），可解释但未写明；`config provider select` 与 `config provider auto/prefer/reorder` 两族命令互不交叉说明。
- **对抗性审查**：反方——这算矛盾吗？三处可能各指创建/冻结/消费三个时点。正方——正因可解释才更要写明，否则执行 agent 会各按各的理解。命令族同理：若无区分说明，模型在恢复场景可能调用不存在的命令。
- **裁决**：并入 A3（backend-selection.md 补一句"创建于 contracts/、冻结副本入 run input/"；first-use.md 或 reason-codes.md 交叉注明两族命令的使用场景）。

### N7 generate 主链

- **现状**：12 步 + 五层非补偿质量门 + 对抗式视觉 QA（借鉴 OfficeCLI 渲染-截图-对抗审查与 PPTAgent `inspect_slide`，与文献一致）。
- **证据**：confirmation-gates 用例 2/2 失守——模型拒绝杜撰（好）但在授权压力下承诺"样张由我定、不再打断"（违反"跳过样张仍不能跳过"硬合同）。
- **行业对照**：PPTAgent v2（EMNLP 2025，3.7k★）走"反思式编辑"路线，PPTEval 以 Content/Design/Coherence 三维评估产出；本技能质量门设计更严，但评测只测行为不测产出质量。
- **对抗性审查**：反方（针对"再加文本反例"）——first-use.md 已明文"用户要求跳过样张时仍不能跳过"，模型仍违反；再加文本已被 E1 证据否决。反方（针对"补 PPTEval 式产出评测"）——需要真实 provider 出图，被评模型又卡在入口层，投入产出极差。
- **裁决**：失守由用例持续测量 + F1 官方模型跑裁决；产出质量评测列 D2 暂缓。

### N8 editable 主链 / N9 upgrade 链

- **现状**：manifest 权威、full-slide-raster-overlay 禁令、partial-hybrid 确认门。
- **证据**：partial-hybrid 用例 PASS（判官去假阳性后）；0004/0006 聚焦回归 5/5。
- **发现（审查）**：reason-codes.md 的恢复路径引用未定义命令（`upgrade propose/confirm`、baseline `inspect/import-baseline` 不在任何命令树中）；worker 返回合同三处口径不齐（execution-contract 说返回 agent id/reason code，两个 worker prompt 的返回清单都没有这些字段）。
- **对抗性审查**：反方——恢复命令可能是 CLI 实际存在但文档漏记？正方——即使 CLI 有，references 是 agent 唯一可见的命令真相源，黑盒即缺陷；应核实 CLI 后或补文档或改指向已定义命令。worker 返回合同同理：父 agent 按 execution-contract 期望的字段去解析 worker 返回会落空。
- **裁决**：并入 A3（核实 CLI 实际命令面后统一三处文本；worker 返回字段对齐是行为合同变更，列入 A3 的"需核实"子项，不做臆改）。

### N10 worker 派发纪律

- **现状**：多页必真 worker、不得串行替代、单页需 CLI `single_unit_current_agent_allowed`。
- **证据**：missing-multi-page-workers 恒 PASS（但判官为子串级弱断言）；single-page 首轮 PASS。
- **对抗性审查**：反方——把 missing-multi-page-workers 判官升级到块级断言？正方——忠实合同原则支持；但它大概率变成第二个恒定 FAIL。裁决：可升级，必须同步打 `model_gating` 标签（B1 范围内可选项，优先级低于 Gate 0 断言）。
- **裁决**：维持节点；判官升级列为可选。

### N11 恢复 / N12 交付合同

- **证据**：delivery-acceptance-pending 恒 PASS；恢复机制（checkpoint/idempotency/cleanup）无 agent 层评测，属 execute 空白（D1 范围）。
- **裁决**：维持现状，随 D1 一并暂缓。

### N13 评测体系

- **现状**：12 用例、判官 v2（位置+值域+反伪造+泄漏红线）、model_gating 语义分层、判官离线回归、FAIL 人工复核实践。
- **行业对照**：与 OpenAI "deterministic first + rubric"、Langfuse 共识栈一致；"把失败变成测试"已实践（confirmation-gates 即真实失守转化）；**轨迹评测（trajectory evaluation）是公认维度而本套件缺失**；判官人工校准已有实践未模板化。
- **提案 B2**：新增轨迹断言判官——对 control-plane 用例断言 transcript 中 `render-control-summary` 调用次数（0 次 = 未走脚本路径），把"为什么失败"从推测变成测量。
- **对抗性审查**：反方——依赖 skill-up 内部产物格式（stdout.json 结构），harness 升级会脆断。正方——断言取宽松形式（grep 计数而非 JSON 解构），并在判官注释标注 harness 依赖；脆弱性风险可接受。反方——人工校准模板化是否官僚化？正方——known-issues 已在这么做，模板化只是把既有实践显式化，一行一条。
- **裁决**：B2 采纳（中优先）；校准模板并入 known-issues 惯例（低优先）。

### N14 确定性工具链

- **现状**：boundary 单测 5/5（0002/0004/0006 已落地）；codex 侧 0001/0003/0005 deferred（诚实登记）。
- **发现（审查）**：patch 0001 归属矛盾——patches/README 把 test_vendor_state 认领给 0001，core-tests.yaml 把同一测试记为 0002 合同且声明 codex 套件"包内无可执行用例"；`test_registered_vendor_patches_apply_to_pinned_source_worktrees` 全仓无定义。
- **提案 B3**：按 0004/0006 已验证模式为 patch 0003（assembly fidelity）与 0005（chroma-key hint）写包内聚焦回归，codex 套件出 deferred 账。
- **对抗性审查**：反方——codex 侧 vendor 代码是否像 editable 侧一样可隔离导入？正方——0004/0006 模式（sys.path + mock 外部依赖）通用，风险在导入面，先做可行性 spike 再承诺。反方——0001 归属怎么解？正方——以 core-tests.yaml 为准（它逐字登记合同），patches/README 改为指认 0002 并澄清 0001 的证明方式。
- **裁决**：B3 采纳（中优先，先 spike）；0001 归属修正并入 A3。

## 3. 横切提案详情与对抗性审查

### A2 · upstream-capabilities.yaml 死引用（唯一[高]项）

- **发现**：12 个 proof/proof_case 指向包内不存在的测试文件（`upstream-capabilities.yaml:27,30,33,42` 等），盘上 `tests/` 仅 boundary 两个文件。作为随包分发的能力审计文件，全部 proof 不可复核。
- **对抗性审查**：反方——这些 proof 可能属于开发仓，文件本身没错。正方——正因如此才必须标注（"开发仓 proof，包内不可复跑"），否则审计文件自证失效。修复路线二选一：(a) 标注来源 + 不可复核声明（低成本，立即）；(b) 逐步在包内落地 proof（高成本）。
- **裁决**：路线 (a) 立即执行；(b) 作为长期项与 B3 合并推进。**路线取舍需确认（C2）**。

### C1 · SKILL.md description 精简（待确认）

- **发现**：frontmatter description 数百 token，远超官方"~100 token"建议与 agentskills.io 规范；但其中承载 Gate 0 负触发语义（"来源未知仍触发但必须立即阻断"）。
- **对抗性审查**：正方（精简）——description 是常驻上下文成本，官方建议放 body；安全语义在 body Gate 0 首节已完整存在。反方（保留）——宿主触发决策只看 description；若负触发词缺失，携带恶意 PPTX 的请求可能根本不激活技能，Gate 0 形同虚设。这是**安全冗余 vs token 成本**的真实权衡，且 evals 无法测量"不触发"场景（skill-up 前提是已触发）。
- **裁决**：**待用户拍板**。若精简，保留负触发关键词句、只剥离实现细节；若保留，接受与官方建议的偏离并在 README 记录理由。

### X · 文档一致性修复包（A3 明细）

全部为低风险文本修正，证据来自审查报告：

1. manifest-schema.md:65,78,363 与 page-decision-tree.md:249 指向 SKILL.md 不存在的章节名（上游合并遗留）→ 改指现行章节。
2. "36 视觉风格"→ 实际 35（style-library.md:29、设计体系.md:45,78）。
3. style-library.md:39 的 05 轴计数 4→3（剔除 `00_合并映射.md`）。
4. slide-worker.md:32-33 的 `upstream --backend-contract ... codex-ppt` 语法与 execution-contract.md:23 统一。
5. patches/README.md 的 0001 聚焦回归归属改为 0002（与 core-tests.yaml 对齐）。
6. 按需读取表补 `execution-contract.md` 与 `cli-helper.md` 的可达性（表与正文一致）。
7. reason-codes.md 恢复命令与 CLI 实际命令面核实后统一；worker 返回合同三处对齐。
8. first-use.md 两问上限划界（见 N5）。
9. backend contract 存放三口径写明关系（见 N6）。

**对抗性审查**：反方——一次改 9 处会不会引入新漂移？正方——每处都有行号级证据且互不依赖；但第 7 条涉及 CLI 实际命令面，必须先核实再改，不臆改。

## 4. 对抗性审查汇总（被否决与被暂缓的提案及理由）

| 提案 | 反方最强论证 | 裁决依据 |
|---|---|---|
| E1 继续加 SKILL.md 文本强化 | 合同已三处强化仍 12F；工具豁免修复零行为变化 | 实测边际为零，文本封笔；修复预算转向评测与换模型验证 |
| E2 Gate 0 引入净化恢复路径 | 行业有沙箱+扫描流水线 | 微软 MOTW 默认阻断 + ACSC 立场 + 2 用例恒 PASS；威胁模型不同 |
| D1 execute 层深化评测 | 编排层零覆盖是最大空白 | 被评模型入口层都未稳定遵守；先 F1 换基线再测编排，否则测的是模型下限 |
| D2 PPTEval 式质量评测 | 领域标准做法 | 依赖真实 provider 出图；当前卡在入口层，投入产出差；记为 F1 之后项 |
| 判官全面强断言化 | 会制造更多恒定 FAIL | 忠实合同原则支持强断言，但每个新增强断言必须配 model_gating 标记防回归误读 |

## 5. 最终建议（执行顺序）

1. **立即（低风险，纯修正）**：A1 互斥修复 → A2(a) 死引用标注 → A3 文档修复包（第 7 条先核实 CLI）。
2. **其次（评测增强）**：B1 Gate 0 块位置 + 歧义固定块断言（新用例或判官升级，强断言配 model_gating）→ B2 轨迹断言判官 → B3 codex 聚焦回归（先 spike 导入面）。
3. **拍板后执行**：C1 description 精简与否；C2 proof 落地路线。
4. **维持不变**：Gate 0 立场、四 route 枚举、worker 纪律、交付分层、SKILL.md 文本侧封笔。
5. **持续**：F1 官方 Claude 模型全量跑（一切模型侧结论的最终裁决）。

## 6. 开放问题

- `upgrade propose/confirm`、baseline `inspect/import-baseline` 是否存在于 CLI 实际命令面（决定 A3-7 是补文档还是改指向）。
- codex 侧 `_vendor/codex_ppt` 的可隔离导入性（决定 B3 成本）。
- 官方模型跑通后，confirmation-gates 失守与 control-plane 缺口是否消失（决定是否需要结构性合同改造）。

## 调研来源

- [Anthropic: Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) · [Agent Skills Overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) · [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [agentskills.io Specification](https://agentskills.io/specification) · [obra/superpowers best-practices 汇编](https://github.com/obra/superpowers/blob/main/skills/writing-skills/anthropic-best-practices.md?plain)
- [PPTAgent (EMNLP 2025)](https://arxiv.org/abs/2501.03936) · [PPTAgent GitHub](https://github.com/icip-cas/PPTAgent) · [PPTAgent v2 评测](https://powerpoint.md/skills/pptagent-v2.html)
- [Microsoft: Macros from the internet are blocked by default](https://learn.microsoft.com/en-us/microsoft-365-apps/security/internet-macros-blocked) · [ACSC: Restricting Microsoft Office macros](https://www.cyber.gov.au/business-government/protecting-devices-systems/applications/restricting-microsoft-office-macros)
- [OpenAI: Testing Agent Skills Systematically with Evals](https://developers.openai.com/blog/eval-skills) · [Hebbia: Hybrid Deterministic and Rubric-Based Framework](https://www.hebbia.com/blog/evaluating-ai-agents-a-hybrid-deterministic-and-rubric-based-framework) · [Langfuse: AI agent evaluation engineering](https://langfuse.com/resources/engineering/ai-agent-evaluation) · [AWS: trajectory evaluation](https://dev.to/aws/how-to-evaluate-ai-agents-llm-as-judge-tutorial-4a6h) · [Monte Carlo: LLM-as-Judge best practices](https://montecarlo.ai/blog-llm-as-judge/)
