# 审校量表

Critical：改变技术保证、安全要求或可执行行为。Major：影响理解、完整性或关键术语。Minor：不改变技术含义的表达或排版。审校分类包括 `semantic_fidelity`、`technical_readability`、`editorial_naturalness` 和 `publication_readiness`。审校问题以块为单位编号（字段名 `block_id`），需包含 block_id、原文/译文证据、严重性、建议、目标版本和 verification；`assets/review.schema.json` 定义最小必填集，证据与建议缺位时该记录不得标记为已解决。`verification` 的操作定义：`passed` 必须有可复核依据（对照原文复查该块、重跑 `validate-output.mjs` 通过、或引用可验证来源），仅凭译者自述只能记 `not-run`。`technical_review`（由同一译者和工具链执行的复核）不等于 `independent_review`（独立第三方审校）；`editorial_review` 只表示中文表达和发布适配检查，未做独立审校不得标注为已独立审校。

## 七类问题类型

`issue_type` 为可选字段，与 `category` 正交：`category` 说明审校维度，`issue_type` 说明出了什么问题，一条记录可两者同填。

| issue_type | 中文名 | 判据 |
|---|---|---|
| `omission` | 漏译 | 原文块在译文中缺失或被摘要替代 |
| `mistranslation` | 误译 | 语义、术语或技术关系译错 |
| `intensification` | 语义强化 | 弱化表达被译成更强判断（may→一定/会） |
| `weakening` | 语义弱化 | 强约束被译弱（MUST→建议、限制→可能） |
| `terminology_inconsistency` | 术语不一致 | 同篇同义术语译法漂移或违反术语优先级 |
| `structure_damage` | 结构损坏 | 代码、Markdown、链接、图片、公式或占位符被破坏 |
| `editorial_overreach` | 编辑越界 | 润色引入原文没有的事实、例子、因果、承诺或结论（清单见 `editorial-style.md`） |

严重性映射：漏译、误译、结构损坏至少 major（触及安全约束或可执行行为时 critical）；语义强化、语义弱化按影响 major 或 critical；编辑越界至少 major（引入原文没有的事实、承诺或因果时 critical）。

最终审校（`delivery_mode: polished` / `publication`）的对象是润色后译文：逐句对照原文，覆盖语义、模态、因果、条件、量词、风险与责任主体。发布判定为合取：保真门（漏译/误译/强化/弱化/术语不一致/结构损坏）未通过或编辑越界时整体不可发布，`editorial_review` 通过不抵消保真失败（合取矩阵见 `publication-delivery.md`）。
