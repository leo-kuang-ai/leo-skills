---
title: "evidence-first-writing 排版合同四件套 - Task Pack"
type: "task-pack"
status: "derived"
date: "2026-08-31"
source_plan: "docs/plans/2026-08-31-005-feat-efw-layout-contract-plan.md"
source_plan_hash: "sha256:4625d45c1b2b9f31e4d4f219c7f7292f17ad2ca00ec0891b87f80b4348b91016"
generated_by: "spec-write-tasks"
mode: "derived"
source_sections:
  - "Requirements"
  - "Key Technical Decitions"
  - "Implementation Units"
  - "Verification Contract"
---

# evidence-first-writing 排版合同四件套 - Task Pack

## Overview

源方案 5 单元编译为 5 任务、3 波次：Wave 1 规约文本与线 2 移交文档（并行）→ Wave 2 lint 脚本与 eval case（并行，均依赖规约）→ Wave 3 接线与登记升级（依赖脚本）。文件互斥经核（T005 与 T003 无同波重叠）。

## Task Pack Contract

```json
{
  "schema_version": "task-pack/v1",
  "execution_waves": [
    { "wave": 1, "tasks": ["T001", "T002"] },
    { "wave": 2, "tasks": ["T003", "T004"] },
    { "wave": 3, "tasks": ["T005"] }
  ],
  "tasks": [
    {
      "task_id": "T001",
      "source_unit": "U1",
      "requirement_refs": ["R1", "R3", "R4", "R5", "R6"],
      "goal": "新增 references/layout-contract.md：结构规约六条（只加标记不改内容）、px 阈值登记判据、渲染器中立兼容条款+CSS 安全区核对表、AI 排版保真条款。",
      "dependencies": [],
      "files": ["evidence-first-writing/references/layout-contract.md"],
      "test_focus": "四节齐全且每条 FAIL 规则与 check_layout 一一对应；来源+许可证+快照标注 rg 检查；净增 ≤80 行。",
      "done_signal": "rg 来源标注四节齐全；行数预算内；与 U2 六类规则映射无缺。",
      "wave": 1,
      "stop_if": "需要引入渲染产物才能判定的条款进 FAIL 层——降级为登记判据。",
      "context_refs": [
        "docs/plans/2026-08-31-005-feat-efw-layout-contract-plan.md#u1-layout-contractmd-规约文本",
        "upstream-absorption-workspace/layout/deepread-line1.md"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T002",
      "source_unit": "U5",
      "requirement_refs": ["R6"],
      "goal": "线 2 增量移交文档（工作区）：guizang 测量规则增量口径 + raphael 参考 + leo 仓内缺口清单。",
      "dependencies": [],
      "files": ["upstream-absorption-workspace/layout/handoff-line2.md"],
      "test_focus": "自包含（leo 会话无需回读漏斗全档）；AGPL 零复制声明在场。",
      "done_signal": "文档存在且含 guizang-R2/R3/R6/R7 口径、scrollH 口径、raphael 六步整形参考、四项仓内缺口。",
      "wave": 1,
      "stop_if": "不适用（工作区文档）。",
      "context_refs": ["upstream-absorption-workspace/layout/deepread-line2.md"],
      "parallelizable": true
    },
    {
      "task_id": "T003",
      "source_unit": "U2",
      "requirement_refs": ["R1", "R2", "R3", "R6"],
      "goal": "新增 scripts/check_layout.py + 单测：6 类规则（CJK 标点邻接判定 + 四类配额 FAIL + 三连同构 WARN）、退出码 0/1/2/3、无汉字守卫、五字段输出。",
      "dependencies": ["T001"],
      "files": [
        "evidence-first-writing/scripts/check_layout.py",
        "evidence-first-writing/tests/test_check_layout.py"
      ],
      "test_focus": "测试场景 ①-⑦ 全过（保护区+邻接反例 3.14/1,000/12:30/e.g.、配额正反例、退出码四态、纯英文/纯表格不误判 exit 3）；红→绿。",
      "done_signal": "单测全绿；遍历 references/*.md + SKILL.md 基线快照已记录。",
      "wave": 2,
      "review_gate": "required",
      "review_focus": "邻接判定与 6 类 mask 保护区无漏报/误报；配额计数粒度与规约一致；退出码语义与 check_prose 对齐。",
      "stop_if": "任何规则需要非标准库依赖或 DOM 渲染——降级登记判据或移交线 2。",
      "context_refs": [
        "docs/plans/2026-08-31-005-feat-efw-layout-contract-plan.md#u2-check_layoutpy-确定性-lint",
        "upstream-absorption-workspace/layout/deepread-line1.md",
        "evidence-first-writing/scripts/check_prose.py"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T004",
      "source_unit": "U3",
      "requirement_refs": ["R4", "R6"],
      "goal": "新增 eval case layout-neutral-output（rule_based 断言：标准链接 any + 裸 HTML/私有容器 not + 半角标点串 not）并注册首跑记基线。",
      "dependencies": ["T001"],
      "files": [
        "evidence-first-writing/evals/cases/layout-neutral-output.yaml",
        "evidence-first-writing/evals/eval.yaml"
      ],
      "test_focus": "list-cases 注册可见；首跑基线记 description 尾部（FAIL 按同义词惯例收口记档）。",
      "done_signal": "注册成功 + 首跑结果在档。",
      "wave": 2,
      "stop_if": "需要新判官脚本——断言一律 rule_based（must_contain_any 引擎缺陷在案）。",
      "context_refs": [
        "docs/plans/2026-08-31-005-feat-efw-layout-contract-plan.md#u3-兼容断言-eval-case",
        "evidence-first-writing/evals/cases/voice-out-of-scope-disclosure.yaml"
      ],
      "parallelizable": true
    },
    {
      "task_id": "T005",
      "source_unit": "U4",
      "requirement_refs": ["R2", "R6"],
      "goal": "SKILL.md 接线句（check_prose 句后 + 条件加载段并入 layout-contract.md）+ tool-selection 升级（autocorrect 双轨 + CSS 安全区核对表指针 + 容量经验值）。",
      "dependencies": ["T001", "T003"],
      "files": [
        "evidence-first-writing/SKILL.md",
        "evidence-first-writing/references/tool-selection.md"
      ],
      "test_focus": "全套单测零回归（test_contract_sync 不受影响——不改合同字段）；SKILL.md 净增 ≤4 行、tool-selection ≤12 行。",
      "done_signal": "单测全绿；行数预算内；来源标注齐。",
      "wave": 3,
      "stop_if": "接线句需要改 canonical 合同字段——返回方案。",
      "context_refs": [
        "docs/plans/2026-08-31-005-feat-efw-layout-contract-plan.md#u4-skillmd-接线与登记升级"
      ],
      "parallelizable": false
    }
  ]
}
```

## Task Cards

JSON 为权威；速览：T001 规约文本(w1) → T003 lint 脚本(w2, review required) + T004 eval case(w2) → T005 接线登记(w3)；T002 移交文档(w1, 独立)。

## Validation Notes

- 派生自 docs/plans/2026-08-31-005-feat-efw-layout-contract-plan.md（sha256:4625d45c…，经无头双人格评审后 14 处修复）。
- 哈希不匹配即拒绝执行并重建。spec_id 双侧未携带（非阻断限制）。
- 实施完成后由编排者跑全量回归（存量 36+1 case 带内）与 CHANGELOG 记档。

## Regeneration Rules

源方案变更或本包被手工编辑后重建；任一 stop_if 触发返回 spec-plan。
