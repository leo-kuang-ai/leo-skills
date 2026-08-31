# 专家 2 报告:AI PPT 端到端产品架构源码评审(15 项目全量)

评审人角色:AI PPT 端到端产品架构产品专家(Gamma 类平台管线、模板系统、导出链路、产品化设计)。
评审对象:15 个开源/前端开源项目,全部完成目录扫描 + README 通读 + 核心源码实读。
集成目标:leo-ppt-generator 技能包(只读对照,未修改)。
评审日期:2026-08-30。

---

## 逐项目评审

### banana-slides

- 一句话定位:基于 nano banana pro 图片生成模型的"原生 AI PPT"全栈应用(Web + Electron 桌面),图片式生成为主、可递归转换为可编辑 PPTX,是本组中工程完成度最高的图片式双轨产品。
- 架构与核心机制:
  - 生成管线在 `backend/services/prompts.py`(1657 行)中集中管理,分 7 区:大纲(生成/解析/细化)→ 页面描述(单页/流式/拆分/细化)→ 图片生成 → 图片处理(背景提取/画质修复)→ 内容提取(文字属性/页面内容/排版分析/风格提取)→ 旁白 TTS。大纲支持 simple 与 part-based 两种 JSON 结构(`_OUTLINE_JSON_FORMAT`),并有"论断式大纲"规则(`_OUTLINE_TAKEWAY_RULE`,L96-111):内容页第一条要点必须是完整论断句(takeaway),后接 1-2 条证据(evidence),封面/目录/章节页豁免;全部 takeaway 依序连读应构成完整故事线。
  - 页面描述采用流式分页标记协议:`get_all_descriptions_stream_prompt`(L674-731)要求 `<!-- BEGIN -->` / `<!-- PAGE_END -->` / `<!-- END -->` 逐页输出,预置字段(页面文字/配图与素材/编排与重点/讲稿)互斥排他、带长度预算(`EXTRA_FIELD_INSTRUCTIONS`)。
  - 图片→可编辑转换是独立子系统 `backend/services/image_editability/`:`service.py` 的 `make_image_editable()` 递归做版面分析(MinerU/hybrid 提取器注册表)、图标主体抠图(百度智能抠图)、`coordinate_mapper.py` 的 local↔global bbox 缩放平移映射,产出 `EditableImage` 树。
  - 导出在 `backend/services/export_service.py`(2070 行):`create_editable_pptx_with_recursive_analysis()`(L1555 起)并发分析各页 → 批量文字样式提取(hybrid 全图+局部两种策略)→ `utils/pptx_builder.py`(803 行)按 bbox 反算字号(`calculate_font_size` 用 PIL 测宽)、支持 HTML 表格解析与 LaTeX 数学元素;`ExportWarnings` 分级收集警告,`fail_fast=False` 时降级继续。
  - 逐页模板系统:`get_template_auto_match_prompt`(prompts.py L1555-1650)"模板调度师"——按角色对齐 > 排版结构匹配(layout_hint/content_density 对 content_capacity/visual_density)> 文字对应消歧 > 风格连贯 > 节奏感(避免连续 5 页同模板)> 置信度 <0.5 返回 `undecided` 交人工,禁止编造 asset_id。
  - Provider 管理 `backend/services/ai_providers/`(genai/lazyllm/ocr/text/image 多源),支持 OpenAI OAuth PKCE 绑定 Codex 作生成源。
- 可搬运资产:
  - 提示词:`backend/services/prompts.py` 全部(论断式大纲规则、流式分页协议、模板调度师、风格提取 `get_style_extraction_prompt`、排版 caption `get_layout_caption_prompt`)。
  - 代码结构:`image_editability/`(递归提取 + 坐标映射 + 提取器注册表)、`export_service.py` 的批量样式提取与警告分级、`utils/pptx_builder.py` 的 bbox→字号反算。
- License:AGPL-3.0(强传染,不可直接复制代码进 MIT 仓库;提示词文本与机制思想可参考但不宜逐字搬运)。
- 对 leo-ppt-generator 的判定:【可借鉴机制】——论断式大纲、流式分页标记、模板调度师匹配、递归可编辑化与 leo 的 deck-master/page-decision-tree 高度同构,可作为提示词与流程设计的对照系;因 AGPL 不宜搬代码。

### frontend-slides

