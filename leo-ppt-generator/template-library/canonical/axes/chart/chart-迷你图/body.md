# 图表语法：迷你图 / 指标卡(Sparkline)

**分类:** 11_图表语法

**定位:** 高密度并置 — 行内小图,给一列指标各配一条「趋势尾巴」。Tufte 判据:用
最少墨水表达最大数据密度,适合台账/账单/指标墙页型(P20 Ledger / P15 Matrix)。

## 说明

**载体**:mermaid 无原生 sparkline;**走可编辑路线原生小图**或「文字趋势箭头 +
近 N 期数值」的最小表达。图片式路线用简化三段线(升/平/降)示意,不承载精确数值
(精确数值由页面文字区承载,见 `template-library/governance/authoring/index/图表样式规范.md` 第五节)。

## 示例语法(文字最小表达,可执行)

```text
| 指标 | 本期 | 趋势 |
| --- | --- | --- |
| MAU | 248万 | ↗ 205→248(近3期) |
| 付费率 | 3.2% | → 3.1→3.2(近3期) |
```

> **示例数字仅为语法演示，必须替换为 approved 真实数据**（见 `template-library/governance/authoring/index/图表样式规范.md`）。

## 纪律

- Sparkline 是**辅助编码**:精确数值必须同现(表格列/直接标注),小图不单独承载结论。
- 全 deck 的趋势窗口一致(都是近 3 期/近 12 月),不得混用制造不同印象。
- 估算期数用「~」前缀。

> 图表的坐标轴/图例/配色处理沿用 `rendering 轴` 与 `template-library/governance/authoring/index/图表样式规范.md`；颜色来自 deck colors 锚点，本文件只定结构与语法。
