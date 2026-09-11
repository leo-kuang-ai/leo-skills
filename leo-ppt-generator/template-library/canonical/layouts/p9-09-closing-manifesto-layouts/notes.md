# P9 · quote-pro

本页是 `layout.json` 的说明投影；几何与数量上限以 JSON 为准，字体与颜色由 canonical theme 提供。

绑定模板：`builtin:template:quote-pro`。页面角色：`closing`。

阅读顺序：`kicker` → `quote` → `source` → `route` → `bound`。

## 区域

| 区域 | x | y | 宽 | 高 |
| --- | --- | --- | --- | --- |
| header | 96 | 56 | 1088 | 62 |
| quote_block | 96 | 152 | 1088 | 288 |
| route_row | 96 | 470 | 1088 | 144 |
| bottom_band | 96 | 638 | 1088 | 60 |

## 内容合同

结构化数组通过母版的 `结构数据: {...}` 提供，按模板 `input_fields` 校验元素类型、必填字段与容量。对照页也接受 `对照侧:`，表格页也接受 `表列:` / `表行:`；同一字段只能有一个来源。

- `kicker`：区域 `header`，最多 60 字符。
- `quote`：区域 `quote_block`，最多 90 字符。
- `quote_em`：区域 `quote_block`，最多 90 字符。
- `source`：区域 `quote_block`，最多 60 字符。
- `route`：区域 `route_row`，0–4 项。
- `bound`：区域 `bottom_band`，最多 70 字符。

数组数量与字符数是预检；真实换行后的区域越界、容器溢出由浏览器检查。不能缩字号、截断或隐藏必需内容以通过验收。图表应按槽位尺寸生成，异单位指标使用分面或明确分母的比例比较。