- 一句话定位:Claude Code 插件形态的"零依赖单文件 HTML 演示"技能,以"show, don't tell"视觉三样张做风格发现,自带 30+ bold 模板包与 PPTX→HTML 转换。
- 架构与核心机制:
  - `SKILL.md`(380 行)定义完整工作流:Phase 0 模式检测(新建/PPT 转换/增强)→ Phase 1 内容发现(四问:用途/页数/内容就绪度/密度模式)→ Phase 2 风格发现(生成 3 个真实首页样张:1 安全预设 + 1 bold 模板 + 1 wildcard,含"预览真实性规则"禁止渲染内部元数据)→ Phase 3 生成 → Phase 4 PPT 转换 → Phase 5 交付 → Phase 6 分享导出。固定 1920×1080 舞台整体缩放、禁止响应式重排是硬规则。
  - 密度模式(speaker-led 低密度 vs reading-first 高密度)直接影响排版决策,超出密度上限"拆页而不是缩字"。
  - 模板包渐进加载:`bold-template-pack/selection-index.json`(858 行紧凑索引,含 mood/tone/best_for/avoid_for/formality/density/scheme 与 preview_md 路径),选中后才读单个 `design.md`,明确"Do not read the other bold templates"。
  - `scripts/extract-pptx.py`(96 行)python-pptx 抽取文本/图片/备注为 JSON;`scripts/export-pdf.sh`(418 行)浏览器截图导 PDF。
- 可搬运资产:`bold-template-pack/selection-index.json` 的索引结构与"紧凑索引→preview→design"三级渐进加载纪律;`STYLE_PRESETS.md`(346 行)安全预设集;反 AI-slop 美学条款(禁 Inter/紫渐变白底等);`extract-pptx.py`。
- License:MIT(可自由搬运)。
- 对 leo-ppt-generator 的判定:【已覆盖(交互层)+ 可借鉴机制(资产加载)】——样张确认、风格推荐、密度档位 leo 均已有(CONFIRM-GATE/style-recommendation);其 selection-index 的"情感/正式度/适不适合"元数据 schema 与三级加载纪律可充实 style-library 的按需索引。

### presentation-ai(ALLWEONE)

- 一句话定位:Gamma 定位的开源对标(Next.js + LangChain),XML 幻灯片 DSL + Agent 工具调用编辑 + 38 内置主题 + 浏览器端 DOM 扫描导出 PPTX。
- 架构与核心机制:
  - `src/ai/agents/presentation/createAgent.ts`(142 行):LangChain `createAgent` + checkpointer,系统提示词定义完整 XML DSL——`<SECTION layout="left|right|vertical|background">` 与 COLUMNS/BULLETS/ICONS/CYCLE/ARROWS/TIMELINE/PYRAMID/STAIRCASE/BOXES/STEPS/COMPARE/BEFORE-AFTER/PROS-CONS/TABLE/CHARTS/INFOGRAPHIC 组件族,带 variant 属性与 item 级 icon;强制"必须调用工具而非裸输出 XML"的执行规则。
  - 主题系统:`src/lib/presentation/theme-schema.ts` 用 zod 定义 7 色(primary/accent/background/text/heading/smartLayout/cardBackground)+ 双字体(带真实字体名白名单约束)+ 圆角/过渡/阴影/遮罩;`src/lib/presentation/pptx-theme-extractor.ts` 用 JSZip 解析用户 PPTX 主题:Office 字体→Web 字体映射表(Calibri→Inter 等 16 条)、亮度/对比度计算自动补全缺失角色色。
  - 导出管线 `src/components/presentation/export/`:`domSlideScanner.ts` 扫描渲染后 DOM 提取元素位置/SVG/EChart;`contentWalker.ts`(882 行)遍历 Plate 编辑器 JSON;`domToPptxConverter.ts`(831 行)用 pptxgenjs 重建;`cssVariableResolver.ts` 解析 CSS 变量为具体值。
- 可搬运资产:theme-schema 的 7 色+smartLayout/cardBackground 角色划分;pptx-theme-extractor 的 Office→Web 字体映射表与角色色推导逻辑;XML DSL 的组件清单(可作版式语义对照)。
- License:MIT(可搬运)。
- 对 leo-ppt-generator 的判定:【可借鉴机制】——PPTX 主题提取器可直接补强"参考图/可信 Office→风格提取"路线(字体映射表 + 亮度补全算法是现成资产);DOM 扫描导出思路与 leo 的确定性组装互补但 skill 形态用不上浏览器。

### oh-my-ppt

- 一句话定位:本地优先 Electron 桌面应用,HTML 为创作载体,自研 HTML→可编辑 PPTX 导出与 PPTX 导入解析(均宣称接近 100% 还原),内置 75 个"风格 Skill"。
- 架构与核心机制:
  - 风格系统 `resources/styles/<id>/`:每个风格 = `style.json`(名称/别名/场景/版本)+ `SKILL.md`(叙事化设计说明:配色/排版/布局/动画/适合场景/不要清单)+ `preview.html`,共 75 个(如 academic-paper、ink-wash-jiangnan)。
  - 模板契约 `src/main/templates/template-design-contract.ts`:八字段 DesignContract(theme/background/palette≤6 色/titleStyle/layoutMotif/chartStyle/shapeLanguage/titleFont/bodyFont),超长文本截断 220 字、palette 兜底三色。
  - HTML→PPTX:`src/main/io/html-pptx/renderer.ts`(506 行)在 Electron BrowserWindow 中执行提取脚本,配套 KaTeX 块标记、静态背景捕获、文本残差检测(网格采样 18×10、颜色距离 ≤62、占比阈值 0.075 判定残留文字是否清干净)。
  - PPTX 导入 `src/main/io/pptx-import/`(3887 行纯自研):XML shape 元数据、图表渲染器、动画映射、文本校验器,还有 `chart-rewrite-agent.ts`(LLM 修正图表转换)。
