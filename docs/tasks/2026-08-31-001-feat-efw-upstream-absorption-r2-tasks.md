---
title: "evidence-first-writing 第二轮上游吸收落地 - Task Pack"
type: "task-pack"
status: "derived"
date: "2026-08-31"
source_plan: "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md"
source_plan_hash: "sha256:d5efb6ae0644403dcb7affff11ec0a5d25647f225c88489e25216c2435ae9a59"
generated_by: "spec-write-tasks"
mode: "derived"
source_sections:
  - "Requirements"
  - "Scope Boundaries"
  - "Key Technical Decisions"
  - "Implementation Units"
  - "Verification Contract"
  - "Definition of Done"
---

# evidence-first-writing 第二轮上游吸收落地 - Task Pack

## Overview

把源方案的 13 个实施单元编译为 15 个任务、5 个执行波次：Wave 1 判官与脚本地基（P0，可全并行）→ Wave 2 独立 references 增补 → Wave 3 依赖研究环证据链的增补与文案组 → Wave 4 行为合同三件套（P2）→ Wave 5 全量回归与记档。同一波次内无共享文件；T010（Wave 2）与 T008/T009（Wave 3）分别触碰的文件再被 T014 复用，靠 Wave 2/3→Wave 4 串行消解。

## Source Summary

- 源方案：`docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md`（implementation-ready；经三人格方案评审修订 + 首轮任务包评审后的最小方案修订：U9/U10 新增 eval case 落入 Files、U1 判官分支标注、U4/U9/U10 首跑基线记录位置定为各自 case YAML description 尾部、U5 明确扩展既有 case）。
- 拆分依据的边界：不新建 references 文件、数值过线门禁禁入、合同口径 3+6（KTD2）、判官先行（KTD1）、全部增补带来源+许可证+快照标注（R14）。
- 实施期未知项：`postpublish_judge.py` 的 bash 委托入口形态在 T001 落地时验证；shuorenhua 阴阳对精选清单在 T005 落地时取材；U12 判定线边界轮（2/8）按 known-issues 记档纪律现场裁决。

## Traceability Matrix

| Source | Requirement | Task(s) | Validation |
| --- | --- | --- | --- |
| U1 | R4, R14 | T001 | test_judges.py 历史重放 100% + 对抗 fixture 100% + 分支标注输出 + 同步测试变异即红 |
| U2 | R6, R5(哈希输出), R14 | T002, T003 | check_prose/check_factual_invariants 单测 + 既有 fixture 重放无新误报 |
| U3 | R5, R14 | T004 | update_postpublish_record 单测（含 ledger 授权、容错与幂等场景） |
| U4 | R7, R14 | T005 | list-cases 输出含新 case + 首跑基线记录于 case YAML description 尾部 |
| U5 | R1, R2, R3, R14 | T006 | 扩展既有 full-article-evidence-chain + 来源标注 rg 检查 |
| U6 | R3, R14 | T007 | 扩展既有 deep-editorial-pipeline（缺摘录拦截断言）+ 净增 ≤60 行 |
| U7 | R1, R9, R14 | T008, T009 | T008 存量观察回归 + 行数预算；T009 扩展既有 audit-does-not-rewrite（收敛断言） |
| U8 | R8, R14 | T010 | chinese-22 聚焦复跑（基线 5/10，注明口径）+ 行数预算 |
| U9 | R10, R14 | T011 | train-voice-provisional 聚焦 + 新 case 注册与首跑基线 + 净增 ≤45 行 |
| U10 | R11, R14 | T012 | copywriting-route 回归 + 新 case 注册与首跑基线 + 净增 ≤70 行 |
| U11 | R1(材料面), R14 | T013 | tool-select 回归 + 登记五项齐全 |
| U12 | R12, R13, R9, R14 | T014 | 四组聚焦（判定线按 branch=canonical 标注计数）+ 独立 commit |
| U13 | R14 | T015 | 全量回归通过线（以各 case YAML 尾部基线为比较点）+ 三处记档 |

