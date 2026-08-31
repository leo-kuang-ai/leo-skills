# 专家3:PPT 视觉风格与排版系统调研报告

调研对象:排版编辑器 / 主题系统 / 视觉卡片生成赛道(8 组分析报告相关小节 + 4 项目源码深读)。
视角:PPT 视觉系统(主题参数化 / 风格可发现性 / 文字渲染保真 / 多页一致性 / 模板化批量 / 编辑器架构)。
被增强对象:`/Users/kuang/knowledge/leo-skills/leo-ppt-generator/`(下称 leo)。

---

## 一、赛道优势总结

### 1. 主题参数化(变量层与主题层分离)

- **md(doocs,13.3k)**:主题 = 分层合并(`packages/core/src/theme/themeApplicator.ts`):`:root` CSS 变量层(`cssVariables.ts`:primaryColor/fontFamily/fontSize/lineHeight/blockSpacing/linkColor/blockquoteBackground 七参数)+ base CSS + 主题 CSS + 标题预设 + 用户自定义 CSS,运行时 `processCSS` 解析 var() 与 calc() 后注入。每主题独立参数快照(`apps/web/src/stores/theme.ts` 的 `PerThemeSettingsMap`,切主题自动加载对应配置),参数可热调不换主题。
- **xiaohu-wechat-format(0.7k)**:85 套主题全部是独立 JSON 文件(`themes/*.json`),主题即数据。
- **guizang-social-card-skill(6.7k)**:8 个规范 token(paper/paper_2/ink/muted/line/accent/accent_soft/accent_on),两套视觉系统(Editorial/Swiss)的 CSS 变量映射到同一组 token——**规范名与实现变量解耦**。
- **mdx-notes**:MDX 组件化,styled-components 突破"纯 CSS 主题"的表达上限。
- **共性优势**:主题是"参数 + 层叠规则"而非整篇样式文本,用户可变量级微调、程序可机器读取。leo 的 137 份 brief 是整篇 markdown(JSON 风格块嵌入),变量级操作仅 brands/ VI 与 social-card 8 token 两处局部存在。

### 2. 预览与可发现性(视觉驱动的风格选择)

- **xiaohu**:`templates/gallery.html` 浏览器画廊,用**用户真实文章**在 34 个精选主题下实时渲染预览,现场调字号字体后选定。
- **guizang**:`assets/screenshot-backgrounds/`(style-a/style-b 九张成品底图)+ `references/` 内嵌成品参照,风格选择以成品图驱动。
- **RedInk(5.5k)/xhs-visual-director(1.3k)**:样图先行——RedInk 大纲逐页可编辑后先出封面;xhs-visual-director 强制"1 张视觉确认图→用户确认→整套",确认图必须接近最终视觉而非线框。
- **共性优势**:选风格时看到的是**渲染结果**而非文字描述。leo 目前 `samples/style-gallery.md` 为目录级表格(风格名+适用场景摘句),无任何视觉呈现。

### 3. 文字渲染保真与图上排版

- **RedInk**:文字精准 = 模型选型(Nano Banana Pro)+ 提示词工程("文字清晰可读、重要信息突出"),无独立渲染层;多页一致性靠**封面参考图链**(`services/image.py`:封面先行→压缩至 200KB→每个内容页生成时作为 reference_image 传入)。
- **guizang**:`references/image-overlay.md` 是赛道最完整的**图上文字合成协议**——安静区测试(≥30% 画布低细节带)、光感测试、无蒙版优先、失败才允许局部图像色调蒙版(radial 限定标题区、取图内色调、峰值 alpha 0.15-0.30)、360px 缩略图终检、多模态主体映射(读图标注人脸/主体位置记为 HTML 注释,文字只进安全区)、逐图 `object-position` 纪律。
- **guizang 截图处理**(`screenshot-treatment.md`):`.frame-shot` 组件六参数(比例 7 档/圆角/阴影/背景/inset/device 包装),正交纪律(禁透视倾斜除非明确要求)。
- **与 leo 对照**:leo 的确定性文字保真(TF-2 overlay_text、render lane HTML/mermaid 逐字保真、check_table_values 机读比对)在"正确性合同"维度**领先全赛道**;但**图像 lane 全出血/大图井页面的图上排版协议缺失**——visual-qa 的对比度判据针对浅底纯色,不覆盖图上文字。

