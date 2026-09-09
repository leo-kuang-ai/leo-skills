# 社交卡片规格（social-card-specs）

> **定位**：社交卡片输出形态（小红书组图 3:4 / 方图 1:1 / 公众号宽图 21:9 + 封面对）的
> **内容与版式规格层**。本文档是这类输出的规格真值：画板、密度、字号带宽、分页策略、
> 主题 token 与测量式质检的判定阈值全部以本文为准。
> **当前为实验性能力**：SKILL.md 路由与 eval 门禁的正式接入属后续专门批次；在接入
> 之前，生成社交卡片时应直接读取本文作为规格约束，不得凭 PPT 16:9 经验类推。
>
> **来源**：guizang-social-card-skill（AGPL，授权已线下确认），快照 2026-07 v0.15。
> 规格抽取自其 `references/`（platform-specs / style-system / components /
> content-planning / portrait-fill / layout-recipes / theme-presets / qa-checklist）
> 与 `validate-social-deck.mjs`（R1-R9 规则实现）。本文与其上游的关系类似
> [`template-library/reference/sources/来源_guizang/`](../template-library/reference/sources/来源_guizang/00_README.md)
> 的组件模板先例（这是 provenance/reference 来源，不是活动风格真值）：
> 判定式抽取，不整篇搬运。

## 一、画板规格

| 画板 | 像素 | 比例 | section class | 命名 | 适用 |
| --- | --- | --- | --- | --- | --- |
| 小红书组图单页 | 1080×1440 | 3:4 | `.poster.xhs` | `xhs-01-cover.png`、`xhs-02-<topic>.png`… | 组图封面与内容页；Live Photo 卡同画板 |
| 方图 | 1080×1080 | 1:1 | `.poster.square` | `wechat-1x1-cover.png` | 公众号 1:1 封面；单图卡片（绿洲/即刻类） |
| 宽图 | 2100×900 | 21:9 | `.poster.wide` | `wechat-21x9-cover.png` | 公众号主封面 |
| 封面对预览 | 2400×1180 起 | — | `.wechat-pair-preview` | `wechat-cover-pair-preview.png` | 21:9 与 1:1 并排核对，仅供审阅，非交付件 |

判定式规则：

- 公众号封面**成对生成**：21:9 主封面 + 1:1 方图封面，同 HTML 文件内各自独立构图；
  预览节仅用于并排检查。1:1 是**另写的短标题构图**，不是 21:9 的裁切或压字。
- 全部按高分辨率导出 PNG（文字多的图不用 JPEG）；文件名稳定有序。
- 3:4 安全区：左右 72-96px、顶 72-112px、底 80-120px；文字与关键对象入安全区。
  1:1/21:9 的贴边下限按外边距 token：四周 80px，宽图左右 160px。
- 每个 `.poster` 尺寸固定，内容禁用 `vw`/`vh`。

## 二、密度硬规则（3:4 组图）

1. **内容覆盖 ≥75% 画布高**（≥1080px / 1440px；按 4 横带占用合并计算，容差后
   机读线为 74.5%）。活跃构图目标 78%。
2. **空白横带 >15% 画布高（>216px）必须给留白理由**。合法理由仅三类：
   hero 图呼吸、单句论点页（M04 类）的天留白、顶部/底部引导边距（合计 ≤15%）。
   无理由即欠填，欠填的修法是**扩内容或换版式**——缩画布、加装饰 blob 都不是修法。
3. **禁 `flex:1` 上下夹击**：不得用弹性空隙把内容顶到垂直居中形成上下大空白；
   页脚吸底用 flex 列 `margin-top:auto`（或 grid `auto 1fr auto`），禁
   `position:absolute` 页脚（上游 Anti-pattern C）。
4. **4 横带判据**（渲染后执行）：把画布按内容分布划 4 个 360px 横带
   （0-25% / 25-50% / 50-75% / 75-100%），每带判三类——
   - **实填**：含文字、图、数据或规则线；
   - **有据留白**：命中第 2 条理由白名单；
   - **欠填**：无理由的空。
   通过条件：实填覆盖 ≥75% 画布高；任一欠填带 >15% 画布高 = 失败；
   相邻两带同为有据留白 = 中段 >25% 空洞，失败。
