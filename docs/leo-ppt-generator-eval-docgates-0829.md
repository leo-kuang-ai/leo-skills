# leo-ppt-generator 内容确认文档门 多轮测评报告（2026-08-29）

## 结论

**18 次 case-run（6 用例 × 3 轮）通过 14 次（77.8%）；5 次失败经逐条取证全部归因为同一测评工装局限——叙述前置状态与技能反编造纪律的冲突，0 次语义违规、0 次 judge 误杀。** 文档门语义本身在全部 18 轮中稳定正确：每个回复（含被阻断的）都正确运用 `content/` 路径、`confirmation` 标记与落盘纪律；被阻断回复的 `next_action` 甚至原样复现了恢复条目语义。矩阵中 3 个用例 3/3 满稳（大纲门直出、中断恢复、advise 边界），2 个 2/3 波动，1 个 1/3 不稳（前置状态最重的一个）。

## 测评设计

- **对象**：内容确认文档门落地行为（`docs/plans/2026-08-29-002-feat-leo-ppt-content-doc-gates-plan.md` 的 U1–U4 / R1–R10 / AE1–AE4 / KTD5）。
- **维度×用例矩阵**：D1 大纲门直出（outline-doc-before-confirm）、D2 母版门前置状态（master-doc-before-confirm）、D3 大纲修订回路 v1→v2（outline-revision-doc-gate，新）、D4 确认后修订不重确认（post-confirm-revision-doc-gate，新）、D5 中断恢复（resume-from-content-docs，新）、D6 advise 模式不落盘（advise-mode-no-content-docs，新）。后四个用例本轮新增，随套件永久生效。
- **轮次**：3 轮全家族真实 agent 运行（claude_code 引擎，串行），iteration-34/35/36。
- **指标**：每轮通过率、用例级稳定档（3/3 稳定；2/3 波动；≤1/3 不稳）、失败归因三分法（用例缺陷 / judge 误杀 / 行为缺陷）。
- **已入测的已知风险**：阶段歧义假阴性（iteration-32 教训）、judge 否定感知误杀、前置状态叙述下的文件核查。

## 结果

| 用例（维度） | R1 | R2 | R3 | 稳定档 |
| --- | --- | --- | --- | --- |
| outline-doc-before-confirm（D1 大纲门直出） | ✅ | ✅ | ✅ | 稳定 3/3 |
| master-doc-before-confirm（D2 母版门前置） | ❌ | ✅ | ✅ | 波动 2/3 |
| outline-revision-doc-gate（D3 修订回路） | ❌ | ✅ | ✅ | 波动 2/3 |
| post-confirm-revision-doc-gate（D4 确认后修订） | ✅ | ❌ | ❌ | 不稳 1/3 |
| resume-from-content-docs（D5 中断恢复） | ✅ | ✅ | ✅ | 稳定 3/3 |
| advise-mode-no-content-docs（D6 advise 边界） | ✅ | ✅ | ✅ | 稳定 3/3 |

每轮合计：R1 4/6、R2 5/6、R3 5/6。

## 失败归因（5/5 同根因，均为工装局限）

skill-up 单轮 harness 无前置状态播种能力，D2–D4 用例的"已确认工件"只能以对话叙述虚构。技能落地后的纪律恰恰要求 agent 不信任聊天叙述、只依据磁盘工件推进（"聊天声明不构成完成证据"）。于是每个含前置叙述的用例都存在真实分叉：**agent 核查 → 发现沙箱无此文件 → 按 `input_material_missing`/`contract_error` 正确阻断**；或 **agent 顺着叙述直接产出文档回复 → 通过**。轮间波动即"这一轮是否选择核查"，与行为质量无关：

- [34] master-doc / outline-revision：agent 全盘搜索确认 `outline-v1.md` 不存在，拒绝"反向编一份大纲冒充初稿"，阻断并要求提供文件或路径——其 `next_action`（"落盘 content/outline-v1.md 后从母版阶段恢复"）正是恢复条目的正确执行。
- [35]/[36] post-confirm：agent 执行了 `mdfind`/`run status`/`doctor` 三重核查后以 `contract_error` 阻断，明确引用"不凭对话记忆凭空重建母版"边界。该用例前置状态最重（完整项目+已确认母版），核查动机最强，故最不稳。

**正向证据**：18 轮回复全部正确使用文档门词表（`content/` 路径、`confirmation` 标记、落盘/恢复语义）；3 个满稳用例中，D1（材料内联、无前置虚构）证明直出门行为完全可靠，D5/D6 证明恢复语义与 advise 边界稳定。

## 建议

1. **工装层（根因修复）**：为 skill-up 用例增加前置 fixture 播种能力（在沙箱预置 `content/` 工件），D2–D4 的波动即消失；在此之前，D2–D4 的单轮结果应按"核查分叉"解读，不以单轮失败判定行为回归。
2. **门禁层**：D1/D5/D6 已可作为稳定回归门；对 D2–D4 建议"连两轮取优"或上述 fixture 落地后再纳入硬门禁。
3. **保持 judge 严格**：不因本轮波动放宽断言——阻断型回复是环境与前提冲突的正确产物，不是应放行的目标行为。

## 附：新增用例与登记

- 新增 `evals/cases/{outline-revision-doc-gate,post-confirm-revision-doc-gate,resume-from-content-docs,advise-mode-no-content-docs}.yaml` 与对应 4 个 judge（家族否定感知模板，合成回路 12+ 项正反例预验通过）。
- `evals/eval.yaml` 登记后套件共 30 用例（全量回归时长相应增加）。
- 原始产物：`leo-ppt-generator-workspace/iteration-{34,35,36}/`（git-ignored）。
