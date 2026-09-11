# P1 · cover-pro

本页是 `layout.json` 的说明投影；几何与数量上限以 JSON 为准，字体与颜色由 canonical theme 提供。

绑定模板：`builtin:template:cover-pro`。页面角色：`cover`。

阅读顺序：`kicker` → `title` → `subtitle` → `footer_left` → `footer_right` → `arch_hint`。

## 区域

| 区域 | x | y | 宽 | 高 |
| --- | --- | --- | --- | --- |
| title_block | 96 | 100 | 1088 | 310 |
| arch_band | 96 | 460 | 1088 | 88 |
| footer_band | 96 | 604 | 1088 | 76 |

## 内容合同

结构化数组通过母版的 `结构数据: {...}` 提供，按模板 `input_fields` 校验元素类型、必填字段与容量。对照页也接受 `对照侧:`，表格页也接受 `表列:` / `表行:`；同一字段只能有一个来源。

- `kicker`：区域 `title_block`，最多 60 字符。
- `title`：区域 `title_block`，最多 40 字符。
- `subtitle`：区域 `title_block`，最多 60 字符。
- `footer_left`：区域 `footer_band`，最多 60 字符。
- `footer_right`：区域 `footer_band`，最多 60 字符。
- `arch_hint`：区域 `arch_band`，最多 70 字符。

数组数量与字符数是预检；真实换行后的区域越界、容器溢出由浏览器检查。不能缩字号、截断或隐藏必需内容以通过验收。图表应按槽位尺寸生成，异单位指标使用分面或明确分母的比例比较。