5. 欠填气味（人审快判）：台账/表格占画布高 <45%；下方 25% 空且非氛围 hero 页；
   四行列表短行 + 下方大片空白；正文垂直居中无节奏。

## 三、字号与标题带宽

**最小可读字号**（1080×1440 在手机 360-420 逻辑像素宽下检视；设计下限与机读
下限双口径，机读值即 `validate_visual_measure.py` R4 阈值）：

| 角色 | 设计下限 | 机读下限（R4） |
| --- | --- | --- |
| 正文 body | 28px | 22px |
| 导语 lead | 30px | 26px |
| 说明/脚注 caption | 20px（不破 18） | 18px |
| 标签/元信息 meta | 20px（mono） | 18px |
| 网格单元标题 | 24px | 20px |
| 数字注释 | 22px | 20px |

放不下时**删文案，不缩字号**；正文缩到下限以下 = 失败。

**中文标题长度-字号带宽表**（先选带宽再定字号； Editorial display 与 Swiss
h-hero 双列，1080×1440 基准）：

| 标题形状 | Editorial display | Swiss h-hero |
| --- | --- | --- |
| 1 行 ≤6 字 | 132px | 240px |
| 1 行 7-10 字 | 108px | 200px |
| 2 行、每行 ≤8 字 | 96px | 180px |
| 2 行、任一行 9-12 字 | 84px | 152px |
| 3 行（少见） | 72px | 132px |

判定式补充：

- 仍放不下 → **先缩文案**；3 行即上限，方形画布上 3 行几乎必错（换标题句，
  参见 [`template-library/reference/sources/来源_guizang/标题压缩模板.md`](../template-library/reference/sources/来源_guizang/标题压缩模板.md)）。
- 字重双系统规则（越大越细、越小越粗）沿用风格库既有表述，判据见
  [`../template-library/governance/authoring/index/通用设计规范.md`](../template-library/governance/authoring/index/通用设计规范.md) 与
  [`visual-qa.md`](visual-qa.md)「字重阶梯」行：按风格表情档校验，同组图不跨档。
- 1:1 方图短标题 4-10 字（1-2 行、每行 ≤6 字）；21:9 宽图 1 行 ≤14 字；
  3:4 组图页标题 12-30 字、1-2 行。
- 展示标题与相邻内容块的间距下限：28px（宽图 24px；局部小标题 16px）。

## 四、组图分页策略

**压缩阶梯**（从原文到卡片，逐层压缩，不整篇上图）：

1. 核心主张：一句话。
2. 观看承诺：滑动能得到什么。
3. 观点地图：4-8 个观点。
4. 页钩子：短、具体、拒绝抽象标签。
5. 碎片正文：只解释当页视觉所需的最少文字。

**页数映射**：600-1000 字 → 5-7 图；1000-1800 字 → 7-9 图；更长源文压缩到
8-10 图、其余进正文文案。多页下方大面积空 → 合并相邻观点。

**判定式规则**：

- **一页一观点**：每页 2-4 条短要点或一段精炼正文；标题用「动词 + 后果」句式。
- **7 页组图 ≥5 种页面形状**。形状库：封面/特写图 · 文章分栏 · 高台账 · 证据截图 ·
  金句/氛围论点 · 清单/对比 · 结语。`标题 + 导语 + 3 行`同一组图重复不超过 2 次。
- 全出血图封面（M16 类）不连续出现两次；截图页给截图 45%-65% 页高并减文字。
- 封面结构：大钩子标题 + 一个强视觉 + 底部 3-5 要点条；长副标题入后页，不上封面。

## 五、主题 token（8 变量）

社交卡片主题用 8 个规范化 token 表达；Editorial 与 Swiss 两套 CSS 变量按下表
映射到同一组（左列为规范名，右上为 Editorial 变量，右下为 Swiss 变量）：

