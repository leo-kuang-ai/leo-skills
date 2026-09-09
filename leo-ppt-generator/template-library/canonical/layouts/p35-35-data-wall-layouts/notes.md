# 版式：P35 · Data Wall · 数据大屏

**分类:** canonical/layouts（数据结构版式）

**用途:** 成果数据墙 / 年度关键指标 / 发布会数据冲击页 / 尾声数字盘点。

**适用内容类型:** **4–8 个真实巨数 KPI**(每个 = 数值 + 标签 + 单位 + 一句口径说明,四件套缺一不可)。数值必须来自 approved 来源序列,按 `template-library/governance/authoring/index/图表样式规范.md` 置信度形状语法标注(估算值 ~ 前缀 + 虚线框,示意值禁入);**数据密度路由**:图片路线本版式 ≤5 点,≥6 点或含估算序列改走 direct-editable(本版式可编辑路线承载 4–8 点,见 backend-selection 与 image-deck-workflow 3a 步);需要 bar 对比的 4 项数据用 P6 KPI Tower,清单式 4–6 项用 P20 Ledger。

**骨架:** 顶部断言标题(h1 8.4vw,把整墙数字的结论说成一句话)/ 下方 2–4 列 × 2 行网格,每格:巨数(8.4vw,限高 `min(8.4vw,14vh)`,weight 200)+ 标签(h3 4.0vw)+ 单位与口径(caption 1.2vw,含统计期间)/ 单一 accent 只给最重要的一个数,其余 ink;格子间 hairline 分隔(不画完整卡片框,避免卡片海)。

**关键类:** `.data-wall` `.wall-kpi` `.wall-num` `.wall-meta` `.wall-kpi.is-accent`

**动效 recipe:** `wall-count` — 引用值巨数允许 count-up 揭晓(600ms);估算值禁用 count-up(见 visual-qa 数据图形判据);格子按对角顺序 stagger(90ms)

> 版式是「页级可粘贴结构」，约束内容类型匹配（见 `template-library/governance/rules/layouts/00_选版式P0原则.md`）。每个数字都要能回答「哪来的」:口径说明缺失 = 数据诚实违例。数值呈现遵守 `template-library/governance/authoring/index/图表样式规范.md`。
