# 新增风格扩展模板（R-29）

> 全库 311 份静态 brief（口径见 [`_INDEX.md`](_INDEX.md) 顶行）之外的用户侧扩展通道（AE-39）：手工新增风格**统一走本模板 +
> 四条治理 lint 合格门**，过门后与内置风格同权参与推荐与渲染。上游出处：
> xhs-visual-director-skill `templates/style_extension_template.md`（模板与
> 合格判断清单的原型），经 leo 化改写为 style-brief-v1 结构与 leo 治理口径。

## 使用方式（四步入位）

1. **复制**：把本模板复制为目标轴子家族目录下的 `<风格名>.md`——
   `01_通用母版/<气质组>/`、`02_行业内容域/<行业组>/`、`03_场景用途结构/<场景组>/`
   选一；仅个人复用不入参考库时，放 `${LEO_PPT_HOME}/styles/`（跳过本门，见
   [`style-library.md`](../../style-library.md)「保存自定义风格」节）。
2. **填写**：替换全部 `<…>` 占位值。占位不替换完，JSON 块无法解析，lint 不会
   统计本文件——以 `lint_style_briefs.py` 输出的 `briefs=` 计数 **+1** 为填写
   完成信号（半成品不会静默通过）。
3. **过门**：逐条核对第九节合格判断清单，四条治理 lint 全绿。
4. **登记**：`_INDEX.md` 对应小节表格加一行、顶行计数 +1；
   `视觉风格配对.md` 主表补配对行（每个可加载风格必须有渲染锚）。

## 一、风格定义

- 风格名称：`<风格名，中文，以"风"结尾，与既有 294 个独立风格不重名（口径见 _INDEX 顶行）>`
- 适合内容：`<一句话：什么内容/场景用它最对>`
- 不适合内容：`<一句话：什么内容用它会错配>`
- 视觉气质：`<3-5 个形容词，如"冷静、精密、克制">`
- 传播优势 / 主要风险：`<各一句话>`

## 二、视觉系统

- 配色（四角色，值内**必须**各含至少一个真实 `#RRGGBB` 锚点）：
  主色 `<…>` / 辅色 `<…>` / 强调色 `<…>` / 中性色 `<…>`
- 字体（**身份字族**，具体到族）：中文主字族 `<如 思源黑体 / Noto Sans SC / MiSans>`
  + 英文搭配 `<如 Inter / IBM Plex>` + 字重区间与气质理由
- 构图：`<标题区位置/主视觉语法/网格>`
- 常用元素：`<3-5 个图元>`
- 标题区 / 正文区 / 留白规则：`<各一句话，可复制的规则不是氛围词>`

## 三、风格 Brief JSON（唯一真值源）

结构契约见 `schemas/style-brief-v1.schema.json`；占位 `<…>` 须全部替换为合法
JSON 值（字符串加引号），并遵守：四角色 HEX 锚点、身份字族、`layout_patterns`
非空。

```json
{
  "type": "16:9 full-slide PowerPoint image",
  "style_name": <"风格名">,
  "aliases": <["中英俗称，供口语命中（R-63），如：暮蓝、dusk-blue"]>,
  "best_for": <"适合内容一句话">,
  "visual_direction": <"英文视觉方向短语，渲染提示词直接消费">,
  "canvas": {
    "aspect_ratio": "16:9",
    "background": <"底色描述 + HEX 锚点">,
    "composition": <"构图骨架一句话">,
    "density": <"low / medium / high + 一句说明">
  },
  "color_palette": {
    "primary": <"主色用途 + #RRGGBB">,
    "secondary": <"辅色用途 + #RRGGBB">,
    "accent": <"强调色用途（克制单点）+ #RRGGBB">,
    "neutral": <"中性色/文字/发丝线 + #RRGGBB">,
    "rule": <"配色纪律一句，写明避免什么">
  },
  "typography": {
    "title": <"标题字族 + 字重 + 气质">,
    "body": <"正文字族 + 行距气质">,
    "labels": <"标签/注记字族 + 规格">,
    "text_quality": <"文字质量要求一句">
  },
  "layout_patterns": [
    <"构图规则 1：可复制的版式句，如：封面＝主标题 30-45% + 单一强调色关键词">,
    <"构图规则 2">,
    <"构图规则 3">
  ],
  "layout_usage_rule": <"整套 deck 的使用纪律一句">,
  "visual_elements": {
    "allowed": <"允许的视觉元素一句话">,
    "avoid": <"禁止的视觉元素一句话">
  },
  "rendering_constraints": [
    <"渲染约束 1：可执行的硬条件">,
    <"渲染约束 2">,
    <"渲染约束 3">
  ],
  "negative_prompt": [
    <"负面提示词 1：要避免的视觉问题，提炼自本风格的 risk/rule">,
    <"负面提示词 2">,
    <"负面提示词 3-5 条">
  ],
  "paired_illustration": {
    "family": <"flat|glass|hand-drawn|dashboard|photographic|editorial|collage|diagram 之一">,
    "density": <"core|supportive|sparse 之一">
  },
  "reference": <"来源标注，如：GitHub: <项目> · <路径>（自创风格写 本库自创）">
}
```