- 可搬运资产:DesignContract 八字段 schema;75 个风格的 SKILL.md 叙事模板(中文、含"不要"负面清单——与 leo 风格文件同构);文本残差检测算法;风格别名/检索字段设计。
- License:Apache-2.0(可搬运)。
- 对 leo-ppt-generator 的判定:【可借鉴机制】——DesignContract 是比 leo 风格 brief 更正式的"模板真值"结构,palette/titleStyle/layoutMotif/chartStyle 字段可充实 deck-master 的视觉行;其"风格=叙事化 SKILL.md"与 leo 的 12 风格文件互证。

### genoffice

- 一句话定位:Genspark 开源的完整 AI Office 套件(六 Electron 应用共享引擎层),其中 pptx-engine 采用"字节保真外科手术式 OOXML 补丁",是本组 OOXML 工程最深的项目。
- 架构与核心机制:
  - `packages/pptx-engine/src/`(约 2 万行):`parse.ts` 语义解析(fast-xml-parser + scanSlide 字节锚点一一对应)与 `generate.ts` 的核心哲学——**不做整体 parse→serialize**(会丢未建模属性),而是对原始 `<p:sp>` 字节切片做原位补丁:run 数与 `<a:r>` 对齐时逐 run 无损替换文本与格式,结构变化才降级为按段落重建 txBody、仍保留 spPr 外层字节。
  - AI 层 `packages/agent-core/src/`:AgentLoop/AgentSkill/IPC 流式传输抽象;`apps/slides/src/renderer/ai/slides-skill.ts`(3548 行)把幻灯片能力封装为 AgentSkill,generate_deck 分 style/plan/images/pages 四阶段进度事件;`landGeneratedPages` 用 pageMarkers(每页一张单页 pptx)兑换合并进当前 deck,单页失败按原位重插,管线失败自动降级元素级模式。
  - 质量层:`layout-audit.ts`(205 行)版面审计、`slide-qc.ts`(261 行)页级质检、`layout-script.ts`(347 行)版式脚本解释器。
- 可搬运资产:字节保真补丁策略(文本编辑只动 `<a:r>`、保留 spPr 原字节);pageMarkers 单页合并 + 失败重插 + 自动降级的页面落地协议;AgentSkill 的四阶段进度事件模型;layout-audit/slide-qc 的检查清单。
- License:Apache-2.0(核心引擎可搬运)。
- 对 leo-ppt-generator 的判定:【可借鉴机制】——"只改你触碰的字节"是 upgrade-selected 路线的正确工程原则(避免 python-pptx 整体重写导致布局漂移);pageMarkers 协议可直接映射到 leo 的逐页 worker 产物合并;四阶段进度事件可充实五字段控制面的 status 汇报粒度。

### LandPPT

- 一句话定位:FastAPI 多_worker 平台(主题/文档→大纲→HTML PPT→讲稿/配音/视频/多格式导出),按角色路由模型,设计层用"全局视觉宪法"两段式生成。
- 架构与核心机制:
  - 服务按职责拆成 20+ 模块:`services/outline/` 12 个文件(生成/流式/校验/修复/页数控制/规范化),`services/slide/` 17 个文件(生成/流式/HTML 校验/清理/恢复/修复/媒体),`services/prompts/` 8 个提示词模块(outline/content/design/repair/speech_script/template/system)。
  - `services/prompts/design_prompts.py`(794 行):`get_global_visual_constitution_prompt`(L261)先让模型产出全 deck 统一的"视觉宪法",再 `get_page_creative_briefs_prompt`(L309)逐页出创意简报,支持模板 HTML 上下文与锁定区域(locked zones)上下文注入。
  - `services/slide/edit_agent/`:对话式页编辑代理,`tools.py` 把工具规格(名称/描述/JSON Schema)写成单一来源,native tool-calling 与文本协议提示词都由它派生"避免两份 schema 漂移";`html_safety.py` 做 CSS 声明级安全校验。
  - `services/pdf_to_pptx_converter.py`:Apryse SDK 自动下载并做 PDF→PPTX。
- 可搬运资产:全局视觉宪法→逐页创意简报的两段式设计提示词结构;edit_agent 的"工具规格单一来源"模式;repair_prompts.py 的修复提示词分类;按角色(大纲/幻灯片/编辑/模板/讲稿)路由模型的配置模式。
- License:Apache-2.0(可搬运)。
- 对 leo-ppt-generator 的判定:【可借鉴机制】——"全局视觉宪法"与 leo 的母版视觉行+风格合同同构且更系统(先全 deck 定宪法再逐页简报),可充实 deck-master.md 的跨页一致性段;修复提示词分类可充实 reason-codes 的重试话术。

### open-slide

