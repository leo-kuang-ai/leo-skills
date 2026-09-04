# leo-ppt-generator 风格系统评审（十位顶尖设计师视角）

- 日期：2026-08-29
- 范围：`leo-ppt-generator/references/styles/` 风格库全量（136 份 JSON 风格 brief + 119 份分节轴文档 + 14 份规则/索引文档）、`references/style-library.md`、`references/visual-qa.md`
- 方法：三源证据交叉——(1) 风格库深读（索引层 / 版式库 / 风格文件 schema / 图表语法 / 页面语义逐层走查，关键断言经本地 grep/diff 复核）；(2) 业界调研（Slidesgo / SketchBubble / Envato / SlideRabbit / 微软 PowerPoint 官方博客 / Canva 中文趋势 / 优设 / Gamma·Beautiful.ai 对比评测 / WCAG / assertion-evidence 学派）；(3) 与仓内既有评审对齐（工程合同侧、UX 侧、行业内容侧三份姊妹篇，见 §四）。
- 结论速览：这套风格库的**骨架领先业界**（六轴正交 + 内容-版式匹配纪律 + 对抗式视觉 QA，恰是 Gamma / Beautiful.ai 的弱项），但风格内容本身存在四类系统性短板：**图表样式规范缺失（最严重，且有一处悬空引用）、排印参数不落地、无障碍只有半条规则、"风格不带 HEX" 的 token 化方向半途而废**。另有版式缺口、麦肯锡风格近重复漂移、deck 级动效规范空白。所有 P0 级事实断言已于落盘前逐条复核。

## 0. 优先级矩阵

| 档位 | 事项 | 一句话理由 |
|---|---|---|
| P0 | 修复悬空引用与库内缺陷：`data-journalism`（14 个文件引用、目标不存在）、P23/P24 版式文件缺失、麦肯锡近重复、`视觉风格配对.md` 表格断裂 | 纯修正、证据已复核、阻断下游一切图表样式工作 |
| P0 | 新建图表样式规范（坐标轴 / 图例 / 数据标签 / 网格线 / 直接标注规则），并给图片式路线的 stylized 图表定披露规则 | 全库最薄弱维度；数据页是商务 PPT 的核心页型 |
| P1 | 排印 token 化：全局中文字体栈 + 行高阶梯进 schema；字号下限按渲染口径校准 | 136 份 brief 的 typography 几乎全是模糊自然语言 |
| P1 | 无障碍体系化：大字 3:1、非文本 3:1、双重编码升格为铁律，进 visual-qa 机检 | 现状只有一条 4.5:1，未成体系 |
| P1 | 补目录 / 团队 / 引用 / 数据大屏 / 纯氛围全图版式骨架 | 高频页型只有语义文件、无骨架 |
| P1 | "风格不带 HEX" 二选一：落地三层 token，或撤回宣称 | `设计体系.md` 方向与 138 份写死 HEX 的实现脱节 |
| P2 | deck 级动效规范（转场白名单、时长预算、morph/kinetic 只给可编辑路线） | 版式级 recipe 优秀，deck 级空白 |
| P2 | 断言式标题合同化；全局信息密度上限 | 业界实证最充分的单条规则，现凭模型即兴 |
| P2 | 迷幻国潮 2.0、暖调柔形等趋势风格；高频风格 light/dark 双模式配对 | 中文市场趋势缺口；暗色已成主流选项 |
| P2 | brief JSON Schema + lint + 护栏前移进 `style render`，纳入 evals | 数值约束从事后打回前移为事前注入，省真实图片成本 |

## 一、业界共识速览（2025–2026）

跨 Slidesgo / SketchBubble / Envato / SlideRabbit / 微软 PowerPoint 官方博客 / Canva 中文趋势 / 优设等来源，与本次评审直接相关的共识有八条：

