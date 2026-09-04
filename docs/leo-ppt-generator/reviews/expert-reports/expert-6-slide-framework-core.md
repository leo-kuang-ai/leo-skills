# 专家 6 报告：幻灯片框架与 Office 格式内核源码评审（面向 leo-ppt-generator 能力补强）

评审人：幻灯片框架与 Office 格式内核产品专家
评审日期：2026-08-30
评审对象：15 个开源项目源码（逐一阅读，无抽查；每项目至少引用 2 个真实读过的源码文件）
对照目标：`/Users/kuang/knowledge/leo-skills/leo-ppt-generator`（只读参考，未做任何修改）

---

## 0. 对照基线：leo-ppt-generator 当前的"格式内核"事实

在评审 15 个项目前，先固定对照物。当前技能包的格式内核由三层组成：

1. **自研手写 OOXML 生成器**（对象级构建权威）：
   `/Users/kuang/knowledge/leo-skills/leo-ppt-generator/runtime/src/leo_ppt_generator/_vendor/editable_ppt/editppt/runtime/build_pptx_from_manifest.py`（1002 行）。它不依赖 python-pptx 生成，而是 `zipfile` + 手写 XML 字符串：`emu()`（px→inch→EMU）、`px_to_inches()`、`fit_content_box()`（比例合同：页图与交付画布同比例，映射进 `content_box` 而非拉伸全画布）、`text_box_xml()`、`image_xml()`、`shape_xml()`（仅 `rect`/`roundRect`/`ellipse`/`line` 四种 preset + `custom_polygon_geometry_xml()` 自由多边形 + `roundRect` 的 `<a:avLst>` 圆角手写）、`notes_slide_xml()`（notesSlide XML 手写）、字体自适应 `fitted_font_size()`/`fit_text_item()`。
2. **python-pptx 作为读取/组装层**：`runtime/src/leo_ppt_generator/editable/adapter.py`（`from pptx import Presentation`）、`hybrid/assembler.py`、`_vendor/codex_ppt/assemble_ppt.py`（`from pptx.util import Inches`）。
3. **manifest-schema 声明式 IR**：`references/manifest-schema.md` 定义 `text_boxes[]/shapes[]/images[]` + `box_px:[x,y,w,h]` / `points_px:[x1,y1,x2,y2]`（source.png 像素坐标系）、`source_corner_radius_px`、`asset_provenance`（source_type 枚举）、`notes_manifest.json`（原 PPT notes 冻结、worker 不得改写）。

**当前对象覆盖缺口**：无原生表格、无原生图表（graphicFrame）、无 SmartArt、无主题/母版系统（theme1.xml 与 slideMaster 依赖 vendor 模板或默认）、无占位符语义、无字体嵌入。这是本次评审的选型主战场。

---

## 1. 逐项目评审

### PptxGenJS
- 一句话定位：JavaScript/TypeScript 上事实标准的"PPTX 对象级生成"库，全 API 手写 XML 打包，零依赖浏览器/Node 双端可用。
- 核心能力与 API 面：
  - `src/core-enums.ts`：`EMU = 914400`；`SLIDE_OBJECT_TYPES = { chart, hyperlink, image, media, online, placeholder, table, tablecell, text, notes }`；`PLACEHOLDER_TYPES = { title, body, pic, chart, tbl, media }`。
  - `src/core-interfaces.ts`（1874 行）：`Coord = number | '${number}%'` —— 坐标既可英寸也可**画布百分比**，是全库坐标合同的根。
  - `src/gen-utils.ts`：`getSmartParseNumber()`（smart 猜测单位：小于 100 当英寸、`%` 当百分比、大于 100 当已经是 EMU）与 `inch2Emu()`。
  - `src/gen-xml.ts`（1898 行）：`slideObjectToXml()` 产出 `ppt/slideN.xml`；`makeXmlTheme()` 产出 `ppt/theme/theme1.xml`（支持 `pres.theme.headFontFace/bodyFontFace` 与 theme colors）；`notesSlide` 的 XML 与 `[Content_Types].xml` Override 生成；`ImageSizingXml.cover/contain/crop` 用 `<a:srcRect>` 百分比裁切实现三种填充模式。
  - `src/gen-charts.ts`（2042 行）：`makeXmlCharts()`、`makeCatAxis()/makeValAxis()/makeSerAxis()` 等完整图表 XML 生成器。
  - `src/pptxgen.ts`：`defineSlideMaster()` 母版定义、`rtlMode`。
- OOXML 覆盖度：形状（借 text 对象 + SHAPE_NAME preset）、文本框、图片（cover/contain/crop sizing）、表格、图表、音视频 media、占位符、母版（defineSlideMaster）、主题（字体/主题色）、notes（`slide.addNotes()`，见 `src/slide.ts` L202）。**无 SmartArt；无字体嵌入**（全库 grep `embedFonts/fntdata` 无结果）。
- 对对象级可编辑 PPTX 生成的适用性：高——API 面几乎覆盖 leo manifest 的全部对象类型，且坐标百分比模型与"页图→画布映射"天然契合；但它是 JS 生态，接入 Python runtime 需跨语言桥。
- License：MIT（Copyright 2015-2022 Brent Ely）。
- 对 leo-ppt-generator 的判定：**可借鉴机制** —— `makeXmlTheme()` 的主题字体/主题色 XML、`<a:srcRect>` 三模式图片填充、百分比坐标合同是自研 builder 可直接抄的成熟 XML 配方；不建议引入 JS 运行时依赖。