- 一句话定位:"为 agent 而建的幻灯片框架"——1920×1080 固定画布 React 运行时 + 脚手架内置 create-slide/slide-authoring 等 agent skills + 浏览器 inspector 评论循环,是 skill 形态亲缘最近的项目。
- 架构与核心机制:
  - `packages/core/skills/create-slide/SKILL.md`:四问范围锁定(美学方向按主题定制 3 个"氛围词+具体视觉线索"选项而非固定预设/页数/每页文本密度/动静态),页面角色表(Cover/Agenda/Section divider/Content/Big number/Quote/Comparison/Closing),"一页一主意,想放两个就拆页"。
  - `packages/core/skills/slide-authoring/SKILL.md`:技术参考与工作流分离("Do not duplicate the knowledge below into other skills — link here instead");文件契约(`slides/<id>/index.tsx` 一个文件 + assets/,禁止建兄弟组件文件);`export const design: DesignSystem` + `var(--osd-X)` token 使生成后仍可被 Design 面板调色;notes export 内建讲稿(索引对齐、增删页必须同步重对齐)。
  - inspector:点击任意元素挂评论,持久化为源码 `@slide-comment` 标记,`/apply-comments` 让 agent 批量应用后清除标记——"present → comment → apply → repeat"循环。
- 可搬运资产:两技能分离(工作流 skill ↔ 技术参考 skill)的信息架构;design token 先行("先生成后可调"而非锁死);页面角色表与"一页一主意"规则;notes 索引对齐纪律。
- License:MIT(可搬运)。
- 对 leo-ppt-generator 的判定:【已覆盖(理念)+ 可借鉴机制】——leo 的 worker 派发/参考文档分层已是同类更严格实现;其 design token 化输出与"美学方向按主题动态生成选项"(反对固定预设菜单)两点可分别充实 style render 与 style-recommendation。

### AiPPT(veasion/文多多)

- 一句话定位:商用 AI PPT(文多多)开源的前端渲染引擎——纯 JS 的 PPTX JSON→Canvas/SVG 双渲染器 + ppt2json 解析工具,后端通过 docmee.cn 开放 API(SSE)闭源。
- 架构与核心机制:
  - `static/ppt2canvas.js`(1327 行)与 `static/ppt2svg.js`(2264 行):双渲染器实现 slideMaster→slideLayout→slide 三层继承,占位符属性逐层补全(`placeholder[type]` 缺失属性从母版继承);`static/geometry.js`(499 行)preset 几何路径;`static/animation.js`(2903 行)动画引擎;`static/chart.js` 图表。
  - `index.html`(735 行):SSE 调 `docmee.cn/api/public/ppt/generateOutline` → `randomTemplates` 选模板 → `generateContent`(asyncGenPptx)→ 轮询 `asyncPptInfo` 取 gzip+base64 的 pptxProperty 再渲染。
  - `ppt2json.html`:上传 PPT→解析 JSON→在线 JSONEditor 编辑→重渲染下载。
- 可搬运资产:母版/版式/占位符三层继承渲染逻辑(p2c 与 leo direct-editable 的 manifest 组装同构);geometry preset 形状路径表。
- License:GPL-3.0(传染;且后端闭源)。
- 对 leo-ppt-generator 的判定:【不适用】——渲染引擎面向浏览器预览,skill 无此需求;后端闭源不可审计;GPL 不宜混入。

### ai-to-pptx

- 一句话定位:GPL 商用系前端(引用 veasion/aippt-react)+ PHP 后端的模板填充式 AI PPT,模板被定义为"固定数量文本元素的结构约定"。
- 架构与核心机制:
  - `README_Make_Template.md`:模板制作规范是元素计数约定——封面恰好 2 个文本元素、目录 13 个(6×2+1)、内容页按 标题+N×M 结构(3×2、3×3 需要 5-8 种变体防重复),PPTX 经 veasion/ppt2json 转 JSON 后连同缩略图注册进 PHP `$Global_Templates`。
  - `src/views/AiPPTX/`:五步向导(StepOneInputData → StepTwoThreeGenerateOutline → StepFourSelectTemplate → StepFiveGeneratePpt),SSE 调后端 PHP(`asyncPptInfo.php`/`downloadPptx.php`),`changePptxTemplate` 支持生成后整体换模板。
- 可搬运资产:模板 JSON 化 + 缩略图注册的模板资产管理思路;换模板不换内容的产品交互。
- License:GPL-3.0(前端;后端另库亦 GPL;模板本身"不是开源的一部分"需授权)。
- 对 leo-ppt-generator 的判定:【不适用】——模板=僵化元素计数约定,内容被结构绑架(README 自认"只支持三小节");GPL 与闭源模板条款双重障碍。

### SlideBot-AI

