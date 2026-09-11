# P2 · chain-flow

本页是 `layout.json` 的说明投影；几何与数量上限以 JSON 为准，字体与颜色由 canonical theme 提供。

绑定模板：`builtin:template:chain-flow`。页面角色：`content`。

阅读顺序：`kicker` → `title` → `nodes` → `side_cards` → `stats`。

## 区域

| 区域 | x | y | 宽 | 高 |
| --- | --- | --- | --- | --- |
| header | 64 | 40 | 1152 | 124 |
| chain | 64 | 180 | 560 | 386 |
| side_cards | 660 | 180 | 556 | 386 |
| stats_band | 64 | 594 | 1152 | 88 |

## 内容合同

结构化数组通过母版的 `结构数据: {...}` 提供，按模板 `input_fields` 校验元素类型、必填字段与容量。对照页也接受 `对照侧:`，表格页也接受 `表列:` / `表行:`；同一字段只能有一个来源。

- `kicker`：区域 `header`，最多 60 字符。
- `title`：区域 `header`，最多 24 字符。
- `nodes`：区域 `chain`，2–5 项。
- `side_cards`：区域 `side_cards`，0–3 项。
- `stats`：区域 `stats_band`，0–4 项。

数组数量与字符数是预检；真实换行后的区域越界、容器溢出由浏览器检查。不能缩字号、截断或隐藏必需内容以通过验收。图表应按槽位尺寸生成，异单位指标使用分面或明确分母的比例比较。