## Task Graph

- T001-T005 无相互依赖（Wave 1 全并行）。KTD1 判官门由 T014 依赖 T001-T013 全部编码：T001 未过历史重放门，Wave 4 不得开始。
- T010-T013 相互独立；其中 T010 依赖 T001（聚焦复跑测量口径），T011-T013 无依赖。
- T006 是研究环证据链上游：T007/T008/T009 依赖它；T006 自身依赖 T001（判官收紧改变聚焦复跑测量口径，与 T010 同因）。T012 无依赖，置于 Wave 3 仅为与 T011 错开 `evals/eval.yaml` 的同波写冲突。
- T014 依赖 T001-T013 全部（判官可信 + 增补层就位）。
- T015 依赖 T014（全量回归在合同改动之后）。
- T010（Wave 2）与 T008/T009（Wave 3）触碰的 chinese-editorial-protocol / editorial 文件再被 T014 复用，靠 Wave 2/3→Wave 4 串行消解。

## Execution Waves

| Wave | Tasks | 说明 |
| --- | --- | --- |
| 1 | T001, T002, T003, T004, T005 | P0 地基层，文件互斥，全并行 |
| 2 | T006, T010, T011, T013 | 独立 references 增补 + voice 新 case，全并行 |
| 3 | T007, T008, T009, T012 | 研究环依赖链增补 + 文案组（含新 case），全并行 |
| 4 | T014 | P2 合同三件套，串行 + 独立 commit |
| 5 | T015 | 全量回归与记档 |

## Task Pack Contract