### 4. 模板化批量与多页一致性

- **xhs-visual-director**:**母版锁定前缀**(master lock prefix)——每页提示词开头逐字复制一段固定文本,锁画布/边距/字体系统/页码位/色 token/圆角/线重/图标风格;每条提示词显式写 `1080x1440px, strict 3:4` + 负面提示词(square/landscape/inconsistent margins)。统一视觉母版是**字段化的硬约束**(画布/安全边距/网格/标题区百分比/色彩令牌/组件语言/节奏规则),不是总说明。
- **guizang**:28 版式骨架 + 10 主题预设 + 双模板种子文件(template-editorial/swiss-card.html),单 HTML 多 `.poster` 节 + Playwright 逐节截图,R1-R9 机读验收。
- **RedInk**:15 路并发(ThreadPoolExecutor + rate limimiter + provider 策略 worker_count)、单页手动重试不自动重试。
- **共性优势**:多页一致性 = 固定件逐页重复(前缀/母版/模板)+ 机读验收。leo 的 style render --anchor(HEX/字族/渲染锚逐字节注入)同构,但锚的是**静态属性**而非**版式系统**(网格/边距/页码位/组件语言);版式骨架(36 版式 CSS 方言)仅可编辑路线原生消费,图像路线靠 --materialize 降译。

### 5. 编辑器架构与生态

- **poster-design(4.8k)**:原生 DOM 画布(非 canvas)、元素组合/对齐分布、PSD 导入辅助生成模板、Puppeteer/Html2canvas 混合出图、AI 抠图带画笔修补。
- **md 主题市场**:`InstalledMarketplaceTheme`(本地安装 + 云同步)、discover/myItems/pending(投稿+管理审核)、`themeExporter` 导出合并主题;另有自定义组件(customComponent + 市场组件)。
- **markdown-nice**:主题投稿共享生态;**html-anything(8.6k)**:75 个 skill 模板 × 9 种交付面,juice 内联 CSS 一键贴公众号、2× PNG 直进推文。
- **共性优势**:用户侧扩展通道 = 模板(空表单 + 合格判断)→ 投稿/导入 → 安装即用。xhs-visual-director 的 `style_extension_template.md` 是轻量版同思路:新增风格空模板 + 合格判断清单(可区分性/负面提示词/可复制构图规则)。

---

## 二、重点项目深读纪要

### 1. md(doocs,13.3k)——主题系统架构基准