### python-pptx
- 一句话定位：Python 生态读写双向的 PPTX 对象模型标准库，opc 包模型 + 声明式 oxml schema 层，"生成 + 解析 + 校验"三位一体。
- 核心能力与 API 面：
  - `src/pptx/presentation.py`：`Presentation`（`slide_width/slide_height` 可写、`slide_layouts/slide_masters`、`notes_master`、`save()`）。
  - `src/pptx/util.py`：`Length` 基类（`_EMUS_PER_INCH = 914400`）及 `Inches/Cm/Emu/Mm/Pt` 子类——单位换算的类型化合同。
  - `src/pptx/shapes/`：`autoshape.py`（`AutoShapeType` + `Adjustment`/`AdjustmentCollection`，preset geometry 的 avLst 调整值模型）、`freeform.py`（`FreeformBuilder`：`add_line_segments()` 折线/闭合路径）、`connector.py`、`group.py`、`graphfrm.py`、`picture.py`、`placeholder.py`、`shapetree.py`。
  - `src/pptx/oxml/`：`xmlchemy.py` 声明式 OOXML 元素 schema 层（自定义元素 = 定义即注册，逃生舱完整）；`shapes/`、`text.py`、`theme.py` 等。
  - `src/pptx/parts/slide.py`：notes slide part 懒创建（`has_notes_slide` / `notes_slide`，从 `templates/notesMaster.xml` 克隆占位符，见 `slide.py` L63-126）。
  - `src/pptx/templates/`：`default.pptx`、`notesMaster.xml`、`theme.xml`、`notes.xml` —— 以最小模板包为骨架起步。
  - `features/` 目录：180+ 个 BDD（behave）行为规格（`cht-*` 图表、`dml-*`、`ph-*` 占位符继承），API 行为有可执行规格背书。
- OOXML 覆盖度：形状（全部 MSO preset + adjustment）、freeform、图片、原生表格（`src/pptx/table.py`）、原生图表（`src/pptx/chart/`，含数据替换 `cht-replace-data.feature`）、母版/版式继承链、notes、主题读取（`oxml/theme.py`，主题**编辑**需下到 oxml 层）。无 SmartArt 高层 API（但可经 oxml 逃生舱写入）。
- 对对象级可编辑 PPTX 生成的适用性：极高——leo 的 manifest IR → python-pptx 对象 API 的编译器化是最短路径；解析方向同样成熟（upgrade 路线读旧 PPTX）。
- License：MIT（Copyright 2013 Steve Canny）。
- 对 leo-ppt-generator 的判定：**可直接集成资产**（且已部分在用）——建议从"读取/组装层"升级为"生成层主力"，详见文末选型判断。

### react-pptx
- 一句话定位：PptxGenJS 之上的 React 声明式 JSX 前端，实现"组件树 → 归一化 IR → PptxGenJS"的两段式编译，并自带浏览器 Preview。
- 核心能力与 API 面：
  - `src/nodes.ts`：`NodeTypes = { SHAPE, LINE, TEXT_LINK, TEXT_BULLET, SLIDE, MASTER_SLIDE, IMAGE, TABLE_CELL, PRESENTATION }`；`Text.Link/Text.Bullet` 组合子；`Slide` 有 `notes?: string` 与 `masterName`。
  - `src/normalizer.ts`：JSX → `InternalPresentation/InternalSlide/InternalSlideObject/InternalTextPart` 归一化中间表示。
  - `src/renderer.ts`：IR → PptxGenJS 调用的适配层（例：`renderSlideObject()` 里 line 的 x1>x2 时交换坐标并置 `flipH/flipV` —— 方向语义到 OOXML flip 的经典换算）。
  - `src/preview/Preview.tsx`：浏览器端幻灯片预览（渲染前所见即所得）。
- OOXML 覆盖度：继承 PptxGenJS 全量（经其 API），自身贡献是声明式节点模型与 IR 分层。
- 对对象级可编辑 PPTX 生成的适用性：间接——它是"声明式定义 → IR → 格式内核"分层架构的最小可行范本，证明 IR 层值得独立存在。
- License：MIT（Copyright 2020 wyozi）。
- 对 leo-ppt-generator 的判定：**可借鉴机制** —— leo 的 manifest 已是 IR，此项目佐证"IR 独立于渲染内核"的架构正确性；Preview 组件模式对可视化 QA 有参考价值。

### OfficeCLI
- 一句话定位：面向 AI agent 的单二进制 Office 套件（C#/.NET，基于 DocumentFormat.OpenXml），以路径选择器 + get/set/add/remove 命令面 + 自带 HTML/PNG 渲染引擎构成"render → look → fix"闭环。
- 核心能力与 API 面（`src/officecli/Handlers/Pptx/` 下 65 个 partial 文件）：
  - `PowerPointHandler.Notes.cs`：notes body placeholder（`ph.Index == 1`）读写，`PopulateNotesFormat()` 把 notes 首 run 格式镜像进 Get 输出，保证 `Set /slide[N]/notes --prop bold=true` 的 round-trip 可观察。
  - `PowerPointHandler.Theme.cs`：`GetMorphCheckNode()` 实现 morph 兼容性分析（OOXML morph 规则：shape 名以 `!!` 开头参与匹配，输出 matched/unmatched + from/to 路径）。
  - `PptxBatchEmitter.cs`：`EmitPptx()` 把整份 PPTX（或任意子树）dump 成**可回放的 batch JSON**（含 `DeferredLinks`、shape id 重分配基址、`UnsupportedWarning` 列表），`batch` 命令重放——"给我一份样例 → 读结构化 spec → 改 → 重放生成 100 个变体"。
  - `PowerPointHandler.Selector.cs`：`/slide[1]/shape[@name=Foo]` 风格路径选择器，`>` 与 `/` 均可。
  - `Core/Rendering/`：`IRenderer/RendererRegistry/RenderOutputKind` 渲染抽象（HTML 预览 + PNG 截图，给 agent"眼睛"）。
  - README 命令面：SmartArt round-trip（`add-part` + `raw-set`）、LaTeX 公式、mermaid → 原生可编辑形状、3D 模型 .glb、动画/过渡预设、主题、连接符（`from/to` 接受完整形状路径）、watch 热预览。