| 规范 token | Editorial 变量 | Swiss 变量 | 用途 |
| --- | --- | --- | --- |
| `paper` | `--paper` | `--paper` | 纸底/主背景 |
| `paper_2` | `--paper-2` | `--grey-1` | 图井/议题条/浅色带 |
| `ink` | `--ink` | `--ink` | 主文字色 |
| `muted` | `--muted` | `--grey-3` | 次级文字 |
| `line` | `--line` | `--grey-2` | 发丝线/边线 |
| `accent` | `--accent` | `--accent` | 强调色（Swiss 全组图仅一个） |
| `accent_soft` | `--accent-soft` | —（不使用） | 强调色的浅衬 |
| `accent_on` | —（不使用） | `--accent-on` | 强调色上的文字色 |

与活动风格库的映射先例：[`eink-magazine/brief.json`](../template-library/canonical/styles/eink-magazine/brief.json) 与
[`瑞士网格风/brief.json`](../template-library/canonical/styles/瑞士网格风/brief.json)
的 `theme_presets` 数组即按本表键名（`paper`/`paper2`/`ink`/`muted`/`line`/
`accent`/`accent_soft` 与 `grey1`/`grey2`/`grey3`/`accent_on`）登记上游
6 + 4 个预设。判定式规则：

- 一组图**一个**预设，不混palette、不混两个 accent；Midnight Ink 是 Editorial
  唯一合法暗色预设，不自造第二套暗色。
- Editorial 禁平色底：纸底 + 纸纹 + 墨晕/等高线/WebGL 氛围层（3-5 层）；
  氛围层不压正文与截图。Swiss 反向禁：无渐变、无阴影、无圆角卡。

## 六、测量质检接入

机读质检脚本：[`scripts/validate_visual_measure.py`](../scripts/validate_visual_measure.py)。
它是 [`visual-qa.md`](visual-qa.md) 人审判据的**机读补充而非替代**——溢出、字号
下限、密度、贴边、标题间距五类几何判据先走脚本，风格身份、构图品味仍走人审。

```sh
# 纯规则态（测试与 CI 主入口）：输入测量结果 JSON
python3 leo-ppt-generator/scripts/validate_visual_measure.py --measurements deck.json

# 渲染测量态（可选）：真实渲染 HTML 并自动收集几何
python3 leo-ppt-generator/scripts/validate_visual_measure.py --html index.html
```

判定式约定：

- **规则子集**：R1 溢出（含 1-40 微调 / 41-90 压缩 / 91-160 删减 / >160 换版式
  的修正阶梯）、R4 最小字号（表 1 机读列）、R5 4 横带密度（3:4）、R8 视觉边界
  （贴边下限 + 底部留白上限）、R9 标题间距。阈值常量写在脚本模块头部，与本文
  数值一一对应。
- **级别与退出码**：R1/R8 出界 = error（退出码 1）；R4/R5/R8 留白与贴边/R9 =
  warn（建议级，不阻断）。退出码 2 = 用法错误；3 = `--html` 渲染态降级。
- **playwright 前置**：`--html` 需要 `pip install playwright && playwright install
  chromium`；缺失时脚本打印固定降级块（含安装指引与 `--measurements` 替代路径）
  并以退出码 3 结束，不抛 traceback。
- **测量 JSON 结构**：画布（宽/高/画板）+ 页列表，每页为内容块数组
  （`id`/`role`/`y_top`/`y_bottom`/`x_left`/`x_right`/`font_size`/`text`），
  可选 `whitespace_reasons` 留白理由标注（豁免第 2 条空白横带判定）与
  `background: true` 氛围层标记（不计密度与贴边）。完整 schema 见脚本 docstring。
- 空白横带豁免在渲染态通过 `<section class="poster"
  data-whitespace-reasons='[{...}]'>` 声明。
- 上游 R1-R9 中依赖计算样式或 DOM 语义的规则（R2 页脚碰撞、R3 Swiss 粗大字、
  R6 标题行数硬上限、R7 figure 默认外边距）不在机读子集内：R2/R3/R7 需渲染态
  计算样式，R6 需断行结构，均留在人审清单（`visual-qa.md` 第三节）执行。
