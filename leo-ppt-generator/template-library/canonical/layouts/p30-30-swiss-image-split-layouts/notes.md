# 版式：P30 · Swiss Image Split · 瑞士图文分栏

**分类:** canonical/layouts（图片证据版式）

**用途:** 单图解释论点、图文混排正文页、低数据 hero。

**适用内容类型:** **1 张核心图片 + 一段解释**(0–1 个数据点)。图片是本页主角:产品界面、机制截图、实验图、场景照。没有真实图源时禁用(占位灰图破坏视觉);需要 3 个 KPI 落地时改用 P22 Image Hero。

**骨架:** 左右 7/5 分屏 / 左图容器 `fit-contain`(保留像素,占页高 60–72%,直角无阴影,白底信息图配 `--paper` 底) / 右列:断言标题 + ≤2 段正文 + 可选单 KPI 巨数(限高 `min(9.2vw,15vh)`) / 图与文案共用顶部基线,底缘对齐。

**关键类:** `.image-split` `.split-img`(fit-contain) `.split-copy`

**动效 recipe:** `image-split` — 左图 fade-in(scale 1.02→1) → 右列标题 rise → 正文两段先后入场

> 版式是「页级可粘贴结构」，约束内容类型匹配（见 `template-library/governance/rules/layouts/00_选版式P0原则.md`）。图片是网格中的证据块,不是装饰背景。数值呈现遵守 `template-library/governance/authoring/index/图表样式规范.md`。
