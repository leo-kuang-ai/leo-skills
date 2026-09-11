# PPT 内容意图与风格版式路由增量计划

## 目标

把“整稿风格推荐”和“逐页版式调度”之间缺失的内容语义层补上，使每页先得到可复核的页面意图，再选择适配的版式与渲染 lane。

## 当前问题

- 风格推荐只接收 genre/domain/audience 等整稿信号，不能判断某一章节页的论点、证据形态和视觉权重。
- `suggest_layout.py` 只按 `page_role/points/est_chars/data_points` 打分，无法区分对比、趋势、流程、机制、证据网格等内容形态。
- layout 的 `page_role`、模板 renderer 和内容结构分别维护，候选可能语义合适但执行 lane 不可用，或只能退化为通用列表。

## 本增量范围

1. 建立版本化 `page_type_regime` 真值源：页面类型的语义要求、首选/回退版式、允许 lane、必需结构与禁止形态。
2. 新增确定性 `page_intent` 分析器：消费显式意图字段和母版结构，缺失时用有限关键词与计数推断；不确定返回 `undecided`。
3. 将意图分析接入 `scripts/suggest_layout.py`，输出 regime 版本、意图摘要、候选的语义/容量/renderer 理由。
4. 增加正负测试：对比、趋势、流程、KPI、证据和纯文本列表的路由；不支持 renderer、结构冲突和未知语义必须降级为待定。

## 非目标

- 不批量重写 320 个 style brief，不复制第二套 token 真值。
- 不自动生成或修改用户母版，不替代样张门、容量闸门或人工裁决。
- 不宣称视觉审美、真实 Provider 或最终用户接受率已验证。

## 验收

- 同一输入重复运行字节级稳定。
- 对比内容首选 P8/compare，趋势首选 P2/P11/timeline，流程首选 P11，KPI 首选 P6/P20/P24，证据首选 frame-shot/P31；纯文本列表不得被误判为 KPI/图表页。
- 明确 `backend` 时只返回该 lane 可执行候选；无候选返回 `undecided`，不静默改成 body-basic。
- 输出包含可解释的意图字段与 regime 版本，便于后续 AI 分析、人工 override 和评测统计。

## 本轮实施结果

- 已新增 `page-type-regime-v1.json` 与 `page_intent.py`，覆盖 cover、agenda、section、statement、kpi、comparison、trend、process、system、evidence、table、text_list、closing。
- `suggest_layout.py` 已接入意图排序；style `layout_routes` 按页面角色范围过滤，避免封面或章节路由泄漏到数据页。
- 已新增 6 个正负回归，验证显式结构优先、纯文本不误判 KPI、对比/表格语义首选、未知语义保留人工裁决及真实 catalog 引用。
- 验证：`runtime/.venv` 下相关 unittest 45 项通过；15 个模板合同/render lint、版式 lint 通过；未进行付费 Provider、整册视觉审美或用户验收。
