# 专家 5：渲染与图像管线基建源码评审报告

> 评审对象：`/Users/kuang/knowledge/ppt-github/` 下 17 个渲染/转换/图表基建项目
> 集成目标：`/Users/kuang/knowledge/leo-skills/leo-ppt-generator`（四路线：generate / direct-editable / upgrade-full / upgrade-selected；页面像素档默认 2560×1440）
> 评审方法：每项目 ls 顶层 → 读 README → 精读核心源码入口（主入口 / 渲染转换模块 / API 定义），并对语料库（PPTist、frontend-slides、presenton、banana-slides、html-ppt-skill、OfficeCLI、slidev、genoffice 等）做 grep 交叉验证真实使用方式。
> 日期：2026-08-30

---

## 一、逐项目评审

### canvg
- 一句话定位：纯 JavaScript 实现的 SVG 解析 + Canvas 栅格化引擎。
- 核心能力与 API 面：`src/index.ts` 汇出全部模块；`src/Canvg.ts` 提供 `Canvg.from(ctx, svg, options)` / `fromString()` / `render()` / `resize(width, height, preserveAspectRatio)`（render 默认 `ignoreAnimation + ignoreMouse`，天然适合静态成图）；`src/Screen.ts` 有 `scaleWidth/scaleHeight` 选项与 DPR 缩放逻辑（Screen.ts L52-L230，`scaleMin/scaleMax` 计算）；配套 `SVGFontLoader.ts` 处理 SVG 内嵌字体。纯 JS、无原生依赖、可跑在 node-canvas 上，完全离线。
- 在 PPT 管线中的角色：语料库内无直接消费者（grep 全库 package.json 仅自身）。定位是 resvg-js 的"零原生依赖兜底"。
- License：MIT（package.json，v4.0.3）。
- 对 leo-ppt-generator 的判定：**可借鉴机制** —— JS 端 SVG→PNG 兜底可行，但 Rust 系 resvg 保真度与性能全面占优，不值得双轨。

### dom-to-image
- 一句话定位：DOM→SVG foreignObject→Canvas 序列化路线的鼻祖（2016 停更）。
- 核心能力与 API 面：`src/dom-to-image.js` 单文件实现 `toSvg/toPng/toJpeg/toBlob/toPixelData`（L17-L30）；L312 `embedFonts` + L638 `newFontFaces()` 通过读取 `document.styleSheets` 中 `CSSRule.FONT_FACE_RULE` 并 base64 内联实现 webfont 嵌入；L53-L83 toSvg 流水线：cloneNode → embedFonts → inlineImages → makeSvgDataUri。
- 在 PPT 管线中的角色：语料库内无消费者；其继任者 html-to-image 被 PPTist 使用（见下）。
- License：MIT（v2.6.0）。
- 对 leo-ppt-generator 的判定：**不适用** —— 停更 8 年以上，直接用其现代替身 html-to-image。

### html-to-image
- 一句话定位：dom-to-image 的现代 TS 重写，浏览器端 DOM→PNG/JPEG 最主流方案。
- 核心能力与 API 面：`src/index.ts` 导出 `toSvg/toCanvas/toPng/toJpeg/toBlob/getFontEmbedCSS`；`toCanvas`（L28-L59）支持 `pixelRatio`、`canvasWidth/canvasHeight`（可做 2560×1440 超采样）、`skipAutoScale`、`backgroundColor`；字体嵌入抽离为独立的 `getFontEmbedCSS()`（L96-L101，src/embed-webfonts.ts）。
- 在 PPT 管线中的角色：**PPTist 的生产实践**（`PPTist/src/hooks/useExport.ts` L6 `import { toPng, toJpeg } from 'html-to-image'`，package.json L26 `"html-to-image": "^1.11.13"`）：`exportImage`（L55-L78）导出单页图、`exportImagePPTX`（L81+）把每页 toJpeg 后塞进 pptxgenjs 生成"图片版 PPTX"——与 leo-ppt-generator 的图片式路线完全同构。两处关键 workaround：L59-L60 手工移除 `foreignObject [xmlns]` 属性（Safari 兼容）；L68 `ignoreWebfont=true` 时 `config.fontEmbedCSS = ''` 直接关闭 webfont 嵌入（嵌入不可靠）。输出宽度仅 1600px，低于 leo 的 2560 档。
- License：MIT（v1.11.13）。
- 对 leo-ppt-generator 的判定：**可借鉴机制** —— 前端预览场景可用；CLI 管线场景该路线（依赖浏览器 DOM + foreignObject）劣于直接无头浏览器截图。

