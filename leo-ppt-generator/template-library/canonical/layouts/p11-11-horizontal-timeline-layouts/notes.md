# P11 · timeline-pro

本页是 `layout.json` 的说明投影；几何与数量上限以 JSON 为准，字体与颜色由 canonical theme 提供。

绑定模板：`builtin:template:timeline-pro`。页面角色：`content`。

阅读顺序：`kicker` → `title` → `steps` → `bottom`。

## 区域

| 区域 | x | y | 宽 | 高 |
| --- | --- | --- | --- | --- |
| header | 64 | 40 | 1152 | 124 |
| step_cards | 64 | 180 | 1152 | 402 |
| bottom_band | 64 | 610 | 1152 | 76 |

## 内容合同

结构化数组通过母版的 `结构数据: {...}` 提供，按模板 `input_fields` 校验元素类型、必填字段与容量。对照页也接受 `对照侧:`，表格页也接受 `表列:` / `表行:`；同一字段只能有一个来源。

- `kicker`：区域 `header`，最多 60 字符。
- `title`：区域 `header`，最多 24 字符。
- `steps`：区域 `step_cards`，3–5 项。
- `bottom`：区域 `bottom_band`，0–2 项。

数组数量与字符数是预检；真实换行后的区域越界、容器溢出由浏览器检查。不能缩字号、截断或隐藏必需内容以通过验收。图表应按槽位尺寸生成，异单位指标使用分面或明确分母的比例比较。
