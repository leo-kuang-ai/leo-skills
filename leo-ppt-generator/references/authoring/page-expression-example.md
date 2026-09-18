# 母版
decision_source: user-delegated
goal: 汇报效率
audience: 管理层
content_model: {"schema_version": 2, "main_claim": "效率提升须按同口径比较", "main_style": "清爽专业风", "brand_constraints": ["内部资料"], "narrative_order": ["ch-context", "ch-evidence"], "chapters": [{"chapter_id": "ch-context", "task": "界定口径", "conclusion": "先统一计量边界", "evidence_refs": [], "previous": null, "next": "ch-evidence"}, {"chapter_id": "ch-evidence", "task": "证明效率", "conclusion": "时长下降", "evidence_refs": ["试点台账"], "previous": "ch-context", "next": null}]}

## S1 口径
page_id: pg-11111111
page_expression: {"chapter_id":"ch-context","semantic_structure":"undecided","media_role":"none","evidence_refs":[],"basis":[],"expression":{"reading_task":"independent","focus":"claim","reading_order":["claim","point:1"],"relation_encoding":{"item_refs":["point:1"],"edges":[]},"fact_refs":[],"uncertainty":["结构尚未确定"]}}
- 标题：先统一口径
- 要点 1：两组必须同期间

## S2 对照
page_id: pg-22222222
page_expression: {"chapter_id": "ch-evidence", "semantic_structure": "comparison", "media_role": "support", "evidence_refs": ["试点台账"], "basis": ["同期间同单位对照"], "budget_seconds": 75, "expression": {"reading_task": "comparison", "focus": "claim", "reading_order": ["claim", "point:1", "fact:1", "fact:2", "/structures/sides/0", "/structures/sides/1"], "fact_refs": ["fact:1", "fact:2"], "uncertainty": [], "relation_encoding": {"item_refs": ["/structures/sides/0", "/structures/sides/1"], "dimension_refs": ["/facts/fact:1/unit"], "cells": [{"item_ref": "/structures/sides/0", "dimension_ref": "/facts/fact:1/unit", "fact_ref": "fact:1", "unknown": false}, {"item_ref": "/structures/sides/1", "dimension_ref": "/facts/fact:1/unit", "fact_ref": "fact:2", "unknown": false}]}}}
- 标题：试点处理时长下降
- 要点 1：从 6 小时降到 2 小时【引用|src:试点台账】
对照侧: 旧流程｜6 小时｜同期间
对照侧: 新流程｜2 小时｜同期间
- 备注：speaker_script: 说明两组相同边界

## 数字登记表
| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 | verified? | as-of |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6 | S2 | 试点台账 | 旧流程 | 2026Q3 | 小时 | 引用 | yes | 2026-09-01 |
| 2 | S2 | 试点台账 | 新流程 | 2026Q3 | 小时 | 引用 | yes | 2026-09-01 |