`packages/core/src/theme/` 七文件分工:cssVariables(参数→CSS 变量)、themeApplicator(五层合并:变量/base/主题/标题预设/自定义 CSS)、cssProcessor(运行时 var()/calc() 解析,不依赖 PostCSS)、cssScopeWrapper(#output 作用域隔离)、themeInjector、themeExporter(合并主题导出)。市场主题 `themeCSS` 与内置主题同通道:marketplace 主题叠在 default base 之上(`resolveThemeCSS`)。web 端 `PerThemeSettingsMap` 按主题名存参数快照。**借鉴核心**:主题=参数面+层叠;参数按主题隔离;第三方主题与内置同通道、同基座。

### 2. guizang-social-card-skill(6.7k)——设计体系与验收工程

SKILL.md 336 行 + 16 份 references。 leo 已吸收其画板/密度/字号/分页/8 token/R1-R9(social-card-specs.md);**未吸收部分**:(a) image-overlay.md 图上文字合成协议(四步阶梯:选图→无蒙版→局部色调蒙版→缩略图终检 + 主体映射);(b) screenshot-treatment.md frame-shot 六参数组件与正交纪律;(c) background-systems.md 3-5 层背景层模型(spec 仅一句话吸收);(d) live-photo-production.md 动态卡全链路(首帧预览→MOV→.pvt→contact sheet 检查);(e) 交付节奏"先看后验"(先出图再问要不要跑 validator);(f) web 图源五级优先级 + SOURCES.md 溯源(leo 有 sources-manifest 同构,渠道策略未吸收)。

### 3. xhs-visual-director-skill(1.3k)——视觉导演模式

559 行 SKILL + 8 docs + 7 templates。核心资产:24 风格库(每风格:适合/不适合内容、视觉气质、配色、字体、构图百分比、常用元素、正/负面提示词模板、示例标题类型)、内容类型→风格映射表 + **风格组合机制**(封面更冲击/内页更理性/主辅风格搭配)、统一视觉母版字段 + 母版锁定前缀、单页提示词结构(沿用元素 vs 本页变化分栏)、style_extension_template(新增风格空模板+合格判断)、苏格拉底 10 问、视觉确认图协议。**与 leo 母版"视觉行"对照**:leo 视觉行是内容真值(容器清单+落位+图像来源三级),xhs 母版是**视觉系统真值**(网格/边距/token/组件语言/节奏规则)——leo 的 deck_spec.style 承载部分,但无逐页重复的"系统锁定"机制(anchor 只锚静态属性)。

### 4. RedInk(5.5k)——批量生成与文字保真的工程取舍

Flask+Vue3,Docker 一键起。链路:文本模型出大纲(`<page>` 分隔、页型标记)→ 封面先行 → 内容页 15 路并发,每页把**封面压缩图 + 用户参考图**作为 reference_images 传入 generator(`services/image.py`);provider 策略层(worker_count/间隔限流)可配置;短 prompt 模式开关。文字保真完全押注模型能力(Nano Banana Pro),无确定性兜底。**对 leo 的启示有限**:leo 的样张参考已系统化(slide-worker.md:"approved sample slide style reference; match style only, do not copy layout")且确定性文字保真更严谨;参考图压缩(200KB)是唯一可拾取的工程细节。

---

## 三、借鉴点清单

| # | 来源项目+机制 | leo 现状 | 建议 | 价值论证 | 优先级 | 验证方式 |
|---|---|---|---|---|---|---|
| V1 | guizang image-overlay.md:图上文字四步协议(安静区/光测试→无蒙版→局部图像色调蒙版→360px 缩略图终检)+ 多模态主体映射 + object-position 纪律 | 无:visual-qa 对比度判据仅覆盖纯色浅底;generate 全出血封面/大图井页面无图上排版规则 | 新增 references/image-text-composition.md(判定式抽取,同 social-card-specs 先例),全出血/大图井版式引用其判据;visual-qa 增"图上文字"检查行 | 图像 lane 废片主因之一是图上文字不可读/压主体;协议把"蒙版补丁"改为"选图与构图前置决策",直接降返工率 | P0 | 新增 eval case(全出血封面含标题→判安静区/蒙版合规);visual-qa 判据表增行;母版视觉行增"主体映射"字段 |
| V2 | xhs-visual-director:每风格必配负面提示词 + master lock 负面清单(no square/landscape/inconsistent margins) | 部分:brief 的 color_palette.rule 有散点 avoid,无系统化 negative_prompt 字段;style render 无负面注入 | brief schema 增可选 negative_prompt 字段(反模式铁律已有素材:00_索引/通用设计规范.md),style render 并入注入链,lint_style_briefs 增字段校验(存量白名单) | 扩散模型对"不要什么"比对"要什么"更敏感;负面提示词是同类 skill 标配,成本极低 | P1 | lint 双跑;prepare_slide_prompts 输出 diff 断言;eval 废片率对比一轮 |
| V3 | xiaohu gallery.html(真实内容实时预览)+ guizang screenshot-backgrounds 成品图库 | 部分:style-gallery.md 目录级表格(P1 曾以"图像 API 成本与确定性不成立"搁置);M1 渲染 lane 已合入(render page --size 确定性、零 token) | 为 11 套内置风格生成确定性缩略图:render page + 每风格固定示例数据 + 代表版式,产 `<风格>.thumb.png` 入 samples/,style-gallery.md 嵌图;126 参考风格维持目录级 | 搁置理由已被 M1 消解(确定性渲染、无 API 成本);11 风格×1 模板成本可控;视觉预览是选风格的最大效率杠杆 | P1 | generate_style_gallery.py 产图;双跑 sha256 一致(HTML lane 按像素容差);--check 防漂移 |
| V4 | md 七参数 CSS 变量 + PerThemeSettings 按主题隔离;xiaohu 85 套 JSON 主题 | 部分:layouts.json sidecar 先例 + social-card 8 token + brands/ VI;137 brief 主体是整篇 markdown,无变量级操作面 | brief 增可选 theme-token sidecar(palette/typography/density 键名对齐 social-card 8 token 扩展),style render 支持 --var key=value 覆盖并复用对比度硬校验 | 用户微调(换个主色/字号)不必改整篇 brief;机器可读 token 为缩略图(V3)、暗场推导、图表色映射提供统一输入 | P1 | render 字节断言(不带 --var 输出不变);brand_contrast_insufficient 复测;lint 增 sidecar 校验 |
| V5 | guizang 28 版式骨架双模板 + html-anything 75 模板面 | 部分:版式库 36 版式是 CSS 方言骨架(可编辑路线消费),render-templates 仅 body-basic/cover-basic 两个 | 渲染模板扩面:把正确性敏感高频版式(P25 规格表/时间线/对比/大引语/四横带台账)逐批 HTML 化,复用 lint_render_templates 六条合同与 data-leo-block 锚点 | 扩大确定性渲染接管面 = 扩大"逐字保真零 token"覆盖;表格/台账恰是图像 lane 最易出错页型 | P1 | lint_render_templates 过;render page 双跑像素 diff;eval 对照图像 lane 同版式废片率 |
| V6 | xhs-visual-director style_extension_template:新增风格空模板 + 合格判断清单 | 部分:save_style 从成品提取沉淀用户风格;手工新增风格无模板引导与验收门 | 新增风格扩展模板(风格定义/视觉系统/负面提示词/构图规则/与既有库区分性),save_style 与手工新增统一过该模板;校验并入 check 类脚本 | 137 静态 brief 的用户侧扩展通道只有"成品反推"一条;模板化降低新增门槛且守住 lint 质量 | P2 | 模板落 references;eval case(用户给新风格描述→按模板产出并通过 lint) |
| V7 | xhs-visual-director 风格组合机制:封面更冲击/内页更理性/主辅风格 | 无:风格路由推荐单风格,一套 deck 一个风格合同 | style-recommendation 候选呈现增"结构页/内容页/结尾页辅助风格"可选档(默认关,呈现时一句话说明) | 发布会/路演 deck 封面与内页气质分化是真实需求;leo 已有全部素材(11 内置+126 参考),只缺组合推荐逻辑 | P2 | eval case(科技发布场景→封面/内页分角色推荐);deck_spec 增可选 per-role style 字段 |
| V8 | xhs-visual-director 母版锁定前缀:网格/安全边距/页码位/组件语言/节奏规则逐页重复 | 部分:--anchor 锚 HEX/字族/渲染锚;composition_hint 译 vw→百分比但无系统级锁定 | anchor 增可选版式锚(网格 token/安全边距/页码位/圆角线重),默认输出字节不变,开启后逐页注入 | 静态属性锚管"颜色字体不漂",版式锚管"网格页码不漂"——后者是组装复验页脚一致性的 prompt 侧前置 | P2 | render 默认字节断言不回归;开启后 eval 多页页码/边距一致性判据 |
| V9 | guizang screenshot-treatment:frame-shot 六参数组件 + device 包装 + 正交纪律 | 无:学术图证据(academic-figure-evidence)管证据纪律,不管截图呈现组件 | render-templates 增 frame-shot 组件模板(比例/圆角/阴影/背景/内边距参数化),证据截图页优先路由渲染 lane | 截图页(Demo/数据看板/代码证据)是图像 lane 另一高废片页型;确定性组件一次建设多风格复用 | P2 | 模板过 lint;eval 截图页走渲染 lane 的路由判定 |
| V10 | md marketplace 安装/导出 + markdown-nice 主题投稿 | 部分:用户风格仅本地 `${LEO_PPT_HOME}/styles/` markdown,无导入导出格式 | 定义风格包目录约定(brief + token sidecar + 缩略图 + 样张)与导入校验(过四条治理 lint 后入位),不做中心化市场 | 用户在机器/团队间迁移风格、社区分享风格包,是 137 静态库之外的低成本生态位 | P2 | 导入 lint 单测;eval case(导入含漂移风格包→拒收并报错) |

## 四、明确排除项及理由

**已被 M1/先前批次吸收(禁止重复立项)**:

1. guizang 画板规格/密度 4 横带/字号带宽/分页压缩阶梯/8 主题 token/R1-R9 测量质检——已在 `social-card-specs.md` + `validate_visual_measure.py`。
2. 社交卡片输出形态(3:4/1:1/21:9 + 封面对)——第二阶段路线图已定,M1 落地。
3. 风格画廊目录级——P1-D 已做;V3 是其缩略图增强,非重复。
4. 渲染 lane 本体(HTML/mermaid 确定性渲染、ready 信号、字体 HTTP、SVG 栅格化、mermaid themeVariables 映射)——M1 已合入,本报告只提议"扩面"(V5)。
5. guizang background-systems 3-5 层背景——spec 第五节已一句话吸收;HTML 实现归入 V5 模板扩面执行细节,不单列。
6. web 图源五级优先级 + SOURCES.md——leo 的 sources-manifest/validate_assets 同构且更严(校验+阻断),渠道策略属社交卡片批次范畴。

**机制不匹配或 leo 已更优**:

7. RedInk 封面参考图链——leo slide-worker 已有样张参考("match style only, do not copy layout")且合同更细;仅参考图压缩至 200KB 属微优化,不立项。
8. RedInk/文生图文字保真路线——leo 的 TF-2 overlay + render lane 逐字保真 + check_table_values 机读比对在正确性维度全面更优,反向不借鉴。
9. poster-design 编辑器架构(DOM 画布/图层/PSD 导入)——leo direct-editable 是 PPTX 对象级重建,非画布编辑器;模板库思想已由版式库+render-templates 承接。
10. guizang Live Photo 动态卡(.pvt/MOV)——PPTX 交付场景外;若未来做"社交卡片批"再评估(授权已确认)。
11. guizang"先看后验"交付节奏——与 leo QA 合同/DELIVERY-GATE 冲突(leo 要求验证分报告前置),哲学差异不采纳。
12. md 图床/AI 助手/多端形态、wenyan 发布 API、md2wechat 草稿箱、wechat 系外链转脚注——发布分发与公众号特化场景,非视觉系统范畴。
13. html-anything juice 内联/2× PNG 导出——面向公众号粘贴与推文编辑器,PPTX 组装链路不需要。
14. ian-xiaohei-illustrations IP 吉祥物插画——是风格库选题候选(IP 角色参与核心动作的构思纪律可参考),非系统机制,不占本轮条目;可在风格库扩批时作为 brief 选题。

**债务提醒(known-issues.md 2026-08-31 M1 批)**:M1 新能力失败主因是"SKILL.md 入口可见性缺口"。上表任何落地条目必须同步把入口行写进 SKILL.md 按需读取表/相关章节,并按 M0.1 协议校准 judge 词表,否则重蹈 19 case 团灭。
