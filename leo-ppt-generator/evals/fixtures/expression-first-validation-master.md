# 母版
decision_source: user-delegated
goal: 汇报效率
audience: 管理层
content_model: {"schema_version": 2, "main_claim": "统一口径并保留证据", "main_style": "清爽专业风", "brand_constraints": ["内部资料"], "narrative_order": ["ch-context", "ch-evidence"], "chapters": [{"chapter_id": "ch-context", "task": "界定口径", "conclusion": "先统一计量边界", "evidence_refs": [], "previous": null, "next": "ch-evidence"}, {"chapter_id": "ch-evidence", "task": "保存证据", "conclusion": "证据可复核", "evidence_refs": [], "previous": "ch-context", "next": null}]}

## S1 先统一口径
page_id: pg-11111111
page_expression: {"chapter_id": "ch-context", "semantic_structure": "undecided", "media_role": "none", "evidence_refs": [], "basis": [], "expression": {"reading_task": "independent", "focus": "claim", "reading_order": ["claim", "point:1", "point:2"], "relation_encoding": {"item_refs": ["point:1", "point:2"], "edges": []}, "fact_refs": [], "uncertainty": ["各事项独立推进"]}}
角色：并列·事项
- 标题：先统一口径
- 要点 1：两组必须同期间
- 要点 2：两组必须同单位

## S2 保留可复核证据
page_id: pg-22222222
page_expression: {"chapter_id": "ch-evidence", "semantic_structure": "undecided", "media_role": "none", "evidence_refs": [], "basis": [], "expression": {"reading_task": "independent", "focus": "claim", "reading_order": ["claim", "point:1", "point:2"], "relation_encoding": {"item_refs": ["point:1", "point:2"], "edges": []}, "fact_refs": [], "uncertainty": ["各事项独立推进"]}}
角色：并列·事项
- 标题：保留可复核证据
- 要点 1：记录数据来源
- 要点 2：复核验收结果