- 一句话定位:纯 Gemini 双模型(gemini-3-pro-preview 文本 + gemini-3-pro-image-preview 出图)的图片式 PPT 生成器,大纲→逐页设计 prompt→整页图片,支持母版分析注入与单页微调。
- 架构与核心机制:
  - `modules/prompts.py`:OUTLINE_PROMPT_TEMPLATE(双格式输出:人读示例 + JSON)、STYLE_GENERATION_PROMPT(逐页出设计理念 + 图片 prompt,配色/字体规范作为结构化 spec 注入)。
  - `modules/gemini_api.py`(617 行):`_generate_ppt_image_sync`(L153)按 reference_type 分三种注入策略——`template` 母版模式把 `analyze_template_design`(L506)的结构化分析(六类色值/字体规格/布局结构/背景类型/风格摘要)拼成"必须严格执行"的规范段;`reference` 风格参考模式;`refine` 微调模式(以当前页图为基准只改指定部分);Logo 统一右上角规则;`page_materials` 素材图嵌入说明。
  - `server.py`(1206 行):FastAPI,母版/Logo 上传校验(禁 EMF/SVG 矢量)、图片压缩 JPEG 85%、导出仅 ZIP(原图打包)与 PIL 拼 PDF,无对象级 PPTX。
- 可搬运资产:母版分析→结构化色值/字体/布局注入 prompt 的完整模板(gemini_api.py L213-260);素材(Excel/截图)按页挂载与描述机制;微调模式 prompt 纪律(只改指定、其余保持)。
- License:MIT(可搬运)。
- 对 leo-ppt-generator 的判定:【可借鉴机制】——它与 leo generate 路线是同一范式(整页图 + 母版约束),其"母版结构化分析字段表"可直接对照充实 deck-master 的母版视觉行与 backend_selection 的 prompt 组装;"refine 模式"对应 leo 的单页重生成话术。

### OpenPPT

- 一句话定位:ChatPPT 官方开源的 Vue3 全功能在线演示编辑器(PPTist 系技术栈:pinia/pptxgenjs/pptxtojson/prosemirror),AI 能力走闭源云服务。
- 架构与核心机制:
  - `src/api/careate.ts`(455 行):AI 能力全部代理到 `/open-ppt/c-service`(vision_slide 生成、writtenwords 辅写、json2ppt、resource 资源库等),前端零 AI 逻辑。
  - `src/hooks/useExport.ts`(前端导出核心):pptxgenjs 按元素类型逐个转换(颜色/渐变/阴影/表格子主题色/clip path/公式),html-to-image 兜底图片化,jsPDF 导 PDF;`src/store/slides.ts` 为对象模型真值。
  - 编辑器视图 `src/views/Editor/`(Canvas/Toolbar/Thumbnails/NotesPanel/OutlineView/MindView/BrowseView),移动端编辑与 AI 聊天独立视图。
- 可搬运资产:pptxgenjs 前端导出的元素级转换映射表(useExport.ts 内的颜色/形状/表格处理细节,MIT 系库通用知识);JSON 中间格式 + json2ppt 服务端渲染的产品链路概念。
- License:GPL-3.0(前端)。
- 对 leo-ppt-generator 的判定:【不适用】——编辑器形态与 skill 不重合,后端闭源,GPL 障碍;仅 useExport 的元素转换经验有参考价值。

### chatppt(ChatPPT Studio)

- 一句话定位:教学级极简参考实现(React + FastAPI + python-pptx),四 preset 画像、LLM 缺失时确定性降级,无许可证文件。
- 架构与核心机制:
  - `backend/app/generator_service.py`(416 行):PRESET_PROFILES(business/tech/education/marketing 各带 audience/tone/language),`generate()` 三分支——FAKE_LLM_RESPONSES=1 假响应(在线 demo 测试)、有 OPENAI_API_KEY 走 LLM 且异常落 `_fallback_outline`、无 key 直接 fallback。
  - `backend/app/ppt_service.py`(201 行):ThemeConfig 六字段 dataclass(title/body/bg 色 + 字体 + 两级字号),`infer_theme_for_presentation` 从全文关键词猜主题,`apply_theme_to_presentation` 遍历占位符角色刷样式;parse_ppt/apply_edits 支持文本级在线编辑。
- 可搬运资产:FAKE_LLM_RESPONSES 确定性降级模式(评测/离线冒烟);preset 画像驱动的提示词参数化。
- License:仓库无 LICENSE 文件(默认保留所有权利,不可搬运代码;模式不受限)。
- 对 leo-ppt-generator 的判定:【不适用】——功能深度远低于 leo 已有能力;唯一启发是"确定性假响应"可用于 evals 的离线回归。

### langchat-slides

- 一句话定位:LangChat 团队的 @antv/infographic 驱动的信息图幻灯片生成器——声明式缩进语法流式渲染,30+ 信息图模板,逐页独立请求。
- 架构与核心机制:
  - `src/api/ai.ts`(149 行):SYSTEM_PROMPT 定义 `infographic <template-name>` + `data`/`theme` 缩进块语法与完整模板名清单(sequence-*/compare-*/list-*/hierarchy-*/chart-*/quadrant-*/relation-*),严格禁止输出 JSON/解释;compare 模板要求构建双根节点。
  - `src/composables/useSlideGenerator.ts`(144 行):逐页独立请求("只输出这一页"),100ms 节流实时更新当前页渲染——页间故障隔离,天然流式。
  - `src/lib/slide-utils.ts` 导出模板清单供校验;导出 PDF/PNG/SVG/PPT 由 infographic 库承担。