1. **AI 原生设计工作流是第一大趋势**，对手的差异化路线已分化：Gamma 走"编辑风卡片 + 叙事流"（但导出保真度弱）、Beautiful.ai 走"结构化智能模板 + 品牌一致性"（但灵活性差）——本技能的 `style render` 确定性注入正好卡在两者之间的空位上，这是护城河，应当强化而非稀释。
2. **粗犷几何大字排版（bold geometric type）领衔 2026**，动态排版成为主流视觉语言（优设）；库里"大字报巨型排版风"已覆盖，方向正确。
3. **图表的"直接标注 + 一页一结论"是数据页最大差异化**（Analyst Academy、storytelling with data 系）：图例是坏东西，直接标在数据点上；坐标轴 / 网格线克制。
4. **暗色模式成为主流选项**（基于千+ 份 deck 的分析），但需成对出现而非孤立风格。
5. **有目的的动效（purposeful motion）取代炫技**：动效用于引导注意力、表达变化，动效本身成为品牌语言（Behance 2026）。
6. **可访问性成体系化**：WCAG 正文 4.5:1、大字与非文本 3:1；投屏正文业界建议 18–24pt 下限。
7. **Bento 不对称分格**仍是 Apple keynote 系主导版式，适合产品 / 功能展示页。
8. **中文市场特有**：「迷幻国潮风 2.0」（东方意象 + 高饱和渐变光影）、新中式传统色（故宫红、琉璃色）、暖色调柔和形状取代纯白页面（微软官方博客）。

## 二、十位设计师的逐项评审

### 1 · 字体排印师（中文排印背景）

字号下限、"越大越轻"字重铁律这些护栏质量很高，但**字体族几乎全部停留在 "clean sans-serif" 模糊描述**，全库只有电子墨水杂志风（Noto Serif SC / Songti SC / Playfair Display）、瑞士网格风（Inter / Helvetica Neue / Noto Sans SC）两份落到具体字体，行高（line-height）数值几乎为零。中文 PPT 的排印成败一半在字体栈（思源黑体 / MiSans / HarmonyOS Sans 的气质差异巨大）。

→ 优化：在通用设计规范中建立**全局中西文 fallback 栈 + 行高阶梯**，风格文件只允许在统一 schema 内 override。

### 2 · 编辑设计师（网格与版面）

无统一版心 / 栅格数值（只有瑞士网格风提了 12/16 栏、93vh/3vh 安全区散落各处）；**目录页、团队页、纯引用页、数据大屏四类高频页面在版式库中没有骨架**（`13_页面语义/` 有对应语义文件但自我声明"只是排序信号"）；跨画幅只有一条反模式，没有适配规则。

→ 优化：补 P23–P27 五个骨架（`12_版式库/00_选版式P0原则.md:31-32,50-51` 已引用 P23 Swiss Image Split / P24 Swiss Evidence Grid 但**文件不存在**）；定义版心 token 与跨画幅换算规则。与多行业评审 §六的版式缺口清单（章节隔页 / 单数字页 / 参数表 / 文献页 / 教学三件套）合并执行。

### 3 · 色彩与品牌系统设计师

`00_索引/设计体系.md` 宣称"风格不带 HEX、色值由 deck colors 锚点锁定"，**但全部 138 份含 color_palette 的 brief 仍然写死 HEX**——规范与实现脱节，品牌轴覆盖时靠运行时遮蔽而非声明式 token。另外 `styles/麦肯锡风格.md`（顶层）与 `01_通用母版/商务专业/麦肯锡咨询风.md` 是内容同义的近重复，且 diff 复核显示 `style_name` / `best_for` / `visual_direction` 措辞已经分叉——**漂移不是风险而是既成事实**。

→ 优化：三层 token（global 护栏 → style 调色板角色 → deck 品牌覆盖）落地到 schema，删除重复文件。与多行业评审 §四的品牌 VI 注入链路（`style render --brand`、`brand_assets` 契约块）同属一条链路，宜合并规划。

### 4 · 数据可视化编辑（FT / 经济学人系）——最严重的一项

`11_图表语法/` 的样式规范被全库 14 个文件转引给一个**不存在的 `data-journalism` 文件**（grep 复核：引用文件 14 个、目标文件 0 个）；坐标轴线宽、图例位置、数据标签格式、网格线密度全库零规定。更结构性的矛盾：`08_图片渲染/` 明确"图内图表 stylized、不含真实数据值"——这与 P0 原则"禁止编数据"形成暗伤：**图片式路线的图表天然无法承载诚实的数据标签**，而业界趋势恰恰是直接标注真实数值。

→ 优化：新建图表样式规范（补上 data-journalism）；数据密集场景在路由层默认导向可编辑 / 混合路线，图片式路线的 stylized 图表在交付时明示局限。

### 5 · 叙事顾问（Duarte / assertion-evidence 学派）

论证模式轴 5 种是同行少有的好设计，但缺一条业界被实证最充分的规则：**完整句断言式标题（assertion headline）+ 视觉证据**（Michael Alley 的对照研究显示显著提升理解率）。现在标题是否为断言句全凭模型即兴。

→ 优化：把"标题必须是完整句断言而非话题词"写进通用设计规范或论证模式轴，作为可 QA 检查项。多行业评审 §五的"行动标题质检闭环 + 标题连读稿"从内容侧独立命中同一缺口，两路评审交叉验证，建议合并为同一改造。