```json
{
  "schema_version": "task-pack/v1",
  "execution_waves": [
    { "wave": 1, "tasks": ["T001", "T002", "T003", "T004", "T005"] },
    { "wave": 2, "tasks": ["T006", "T010", "T011", "T013"] },
    { "wave": 3, "tasks": ["T007", "T008", "T009", "T012"] },
    { "wave": 4, "tasks": ["T014"] },
    { "wave": 5, "tasks": ["T015"] }
  ],
  "tasks": [
    {
      "task_id": "T001",
      "source_unit": "U1",
      "requirement_refs": ["R4", "R14"],
      "goal": "post-publish 判官升级为双分支结构化解析（canonical YAML 块走四值枚举校验、自然语言走同义词分支、哨兵全串精确匹配），输出接受分支标注，并建立合同-references-判官三方同步测试。",
      "dependencies": [],
      "files": [
        "evidence-first-writing/evals/scripts/check-post-publish-boundary.sh",
        "evidence-first-writing/evals/scripts/postpublish_judge.py",
        "evidence-first-writing/tests/test_postpublish_judge.py",
        "evidence-first-writing/tests/test_judges.py",
        "evidence-first-writing/tests/test_contract_sync.py",
        "evidence-first-writing/tests/fixtures/judge_replay/postpublish__adv_promoted_bare.md",
        "evidence-first-writing/tests/fixtures/judge_replay/postpublish__adv_fields_missing.md"
      ],
      "test_focus": "历史在案响应重放 100% 接受 + 对抗 fixture 100% 拒绝（新 fixture 登记进 test_judges.py 既有 CASES 矩阵；场景③『promoted 伴随同义替换越权』由 test_postpublish_judge.py 内联用例承载，不入回放 fixture）+ 同步测试变异即红 + 判官输出 branch=canonical|synonym 标注。",
      "done_signal": "单测全绿；历史重放与对抗双 100%；判官输出接受分支标注（供 T014 判定线计数）。",
      "wave": 1,
      "review_gate": "required",
      "review_focus": "双分支边界是否守住 known-issues 词汇漂移纪律；值域是否与 editorial-pipeline Node 14 四值枚举对齐。",
      "stop_if": "收紧需要改既有 case 的断言语义或更名 canonical 字段——返回方案裁决。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u1-p0-判官收紧与三方同步测试",
        "upstream-absorption-workspace/deepread/T3-contract-enforcement.md",
        "evidence-first-writing/evals/known-issues.md"
      ],
      "parallelizable": true,
      "risk_note": "判官收紧误拒合规响应是回归信号失真的根因，历史重放门是硬前置。",
      "handoff_owner": "判官工程执行者"
    },
    {
      "task_id": "T002",
      "source_unit": "U2",
      "requirement_refs": ["R6", "R14"],
      "goal": "check_prose.py 移植 METAPHOR_LITERAL_PREFIX 字面排除表消除技术术语误报，并新增过程叙述 lint（警告级，诊断线索非门禁）。",
      "dependencies": [],
      "files": [
        "evidence-first-writing/scripts/check_prose.py",
        "evidence-first-writing/tests/test_check_prose.py"
      ],
      "test_focus": "技术名词句不触发比喻场 WARN、真实比喻仍触发、过程叙述在正文报/在状态块不报、既有豁免回归不破、退出码语义不变。",
      "done_signal": "全套 unittest 通过且既有 eval fixture 重放无新误报。",
      "wave": 1,
      "stop_if": "排除表需要引入外部词表依赖或网络获取——返回方案改设计。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u2-p0-检查器脚本增量",
        "upstream-absorption-workspace/deepread/T2-chinese-humanize.md"
      ],
      "parallelizable": true,
      "risk_note": "排除表过宽会吞真阳性，须保留反向用例。"
    },
    {
      "task_id": "T003",
      "source_unit": "U2",
      "requirement_refs": ["R5", "R14"],
      "goal": "check_factual_invariants.py 输出 before/after 内容哈希（auto-stale 输出端，消费方为 T004 ledger 与 T014 指针句）。",
      "dependencies": [],
      "files": [
        "evidence-first-writing/scripts/check_factual_invariants.py",
        "evidence-first-writing/tests/test_factual_invariants.py"
      ],
      "test_focus": "哈希输出稳定、正文单字改动后哈希变化、既有校验行为不回归。",
      "done_signal": "单测通过且既有调用方输出格式兼容。",
      "wave": 1,
      "stop_if": "哈希需要引入非标准库依赖——返回方案。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u2-p0-检查器脚本增量"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T004",
      "source_unit": "U3",
      "requirement_refs": ["R5", "R14"],
      "goal": "新增 update_postpublish_record.py：argparse 枚举 + promoted 三条件强制 + 仅显式 --ledger 的 append-only JSONL + --invariant-hash 记录 + stdout 吐 canonical YAML 块。",
      "dependencies": [],
      "files": [
        "evidence-first-writing/scripts/update_postpublish_record.py",
        "evidence-first-writing/tests/test_update_postpublish_record.py"
      ],
      "test_focus": "合法参数产 canonical 块、promoted 缺条件非零退出、append-only、重复写入幂等跳过或显式新条目、无 --ledger 不写文件、技能目录路径拒绝、损坏行容错、哈希条目失效语义。",
      "done_signal": "单测全绿，--help 与失败路径清晰。",
      "wave": 1,
      "stop_if": "需要默认落盘路径或绕过用户显式授权——违反 SKILL.md 持久写入红线，返回方案。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u3-p0-postpublish-状态外置脚本",
        "upstream-absorption-workspace/deepread/T3-contract-enforcement.md"
      ],
      "parallelizable": true,
      "risk_note": "脚本与判官为 compose 关系：脚本产 canonical 块，判官校验之。"
    },
    {
      "task_id": "T005",
      "source_unit": "U4",
      "requirement_refs": ["R7", "R14"],
      "goal": "以 shuorenhua SF/SNF 阴阳对精选 10-20 组，新增系统性\"不该改\"负例 eval case 并注册。",
      "dependencies": [],
      "files": [
        "evidence-first-writing/evals/cases/chinese-humanize-preserve-negative.yaml",
        "evidence-first-writing/evals/eval.yaml"
      ],
      "test_focus": "SNF 侧无误报改写建议、SF 侧漏报被捕获、断言用否定感知匹配。",
      "done_signal": "list-cases 输出含 chinese-humanize-preserve-negative；首跑基线（日期/轮次/结果）记录于该 case YAML description 尾部（T015 比较点）；首跑 FAIL 的收口结论留待 T015 统一记档。",
      "wave": 1,
      "stop_if": "精选素材不足以构成 10 组阴阳对——回到深读报告与语料 fixture 补取材；取材仍不足则返回 spec-plan 裁决。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u4-p0-负例评测夹具",
        "upstream-absorption-workspace/deepread/T2-chinese-humanize.md"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T006",
      "source_unit": "U5",
      "requirement_refs": ["R1", "R2", "R3", "R14"],
      "goal": "source-analysis.md 新增三个小节：终止与预算、策展与准入（含 source_status 十态）、压缩保真与引用忠实（含 T4-C2 双向终止）。",
      "dependencies": ["T001"],
      "files": [
        "evidence-first-writing/references/source-analysis.md",
        "evidence-first-writing/evals/cases/full-article-evidence-chain.yaml"
      ],
      "test_focus": "扩展既有 full-article-evidence-chain（research 终止即停/证据不可得记缺口断言）、与既有阴性纪律无表述冲突、每节来源+快照标注。",
      "done_signal": "聚焦复跑通过且 rg 确认标注齐全，每节 15-30 行。",
      "wave": 2,
      "stop_if": "需要改变 STORM 多视角节既有方法论表述——返回方案。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u5-p1-source-analysis-增补",
        "upstream-absorption-workspace/deepread/T1-deep-research.md",
        "upstream-absorption-workspace/deepread/T4-review-mechanism.md"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T007",
      "source_unit": "U6",
      "requirement_refs": ["R3", "R14"],
      "goal": "workflow-contract.md 增补：账本摘录必填（按 risk 分档）、引用呈现契约（family 分治，合同性 †）、对齐抽查、段首判据、起草前回看（deep 限）。",
      "dependencies": ["T006"],
      "files": [
        "evidence-first-writing/references/workflow-contract.md",
        "evidence-first-writing/evals/cases/deep-editorial-pipeline.yaml"
      ],
      "test_focus": "扩展既有 deep-editorial-pipeline（账本行缺摘录时正文引用该主张被拦截断言）、回看不开新检索、净增 ≤60 行。",
      "done_signal": "聚焦复跑通过且行数预算内。",
      "wave": 3,
      "stop_if": "需要把数量阈值（如每主张 N 条证据）写入合同——违反 KTD6 数值禁令，返回方案裁决。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u6-p1-workflow-contract-增补"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T008",
      "source_unit": "U7",
      "requirement_refs": ["R1", "R9", "R14"],
      "goal": "editorial-pipeline.md 增补拒答式评审（合同性 †）与 Node 11 返工上限语义（合同性 †）。",
      "dependencies": ["T006"],
      "files": ["evidence-first-writing/references/editorial-pipeline.md"],
      "test_focus": "观察性全量回归中存量既有 case（存量 33）无退化——新增 case 以首跑基线另行比较，官方通过线归 T015，本次观察回归在 wave 3 文件变更全部落定后执行；净增 ≤25 行。",
      "done_signal": "观察性全量回归存量 33 无退化且行数预算内（聚焦 case 由 T009 承载）。",
      "wave": 3,
      "stop_if": "返工上限需要按 depth 写成数值门禁——违反数值禁令，改为默认工作约定表述。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u7-p1-编辑管线与审查协议增补",
        "upstream-absorption-workspace/deepread/T1-deep-research.md"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T009",
      "source_unit": "U7",
      "requirement_refs": ["R9", "R14"],
      "goal": "editorial-review.md 去模板感协议第 7 步附近增补收敛早停三条，并与保护性编辑边界合并表述。",
      "dependencies": ["T006"],
      "files": [
        "evidence-first-writing/references/editorial-review.md",
        "evidence-first-writing/evals/cases/audit-does-not-rewrite.yaml"
      ],
      "test_focus": "扩展既有 audit-does-not-rewrite（第二轮无新发现时显式声明收敛而非硬造 finding 断言）、净增 ≤12 行。",
      "done_signal": "聚焦复跑通过且行数预算内。",
      "wave": 3,
      "stop_if": "收敛协议与保护性编辑边界出现两套停止规则表述冲突——合并为一条。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u7-p1-编辑管线与审查协议增补",
        "upstream-absorption-workspace/deepread/T4-review-mechanism.md"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T010",
      "source_unit": "U8",
      "requirement_refs": ["R8", "R14"],
      "goal": "中文协议三文件增补：七要素核对/动词强度/venue-first/归属分层/压缩试验/需作者确认区块（†）入 protocol；Never-inject 第 8 条与 CCL 锚点入 catalog；两域 AI tells 入 patterns 渠道矩阵。",
      "dependencies": ["T001"],
      "files": [
        "evidence-first-writing/references/chinese-editorial-protocol.md",
        "evidence-first-writing/references/humanizer-pattern-catalog.md",
        "evidence-first-writing/references/humanizer-patterns.md"
      ],
      "test_focus": "chinese-22-rules 聚焦复跑（基线 5/10，注明判官口径）、七要素不机械挂限定语、需作者确认区块触发。",
      "done_signal": "聚焦复跑通过；净增 protocol ≤65 行、catalog ≤20 行、patterns ≤10 行。",
      "wave": 2,
      "stop_if": "需将 74/18/8 英文语料数字设为中文目标——只可作参照注记。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u8-p1-中文协议增补",
        "upstream-absorption-workspace/deepread/T2-chinese-humanize.md"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T011",
      "source_unit": "U9",
      "requirement_refs": ["R10", "R14"],
      "goal": "voice-profiles.md 增补认知层两章节定义、行级证据格式、覆盖边界披露（†）、负例锚与自检清单；注册 voice-out-of-scope-disclosure 新 case。",
      "dependencies": [],
      "files": [
        "evidence-first-writing/references/voice-profiles.md",
        "evidence-first-writing/evals/cases/voice-out-of-scope-disclosure.yaml",
        "evidence-first-writing/evals/eval.yaml"
      ],
      "test_focus": "train-voice 产物 lint（稳定特征行含出处标记）、覆盖披露复用 voice_basis 不新增状态名、净增 ≤45 行；新 case：超样本主题任务产出覆盖不足声明且无超样本立场归因。",
      "done_signal": "train-voice-provisional 聚焦复跑通过；list-cases 输出含 voice-out-of-scope-disclosure 且首跑基线记录于其 YAML description 尾部。",
      "wave": 2,
      "stop_if": "需要吸收策略层内容或照搬上游 ≥3 阈值——违反 KTD 与档案纪律，返回方案裁决。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u9-p1-声音档案增补",
        "upstream-absorption-workspace/deepread/T5-voice-distillation.md"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T012",
      "source_unit": "U10",
      "requirement_refs": ["R11", "R14"],
      "goal": "copywriting.md 增补溯源纪律（†）；copy-frameworks-ext.md 增补双层语义质检、战术失效双列、修辞公式子集、评分有界停止、语感差集；注册 copy-grounding-ungrounded 新 case。",
      "dependencies": [],
      "files": [
        "evidence-first-writing/references/copywriting.md",
        "evidence-first-writing/references/copy-frameworks-ext.md",
        "evidence-first-writing/evals/cases/copy-grounding-ungrounded.yaml",
        "evidence-first-writing/evals/eval.yaml"
      ],
      "test_focus": "copywriting-route 回归不退化、边界改写（暗示不豁免证据）在位、净增 ≤70 行；新 case：无 grounding 的转化主张须带 ungrounded 披露。",
      "done_signal": "聚焦复跑通过；list-cases 输出含 copy-grounding-ungrounded 且首跑基线记录于其 YAML description 尾部。",
      "wave": 3,
      "stop_if": "需要吸收操纵性双关技巧原文而不带边界改写——违反反操纵红线，返回方案裁决。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u10-p1-文案协议增补",
        "upstream-absorption-workspace/deepread/T6-copywriting.md"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T013",
      "source_unit": "U11",
      "requirement_refs": ["R1", "R14"],
      "goal": "article-workflows.md 新增长文起草材料指引小节（指引非门禁）；tool-selection.md 登记批五项（newsnow/xiaohongshu-mcp/md2wechat-skill/autocorrect/Wechatsync）。",
      "dependencies": [],
      "files": [
        "evidence-first-writing/references/article-workflows.md",
        "evidence-first-writing/references/tool-selection.md"
      ],
      "test_focus": "tool-select 回归、材料指引不改变 quick 档行为、登记条目含维护状态与许可证。",
      "done_signal": "聚焦复跑通过且登记五项齐全。",
      "wave": 2,
      "stop_if": "材料量指引需要变成硬门禁——违反 KTD7，返回方案裁决。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u11-p1-工作流指引与工具登记"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T014",
      "source_unit": "U12",
      "requirement_refs": ["R12", "R13", "R9", "R14"],
      "goal": "落地三项 SKILL.md 级合同改动：C1+L1 结构锚（含 U3 脚本指针句与哈希记录）、C4 审查输出完备性契约（最少 1 条问题或未发现+检查范围出口）、S2+P3 长文缩水控制；三项各自独立 commit。",
      "dependencies": ["T001", "T002", "T003", "T004", "T005", "T006", "T007", "T008", "T009", "T010", "T011", "T012", "T013"],
      "files": [
        "evidence-first-writing/SKILL.md",
        "evidence-first-writing/references/editorial-pipeline.md",
        "evidence-first-writing/references/editorial-review.md",
        "evidence-first-writing/references/chinese-editorial-protocol.md"
      ],
      "test_focus": "post-publish-no-causal-unprompted 聚焦 8 轮（判定线：≥3/8 结构完整记改善、≤1/8 触发回退；结构完整按判官 branch=canonical 标注计数）；signal-bearing-topic-proceeds/bare-topic-fork-two-turns 各 10 轮（首锚不破坏 turn-1 无卡期望）；chinese-22-rules 十轮；健康稿不因完备性契约误报。",
      "done_signal": "四组聚焦完成且结论按判定线记档；三项独立 commit 可二分回退。",
      "wave": 4,
      "review_gate": "required",
      "review_focus": "锚表述是否弱化实质断言；C4 是否与既有 Finding 字段合同漂移；回退路径是否按停止条件执行。",
      "stop_if": "聚焦 8 轮按判定线判无改善——停止合同路径，转 T004 脚本裁决为主并记档，不追加 SKILL.md 文本尝试。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#u12-p2-行为合同三件套",
        "upstream-absorption-workspace/deepread/T3-contract-enforcement.md"
      ],
      "parallelizable": false,
      "risk_note": "本轮最大受控试验；失败回退路径已预注册。",
      "handoff_owner": "合同工程执行者"
    },
    {
      "task_id": "T015",
      "source_unit": "U13",
      "requirement_refs": ["R14"],
      "goal": "全量回归（存量 33 + 新增 case 双轨通过线，新增 case 以各自 YAML description 尾部基线为比较点）+ CHANGELOG/known-issues/upstream-source-audit 第二轮章节三处记档。",
      "dependencies": ["T014"],
      "files": [
        "CHANGELOG.md",
        "evidence-first-writing/evals/known-issues.md",
        "evidence-first-writing/references/upstream-source-audit.md"
      ],
      "test_focus": "存量 33 扣除在案故意失败项 ≥90% 且无新增稳定 FAIL；新增 case（chinese-humanize-preserve-negative/voice-out-of-scope-disclosure/copy-grounding-ungrounded）不低于各自首跑基线；记档含判定线结论与口径差异说明。",
      "done_signal": "回归通过线达标、三处记档齐备、git diff --check 干净。",
      "wave": 5,
      "review_gate": "required",
      "review_focus": "记档是否完整披露受控试验结果与新增用例口径差异。",
      "stop_if": "回归出现新增稳定 FAIL 且无法归因到在案类别——暂停并回方案评审。",
      "context_refs": [
        "docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md#verification-contract"
      ],
      "parallelizable": false
    }
  ]
}
```