### html2canvas
- 一句话定位：自研 CSS 解析 + Canvas 重绘的 DOM 截图库（与 foreignObject 路线对立的另一条技术路线）。
- 核心能力与 API 面：`src/index.ts` `renderElement`（L29-L149）双路径：默认 `CanvasRenderer`（解析克隆 DOM 的 computed style 重绘）或 `foreignObjectRendering: true` 走 `ForeignObjectRenderer`；`scale` 选项（L108，默认 devicePixelRatio）、`windowWidth/windowHeight`、`width/height`、`backgroundColor`；克隆发生在独立 iframe（L96 `documentCloner.toIFrame`）。
- 在 PPT 管线中的角色：语料库内无消费者（PPTist 选了更轻的 html-to-image）。自研 CSS 子集意味着部分现代 CSS 不支持，发布节奏慢（1.4.1）。
- License：MIT（v1.4.1）。
- 对 leo-ppt-generator 的判定：**不适用** —— 在"有真浏览器可用的管线"里没有理由用 CSS 模拟器。

### konva
- 一句话定位：面向交互编辑器的高性能分层 Canvas 对象模型（2D 场景图）。
- 核心能力与 API 面：`src/Stage.ts`（舞台/事件体系，L45-L64 完整鼠标/触摸/指针事件矩阵）；`src/Node.ts` L2186 `toCanvas(config)`、L2212 `toDataURL`、L2257 `toImage`、L2296 `toBlob`，CanvasConfig 含 `pixelRatio`（L231）——序列化成图 API 齐全且分辨率可控。
- 在 PPT 管线中的角色：**编辑器画布而非成图管线**：presenton/servers/nextjs/package.json L55/L66（`konva ^10.3.0` + `react-konva ^19.2.4`）用于 slide-editor 组件（components/slide-editor/tables/TemplateV2TableElement.tsx 等）；genoffice/apps/slides/src/renderer/konva-adapter.ts 作为幻灯片渲染器适配层。
- License：MIT（v10.3.2）。
- 对 leo-ppt-generator 的判定：**不适用** —— 编辑器生态位资产；leo 的 direct-editable 路线目标是 PPTX XML，不是 canvas 场景图。

### mermaid
- 一句话定位：文本语法→图解（流程/时序/思维导图/甘特/xychart）的事实标准渲染器。
- 核心能力与 API 面：`packages/mermaid/src/mermaid.ts` L203 `render(id, txt, element)` ——**需要 DOM container**（Node 端 SSR 必须配无头浏览器或 jsdom，mermaid-cli 即用 puppeteer）；`src/Diagram.ts` `Diagram.fromText()`（detectType + 图表懒加载注册）；`src/mermaidAPI.ts` L465 render 实现，L676-L692 支持 `fontFamily`/`themeVariables` 注入（中文字体与主题可控）；monorepo 还含 mermaid-layout-elk / mermaid-layout-tidy-tree 布局包。
- 在 PPT 管线中的角色：**slidev 的生产实践**（slidev/packages/client/modules/mermaid.ts：`mermaid.render(id, code, containerElement)` 输出 SVG 字符串并按 `lz-string + options` 缓存，codeblock 语法集成 slidev/packages/slidev/node/syntax/codeblock/index.ts）；**leo-ppt-generator 自身资产已就绪**：`references/styles/11_图表语法/` 18 个文件（折线图=xychart-beta、思维导图、时序图、甘特图、桑基图等）全部以 mermaid 语法为载体，明文写着"文本描述即可渲染（mermaid 语法），是「可执行的图解」"——目前只作为图像模型的 prompt 参考，未做确定性渲染。
- License：MIT（monorepo v10.2.4）。
- 对 leo-ppt-generator 的判定：**可直接集成资产** —— 图表语法库已经是 mermaid 方言，引入确定性渲染等于把这 18 个文件从"参考"升级为"可执行"。

