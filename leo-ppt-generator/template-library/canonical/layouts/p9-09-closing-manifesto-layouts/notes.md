# 版式：P9 · Closing Manifesto · 收束宣言

**分类:** canonical/layouts（guizang-ppt-skill Swiss 版式）

**用途:** 整套 deck 收尾页。

**适用内容类型:** **deck 收尾**(每个 deck 只有一页)。固定结构:左侧宣言短句 + 右侧 3 条 takeaway(编号 + 标题 + 一行说明)。**不能在中间页使用**(那会与 P1 封面重复)。

**骨架:** 左右 5/7 分屏 / 左 ink 或 IKB 底色大字宣言(断言句 ≤12 字,字阶限高 `min(9.2vw,15vh)`,`.ascii-bg` 打点纹理) / 右白底 3 条 takeaway(编号 mono + 标题 + 一行说明,行间距 ≥9vh) / 底部 hairline + 出处行(可选)。

**关键类:** `.slide.split` `.half.b-accent` `.ascii-bg`(IIFE 自动启动)

**动效 recipe:** `split-statement` — 左 ink/IKB 标题字符序列升起 → 右白半 takeaway 三条尾随

> 版式是「页级可粘贴结构」，约束内容类型匹配（见 `template-library/governance/rules/layouts/00_选版式P0原则.md`）。动效 recipe 与图形语义耦合，不是统一 fade-up。