## 四、负面提示词（negative_prompt）

提炼本风格**最容易被渲染错**的 3-5 条视觉问题（不是通用免责清单）——
例如深色风的"廉价蓝紫渐变"、极简风的"装饰堆砌"。

## 五、插画配对（paired_illustration）

family 八选一、density 三选一（词表见 `scripts/lint_style_briefs.py`
`ILLUSTRATION_FAMILIES`）：core＝插画承担主要视觉载体 /
supportive＝辅助证据与氛围 / sparse＝极简点缀。

## 六、构图规则

`layout_patterns` 数组即构图规则真值：每条必须**可复制**（位置 + 占比 +
元素 + 纪律），不是风格词堆砌；配 `layout_usage_rule` 声明整套纪律。

## 七、区分性声明（与既有 294 个独立风格）

> 上游合格判断第 5 条 leo 化：新风格必须自证与既有风格库可区分。

- 最相近的既有风格：`<风格 A>` / `<风格 B>`（至多 3 个，按名称/色板/构图检索）
- 与 A 的差异：`<色板指纹不同：HEX 集合不相等 / 构图语言不同 / 语境不同，一句话>`
- 与 B 的差异：`<一句话>`
- 同板场景（色板与某主风格相同）：**不得**作为独立顶层风格——改在该风格
  brief 上走 `variant_of` 家族变体归属（R-66），或先改色板再入位。

## 八、aliases（口语命中）

中英俗称若干，供"点名"路径经别名命中（R-63）；用户口语反馈补进 aliases
候选须先经治理确认，不直接落盘（R-64）。

## 九、合格判断清单

> 若本风格来自候补源矿（见 [`style-candidates.md`](../../style-candidates.md)），
> 合格门为其表头"补货门"五步流程（信号确认 → 四重去重 → 精选与许可核验 →
> 金样板三页 + 配对预览 → lint + audit 出口）；本清单是其中第 4-5 步的执行细节，
> 前三步在候补台账侧完成并留痕。

结构门（可机检，风格级四条治理 lint 全绿才算过门；仓库级
`lint_render_templates`/`lint_skill_structure` 提交前另跑，合计六条）：

- [ ] `lint_style_briefs.py`：`briefs=` 计数 +1；无 ERROR、无未登记 WARNING
      （四角色 HEX 锚点 + 身份字族，新文件不进基线白名单）；
      `family_duplicate` 不触发（色板指纹不与既有顶层风格相同）。
- [ ] `lint_style_index.py`：`_INDEX.md` 顶行计数与表格行已同步（+1）。
- [ ] `lint_style_governance.py`：`视觉风格配对.md` 已补配对行（有渲染锚）。
- [ ] `lint_layout_grid.py`：本风格未引入版式网格偏离（若带 layouts
      blueprint，须过 0.4vw 模数与双约束）。

人工门（上游清单 leo 化，逐条自述）：

- [ ] 能说明**为什么**适合该内容（不是只给风格词）。
- [ ] 有明确主视觉（第一眼落点可描述）。
- [ ] 有可复制的构图规则（`layout_patterns` 每条可执行）。
- [ ] 有清晰的负面提示词（针对本风格的真实风险）。
- [ ] 能和已有 294 个独立风格区分开（第七节自述成立）。

可选门：

- [ ] 金样板三页（封面/内容/图表）：`generate_style_gallery.py --render-golden`
      路线按需补做，产物进 `samples/style-gallery/<风格名>/`，双跑 sha256 一致。