### 6 · 动效设计师

版式级动效 recipe（P11 timeline-walk 220ms/节点、P20 180ms/行、P4 90ms/格、P21 50ms 错开等）是同类产品罕见的精细度，**但 deck 级完全空白**：无翻页 / 转场规范、无总时长预算、无降级策略。图片式路线整页一张图、内动效天然为零，这个局限没有被披露给用户。

→ 优化：新增 deck 级动效规范（转场白名单 fade/morph、时长预算、"每动效必须回答引导什么注意力"）；可编辑路线启用 morph + kinetic typography（2026 主流动效手法），图片式路线在交付说明中标注。

### 7 · 无障碍专家

全库唯一一条是 4.5:1（数值上恰为 WCAG AA 正文线，但没有体系：无大字 3:1、无非文本对比、双重编码只在 visual-qa 有一条）。还有一个需要校准的疑点：**正文 ≥18px 下限**换算到标准 16:9 PPT 页面（960×540pt）约只有 9–13.5pt，明显低于业界投屏 18–24pt 的正文建议——px 口径若基于 1920 宽画布则偏小近一半。

→ 优化：把对比度体系化成文并进 visual-qa 机检（runtime `validate_pptx.py` 可挂读屏顺序 / alt text 检查）；按实际渲染口径校准字号下限。多行业评审 §四的"compose 阶段程序化对比度计算 + 色盲安全序列"从工程侧命中同点，交叉验证。

### 8 · 信息设计 / 认知科学

版式数量硬约束（P4=6、P8=2）很好，但**没有全局"每页字数 / 要点数"上限**，密度只有 low/medium 定性词；行业域风格（46 份）装饰自由度大，无认知负荷上限护栏。

→ 优化：在通用设计规范加每页字数与要素总数上限，行业域风格渲染后同样强制过闸。

### 9 · AI 原生产品设计师（对标 Gamma / Beautiful.ai / Lovart）

风格广度 136 份远超对手，但对手在拼"生成后可迭代"与"风格质量一致性"。两个趋势缺口：中文市场的**迷幻国潮 / 新中式 2.0**（高饱和渐变 + 东方意象 + 传统色）库里只有水墨禅意、历史古风，缺现代高饱和变体；微软趋势指向的**暖色调柔和形状**全库整体偏冷（科技 / 商务系大量深蓝底）。

→ 优化：补 2–3 份趋势风格（迷幻国潮、暖调柔形）；与模版推荐计划（`docs/plans/2026-08-28-001-feat-leo-ppt-style-recommendation-plan.md`）联动，把"样张双生"扩展为趋势新风格的验收场。

### 10 · 设计系统工程师

风格 brief 是 JSON 块、`runtime/src/leo_ppt_generator/styles.py` 可解析，但**没有 JSON Schema 校验文件**：18px/4.5:1 等数值约束全在 QA 侧（事后打回），不在生成侧（事前注入）——每张打回重做的图都是真实图片成本。字号数值散落三处（通用设计规范 18/16/14px、电子墨水 28/24/64px、瑞士网格 72px 阈值）靠"上位护栏优先"的口头约定防冲突。`设计体系.md` 定义的视觉风格六节 markdown 格式也零落地（全部视觉风格仍是 JSON brief）。

→ 优化：给 brief 定 schema + lint（HEX 格式、数量约束、禁词），把护栏数值**前移进 `style render` 输出**而非只留在 QA 清单；schema 校验纳入 evals。

## 三、优化清单（按优先级）