## Task Cards

任务的机器可读权威来源是上方 `Task Pack Contract` JSON；以下为执行者速览镜像（字段冲突时以 JSON 为准）。

- T001（U1, wave 1）判官双分支收紧+分支标注+三方同步测试。deps: 无。files: check-post-publish-boundary.sh、postpublish_judge.py、test_postpublish_judge.py、test_judges.py、test_contract_sync.py、judge_replay/ 两个 adv_ 前缀新对抗 fixture（场景③同义替换越权由单测承载）。done: 历史重放+对抗双 100% 且输出分支标注。stop: 需改既有断言语义或更名 canonical 字段。
- T002（U2, wave 1）check_prose 排除表+过程叙述 lint。deps: 无。files: check_prose.py、test_check_prose.py。done: 单测过+fixture 重放无新误报。stop: 需外部词表依赖。
- T003（U2, wave 1）check_factual_invariants 哈希输出。deps: 无。files: check_factual_invariants.py、test_factual_invariants.py。done: 单测过且输出兼容。stop: 需非标准库依赖。
- T004（U3, wave 1）postpublish 状态外置脚本。deps: 无。files: update_postpublish_record.py、test_update_postpublish_record.py。done: 单测全绿含授权/容错/幂等场景。stop: 需默认落盘路径。
- T005（U4, wave 1）阴阳对负例 case。deps: 无。files: chinese-humanize-preserve-negative.yaml、eval.yaml。done: list-cases 含新 case + 基线记录于 case YAML 尾部。stop: 素材不足 10 组。
- T006（U5, wave 2）source-analysis 三小节。deps: T001。files: source-analysis.md、full-article-evidence-chain.yaml（扩展断言）。done: 聚焦过+标注齐+每节 15-30 行。stop: 需改 STORM 节既有表述。
- T007（U6, wave 3）workflow-contract 增补。deps: T006。files: workflow-contract.md、deep-editorial-pipeline.yaml（扩展断言）。done: 聚焦过+≤60 行。stop: 需写数量阈值。
- T008（U7, wave 3）editorial-pipeline 拒答评审+返工上限。deps: T006。files: editorial-pipeline.md。done: 存量观察回归无退化+≤25 行。stop: 需数值门禁化。
- T009（U7, wave 3）editorial-review 收敛早停。deps: T006。files: editorial-review.md、audit-does-not-rewrite.yaml（扩展断言）。done: 聚焦过+≤12 行。stop: 出现两套停止规则。
- T010（U8, wave 2）中文协议三文件增补。deps: T001。files: chinese-editorial-protocol.md、humanizer-pattern-catalog.md、humanizer-patterns.md。done: chinese-22-rules 聚焦过+行数预算内。stop: 英文数字设为中文目标。
- T011（U9, wave 2）voice-profiles 认知层+新 case。deps: 无。files: voice-profiles.md、voice-out-of-scope-disclosure.yaml、eval.yaml。done: 聚焦过+新 case 注册与基线记录+≤45 行。stop: 需策略层或 ≥3 阈值。
- T012（U10, wave 3）文案协议增补+新 case。deps: 无（wave 3 仅为错开 eval.yaml 同波写冲突）。files: copywriting.md、copy-frameworks-ext.md、copy-grounding-ungrounded.yaml、eval.yaml。done: 聚焦过+新 case 注册与基线记录+≤70 行。stop: 操纵技巧不带边界改写。
- T013（U11, wave 2）材料指引+工具登记。deps: 无。files: article-workflows.md、tool-selection.md。done: 回归过+登记五项。stop: 指引变硬门禁。
- T014（U12, wave 4）合同三件套（独立 commit×3）。deps: T001-T013 全部。files: SKILL.md、editorial-pipeline.md、editorial-review.md、chinese-editorial-protocol.md。done: 四组聚焦按判定线（branch=canonical 计数）记档。stop: 判定线判无改善→转脚本路径记档。
- T015（U13, wave 5）全量回归+三处记档。deps: T014。files: CHANGELOG.md、known-issues.md、upstream-source-audit.md。done: 通过线达标（新 case 比各自 YAML 尾部基线）+记档齐+diff 干净。stop: 新增稳定 FAIL 无法归因。