### playwright
- 一句话定位：微软出品的多浏览器自动化框架，跨浏览器无头截图 + deviceScaleFactor 精确控像素密度。
- 核心能力与 API 面：`packages/playwright-core/src/client/page.ts` L633 `screenshot(options)`（type/mask/path/timeout）；viewport 由 context 控制，`channels.d.ts` 多处 `deviceScaleFactor?: number`（L408/L475/L855/L925/L998）——`viewport 1280×720 + deviceScaleFactor 2` 即得 2560×1440 位图；monorepo 含 playwright-chromium/firefox/webkit 全家桶与 `npx playwright install chromium` 安装器。
- 在 PPT 管线中的角色：**frontend-slides 的完整生产管线**（`frontend-slides/scripts/export-pdf.sh`，420 行）：起本地 HTTP server（"字体加载需要 HTTP，file:// 不可靠"）→ `chromium.launch()` + viewport 1920×1080 → `page.goto(..., {waitUntil:'networkidle'})` → `await page.evaluate(() => document.fonts.ready)` → 三种导航策略切页（直接改 display / window.presentation.goToSlide / scrollIntoView）→ 强制 `.reveal` 元素 opacity:1 → 逐页 `page.screenshot()` → 第二个浏览器实例拼 PDF；支持 `--compact` 1280×720 档。**banana-slides** 用它跑 e2e（banana-slides/frontend/e2e/*.spec.ts）。
- License：Apache-2.0（playwright-core）。
- 对 leo-ppt-generator 的判定：**可直接集成资产** —— 页面 HTML→2560×1440 PNG 的确定性渲染首选执行器，语料已验证完整工程形态。

### puppeteer
- 一句话定位：Google 出品的 Chrome DevTools Protocol 自动化库，PDF/截图导出栈常客。
- 核心能力与 API 面：`packages/puppeteer-core/src/api/Page.ts` L2707 `screenshot()`（L2727-L2794 参数校验：quality 仅 jpeg/webp、clip 正数、扩展名推断类型）；viewport 含 `deviceScaleFactor`（src/common/Viewport.ts、EmulationManager.ts）；ChromeLauncher（src/node/ChromeLauncher.ts）支持自定义 executablePath。
- 在 PPT 管线中的角色：**presenton 的导出栈**：electron/app/ipc/export_handlers.ts（`export-presentation` → pptx/pdf）、electron/app/utils/export-chromium.ts（@puppeteer/browsers 管理浏览器缓存）、servers/fastapi/services/export_task_service.py L187（`PUPPETEER_EXECUTABLE_PATH` 环境变量定位 chromium）。
- License：Apache-2.0（puppeteer / puppeteer-core）。
- 对 leo-ppt-generator 的判定：**可借鉴机制** —— 与 playwright 二选一；语料两者都有生产案例，playwright 的 deviceScaleFactor + 自动安装器对技能包分发更友好。

### resvg-js
- 一句话定位：Rust resvg 引擎的 Node 绑定，SVG→PNG 栅格化的确定性天花板。
- 核心能力与 API 面：`index.js` 导出 `render/renderAsync/Resvg` 类；`index.d.ts` 完整 API 面：`font: { fontFiles: string[], fontDirs: string[], loadSystemFonts, defaultFontFamily, serifFamily/sansSerifFamily/... }`（**中文字体按目录显式加载**，关闭 loadSystemFonts 即完全确定性）；`fitTo: {mode:'width'|'height'|'zoom', value}`（**2560×1440 档直接 fitTo.width=2560**）；`background`、`crop`、`textRendering/geometricPrecision`；`Resvg.render().asPng()` 返回 Buffer；`getBBox()/cropByBBox()` 支持紧凑裁剪；`imagesToResolve()/resolveImage()` 处理外链图。
- 在 PPT 管线中的角色：语料库内无消费者（前瞻性资产，Vercel OG 生态标准件）。
- License：MPL-2.0（v2.7.0-alpha.2）——文件级 copyleft，作为独立 npm 二进制依赖引入不传染宿主，需登记。
- 对 leo-ppt-generator 的判定：**可直接集成资产** —— SVG→PNG 环节的最优解：无浏览器、无 DOM、位级确定、离线。

### satori
- 一句话定位：JSX/React 元素→SVG 字符串的无浏览器排版引擎（Vercel OG 底座）。
- 核心能力与 API 面：`src/satori.ts` `satori(element: ReactNode, { width, height, fonts: FontOptions[], loadAdditionalAsset, pointScaleFactor })` → SVG string；Yoga wasm 做 flexbox 布局（yoga.wasm、src/yoga.ts）、HarfBuzz 做文本整形（src/harfbuzz.ts —— **CJK 断行正确性的关键**）；字体必须显式传 data buffer（src/font.ts FontLoader），`loadAdditionalAsset(languageCode, segment)` 支持按语言分段懒加载字体（中文大字库的子集化通道）；`segment()`（src/utils.ts）按字符类切分文本。只支持 flexbox 子集，不支持 CSS grid。
- 在 PPT 管线中的角色：语料库内无消费者（前瞻性资产）。
- License：MPL-2.0 —— 需登记。
- 对 leo-ppt-generator 的判定：**可借鉴机制** —— "结构化模板→确定性 SVG"的范式极佳，但要求页面模板改写为 JSX 子集，迁移成本高；更适合未来的"信息图卡" lane 而非当前主路线。

### sharp
- 一句话定位：libvips 封装的高性能图像处理瑞士军刀（resize/composite/format 转换）。
- 核心能力与 API 面：`lib/index.mjs` mixin 架构（input/resize/composite/operation/colour/channel/output/utility）；`lib/constructor.mjs` L169 `density`（SVG/PDF 输入的栅格化 DPI——**SVG→PNG 的备用路径**）、L212-L214 `svg.stylesheet`（SVG 栅格化时注入 CSS）；`lib/resize.mjs` kernel/fit（lanczos3 等卷积核、cover/contain/inside/outside）；`lib/output.mjs` png 压缩参数、density EXIF 写入。
- 在 PPT 管线中的角色：**presenton 生产使用**（presenton/package.json、start.js L229 `require('sharp')` 可用性探测）。
- License：Apache-2.0（v0.35.4）。
- 对 leo-ppt-generator 的判定：**可直接集成资产** —— 像素档后处理（2560×1440 断言后的降档 -web 变体、EXIF density）与图像页体积治理；librsvg 后端 SVG 能力弱于 resvg，仅作后备。

### awesome-gpt-image-2
- 一句话定位：GPT-Image2 工业化提示词资产库（544 案例反向工程 + 20+ 模板）+ 可复用 agent skill。
- 核心能力与 API 面：`agents/skills/gpt-image-2-style-library/SKILL.md` 定义完整工作流（模板类别→风格标签→场景标签→案例匹配→六段式 prompt 组装：subject/composition/style/text-labels/aspect-ratio/constraints）；`references/style-library.md` 由 `data/style-library.json` 生成（维护命令 `npm run generate:style-skill`）；src/ 是 Vite 展示站。
- 在 PPT 管线中的角色：leo-ppt-generator 已 vendored 为 `references/styles/05_来源_awesome-gpt-image-2/`（含 00_合并映射.md 与借鉴新增），是图像模型页的提示词语法来源。
- License：MIT。
- 对 leo-ppt-generator 的判定：**已覆盖** —— 本地化拷贝已在技能内，本次评审仅需保持同步。

### G2
- 一句话定位：AntV 声明式统计可视化引擎（v5 基于 @antv/g 渲染器架构）。
- 核心能力与 API 面：`src/runtime/render.ts` 基于 `@antv/g` Canvas + g-plugin-dragndrop（L1-L10 import 证据），`inferKeys()`（L18-L55）为视图树生成唯一 key 支持增量渲染；渲染器可替换（g-svg/g-canvas/g-webgl）；`src/api/` 链式语法 + options 语法双轨。
- 在 PPT 管线中的角色：语料库内无消费者（presenton 用 React 系 recharts：servers/nextjs/app/hooks/compileLayout.ts L5）。
- License：MIT（@antv/g2 v5.4.8）。
- 对 leo-ppt-generator 的判定：**不适用** —— 面向交互式 Web 分析场景；静态成图场景 echarts 的 SVG 字符串输出更直接。

### echarts
- 一句话定位：百度/ASF 出品的统计图表标准库，原生支持无 DOM 的 SVG 字符串输出（SSR）。
- 核心能力与 API 面：`src/core/echarts.ts` L940 `renderToSVGString({useViewBox})`（SVG 渲染器下直接返回 SVG 字符串，Node 端配 setPlatformAPI 可用）；L923 `renderToCanvas({pixelRatio})`；L958 `getSvgDataURL()`；L969 `getDataURL({type:'png'|'jpeg'|'svg', pixelRatio, backgroundColor})`；`ssr/client/src/index.ts` `hydrate()` 提供服务端 SVG 的客户端水合（事件代理 via `ecmeta_*` 属性）。i18n 目录含中文语言包。
- 在 PPT 管线中的角色：**PPTist 的图表元素引擎**（PPTist/src/views/components/element/ChartElement/Chart.vue L11-L14：`echarts/core` 按需引入 + BarChart/LineChart/PieChart/ScatterChart/RadarChart + `SVGRenderer`）。
- License：Apache-2.0。
- 对 leo-ppt-generator 的判定：**可直接集成资产** —— 数据图表页确定性成图的最短路径：option JSON → renderToSVGString → resvg 栅格化 2560 宽。

### nivo
- 一句话定位：React + d3 之上的声明式图表组件族，自带 headless SVG 渲染包。
- 核心能力与 API 面：`packages/static/src/renderer.ts` `renderChart()`：`renderToStaticMarkup(createElement(component, {animate:false, isInteractive:false, renderWrapper:false, ...}))` → `<?xml...?>` + SVG 字符串（Node 可直接跑）；packages/ 下 30+ 图表类型（bar/line/pie/heatmap/chord/network/...）；根目录 Dockerfile.nivo-api / api/ 是渲染服务化形态。
- 在 PPT 管线中的角色：语料库内无消费者（React 技术栈门槛）。
- License：MIT（packages/static/package.json；根 LICENSE.md MIT 文本）。
- 对 leo-ppt-generator 的判定：**不适用** —— React 组件树依赖对 CLI 技能包过重，SVG 输出能力 echarts/vega 均可替代。

### vega
- 一句话定位：声明式 JSON 图表语法（学术出版标准）的参考实现，headless 渲染到 SVG/Canvas。
- 核心能力与 API 面：`packages/vega-view/src/View.js` L388-L389 `toSVG: renderToSVG, toCanvas: renderToCanvas`；`render-to-svg.js`：`renderHeadless(this, RenderType.SVG, scaleFactor)` → `r.svg()`（scaleFactor 直接控制输出分辨率）；渲染后端在 vega-scenegraph（CanvasRenderer/SVGRenderer/HybridRenderer）。spec 即 JSON，天然适合 LLM 生成与 schema 校验（vega-schema 包）。
- 在 PPT 管线中的角色：语料库内无消费者。
- License：BSD-3-Clause。
- 对 leo-ppt-generator 的判定：**可借鉴机制** —— "JSON spec + schema 校验 + headless 渲染"的架构范式值得图表 lane 借鉴；但图型覆盖与中文社区资料不如 echarts。

### fabric.js
- 一句话定位：面向 canvas 编辑器的对象模型（选区/变换/序列化），带独立 Node 入口。
- 核心能力与 API 面：`index.node.ts` → `@fabricjs/node`（Node canvas 无 DOM 运行）；`packages/core/src/canvas/StaticCanvas.ts` L950 `toSVG(options, reviver)`、L173 起 toDataURL（controls 排除导出）、markup 逐对象拼接（L1149）；场景图 JSON 序列化往返。
- 在 PPT 管线中的角色：语料库内无消费者（编辑器生态位被 konva 占据）。
- License：MIT。
- 对 leo-ppt-generator 的判定：**不适用** —— 与 konva 同一生态位，成图与编辑均无相对优势。

---

## 二、语料库使用证据汇总（grep 结果）

| 基建 | 消费者 | 用途 | 证据文件 |
|---|---|---|---|
| html-to-image | PPTist | 浏览器端导出图片与"图片版 PPTX"（toJpeg→pptxgenjs） | `PPTist/src/hooks/useExport.ts` L6/L55/L81 |
| echarts | PPTist | 图表元素渲染（echarts/core + SVGRenderer 按需引入） | `PPTist/src/views/components/element/ChartElement/Chart.vue` L11-L14 |
| playwright | frontend-slides | HTML 演示→逐页截图→PDF 全管线（HTTP server + fonts.ready + 导航状态机） | `frontend-slides/scripts/export-pdf.sh` |
| playwright | banana-slides | e2e 测试（pptx-export-panel 等 20+ spec） | `banana-slides/frontend/e2e/*.spec.ts` |
| puppeteer | presenton | Electron/服务端 pptx+pdf 导出（PUPPETEER_EXECUTABLE_PATH） | `presenton/electron/app/ipc/export_handlers.ts`、`servers/fastapi/services/export_task_service.py` L187 |
| mermaid | slidev | codeblock→SVG 客户端渲染 + 缓存 | `slidev/packages/client/modules/mermaid.ts` |
| konva | presenton / genoffice | 幻灯片编辑器画布（react-konva / konva-adapter） | `presenton/servers/nextjs/package.json` L55、`genoffice/apps/slides/src/renderer/konva-adapter.ts` |
| sharp | presenton | 服务端图像处理 | `presenton/start.js` L229 |
| （渲染→截图→审查） | OfficeCLI | PPTX 高保真 HTML 渲染引擎 + 无头浏览器逐页 PNG，供多模态 agent"看"输出 | `OfficeCLI/README.md` L259-L267 |
| （裸 Chrome 截图） | html-ppt-skill | `chrome --headless=new --screenshot --window-size=1920,1080 --virtual-time-budget=4000` | `html-ppt-skill/scripts/render.sh` L48-L60 |
| resvg-js / satori / vega / G2 / nivo / fabric / canvg / dom-to-image / html2canvas | 无 | 语料内无生产消费者 | 全库 grep |

关键结论：语料库把"确定性渲染"分成了三个梯队——(1) 产品级完整管线已存在于 frontend-slides（playwright）与 OfficeCLI（渲染引擎+截图）；(2) 浏览器端 DOM 截图在生产被 PPTist 验证但暴露了 foreignObject 字体坑；(3) SVG/headless 新基建（resvg/satori）在语料内尚未有人用，属于 leo 可以抢跑的位置。

---

## 三、Top 5 集成建议（按 ROI 排序）

### 1. 引入 Playwright 无头浏览器渲染 lane，作为图像模型之外的"确定性页面渲染 backend"
- **来源与证据**：`frontend-slides/scripts/export-pdf.sh`（L136-L284：chromium.launch → networkidle → document.fonts.ready → 切页 → page.screenshot）；`playwright/packages/playwright-core/src/client/page.ts` L633（screenshot API）+ channels.d.ts（deviceScaleFactor）；`OfficeCLI/README.md` L259（渲染→截图→对抗式审查，已被 leo 的 `references/visual-qa.md` 明文借鉴）。
- **预期收益**：generate 路线获得第二 backend：文本密集页/表格页不必再赌图像模型的文字保真（backend-selection.md 已承认"图片路线的 stylized 图表不承载精确数值标注"、"密集表格页持续高 token 低通过 → 默认改走 direct-editable"——确定性渲染给了第三条出路）；视觉质检从"看模型输出图"升级为"渲染即所见"。
- **集成成本**：中。需要：页面 HTML 模板族（可从版式库 12_版式库 映射）、本地字体注入（@font-face 指向本地 woff2 或系统字体）、`npx playwright install chromium` 的 setup 步骤、2560×1440 档用 `viewport 1280×720 + deviceScaleFactor 2` 或直接 2560 viewport。
- **形态建议**：`"$LEO_PPT" render page --template <id> --data slide.json --out slide_N.png --size 2560x1440`，产物继续走既有 check_deck_geometry.py 与 image record 质检闭环。

### 2. 图表页确定性渲染：11_图表语法（mermaid）在无头浏览器内 render → SVG → PNG
- **来源与证据**：`mermaid/packages/mermaid/src/mermaid.ts` L203（`render(id, txt, element)` 需 DOM container，故与建议 1 的浏览器实例天然共生）；`mermaidAPI.ts` L676-L692（fontFamily/themeVariables 注入，deck colors 锚点可直接映射 themeVariables）；`slidev/packages/client/modules/mermaid.ts`（等价集成的生产参照）；**决定性事实**：`leo-ppt-generator/references/styles/11_图表语法/` 18 个文件已全部采用 mermaid 语法（折线图.md 的 xychart-beta、思维导图.md、时序图.md 等），图表样式规范.md 也已写明"任何图表——mermaid 原生、……"。
- **预期收益**：图表数值/单位/标签 100% 逐字保真，直接消灭 visual-qa.md 对抗清单中"图表数值与 approved 完全一致？""无数据授权的 chart-like 形状"两类最高频失败项；18 个图表语法文件从参考文档升级为可执行资产，零改写成本。
- **集成成本**：低-中。复用建议 1 的浏览器实例；mermaid 输出 SVG 后可直接在页面内栅格化（或抽 SVG 交给建议 3 的 resvg）。

### 3. 引入 resvg-js 作为 SVG→PNG 栅格化引擎（中文字体 fontDirs 显式管理）
- **来源与证据**：`resvg-js/index.d.ts`（`font.fontDirs/fontFiles/loadSystemFonts:false` —— 离线且确定；`fitTo:{mode:'width',value:2560}` —— 像素档一等公民；`asPng(): Buffer`）；`index.js`（同步/异步双 API）。
- **预期收益**：mermaid/echarts/satori 输出的 SVG 在无浏览器环境下栅格化为 2560×1440 PNG；位级可复现（同输入同输出），适合评测与回归（skill-up eval 可做像素 diff）；Rust 性能让批量页渲染在秒级。
- **集成成本**：低。单一 napi 依赖；注意 MPL-2.0 需在包级 NOTICE/UPSTREAM 登记（独立二进制依赖不触发源码开放义务）。

### 4. 数据图表增强 lane：echarts renderToSVGString（统计图表超出 mermaid 表达力时）
- **来源与证据**：`echarts/src/core/echarts.ts` L940 `renderToSVGString()`、L969 `getDataURL({type:'svg', pixelRatio})`；`PPTist/src/views/components/element/ChartElement/Chart.vue` L11-L14（SVGRenderer 路线的生产验证）；`ssr/client` 证明官方把 SVG SSR 当一等能力。
- **预期收益**：mermaid xychart-beta 的图型与标注能力有限（无对数轴、无双轴、无堆叠百分比）；echarts option JSON 由 LLM 生成即可渲染专业统计图，补齐"数据仪表盘风""科研答辩风"等风格对图表的要求；SVG 输出可统一进建议 3 的栅格化管线。
- **集成成本**：中。Node 端需 setPlatformAPI 文本测量 shim；样式需从 deck colors 锚点映射 theme。

### 5. 引入 sharp 做像素档后处理与体积治理
- **来源与证据**：`sharp/lib/resize.mjs`（kernel/fit 降采样）；`lib/output.mjs`（png 压缩、density EXIF）；`lib/constructor.mjs` L169（SVG 输入 density 备用栅格化）；`presenton/start.js` L229 + package.json（生产使用先例）；leo 自身 `image_gen.py` 已有 `DEFAULT_DOWNSCALE_SUFFIX = "-web"` 概念但依赖 Python 栈。
- **预期收益**：交付档（2560×1440）与 web 预览档（1280×720，参照 frontend-slides --compact）一条命令切换；PNG 体积优化降低 PPTX 总重；EXIF density 写入让 PowerPoint 打开时物理尺寸正确。
- **集成成本**：低。单依赖、Apache-2.0 宽松。

---

## 四、确定性页面渲染路线技术判断

**候选路线对比**（以"确定性生成 PPT 页图 @2560×1440、中文字体、离线、可控性"为标准）：

| 维度 | 无头浏览器截图（playwright/puppeteer） | SVG 管线（mermaid/echarts/satori → resvg） | canvas 序列化（konva/fabric） |
|---|---|---|---|
| 布局/CSS 表达力 | 完整（真浏览器排版） | 子集（satori 仅 flexbox；mermaid/echarts 是封闭图形语法） | 场景图 API，无文档排版语义 |
| 确定性 | 视觉确定（抗锯齿/子像素渲染可能跨版本微差） | **数学级确定**（同输入位级一致） | 确定，但序列化格式专有 |
| 中文字体 | 系统字体或 @font-face（file:// 不可靠，需本地 HTTP——frontend-slides 证明） | resvg fontDirs 显式目录 / satori 传 buffer（中文大字库需子集化） | node-canvas registerFont |
| 离线 | 浏览器二进制 ~150MB（可复用系统 Chrome） | 全离线（wasm/napi） | 全离线 |
| 2560×1440 | viewport 或 deviceScaleFactor=2 | fitTo.width=2560 / scaleFactor | pixelRatio 2 |
| 生态证据 | frontend-slides 全管线、OfficeCLI、presenton | 语料内空白（前瞻） | presenton/genoffice 编辑器用 |

**取舍建议：双层组合，而非单选。**

1. **页面级（整页版式、文字密集页、混合排版）→ 无头浏览器截图为主**。理由：PPT 页面的本质是"文档排版"，完整 CSS 排版引擎只有浏览器有；中文字体在 macOS/Windows 系统字体开箱即得；语料中该路线工程形态最成熟。工程要点从 frontend-slides 的教训直接继承：本地 HTTP server 供字体、`document.fonts.ready` 门、页面模板必须提供 deterministic 模式（禁动画、`data-slide-ready` 属性代替定时等待）。
2. **图表级（数据可视化、结构图解）→ SVG 管线为确定性主干**。理由：图表的正确性合同（数值逐字一致、零基线、估算虚线）是 leo 质检体系中最刚性的条款，交给图像模型或浏览器排版都是不必要的风险面；mermaid/echarts → SVG → resvg 的链路每一步可断言、可缓存、可像素 diff 回归。浏览器实例可作为 mermaid 的宿主（同一次 page.evaluate 内完成），resvg 负责最终栅格化。
3. **canvas 序列化不引入**。konva/fabric 的价值在交互编辑器（presenton/genoffice 的用法），其场景图 JSON 对"从内容合同生成页面图"没有表达优势，反而引入专有格式锁定。
4. **dom-to-image/html-to-image/html2canvas 一族仅限浏览器内预览导出**（PPTist 用法），永远不要进 CLI 成图管线——它们本质是"借用用户浏览器渲染再序列化"，字体嵌入正是其最脆环节（PPTist 被迫 `fontEmbedCSS=''`）。

---

## 五、专家署名观点与反面教训

**观点（渲染与图像管线基建评审人）：**

确定性渲染与图像模型不是替代关系，是**页型路由的两条 lane**。leo-ppt-generator 的 backend-selection.md 已经建立了 `chart|text-heavy|image` 页型路由与 backend_stats 通过率统计——这套架构天生为"确定性渲染 backend"预留了插槽。我的判断是：图像模型继续负责视觉创意（封面、概念图、氛围页），确定性渲染接管"正确性合同"最重的页型（数据图表、表格、流程图）。当 backend_stats 显示某页型在图像 backend 持续低通过率时，路由到渲染 lane 的边际收益最大。11_图表语法 18 个 mermaid 文件是本次评审发现的最大存量资产：它们写于图像路线时代，却恰好是确定性渲染的现成输入，引入渲染 lane 的边际成本被这笔资产摊薄到接近零。

**反面教训：**

1. **foreignObject 字体嵌入陷阱**（PPTist/src/hooks/useExport.ts L59-L68）：PPTist 在导出前要手工移除 `foreignObject [xmlns]` 属性，且在 `ignoreWebfont` 默认开启时直接 `fontEmbedCSS = ''` 放弃 webfont 嵌入——dom 序列化路线的字体内联在真实世界不可靠，被头部项目公开降级处理。教训：任何成图管线的字体策略都应该是"渲染环境提供字体"（系统字体/本地 @font-face/resvg fontDirs），而不是"把字体序列化进文档"。
2. **截图管线真正的难点是状态收敛，不是截图**（frontend-slides/scripts/export-pdf.sh L199-L278）：fonts.ready 之后仍需 1500ms+300ms+200ms 三段魔法等待、三种切页策略兜底、强制 `.reveal` 元素可见——因为页面模板从没为"截图"这个消费者设计过。教训：leo 若引入渲染 lane，页面模板合同必须包含 deterministic 渲染模式（禁用动画与 IntersectionObserver、提供显式 ready 信号），否则质检的"可复现"会在时序上漏气。
3. **裸 Chrome --screenshot 的分辨率天花板**（html-ppt-skill/scripts/render.sh L50-L58）：`--window-size=1920,1080 --virtual-time-budget=4000` 虽零依赖，但 window-size 即最终像素、无 deviceScaleFactor 语义，上 2560×1440 档和 retina 文字锐度都受限。教训：最低成本路线要先对齐像素档合同再谈便利。

---

## 附：License 汇总

| 项目 | License |
|---|---|
| canvg / dom-to-image / html-to-image / html2canvas / konva / mermaid / G2 / nivo / fabric.js / awesome-gpt-image-2 | MIT |
| playwright / puppeteer / echarts / sharp | Apache-2.0 |
| resvg-js / satori | MPL-2.0（文件级 copyleft，独立依赖引入需登记） |
| vega | BSD-3-Clause |
