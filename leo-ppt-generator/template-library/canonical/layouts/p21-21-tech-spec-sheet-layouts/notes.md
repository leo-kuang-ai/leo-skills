# 版式：P21 · Tech Spec Sheet · 规格说明书

**分类:** canonical/layouts（guizang-ppt-skill Swiss 版式）

**用途:** 产品规格、benchmark 数据、性能基线展示(多 KPI + 数据授权竖线)。

**适用内容类型:** **产品规格 / benchmark / 性能基线**(必须有真实多维数据,3 KPI + 9 项竖线序列 = 12+ 数据点)。典型如:模型评分、API 性能、压测结果。是 deck 中数据密度最高的版式。

**骨架:** 左 4 行大标题 / 中部 3 KPI(顶部 hairline + 数字 + 单位)/ 右下 9 根垂直竖线——**高度必须绑定 9 项 approved 真实数值序列并直接标注数值,无数据序列时删除竖线改 hairline 网格**(装饰性高低竖线 = 编形状,见图表样式规范 §一) / 底部巨数 + Yearly goal + 三 tag + 右下角 MP-XX + 页码。

**关键类:** `.tech-spec` `.spec-title-col` `.spec-kpi-grid` `.spec-bars`(`.bar-vert`,scaleY 弹起,transform-origin:bottom;高度∝数值)

**动效 recipe:** `tech-spec` — hero 区淡入 → 标题入 → KPI 顶线一根根画出 → 底巨数 pop → 竖线从底部 scaleY 弹起(50ms 错开)

> 版式是「页级可粘贴结构」，约束内容类型匹配（见 `governance/rules/layouts/00_template-library/governance/rules/layouts/00_选版式P0原则.md`）。动效 recipe 与图形语义耦合，不是统一 fade-up。数值呈现遵守 [`../../../governance/authoring/index/图表样式规范.md`](../../../governance/authoring/index/图表样式规范.md)（形状授权/置信度语法/直接标注）。