- OOXML 覆盖度：15 个项目中最全（形状/图片/表格/图表/动画/过渡/SmartArt/notes/评论/占位符/母版/版式/主题全支持）。
- 对对象级可编辑 PPTX 生成的适用性：高——尤其 dump→batch 的"结构化 spec 往返"与 leo manifest 的定位同构，且带渲染校验闭环。
- License：Apache-2.0（NOTICE、THIRD-PARTY-NOTICES 齐全）。
- 对 leo-ppt-generator 的判定：**可借鉴机制** —— 二进制依赖与 C# 栈不适合直接进 Python 技能包，但其 dump/batch JSON、路径选择器、morph 名字约定、notes round-trip 语义是 manifest-schema 与 upgrade 路线可以直接吸收的接口设计。

### impress.js
- 一句话定位：基于 CSS3 3D transform 的无限画布演示框架（prezi 式），slide 即绝对定位的 transform 目标。
- 核心能力与 API 面：
  - `src/impress.js`：`initStep()`（L279-316）读取 `data-x/y/z/rotateX/rotateY/rotateZ/rotateOrder/scale`，组装 `translate3d(...) rotateX(...) scale(...)` 矩阵；`buildConfig()` 读 root 的 `width/height/maxScale/minScale/perspective`；`computeWindowScale` 视口适配。
  - `src/lib/util.js`：`toNumberAdvanced()`（支持 `%` 的数值解析）；`src/plugins/navigation/`、`autoplay/`、`substep/` 等插件化扩展。
- OOXML 覆盖度：零（纯 Web 演示，无任何 Office 格式产出）。
- 对对象级可编辑 PPTX 生成的适用性：无直接适用；其"每步一个 3D 变换 + 相机插值"模型与 PPTX 的 EMU 平面坐标系不同构。
- License：MIT（Copyright 2011-2016 Bartek Szopka 等）。
- 对 leo-ppt-generator 的判定：**不适用** —— 无格式内核价值；唯一可记的是"非线性叙事画布"这一产品形态。

### reveal.js
- 一句话定位：事实标准的 HTML 演示框架，`<section>` 层级 + CSS 状态类驱动，配 PDF 打印导出与独立演讲者视图。
- 核心能力与 API 面：
  - `js/controllers/printview.js`：`activate()` 注入 `@page{size:Wpx Hpx}` 样式表、按 `getComputedSlideSize` 重排每页、逐页复制布局（含 `pdfMaxPagesPerSlide/pdfSeparateFragments/pdfPageHeightOffset` 处理超长页），是"HTML → 分页 PDF"的浏览器内标准做法。
  - `js/controllers/autoanimate.js`：跨页元素自动动画（`data-auto-animate` + `data-auto-animate-id` 匹配）。
  - `plugin/notes/plugin.js` + `speaker-view.html`：弹窗演讲者视图（时间、下一页、notes 渲染）。
  - `js/config.ts`：pdf 导出、slideNumber、autoSlide 等全局合同。
- OOXML 覆盖度：零（HTML/CSS/JS；PDF 经浏览器打印 CSS）。
- 对对象级可编辑 PPTX 生成的适用性：无直接对象级输出；其 print-css 分页范式对"HTML → PDF → 图片页"的备选管线有参考。
- License：MIT（Copyright 2011-2026 Hakim El Hattab 等）。
- 对 leo-ppt-generator 的判定：**不适用**（对格式内核）；notes 视图与 print 分页可作为产品交互参照。