## Orientation Evidence

- provider: direct-repo-reads
- posture: bounded
- evidence_refs: `evidence-first-writing/evals/scripts/check-post-publish-boundary.sh`（post-publish case 的 script_path 实际指向，已核实）；`evidence-first-writing/tests/`（实际测试文件名 test_factual_invariants.py/test_judges.py/test_check_prose.py，已核实）；`evidence-first-writing/tests/fixtures/judge_replay/`（现有 16 个回放 fixture，postpublish 三件在档）；`evidence-first-writing/evals/cases/post-publish-no-causal-unprompted.yaml`（judge type: script 结构已核实）；`evidence-first-writing/evals/eval.yaml`（存量 33 case 注册）。
- limitations: postpublish_judge.py 与两个对抗 fixture 为计划内新文件（T001 落定）；三个新 case YAML 为计划内新文件（T005/T011/T012 落定）；context_refs 中 upstream-absorption-workspace/ 为 git-ignore 工作区证据（本地缺失时回方案与 03/04/05 阶段文件取等价证据）。

## Validation Notes

- 本任务包派生自 `docs/plans/2026-08-31-004-feat-efw-upstream-absorption-r2-plan.md`（首轮任务包评审后的修订版），body 哈希由 `spec-first tasks hash --repo /Users/kuang/knowledge/leo-skills --json` 产出。
- 哈希不匹配（源方案再修订）时执行必须拒绝，重跑 spec-write-tasks 再生成。
- 首轮评审修复映射：U9/U10 新 case 落入 T011/T012 files（方案 U9/U10 Files 同步补齐）；首跑基线记录统一为 case YAML description 尾部（T005/T011/T012 产出、T015 取用）；T001 增加分支标注与对抗 fixture 文件声明并移除惰性 list-cases 信号；T004 补幂等场景；T008 done_signal 与 test_focus 对齐；Task Graph 摘要 T0013 笔误与波次表述修正；T012 移入 Wave 3 消解 eval.yaml 同波冲突。
- 判定拆分是否有用的最好验证：T001 的历史重放门与 T014 的判定线——两者都是方案预注册的仲裁点。
- spec_id 双侧均未携带，validator 将记录 task-pack-spec-id-trace-missing 限制（不影响可执行性）。
- 第二轮语义评审（coherence/feasibility/scope-guardian，roster:full）：首轮 8 项修复全部验证落地；本轮零 P0/P1，2 条 P2 与 5 条 P3 均为 producer 修复项并在评审后立即应用——T008 观察回归限定存量 33 并移至 wave 3 文件落定后执行；T006/T007/T009 聚焦 case 具名为 full-article-evidence-chain/deep-editorial-pipeline/audit-does-not-rewrite 并纳入 files；T001 对抗 fixture 改 adv_ 前缀并映射场景③载体；5 个 stop_if 补返回 owner；Task Graph 补 T006→T001 依赖。全部为任务包侧修订，源方案哈希未变，评审后已重跑确定性校验。

## Regeneration Rules

- 源方案任一 U-ID 的 Files/依赖/验证变更、Scope Boundaries 变更、或 task pack 语义被手工编辑后：重建本包。
- `source_plan_hash` 不匹配即拒绝执行并重建。
- 任一任务触发 `stop_if`：返回 spec-plan 或重跑 spec-write-tasks。
