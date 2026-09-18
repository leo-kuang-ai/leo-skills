# 任务内版式提案

在 `PipelineRequest.proposals` 中按稳定 `page_id` 提供
`task-local-layout-proposal-v1` 文档。文档固定 `run_scope`、base asset、base generation
和实际 base profile 摘要；每页至多三个 candidate，每个 candidate 固定 lane。

只允许 `set_region_assignment`、`set_anchor_gap`、`set_span`、`set_slot_mapping`。
槽位置换必须为同类型双射；共用 region 的槽须一致移动。未知字段、自由 CSS、
不明 anchor、越界、跨 run 或基线漂移均拒绝。op 顺序规范化后计算 patch 摘要。

共享候选全不合格时，统一候选池才展开一次提案。`proposal_probe_cases` 可提供已冻结的
独立正反关系用例，格式与 `probe_relation_capabilities.py --cases` 相同；HTML 在任务私有
库内真实渲染并重新计算证据。原版式证据不能授予 patch 资格。缺探针、image 输出 oracle
或视觉裁决时保留具体 gap；只有仅缺视觉的 provisional 可用于 `purpose=validation`。

选择后，原始资产 pin、规范 patch、内容与主题、正反原始观测和导出一起进入 immutable
input generation。渲染前从原始 profile 重放 op，不信任手写 effective profile。
HTML 消费实际数值几何与字段置换；image recipe 明确接收区域和槽位映射，真实 image
资格与视觉仍单独取证。

`qa/proposal-curation-<lane>.json` 保留逐候选尝试与失败原因，不能据此自动晋升 canonical。
人工修改约束需创建新的 run scope；不能用失败输出递归生成下一轮提案。