### marp-cli
- 一句话定位：Marpit 引擎的官方 CLI 转换器，Markdown → HTML/PDF/PNG/**PPTX**，PPTX 有"图片式（默认）"与"实验性可编辑（--pptx-editable）"两条路线——与 leo 的 generate/direct-editable 路线完全同构。
- 核心能力与 API 面：
  - `src/converter.ts`：`convertFileToPPTX()`（L563-604）—— 先 `convertFileToImage(pages:true, png)` 逐页截图，再 `new PptxGenJS()` + `defineLayout({width: px/96, height: px/96})`（96dpi 像素→英寸合同），每页 `slide.background = {data: base64}`，`tpl.rendered.comments[page].join('\n\n')` 注入 `slide.addNotes(notes)`；`convertFileToEditablePPTX()`（L606-650）—— ** EXPERIMENTAL 警告后走 PDF → LibreOffice `--infilter=impress_pdf_import --convert-to pptx:Impress Office Open XML:UTF8` **。
  - `src/soffice/soffice.ts` + `finder.ts`：SOffice 封装（spawn 串行队列、独立 profile 目录、路径探测）。
  - `src/theme.ts`：`Theme/ThemeSet`（主题文件发现与覆盖）。
- OOXML 覆盖度：图片式路线 = 整页位图 + notes（无对象）；editable 路线 = LibreOffice 转换质量（官方自己承认 "slide reproducibility is not fully guaranteed"）。
- 对对象级可编辑 PPTX 生成的适用性：作为竞品对照价值极高——它证明业界"图片式 PPTX"收敛到 PptxGenJS 截图方案，而"对象级可编辑"没有免费午餐，LibreOffice PDF 通道只是实验性兜底。
- License：MIT。
- 对 leo-ppt-generator 的判定：**已覆盖**（两条路线 leo 均有更强实现）——leo 的图片式路线带风格库与比例合同，对象级路线用 worker+manifest 显式建模，均优于 marp-cli；其 soffice 兜底通道值得记录为反面教训（见文末）。

### marpit
- 一句话定位：Markdown → 幻灯片 HTML 的引擎核心（marp-cli 的底座），用 CSS 注释元数据 + 指令系统实现"主题即 CSS、控制即指令"。
- 核心能力与 API 面：
  - `src/theme.js` + `src/theme/scaffold.js`：`Theme` 类从 CSS 注释解析 `@theme` 元数据（`src/postcss/meta.js` 的 `@key value` 正则），`width/height` 必须绝对单位并 memoize 出 `widthPixel/heightPixel`；scaffold 主题定义默认 `section { width:1280px; height:720px }` 与 `section::after` 页码。
  - `src/markdown/directives/parse.js`：YAML front-matter + HTML 注释双通道指令解析（全局/局部指令、`looseYAML` 容错），`applyBuiltinDirectives` 展开内建指令。
  - `src/markdown/comment.js`：HTML 注释 token 化，产出 `marpit.js`（L209-226）的 `comments: this.lastComments` —— **每页 HTML 注释数组，官方注释即 presenter notes**（marp-cli 直接 join 后 addNotes）。
- OOXML 覆盖度：零（产物是 HTML/CSS slide 容器，`inline_svg.js` 可选 SVG 模式）。
- 对对象级可编辑 PPTX 生成的适用性：无直接；但"主题元数据内嵌于样式文件 + 注释即 notes"两个约定极轻量。
- License：MIT。
- 对 leo-ppt-generator 的判定：**可借鉴机制** —— `@theme` 元数据模式可平移到 leo 风格库 brief（styles.py + lint 已有结构），"注释即 notes"可降低 page-worker 产出 notes 的格式摩擦。

### slidev
- 一句话定位：开发者向 Markdown+Vue 幻灯片框架（monorepo），拥有独立 parser 包（`---` 分页 + 每页 frontmatter + 注释 notes）与浏览器导出管线，PPTX 导出 = 截图 + PptxGenJS。
- 核心能力与 API 面：
  - `packages/parser/src/core.ts`：`RE_FRONTMATTER/RE_HEADING` 等正则族；`advanceHtmlCommentState()` 跨行注释状态机；`prettifySlide()` 把 note 回写为 `<!--\n...\n-->`（notes 与内容可逆序列化）。
  - `packages/parser/src/config.ts`：默认 `aspectRatio: 16/9`、`canvasWidth: 980`（设计画布宽度合同，缩放由运行时承担）、导出/字体/绘图配置。
  - `packages/slidev/node/commands/export.ts`：`genPagePptx()`（L508-545）——注释明确 **"Ported from marp-team/marp-cli"**，`defineLayout({width/96,height/96})` + 每页 PNG 背景 + `slide.addNotes(slides[slideIndex].note)`。
- OOXML 覆盖度：与 marp-cli 相同的图片式 PPTX；无对象级。
- 对对象级可编辑 PPTX 生成的适用性：间接——parser 包是"Markdown slides 中间表示"的最佳工程化样例（独立 npm 包、可复用、注释即 note 且可回写）。
- License：MIT。
- 对 leo-ppt-generator 的判定：**可借鉴机制** —— 独立 parser 包的分层、`canvasWidth + aspectRatio` 的画布合同与 leo 比例合同（2560×1440）同构，可对齐字段命名与换算约定。

### spectacle
- 一句话定位：Formidable Labs 的 React/MDX 演示库，JS 对象主题（size/colors/fonts/fontSizes/space）+ `---` JSON 头分页 + "Notes:" 文本标记提取演讲者备注。
- 核心能力与 API 面：
  - `packages/spectacle/src/theme/default-theme.ts`：`defaultTheme = { size:{width:1366,height:768}, colors, fonts:{header,text,monospace}, fontSizes:{h1:'72px',...}, space:[16,24,32] }` —— 完整可 DeepPartial 覆盖的主题 token 系统。
  - `packages/spectacle/src/utils/notes.ts`：`isolateNotes()/removeNotes()` 用 `^Notes: ` 行首标记切分内容与 notes。
  - `packages/spectacle/src/utils/separate-sections-from-json.ts`：`---` + 行内 JSON 头分页。
  - `packages/spectacle-mdx-loader/`：MDX 加载器（markdown 组件映射）。
- OOXML 覆盖度：零（React 组件树）。
- 对对象级可编辑 PPTX 生成的适用性：无直接；主题 token 分层（设计令牌 → 组件样式）是风格库的干净参照。
- License：MIT（Copyright 2013-2018 Formidable Labs）。
- 对 leo-ppt-generator 的判定：**可借鉴机制** —— 主题 token 结构（size/colors/fonts/fontSizes/space 五段）可作为 leo 风格 brief 的规范化字段参照。

### deckjs（gitee-mirrors/deckjs）
- 一句话定位：jQuery 时代的 CSS class 状态机演示框架（2011-2014），核心只做"翻页加 class"，一切视觉交给 CSS。
- 核心能力与 API 面：
  - `core/deck.core.js`：`deck.beforeChange/deck.change/deck.init` 事件模型 + `.deck-current/.deck-prev/.deck-next` 状态类；`lockInit()/releaseInit()` 初始化锁。
  - `extensions/scale/deck.scale.js`：视口 scale 适配扩展；`extensions/goto|menu|navigation|status/`。
  - `themes/style/{swiss,neon,web-2.0}.scss` + `core/print.scss`：风格主题与打印样式分离。
- OOXML 覆盖度：零。
- 对对象级可编辑 PPTX 生成的适用性：无。
- License：MIT（`MIT-license.txt`，Dual licensed，Copyright 2011-2014 Caleb Troughton）。
- 对 leo-ppt-generator 的判定：**不适用** —— 仅历史价值；"核心状态机 + CSS 主题 + 扩展"的解耦是它留下的唯一架构注脚。

### nodePPT（gitee-mirrors/nodePPT）
- 一句话定位：三节课出品的中文 Markdown → HTML 演示工具（markdown-it + posthtml 双阶段），`<slide>`/`<note>` 自定义标签 + echarts/mermaid/katex 富内容。
- 核心能力与 API 面：
  - `packages/nodeppt-parser/lib/tags/note.js`：`<note>` → `div.speaker-note`（挂在 slide 节点内，演示端隐藏、演讲端显示）。
  - `packages/nodeppt-parser/lib/tags/slide.js`：`<slide>` → `section.slide`；`:attr` 透传为 wrap 样式；`image="url .class"` 属性展开为背景 class。
  - `packages/nodeppt-parser/lib/get-markdown-parser.js`：markdown-it 插件链（prism、katex、`markdown/echarts.js`、`markdown/mermaid.js`、fa、attrs、img、cite、span、container(column/shadowbox/steps/card)）。
- OOXML 覆盖度：零（HTML 演示）。
- 对对象级可编辑 PPTX 生成的适用性：无直接；`<note>` 标签化的 notes 语法与富图表容器（echarts/mermaid 代码块 → 渲染节点）对 manifest 的 `visual_inventory` 建模有启发。
- License：MIT（`MIT-LICENSE.txt`；packages/* 全部 `"license": "MIT"`）。
- 对 leo-ppt-generator 的判定：**可借鉴机制**（弱）—— notes 标签语法与图表代码块→对象的映射思想；中文演示场景的字号/排版经验可查。

### remark（gitee-mirrors/remark，gnab/remark）
- 一句话定位：轻量 Markdown 幻灯片框架，自写词法器把 `---`/`--`/`???` 三个分隔符切成页/fragment/notes 三级结构，再交给 marked 渲染。
- 核心能力与 API 面：
  - `src/remark/lexer.js`：`SLIDE_SEPARATOR: (?:^|\n)(---|<!--\s*break\s*-->)(?:\n|$)`、`FRAGMENT_SEPARATOR: (?:^|\n)(--)(?![^\n])`、`NOTES_SEPARATOR: (?:^|\n)(\?{3})(?:\n|$)` —— 一份正则族完成三级切分；`.class[...]` CONTENT 语法支持内容类。
  - `src/remark/converter.js`：基于 marked（`pedantic:true` 等）把 token 树转 HTML，`convertMarkdown()` 递归展开内容类嵌套。
  - `src/remark/scaler.js`：`referenceWidth 908 / referenceHeight 681` 基准 + `scaleToFit()` 比例适配（4:3 时代遗产）。
- OOXML 覆盖度：零。
- 对对象级可编辑 PPTX 生成的适用性：无直接；`???` 单行 notes 分隔符是"最低摩擦 notes 语法"的代表。
- License：MIT（Copyright 2011-2013 Ole Petter Bang）。
- 对 leo-ppt-generator 的判定：**不适用** —— 已停止演进（marked 时代、4:3 基准）；仅语法考古价值。

### unioffice（gitee-mirrors/unioffice）
- 一句话定位：Go 语言的 OOXML 全家桶库（word/excel/pptx），API 面覆盖动画/notes/文本提取——但它是 **UniDoc 商业产品：混淆代码 + 付费 license key**。
- 核心能力与 API 面：
  - `presentation/presentation.go`：`AddSlide()`（完整 sldIdLst/SpTree/relationship/content-type 接线）、`Slides()`、`Slide.ExtractText()`（含表格逐格、组内递归 + `sort2d` 坐标排序）、`Notes.AddParagraph()`、`EntranceEffect`（FlyIn/Fade → presetID 映射）、`SlideScreenSize.SetWidth(EMU)`。**注意：该文件头部标注 "DO NOT EDIT: generated by unitwist Go source code obfuscator"，所有标识符被混淆。**
  - `measurement/measurement.go`：`FromEMU/ToEMU`、`EMU = 1/914400.0*Inch`、`Point/Pixel72/Pixel96/Twips/HalfPoint` 单位常量族。
  - `schema/soo/`：pml（presentationml）、dml（drawingml）、ofc、sml、wml —— 从 schema 生成完整类型树，是其覆盖度极高的根因。
- OOXML 覆盖度：非常高（形状/文本/图片/表格/notes/动画/主题皆有 API）。
- 对对象级可编辑 PPTX 生成的适用性：技术上高、**法律与工程上为零** —— `LICENSE.md` 明示 commercial product + EULA + 混淆源码，不可集成、不可 fork、不可作为代码参考基础。
- License：**UniDoc EULA（商业）**，非 OSI 开源。
- 对 leo-ppt-generator 的判定：**不适用** —— 许可证一票否决；唯一价值是当作"OOXML schema 覆盖度对照表"（pml/dml 类型树的完整性参照）。

### webslides（gitee-mirrors/webslides）
- 一句话定位：CSS-first 的结构化 HTML 演示框架（`section` + 语义 class 体系 + 垂直滚动叙事），JS 只做滚动与插件。
- 核心能力与 API 面：
  - `src/js/modules/webslides.js`：`WebSlides` 类（`VERTICAL/HORIZONTAL` 布局判定、`goToSlide()` 用 `scrollTo(el.offsetTop)` 翻页）。
  - `src/js/plugins/`：`scroll.js`、`grid.js`（网格对齐辅助）、`zoom.js`、`autoslide.js`、`click-nav.js`、`youtube.js`。
  - `src/scss/_base.scss` + `modules/`：`grid`/`column` 布局与排版令牌全部在 SCSS 层。
- OOXML 覆盖度：零。
- 对对象级可编辑 PPTX 生成的适用性：无；其 `grid/column` CSS 类体系对版式库（leo 的 layout-grid lint）的"命名化版式"思想有弱参照。
- License：MIT（Copyright 2017 José Luis Antúnez）。
- 对 leo-ppt-generator 的判定：**不适用** —— 维护停滞；仅语义 class 版式命名可作低优先级参照。

> gitee-mirrors 与顶层同名项目差异核对：`gitee-mirrors/slidev` package.json version 52.19.1 与顶层 `/Users/kuang/knowledge/ppt-github/slidev` 一致；`gitee-mirrors/PPTist` 2.0.0 与顶层一致；`gitee-mirrors/marp`、`officecli`、`pptagent` 与顶层为同源镜像，未见内容性差异，未重复分析。

---

## 2. Top 5 集成建议（按 ROI 排序）

### 建议 1：把对象级生成内核从"手写 XML"迁移到 python-pptx 对象 API，manifest 保持为唯一 IR
- 来源项目+文件证据：python-pptx `src/pptx/shapes/autoshape.py`（AutoShapeType/Adjustment 覆盖全部 preset geometry 与圆角 avLst）、`src/pptx/shapes/freeform.py`（FreeformBuilder 多边形）、`src/pptx/util.py`（EMU 类型化换算）；对照现状 `leo-ppt-generator/runtime/src/leo_ppt_generator/_vendor/editable_ppt/editppt/runtime/build_pptx_from_manifest.py`（手写 `<a:prstGeom prst="roundRect"><a:avLst>`、手写 notesSlide XML）。
- 预期收益：一次性补齐 rect/roundRect/ellipse/line 之外的形状库（MSO 全 preset）、原生表格（`pptx.table`）、原生图表（`pptx.chart`）、母版/版式继承、notes part 懒创建（`parts/slide.py` L63-126 已实现模板克隆）；shape id/relationship/content-type 接线由库负责，消除自研 XML 的合规风险；`xmlchemy` 逃生舱保留 custom polygon 等特殊 geometry 的现有能力。
- 集成成本：中——builder 是单文件 1002 行且接口（manifest 进、page.pptx 出）清晰；python-pptx 已是运行时依赖（adapter.py/assembler.py 在用），无新依赖；风险点是行为回归，需以现有 validator + `features/` 式行为规格兜底。

### 建议 2：吸收 OfficeCLI 的 dump/batch 机制，为 upgrade-full/upgrade-selected 增加"对象级结构化 spec"能力
- 来源项目+文件证据：OfficeCLI `src/officecli/Handlers/Pptx/PptxBatchEmitter.cs`（EmitPptx：整文档/子树 → 可回放 batch JSON，含 DeferredLinks 与 UnsupportedWarning）、`PowerPointHandler.Selector.cs`（`/slide[N]/shape[@name=X]` 选择器）；其 README L297 明确定位 "Bridges 'I have an existing template' and 'generate me 100 variations'"。
- 预期收益：可信 Office 输入在 prepare 阶段即可 dump 成结构化 JSON（对象清单、坐标、样式），与 manifest-schema 同构对照：a) 生成 page_request 时提供对象级 ground truth（当前 text hints 是文本级）；b) finalize 后可做"源 vs 产物"的对象级 diff 验收（位置/文本/notes 三轴）；c) 为未来的"模板变体"路线预留接口。
- 集成成本：中高——不引入 C# 二进制，而是用 python-pptx 解析侧（`Presentation()` 遍历 spTree）+ 选择器/回放语义移植；建议先实现只读 dump（一页一 JSON），回放后置。

### 建议 3：补齐 notes 全链路与母版/主题的最小 OOXML 合同（字体主题 + 占位符语义）
- 来源项目+文件证据：PptxGenJS `src/gen-xml.ts`（`makeXmlTheme()`：`pres.theme.headFontFace/bodyFontFace` → `ppt/theme/theme1.xml` 的 `<a:latin typeface>`；notesSlide XML 与 Content-Types Override 生成）；python-pptx `src/pptx/templates/theme.xml` + `src/pptx/parts/slide.py`（notesMaster 克隆）；marp-cli `src/converter.ts` L596-597（`comments[page].join('\n\n')` → `slide.addNotes()`）证明 notes 与图片式/对象式两条管线共用同一数据源。
- 预期收益：leo 已有 `notes_manifest.json`（冻结、不交 worker 改写），但产物端 notes 的母版接线与"全 deck 统一字体主题"仍依赖 vendor 模板默认值；引入 theme 字体双槽（标题/正文）后，字体替代记录（editable-workflow.md 的质量门）可以在主题层表达，升级版换字体不再逐页改 run。
- 集成成本：低——PptxGenJS 的 theme XML 配方可直接抄进自研 builder 或交给 python-pptx 默认模板参数化。

### 建议 4：渲染回看闭环——为 validator 增加"HTML/PNG 渲染证据"通道
- 来源项目+文件证据：OfficeCLI `src/officecli/Core/Rendering/RendererRegistry.cs` + `Handlers/Pptx/PowerPointHandler.HtmlPreview.*.cs`（pptx → HTML 预览，"render → look → fix"）；reveal.js `js/controllers/printview.js`（`@page{size}` + 逐页复制布局的打印范式）；react-pptx `src/preview/Preview.tsx`（IR 级浏览器预览）。
- 预期收益：当前 editable-workflow.md 的质量门要求"字体替代后的视觉效果、桌面打开必须另行实际验收"——一个 headless 渲染通道（PowerPoint/LibreOffice 导出 PNG，或轻量 HTML 近似渲染）能把该项从人工验收升级为机器证据，直接接入 `run record` 的 validation.json。
- 集成成本：中——PowerPoint 自动化（macOS 上 AppleScript/COM）或 soffice headless（marp-cli `src/soffice/soffice.ts` 有成熟封装可参照，注意其 spawn 队列与 profile 隔离做法）；HTML 近似渲染则可复用现有 preview.png 管线。

### 建议 5：风格库吸收 marpit/spectacle 的"主题元数据内嵌"模式，统一比例与设计令牌声明
- 来源项目+文件证据：marpit `src/postcss/meta.js`（`@key value` CSS 注释元数据解析）+ `src/theme/scaffold.js`（`section{width:1280px;height:720px}` 尺寸进主题）+ `src/theme.js`（width/height 必须 CSS 绝对单位、memoize 像素换算）；spectacle `packages/spectacle/src/theme/default-theme.ts`（size/colors/fonts/fontSizes/space 五段设计令牌，DeepPartial 覆盖）。
- 预期收益：leo 的 style brief（styles.py + `lint_style_briefs.py`/`lint_layout_grid.py` 双 lint）可对齐这两类约定：把画布比例/尺寸（16:9 基准 2560×1440）与五段设计令牌写进每个 brief 的头部元数据，page-worker 与 builder 从同一主题源解析，消除"风格字段在 prompt 与 runtime 两处重复定义"的漂移面。
- 集成成本：低——纯 schema/约定层改动，不触格式内核；与建议 3 的主题 XML 打通后形成"brief → theme1.xml"的单一上游。

---

## 3. 对象级可编辑 PPTX 内核选型：技术判断

**结论：python-pptx 深耕为主，manifest-schema 作为独立 IR 保留并加厚，不采用多内核并用；unioffice 直接排除。**

推理链：

1. **运行时同栈是决定性因素。** leo-ppt-generator 的全链路（runtime manager、editable adapter、validator、finalize）是 Python，python-pptx 已在依赖树内（`editable/adapter.py`、`hybrid/assembler.py`）。PptxGenJS 虽然对象覆盖与坐标模型（百分比 + smart parse，`src/core-interfaces.ts` 的 `Coord`）优秀，但引入 Node 运行时意味着跨进程桥、双份依赖管理与 CI 复杂度——对"技能包"形态的发布物是净负担。react-pptx 依赖 PptxGenJS，同理。
2. **对象覆盖差距的方向。** leo 当前缺口（原生表格、图表、母版/主题、占位符）恰好是 python-pptx 的强项（`src/pptx/table.py`、`src/pptx/chart/`、`shapes/placeholder.py`、`parts/slide.py` 的 notes/master 接线、`templates/default.pptx` 骨架）；而 PptxGenJS 的强项里 leo 已自研覆盖的部分（手写 XML 的灵活性）在 python-pptx 有 `oxml/xmlchemy.py` 逃生舱承接（custom polygon 等特殊 geometry 无损迁移）。
3. **"声明式中间表示（IR）"不是一个选项，而是已存在的事实。** `references/manifest-schema.md` 定义的 `text_boxes/shapes/images + box_px/points_px + asset_provenance` 就是 slides IR；react-pptx（`src/normalizer.ts` 的 InternalPresentation）与 slidev parser（`packages/parser/src/core.ts`）证明该分层的普遍性。正确演进是 **"manifest IR → python-pptx 编译器"**，即把手写 XML 的 vendor builder 重写为 IR 到对象 API 的翻译层；IR 层继续吸收两个来源：OfficeCLI 的文档树/选择器语义（读方向）、spectacle/marpit 的主题令牌（设计方向）。
4. **多内核并用的唯一合理边界是"格式转换兜底"，且业界已给出警戒线。** marp-cli 的 `--pptx-editable`（`src/converter.ts` L606-650）用 LibreOffice PDF→PPTX 通道，官方标注 EXPERIMENTAL 且"reproducibility is not fully guaranteed"——这与 leo 用 worker+manifest 显式重建对象级的路线相比是降级。若未来需要"读任意第三方 PPTX"的兜底，soffice 通道可作只读降级路径，但不能成为可编辑交付的主路径。
5. **unioffice 一票否决。** `LICENSE.md` 为 UniDoc EULA 商业许可，源码经 unitwist 混淆（`presentation/presentation.go` 头部自证）；即便 gitee 镜像可读，也不可集成、不可参考改写。它的 `schema/soo/pml|dml` 类型树只可作为覆盖度对照表使用。
6. **OfficeCLI 的定位是"机制参照 + 可选外部工具"，不是内核。** 其 dump/batch、路径选择器、morph `!!` 命名约定、notes round-trip 语义值得移植进 Python 侧；是否把 officecli 二进制作为可选 QC 工具（渲染 HTML/PNG 证据）由发布形态决定（Apache-2.0 允许，但引入外部二进制与技能包自包含原则冲突，建议只借鉴机制）。

---

## 4. 专家署名观点与反面教训

**署名观点（幻灯片框架与 Office 格式内核方向）：**
"图片式 PPTX 不是过渡形态，而是业界收敛的稳定形态；对象级可编辑没有捷径，谁把对象清单（manifest/dump/batch）做成可验证的构建合同，谁就拥有可编辑内核。slidev 的 PPTX 导出代码直接注明移植自 marp-cli（`packages/slidev/node/commands/export.ts` L507），marp-cli 又站在 PptxGenJS 之上——这条'截图 → 背景图 + addNotes'链路已被三个独立项目收敛验证。leo-ppt-generator 的差异化恰恰在于反其道而行：用 manifest 把对象级重建变成可校验的合同（`box_px` 缺失即违规、asset_provenance 枚举、notes 冻结），这个方向应坚持，缺的不是理念而是 OOXML 对象面的纵深——那正是 python-pptx 一跳可达的地方。"

**反面教训：**
1. **LibreOffice 通道的保真度陷阱**（marp-cli `src/converter.ts` L606-650）：PDF→PPTX 的 editable 输出被官方标记实验性且不保证可复现；任何把"格式转换器"当"对象级重建器"的路线都会在字体、表格、图表上翻车。leo 的 direct-editable 不应引入此通道作为主路径。
2. **"镜像可见 ≠ 可用"的许可证陷阱**（unioffice `LICENSE.md` + 混淆源码）：gitee 镜像里躺着一个 API 全覆盖的 Go OOXML 库，但它是商业 EULA + 代码混淆。引入任何内核前，LICENSE 与源码可读性是先于能力评估的硬门禁。
3. **维护停滞的代际风险**（deck.js 2011-2014 jQuery 状态机、nodePPT/remark/webslides 的 lerna/结构老化）：HTML slides 框架十年三代（class 状态机 → markdown 词法 → 组件化/MDX），只有沉淀为"解析独立包"的（slidev parser、marpit 引擎）活了下来。任何引入 leo 的外部机制都应优先选择"独立、薄、可替换"的层，而非框架整体。
4. **手写 XML 的隐性成本已在当前 vendor builder 显形**（`build_pptx_from_manifest.py` 手写 roundRect avLst、notesSlide、content-type）：每新增一种对象都要重学一遍 OOXML 接线（id/rel/override 三线对齐），这是 python-pptx/OfficeCLI 这类库存在的根本理由——不要在自研路径上继续扩张对象面。

---

## 附：逐项目判定一览表

| 项目 | 判定 | 一句话理由 |
|---|---|---|
| PptxGenJS | 可借鉴机制 | theme XML/百分比坐标/srcRect 填充配方成熟，但 JS 栈不宜进 Python 技能包 |
| python-pptx | 可直接集成资产 | 读写双向 + 全 preset 形状/表格/图表/母版/notes，且已在依赖树内 |
| react-pptx | 可借鉴机制 | 佐证"声明式 IR 独立于格式内核"分层，Preview 模式可参考 |
| OfficeCLI | 可借鉴机制 | dump/batch JSON + 路径选择器 + 渲染闭环是 manifest/upgrade 路线最佳接口范本（Apache-2.0 但为 C# 二进制） |
| impress.js | 不适用 | CSS3 无限画布，无 OOXML 输出 |
| reveal.js | 不适用 | HTML 演示；print-css 分页与 notes 视图仅有弱参照 |
| marp-cli | 已覆盖 | 图片式+实验性 editable 两路线 leo 均有更强实现；soffice 兜底是反面教材 |
| marpit | 可借鉴机制 | @theme 元数据 + 注释即 notes 的极轻量约定可平移进风格库 |
| slidev | 可借鉴机制 | 独立 parser 包与 canvasWidth/aspectRatio 画布合同同构可比 |
| spectacle | 可借鉴机制 | 五段主题 token（size/colors/fonts/fontSizes/space）可规范风格 brief 字段 |
| deckjs | 不适用 | jQuery 时代 class 状态机，停止维护 |
| nodePPT | 可借鉴机制（弱） | `<note>` 标签语法与 echarts/mermaid 代码块→对象的映射思想 |
| remark | 不适用 | marked 时代词法器 + 4:3 基准，仅语法考古 |
| unioffice | 不适用 | UniDoc 商业 EULA + 混淆源码，许可证一票否决 |
| webslides | 不适用 | CSS-first 滚动叙事，维护停滞 |