- 可搬运资产:声明式语法 + 模板名白名单约束 LLM 输出的做法;逐页独立请求的隔离模型;compare/list/sequence 等模板分类学(与 leo 13_页面语义/07_信息图类型可互校)。
- License:Apache-2.0(可搬运)。
- 对 leo-ppt-generator 的判定:【已覆盖】——逐页派发隔离、模板语义分类 leo 均已有更完备实现(worker 派发 + styles 13 分类);其模板分类命名可作 13_页面语义的交叉校对。

### ChatPPT-MCP

- 一句话定位:ChatPPT(BIYOO)云服务的 MCP 封装(Python/Node/Streamable HTTP 三实现,18 个文档 API 工具),纯 API 网关无本地逻辑。
- 架构与核心机制:
  - `python/src/ppt.py`(717 行):FastMCP 注册 18 个工具——build_ppt(主题+复杂度+字体+语言+主题色枚举)、text_build_ppt、build_ppt_by_file、query_ppt(轮询 status 1/2/3 + process_url)、download_ppt、editor_ppt、简历/匹配类等;工具 docstring 即给 agent 的调用说明("成功后调用 query_ppt 轮询…再调用 download_ppt")。
  - `node/src/index.ts`(941 行):官方 SDK 手写 ListTools/CallTool 的平行实现。
- 可搬运资产:异步任务工具协议(build→query 轮询→download→editor 的工具链描述写法);把"下一步调哪个工具"写进工具 docstring 的模式。
- License:AGPL-3.0。
- 对 leo-ppt-generator 的判定:【不适用】——无本地生成能力,云依赖;其工具 docstring 的"链式指引"写法对 leo 的 worker 派发文档有小参考价值。

### OpenCanvas

- 一句话定位:Claude 规划 + Gemini 出图的双模型学术风生成器(HTML/图片双模式),带图像校验子系统与提示词进化/视觉对抗评测体系,是"生成质量工程化"的样本。
- 架构与核心机制:
  - `src/opencanvas/generators/image_generator.py`(774 行):两步法——`_plan_blueprints`(L308)让 Claude 产出每页 blueprint JSON(slide_type/layout_type/title/content/visual_notes/figure_ids),规划 prompt 内嵌 18 种布局变体清单(Title Typography/Text+Data Emphasis/Card Grid/Vertical Timeline/…)+ 全局设计设置(调色板/字体/网格/留白)并要求"跨页变化布局,不重复";再逐页把 layout_type 拼进 Gemini 出图 prompt(L586-608)。PDF 输入时抽取图表(docling_extractor + plot_caption_extractor)按 figure_ids 匹配嵌入。
  - `src/opencanvas/image_validation/`:URL 校验、无效图替换(image_replacer)、主题图缓存(DuckDB topic_image_cache)、HTML 解析校验——对 HTML 模式中 LLM 编造的图片链接做闭环治理。
  - `src/opencanvas/evolution/` + `PROMPTS_REGISTRY.md`:多代理提示词进化,registry 记录每次成功/失败编辑(yaml:name/improvement/dimension/edit_type/change/lesson),如"显式禁止编造数字比正向引导有效 +2.0";`examples/visual_adversarial_*` 视觉对抗样例生成与测试。
- 可搬运资产:18 种布局变体清单与"跨页不重复"规则;blueprint 中间 JSON 结构;image_validation 的"编造图片链接→校验→替换→缓存"闭环;PROMPTS_REGISTRY 的提示词进化记账格式;视觉对抗测试样例思路。
- License:MIT(可搬运)。
- 对 leo-ppt-generator 的判定:【可借鉴机制】——其 image_validation 闭环与 visual-qa.md 互补(可补"素材引用真实性校验");布局变体清单可并进 12_版式库索引的检索维度;PROMPTS_REGISTRY 记账格式适合 leo 的风格/提示词迭代治理。

---

## Top 5 集成建议(按 ROI 排序)

1. 【提示词层,零代码】引入 banana-slides 的"论断式大纲(takeaway-evidence)"规则,充实 generate 路线大纲与 deck-master 的结论句标题段。
   来源证据:`/Users/kuang/knowledge/ppt-github/banana-slides/backend/services/prompts.py` L96-111(`_OUTLINE_TAKEWAY_RULE`:内容页第一条要点必须是完整论断句、后接 1-2 条证据、功能页豁免、连读成故事线)与 L700(描述层"标题优先写成论断句,大纲第一条 takeaway 是首选来源")。
   预期收益:大纲层叙事质量直接提升,与 leo 已有"结论句标题(按论证模式条件化)"形成"大纲-标题"两段贯通;leo 目前母版有结论句标题但缺"证据条目跟随"与"功能页豁免"显式规则。
   集成成本:极低——只改 `prompts/slide-worker.md` 与 `references/deck-master.md` 的相应段落(参考思想,不逐字复制 AGPL 文本)。