| 档 | 事项 | 落点 | 交叉验证 |
|---|---|---|---|
| **P0** | 修复悬空引用：`data-journalism`（14 处）、P23/P24 版式文件缺失、麦肯锡近重复、`视觉风格配对.md:46` 表格断裂 | `references/styles/` | 本报告 §二.2/3/4 |
| **P0** | 新建图表样式规范（坐标轴 / 图例 / 数据标签 / 网格线 / 直接标注规则），并给图片式路线的 stylized 图表定披露规则 | `11_图表语法/` + `00_索引/` | 多行业评审 §七（技术图保真） |
| **P1** | 排印 token 化：全局中文字体栈 + 行高阶梯进 schema；字号下限按渲染口径校准 | `00_索引/通用设计规范.md` | — |
| **P1** | 无障碍体系化：大字 3:1、非文本 3:1、双重编码升格为铁律，进 visual-qa 机检 | `通用设计规范.md` + `visual-qa.md` | 多行业评审 §四 |
| **P1** | 补目录 / 团队 / 引用 / 数据大屏 / 纯氛围全图 5 个版式骨架 | `12_版式库/` | 多行业评审 §六（合并清单） |
| **P1** | "风格不带 HEX" 二选一：落地三层 token，或撤回宣称 | `设计体系.md` + `styles.py` | 多行业评审 §四（品牌 VI 链路） |
| **P2** | deck 级动效规范（转场白名单、时长预算、morph/kinetic 只给可编辑路线） | 新增轴文档 | — |
| **P2** | 断言式标题合同化；全局信息密度上限 | `06_论证模式/` + 通用设计规范 | 多行业评审 §五（独立命中） |
| **P2** | 迷幻国潮 2.0、暖调柔形等趋势风格；高频风格 light/dark 双模式配对 | `01_通用母版/` | 多行业评审 §四（dark-deck 预设） |
| **P2** | brief JSON Schema + lint + 护栏前移进 style render，纳入 evals | `runtime/` + `evals/` | — |

## 四、与仓内既有评审的关系

本仓现有四份 leo-ppt-generator 评审，视角互补不重叠：

- `docs/leo-ppt-generator-optimization-review.md`（2026-08-27）——工程合同与评测体系侧（控制面合同、判官、patch 归属）。
- `docs/leo-ppt-generator-ux-review.md`（2026-08-27）——交互旅程侧（确认序列、失败处置、机器词表）。
- `docs/leo-ppt-generator-multi-industry-expert-review.md`——行业内容正确性侧（content_rules 轴、数字元数据、敏感数据、品牌 VI 链路、行业版式深化）。
- 本篇——**风格视觉系统本身**（排印、色彩 token、图表样式、无障碍、动效、趋势风格、schema 化）。

交叉验证点（两路独立评审命中同一缺口，优先级应上调）：断言式标题（本篇 §二.5 ↔ 多行业 §五）、可访问性程序化（§二.7 ↔ 多行业 §四）、品牌 token 链路（§二.3 ↔ 多行业 §四）、版式缺口（§二.2 ↔ 多行业 §六）。P0 两项（悬空引用、图表样式规范）建议并入下一批文档修复包执行；落地为实施计划时适合走 spec-work 路线另立 plan。

## 调研来源

- [Slidesgo – Presentation Design Trends 2026](https://slidesgo.com/slidesgo-school/ai-presentations/presentation-design-trends-2026) · [SketchBubble – 2026 Ultimate Guide](https://www.sketchbubble.com/blog/presentation-design-trends-2026-the-ultimate-guide-to-future-ready-slides/) · [Envato – Presentation Design Trends](https://elements.envato.com/learn/presentation-design-trends-ppt) · [SlideRabbit – Trends 2026](https://sliderabbit.com/blog/presentation-design-trends-shaping-modern-slides-in-2026/) · [Microsoft PowerPoint 设计博客](https://powerpoint.cloud.microsoft/create/en/blog/powerpoint-design-ideas/)
- [Plus AI – Beautiful.ai vs Gamma](https://plusai.com/blog/beautiful-ai-vs-gamma/) · [Presenti – 四工具对比](https://presenti.ai/blog/presentation-ai-compared/) · [Getal – Gamma Review 2026](https://getalai.com/blog/gamma-alternatives)
- [W3C – WCAG 2.2 Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum) · [WebAIM Contrast Guide](https://webaim.org/articles/contrast/) · [NDRN 无障碍字号指南](https://www.ndrn.org/accessibility-guidelines/) · [Section 508 Fonts & Typography](https://www.section508.gov/develop/fonts-typography/)
- [Assertion-Evidence 方法（Michael Alley）](https://www.assertion-evidence.com/) · [Duarte Presentation Principles](https://www.duarte.com)
- [Analyst Academy – 图表标注五实践](https://www.theanalystacademy.com/annotating-your-visuals-in-presentations/) · [Deck.Gallery – Apple Bento Grid](https://www.deck.gallery/blog/apple-bento-grid-decks-roundup/) · [Behance – Design Trends 2026](https://www.behance.net/gallery/239027109/Design-Trends-2026)
- [Canva 中文 – 2026 设计趋势](https://www.canva.cn/work-kits/2026-trendy/) · [优设 – 2026 UI/UX 趋势](https://www.uisdc.com/2026-ui-ux-ai-trends/) · [知乎 – Lovart 冲击 PPT 赛道](https://zhuanlan.zhihu.com/p/1985559762688046485)
