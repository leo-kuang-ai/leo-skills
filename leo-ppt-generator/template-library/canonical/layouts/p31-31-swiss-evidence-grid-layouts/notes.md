# 版式：P31 · Swiss Evidence Grid · 瑞士证据网格

**分类:** canonical/layouts（图片证据版式）

**用途:** 2–3 张同类图片组成的证据链(竞品对比、版本演进、多场景验证)。

**适用内容类型:** **2–3 张同类真实截图/照片,每张必须配一句证据说明**(caption)。纯文字卡片场景禁用(用 P4 六格 / P16 微卡);超过 3 张同类图片改用 P15 Image Matrix(可承载 8–12 张 + 总数据)。

**骨架:** 顶部断言标题(一行,把 2–3 张图的关系说成结论)/ 下方 2–3 列等宽网格(gap 与版心 gutter 一致)/ 每格:图片 `fit-contain` + 底部 caption 带(kicker + 一行说明,字号 ≥16px 双口径见通用设计规范)。

**关键类:** `.evidence-grid` `.ev-cell` `.ev-caption`

**动效 recipe:** `evidence-grid` — 格子依序 stagger-in(120ms 错开) → caption 底线最后画出

> 版式是「页级可粘贴结构」，约束内容类型匹配（见 `template-library/governance/rules/layouts/00_选版式P0原则.md`）。证据链的意义在 caption:每张图必须回答「它证明了什么」。数值呈现遵守 `template-library/governance/authoring/index/图表样式规范.md`。