2. 【机制层,低代码】引入 banana-slides"模板调度师"逐页版式匹配,为 generate 路线自动化 12_版式库(40+ 版式)的逐页分配。
   来源证据:`banana-slides/backend/services/prompts.py` L1555-1650 `get_template_auto_match_prompt`——角色对齐 > 排版结构匹配(layout_hint×content_density 对 content_capacity×visual_density)> 文字对应消歧 > 风格连贯 > 节奏感(避免连续 5 页同版式、同版式至少隔 1 页)> 置信度 <0.5 返回 undecided 交人工、禁止编造 asset_id。
   预期收益:leo 的版式库目前靠 Agent 逐页自选;调度师模式给出可解释的优先级序 + undecided 兜底,匹配结果直接进入母版确认(CONFIRM-GATE 兼容,不新增确认门)。
   集成成本:低——新增一个 references 小节(如 deck-master.md 附"逐页版式分配规则")或在 slide-worker 提示词中嵌入优先级序;可先用 evals 验证。

3. 【工程层,中代码】吸收 genoffice 两条机制:(a)"字节保真外科手术式 OOXML 补丁"原则进入 direct-editable/upgrade 路线的运行时约定;(b)pageMarkers"单页 PPTX 兑换合并 + 失败原位重插 + 自动降级"协议映射到 leo 的逐页 worker 产物组装。
   来源证据:`/Users/kuang/knowledge/ppt-github/genoffice/packages/pptx-engine/src/generate.ts` 头注("no wholesale parse→serialize…surgical in-place patches of the original <p:sp> byte slice",run 对齐时逐 run 无损替换);`genoffice/apps/slides/src/renderer/ai/slides-skill.ts` 的 `landGeneratedPages`(pageMarkers→replace/append/insert_at,失败页原位重插,管线失败自动降级元素级)。
   预期收益:upgrade-selected 只重做选中页时避免整库重写引入的样式漂移;页面级失败不再废整 deck,与 leo 的 partial/恢复语义(reason-codes)天然对齐。
   集成成本:中——需要在 runtime 组装层(templates.py / editable adapter)约定"母本字节保留、仅补丁页替换"的合并策略;可先在文档层立原则再逐步落代码。

4. 【资产层,低代码】搬运 presentation-ai 的 PPTX 主题提取器逻辑与 oh-my-ppt 的 DesignContract 八字段,补强"参考图/可信 Office→风格提取"与 style render --brand。
   来源证据:`/Users/kuang/knowledge/ppt-github/presentation-ai/src/lib/presentation/pptx-theme-extractor.ts`(JSZip 解析 theme1.xml、Office→Web 字体映射表 16 条、亮度/色距推导补全 7 角色色)与 `presentation-ai/src/lib/presentation/theme-schema.ts`(zod:primary/accent/background/text/heading/smartLayout/cardBackground + 字体白名单);`/Users/kuang/knowledge/ppt-github/oh-my-ppt/src/main/templates/template-design-contract.ts`(theme/background/palette/titleStyle/layoutMotif/chartStyle/shapeLanguage/titleFont/bodyFont 归一化)。两者均 MIT/Apache 可搬。
   预期收益:direct-editable 路线的"可信 PPTX 风格提取"从 Agent 肉眼判读变为确定性解析(色板+字体+背景),Office 字体映射表解决"提取出的 Calibri 在 web/图像后端不可用"的落地问题;DesignContract 可作为 deck-master 视觉行的结构化字段对照。
   集成成本:低——一个纯函数脚本(python 解析 OOXML theme 即可,不必搬 JS)+ 风格 brief 字段扩展(style-brief-v1.schema.json 增补)。

5. 【质量层,中代码】引入 OpenCanvas 的 image_validation 闭环与提示词进化记账,充实 visual-qa 与 evals。
   来源证据:`/Users/kuang/knowledge/ppt-github/OpenCanvas/src/opencanvas/image_validation/`(url_validator.py/image_replacer.py/topic_image_cache.py:编造链接→校验→替换→DuckDB 缓存)与 `OpenCanvas/PROMPTS_REGISTRY.md`(yaml 记账:name/improvement/dimension/edit_type/change/lesson,如"显式禁止编造数字 +2.0");`examples/visual_adversarial_prompts.py` 对抗样例。
   预期收益:leo 三级标注管"数字来源",但没有管"图片引用真实性"(manifest 中素材路径/URL 是否存在且有效)——校验闭环直接堵住一类交付事故;PROMPTS_REGISTRY 格式适配 lint_style_briefs/baseline 的收敛纪律,给风格文件迭代提供"哪条规则值多少分"的度量。
   集成成本:中——新增一个 check 脚本(素材存在性/URL 可达性入 DELIVERY-GATE 前检查)+ registry markdown 约定;对抗样例并入 evals/eval.yaml。

---

## 专家署名观点

**架构趋同点。** 15 个项目在"分段管线"上高度趋同:大纲(结构化)→分页内容(描述/简报)→设计排版(风格+版式)→导出,差异只在每段的执行者与中间表示。中间表示分三派:文本派(banana 的 markdown 描述、LandPPT 的视觉宪法+创意简报)、DSL 派(presentation-ai 的 XML 组件语法、langchat 的 infographic 语法、ai-to-pptx 的模板 JSON)、图像派(SlideBot/OpenCanvas/banana 直接整页出图)。编辑器是产品化分水岭:有对象模型编辑器的(presentation-ai、OpenPPT、oh-my-ppt、genoffice)都演化出"渲染层扫描→PPTX 重建"的导出链,没有编辑器的只能靠重新生成。图片式→可编辑只有两条被验证的路:banana 的"递归版面分析+inpaint+坐标映射"与 oh-my-ppt 的"HTML 受控渲染+DOM 提取";leo 的 page-decision-tree 三步法(背景→前景资产→原生元素)与前者同构但约束更严(对象源规则不可降级),这是对的。多 Provider 按角色路由(LandPPT)与 BYOK(genoffice)是治理标配。

**与 skill 形态的能力互补。** 产品有而 skill 没有的:GUI 编辑器与实时所见即所得、inspector 式逐元素反馈(open-slide)、在线分享/协作/演示域。skill 有而产品普遍没有的:leo 的 Gate 0 信任门禁(本组 15 个项目无一对外来 Office 输入做信任拦截,banana 甚至修过参考文档远程图片 SSRF)、三级标注(引用/估算/示意)的事实纪律(OpenCanvas 的反幻觉规则只到"不编数字"粒度)、版本化可确认的中间工件(outline-v<N>.md/deck-master-v<N>.md——产品的中间表示都是会话态,不可审计)、以及确定性 CLI 验证(check_deck_geometry 非零即阻交付)。产品的"接近 100% 还原"是营销话术,leo 的 validation.json.passed + 再检要求才是可验证承诺。

**最值得引入的 1 个产品机制。** banana-slides 的"模板调度师"(per-page template matching with undecided fallback)。理由:leo 的 12_版式库(40+ 版式)与 13_页面语义(25+ 语义)是全组最丰富的版式资产,但分配权完全落在逐页 Agent 的自由裁量;调度师机制用"角色对齐→结构匹配→节奏感→undecided 交人工"的优先级序把这笔资产变成可自动调度、可解释、可兜底的能力,且匹配结果进母版确认即寄生既有 CONFIRM-GATE,零新增交互成本。这是把"资产厚度"转化为"自动化质量"的杠杆点。

**反面教训(明确不该学)。**
1. ai-to-pptx 的"模板=固定文本元素计数"(封面必须恰好 2 个文本元素、目录必须 13 个):模板结构绑架内容,README 自认"只支持三小节"。leo 的版式应是语义约束(要点数禅档位)而非元素计数硬约定。
2. ChatPPT-MCP / OpenPPT / AiPPT 的"前端开源+后端闭源 API":能力不可审计、不可自托管、密钥出境,与 skill 的本地确定性原则根本冲突。
3. SlideBot 把设计原则硬编码进 prompt(DEFAULT_DESIGN_PRINCIPLES 写死"商务简约白底"),风格不可配置——对照 leo 的风格库架构,设计默认值必须外置于提示词。
4. genoffice 的 2 万行自研引擎不可复制进 skill,但它的教训是反向的:不要用 python-pptx 整体重写已有 PPTX(整体 parse→serialize 丢未建模属性);upgrade 路线只做外科手术式补丁。
5. banana/oh-my-ppt 式"接近 100% 还原"宣传:不可验证的还原度承诺会造成交付争议;leo 应坚持 validation 布尔 + 逐项判据 + 波及面结论的再检纪律。
6. OpenCanvas 把进化/评测产物(*_test.txt、test_simple_slide.png 等 15+ 个根目录散落文件)直接提交进仓库:生成产物必须 git-ignore——与 leo 仓库 `*-workspace/` 的治理一致,勿学其散乱。

---

## 附:License 一览

| 项目 | License |
| --- | --- |
| banana-slides | AGPL-3.0 |
| frontend-slides | MIT |
| presentation-ai | MIT |
| oh-my-ppt | Apache-2.0 |
| genoffice | Apache-2.0(含 ee/ 商业目录) |
| LandPPT | Apache-2.0 |
| open-slide | MIT |
| AiPPT | GPL-3.0 |
| ai-to-pptx | GPL-3.0(模板另计) |
| SlideBot-AI | MIT |
| OpenPPT | GPL-3.0 |
| chatppt | 无 LICENSE 文件 |
| langchat-slides | Apache-2.0 |
| ChatPPT-MCP | AGPL-3.0 |
| OpenCanvas | MIT |
