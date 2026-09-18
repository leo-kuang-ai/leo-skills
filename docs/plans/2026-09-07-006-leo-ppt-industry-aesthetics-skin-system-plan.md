# leo-ppt-generator 审美分层与行业皮肤体系优化方案

> **当前状态：superseded，历史参考。** 2026-09-08 起，本方案的主题、字体、图表、容量、溯源和行业视觉验收设计已并入 [PPT 模板系统全量重构与生成质量优化技术方案](2026-09-08-001-feat-leo-ppt-template-quality-plan.md)（当前 v4，行业方案逐节处置见主方案附录）。后者是当前唯一实施入口；以下正文保留历史论证，其中兼容迁移、阶段门禁和未定位模板的处理不再约束新方案。尚未实施。

> 编号:2026-09-07-006 · 历史版本:提案·v3(技术合同已修订,未实施;历史模板迁移受基线条件约束)
> 修订记录:v1(2026-09-07)初稿;v2(2026-09-08)新增三域模版管理审计与 M0 重构设计;v3(2026-09-08)按源码审查修订主题消费、容量、基线、质检、路由、溯源和行业验收合同。
> 触发:SDLC 分享 deck 实战(图像 lane 三轮返工不收敛 → 用户指令切换确定性渲染 lane → 自建 blueprint/doodle 两套一次性皮肤)+ 用户需求"生成 PPT 要具备各行业、各类型的美学审美"。
> 方法:业界调研(§2)+ 现状审计(§1,含结构化审计 §1.4)+ 模拟专家圆桌(§3,**合成的多视角批判分析,非真实会议**,每条结论标注依据来源)+ 综合方案(§4–§8)。

**目标与推荐路径**:保留精选行业皮肤方向,扩展现有渲染入口,连接“风格选择 → 有效主题 → 页面/图表 → 容量与质检 → 产物溯源”。先完成七个在库模板的兼容迁移和反例验证,再扩八个行业种子;不以批量加色板代替行业适配。

**本轮边界**:只修订本文及变更记录,不修改运行时、模板、其他计划或执行外部出图。保留既有用户选择与样张合同;不新增用户确认门。以下技术选择由模型在用户“修复方案”的授权范围内提出,不记录为人工逐项验收。

**实施条件**:M0a 可从当前七个模板建立基线;blueprint/doodle 与 SDLC r3/r4 的原始路径、数据和环境尚未定位,只阻塞 M0b 历史迁移与历史等价声明。本文不宣称整个计划已经达到无条件实施就绪。

---

## 1. 问题定义与现状审计

### 1.1 核心命题

"具备各行业、各类型 PPT 的美学审美"拆解为三个可工程化的子问题:

1. **审美知识的覆盖**——系统是否"知道"每个行业/场合的正确审美?(知识层)
2. **审美决策的路由**——给定受众/场景,能否选对审美方向并解释理由?(决策层)
3. **审美执行的保真**——选定的审美能否稳定落到每一页,不漂移、不翻车?(执行层)

### 1.2 现状审计(历史观察与 2026-09-08 源码复核分列)

| 层 | 资产 | 覆盖 | 缺口 |
| --- | --- | --- | --- |
| 知识层 | 历史盘点 **318 份 brief**、8 大主家族;原分类分项不能加总为 318,本轮未重做全量盘点 | 历史风格路由报告为机制证据,005 本身仍是未执行的内容测评方案 | 部分 brief 含 token_sidecar,但缺到渲染主题的正式转换合同;实施时按 generated counts 与源文件重新盘点 |
| 决策层 | 风格路由表 + `style_hard_rules.py` 硬规则 + 归因推荐(AE1) | 已运行 | 路由终点仍是图像 lane 的 brief,渲染 lane 无对应终点 |
| 执行层 | 当前源码含 **7 个内置模板**;blueprint/doodle 是历史实战记录,未在当前仓库定位 | 七个模板均未消费 `__LEO_THEME_VARIABLES__`;CLI 能传参不等于模板已支持换肤 | 审美描述到 HTML/CSS、Mermaid 的转换及消费链未闭合;历史实战的返工次数和文字保真结论尚不能在本仓复现 |

### 1.3 实战教训清单(本方案的直接输入)

来自原方案记录的 SDLC deck 生成全过程(图像 lane r1/r2 与渲染 lane r3/r4)。以下为待补原始证据的历史观察,不是本轮重跑结果;不作为一般模型能力或全部模板行为的证明:

- 图像模型对长 prompt 的风格执行是**统计倾向**而非合同:同一 prompt 三次重试,英文残留/水印/计数漂移反复出现且不可通过负面词收敛(点名禁词反而被渲染)。
- 渲染 lane 的审美是**构造性合同**:文字逐字、色彩精确、装饰确定;但每套皮肤是 600 行手写 HTML,视觉系统与版式骨架耦合,加风格=重写模板。
- 质检判据本身携带风格假设:`visual_qa.py` 的 BLANK-01(内容比≥15%)与 SIZE-01(≥200KB)按"扩散模型噪点图"校准——深底细线稿与纯色矢量都会误伤,调色以过判据为目标偏离了审美本体(应反向:判据按风格档位参数化)。
- 中文字体单一(离线仅 Noto Sans SC),"手写感"只能靠线条抖动模拟——字体气质是行业审美的硬缺口。

### 1.4 模版管理结构化审计(v2 新增)

三域资产按"分类本体 / schema / 机器真值 / lint 门禁 / 准入纪律"五维评估:

| 维度 | 风格库(历史 318 brief) | 版式库(以当前 sidecar 为准) | 渲染模板(当前 7 个) |
| --- | --- | --- | --- |
| 分类本体 | ✅ 目录即轴(通用母版/行业域/场景用途/来源) | ✅ page_type 六值枚举 + P 码封闭集 | ✅ 模板 id 封闭目录 |
| schema | ✅ style-brief-v1 + metadata 封闭字段 | ✅ .layouts.json sidecar(容量真值) | ⚠️ 基础文本合同与运行时溢出哨兵已存在,无 theme schema |
| 机器索引 | ✅ generated/ 名称别名/家族/counts/分面 | ✅ suggest_layout 角色映射封闭词表 | —(目录即全集) |
| lint 门禁 | ✅ lint_style_briefs + 金样板回归 + 家族盘点 + 基线白名单 | ✅ lint_layout_grid + check_layout_reuse | ✅ lint_render_templates(ERROR=0 实测) |
| 准入纪律 | ✅ 渐进债登记在案 | ✅ sidecar 必须、不得先入库后补门禁 | ✅ 模板 lint、运行时检查与 provenance sidecar;不等于视觉准入 |

**结构缺口登记(按影响排序)**:

- **G1(本方案主目标)**:皮肤层无 schema——`render page --theme-file` 与 brief `token_sidecar` 已存在,但前者只注入全局变量,后者主要服务 prompt 组合。缺口同时包括 schema、表示转换、模板实际消费和准入门禁,不是仅增加一份 JSON schema。
- **G2(渐进债,登记未收敛)**:约 126 份早期 brief negative_prompt 不足 3 条;约 40 组口语别名跨风格冲突(靠路由规则消歧);10 个疑似同族簇未做 R-66 合并。结构化是"有账、在还",不阻塞本方案。
- **G3(历史反例,待补证)**:blueprint/doodle 的耦合观察保留为迁移线索,在 M0b 定位源文件后逐项确认。当前七个模板的硬编码颜色与字体可直接从源码复核,由 M0a 处理。

### 1.5 当前证据与限制

本轮依据 2026-09-08 工作树源码;工作树含其他会话未提交改动,不以历史 CHANGELOG 声明替代当前文件。以下路径均相对仓库根目录。

| 证据 | 已确认事实 | 对方案的约束 |
| --- | --- | --- |
| `leo-ppt-generator/runtime/src/leo_ppt_generator/render/page.py`、`leo-ppt-generator/runtime/src/leo_ppt_generator/cli.py`、`leo-ppt-generator/assets/render-templates/*.html` | 页面主题原样注入;7/7 模板未消费主题全局 | M0a 必须逐模板迁移,不能只扩 CLI |
| `leo-ppt-generator/runtime/src/leo_ppt_generator/render/chart.py` | `build_theme_variables` 只识别平铺色彩键;v2 嵌套示例产生空映射和默认主题警告 | 新 schema 必须先转换为图表适配输入 |
| `leo-ppt-generator/runtime/src/leo_ppt_generator/templates.py` | `_enforce_sidecar_contrast` 是覆盖操作门禁;未覆盖颜色不检查 | 只复用 WCAG 数学函数,不复用其调用范围作为完整主题门禁 |
| `leo-ppt-generator/scripts/check_deck_geometry.py` | 容量依赖槽位与字号;现预检不消费新 theme | 新主题必须解析出有效几何和字体再检查 |
| `leo-ppt-generator/runtime/src/leo_ppt_generator/render/page.py`、`leo-ppt-generator/runtime/src/leo_ppt_generator/render/provenance.py`、`leo-ppt-generator/runtime/src/leo_ppt_generator/render/receipt.py` | 单页收据未纳入有效主题/字体/装饰依赖;交付收据已有输入文件指纹机制 | 扩展现有溯源与失效检测,不另建状态机 |
| `python3 -B leo-ppt-generator/scripts/lint_render_templates.py` | 审查轮 7 templates, ERROR=0;只证明现合同 lint | 不能据此声明九模板在场或已具备换肤能力 |

原始 SDLC 资产不可复现、外部统计未逐条核验、行业视觉效果未出图验证。§2 是设计参考,§3 是合成分析;最终工程决策以 §4–§8 为准。

---

## 2. 业界研究(参考假设,不直接作为硬规则)

原方案收录的外部链接本轮未逐篇核验。下文仅保留可供设计探索的原则;产品模板数量、医疗样本比例、文化色义等不能直接外推为行业能力或强制禁色规则。行业合规来自具体任务及既有 content_rules,不从审美文章推导。

### 2.1 AI 演示产品的审美体系

- **Gamma**:官方模板库 100+ 精选模板,按 Company/Consulting/Creative/Education/Fundraising/Marketing 分类;核心是 **AI 主题系统而非刚性模板**——主题=字体+色彩+版式美学的组合,自动适配内容(来源:[Gamma Templates](https://gamma.app/templates)、[官方指南](https://gamma.app/explore/content/guides/the-complete-guide-to-presentation-templates-with-ai)、[24Slides 评测](https://24slides.com/presentbetter/gamma-app-review))。第三方宣传的"1000+/20 万模板"是社区库口径——**业界头部产品的审美中枢是百级精选而非万级堆量**,且"主题自适应内容"是其关键差异点。
- 启示:我们的"皮肤"应走 Gamma 式**精选+可组合**,而非把 318 份 brief 全量投影。

### 2.2 多主题/多品牌 token 架构(工程范式)

业界成熟做法是**三层 token**([Material Design 3 token 分类](https://m3.material.io/foundations/design-tokens)、[zeroheight 多品牌架构](https://zeroheight.com/learn/multi-brand-multi-product-and-white-label-token-architecture/)、[Design Systems Collective](https://www.designsystemscollective.com/choosing-the-right-architecture-for-your-multi-brand-design-system-ff8195cba088)、[Style Dictionary 工作流](https://alwaystwisted.com/articles/a-design-tokens-workflow-part-9.html)):

1. **primitive/global**——原始值(`#0F1B33`、`16px`、`700`);
2. **semantic/alias**——语义角色(`bg-canvas`、`text-primary`、`accent-singular`);
3. **component**——组件槽(`card.surface`、`title.size-tier`)。

颜色与视觉角色差异可留在 token 层,通过 CSS 自定义属性切换。字体度量、密度和组件结构仍需明确兼容与容量边界,不能从这套范式推出“任意皮肤适配任意骨架”。

### 2.3 咨询业演示美学(结构美学的标杆)

顶级咨询公司的幻灯片标准(来源:[Deckary 咨询标准](https://deckary.com/blog/consulting-slide-standards)、[Perceptis](https://perceptis.ai/blog/how-to-create-a-slide-like-mckinsey-or-bcg)、[SlideModel](https://slidemodel.com/mckinsey-presentation-structure/)):

- **行动标题(action title)**:标题必须是完整句结论("so-what"),不是话题词——本仓"结论先行金字塔"模式已对齐;
- **金字塔原理 + MECE** 自上而下论证;
- 严格对齐网格、克制的字重阶梯、密而可扫读的信息密度;BCG 比 McKinsey 单页更密([Poesius 对比](https://poesius.com/blog/consulting-slide-design-mckinsey-bcg-bain-guide))。
- 启示:咨询审美的"美"很大部分是**结构纪律**,本仓母版层已具备,渲染皮肤只需承载其版面气质(细线网格/衬线标题/双栏密度)。

### 2.4 行业色彩/字体惯例与跨文化语义

- **金融**:蓝与蓝灰可作为稳定、克制的初始设计方向,但不使用未核验的“85% 信任联想”支撑推荐;深绿等品牌方案同样进入样张验证(来源:[The Slide House](https://theslidehouse.com/color-palettes-for-business-presentations-2026/)、[eWeek](https://eweek.wfglobal.org/weekly/best-practices-typography-color-investor-presentations-158055))。
- **医疗**:优先清晰字号、对比和信息层次;门诊字体研究的样本及适用范围未核验,不将其比例推广到医院汇报或生物路演(来源:[ResearchGate 门诊研究](https://www.researchgate.net/publication/244879477_Evaluating_patient_choice_of_typeface_style_and_font_size_for_written_health_information_in_an_outpatient_setting))。WCAG 阈值在本方案中是可读性工程基线;FDA 等监管要求只在具体内容适用时沿用业务规则。
- **教育/创意**:允许探索更暖或更有个性的视觉,保守度由受众和场合决定,不将行业名直接等同固定审美(来源:[Piktochart](https://piktochart.com/blog/fonts-and-colors/))。
- **字体气质**:衬线=传统权威(法律/金融/保险),无衬线=现代亲和(科技/医疗/教育)(来源:[Adobe 字体心理](https://www.adobe.com/express/learn/blog/psychology-font)、[Figma](https://www.figma.com/resource-library/professional-fonts/))。
- **跨文化**:红、紫等色彩的语义受地区、品牌与图表惯例共同影响。将来源线索作为条件提示,不推出“金融禁红”或“东亚禁紫”;涉及涨跌时由任务明确符号、图例和地区口径(来源:[Eriksen](https://eriksen.com/marketing/color_culture/)、[BINUS](https://international.binus.ac.id/graphic-design/2022/06/01/color-symbolism-psychology-across-cultures/)、[ResearchGate 信任研究](https://www.researchgate.net/publication/334550253_Trustworthy_Blue_or_Untrustworthy_Red_The_Influence_of_Colors_on_Trust)、[Academia 跨文化研究](https://www.academia.edu/6647564/Colours_Across_Cultures_Translating_Colours_in_Interactive_Marketing_Communications))。
- 通用原则:克制色板、一个主导色、少量中性支撑、标题与数据标签高对比(来源:[NEN 对比指南](https://www.nen.wfglobal.org/digest/presentation-design-color-contrast-typography-pitch-deck-958075)、[Deckary](https://deckary.com/blog/pillar-powerpoint-design-guide))。

### 2.5 本仓既有基础

- 005 方案已定义 20 行业 × 场景内容质量评测矩阵与五维判据,但尚未执行且截断在样张前;本方案复用其行业与任务定义,新增独立视觉阶段;
- 风格库 token_sidecar 已提供 palette/typography/density/layout 等信息;`style render --var` 支持既有键覆盖。它不是可直接执行的渲染主题,表示转换、全量对比度检查与选择绑定由 §4 定义。

---

## 3. 模拟专家圆桌(合成多视角批判分析)

> **诚实声明**:以下七位"专家"是基于 §2 研究与工程实践的**合成视角**,用于强迫方案接受不同学科立场的批判;非真实人物会议。每位给出:对现状的批判 → 审美原则 → 可机检判据/工程要求。

### 3.1 版式与网格专家(瑞士学派立场)

- **批判**:doodle/blueprint 的卡片是"居中堆叠+倾斜",没有真正的**网格纪律**——12 栏栅格、基线对齐、留白节奏才是专业感的来源;倾斜贴纸是风格选择,但**倾斜内部的文字仍须严格对齐**。当前模板的 tilt 是整卡 transform,可接受,但间距靠手调 magic number,换内容就失衡。
- **原则**:任何皮肤必须声明网格(栏数/槽宽/边距);装饰自由度只在"外框层",内容层永远对齐。
- **工程要求**:theme 引用版式 profile,有效网格仍由版式 sidecar 管理;R-31 的五个字符串锚需要显式转换,不能视为可直接执行的几何数据。

### 3.2 字体排印专家(中西混排立场)

- **批判**:全套 deck 只有 Noto Sans SC 一个家族,字体气质维度为零——"政务红金稳重"和"科技暗色"用同一副字,行业审美先输一半。且中文字重在 700/400 之外没有中间档,标题"越粗越好"是新手病。
- **原则**:**字体气质 = 行业审美的第一信号**(衬线=权威、几何无衬线=科技、圆体=亲和、仿宋=公文);中文字号阶梯要离散(版心 Canon 已有,执行层要接);中西混排必须自动加空隙。
- **工程要求**:扩充离线字体矩阵,每个实际 family/weight 绑定包内字体文件与许可证;theme 用可解析字体角色引用,不用 `family_tier` 自然语言直接驱动渲染。字体改变必须重新检查容量。

### 3.3 色彩与品牌 VI 专家

- **批判**:原实战记录中的“琥珀唯一强调”提示计数纪律可能脆弱,但仍待基线复核。色彩系统应采用角色制,由任务确定主色、辅色、中性、警示与强调的用途;文化提示需要具体地区与用途证据,不能以国家或行业名称推出禁色结论。
- **原则**:每主题声明 5–7 个**语义色角色**+使用规则(哪些角色允许重复出现、哪些唯一);对比度(WCAG 4.5:1/3:1)按角色硬校验;跨文化红/紫/白/绿语义表进决策依据。
- **工程要求**:theme 的 palette 按角色键组织;复用 WCAG 比值计算函数,新增按实际组件槽位逐对检查的主题门禁,不继承 `--var` 仅检查修改键的范围。

### 3.4 数据可视化专家(Tufte 立场)

- **批判**:行业审美在数据页最容易失真,需要明确数值、单位、比较尺度和图表类型对应的基线规则。当前七个内置页面模板有 spec-table,另有 Mermaid 图表入口;本方案扩展这些确定性路径,不从单次图像实战推导其他技术路线一概不可用。
- **原则**:数据组件家族(KPI 卡/表格/条形/趋势/瀑布/矩阵)按行业密度档提供;每类组件绑定图表语法规范(本仓 11_图表语法 + 图表样式规范已有判据,缺渲染侧组件)。
- **工程要求**:M2 按真实数据任务扩 KPI/矩阵组件,条形与趋势优先复用 Mermaid,保持图表语法权威。ECharts 作为后续能力候选,不计入本轮范围或验收。

### 3.5 认知心理学专家(受众立场)

- **批判**:"行业审美"本质是**受众预期管理**:给工程师看商务蓝会睡着,给监管看荧光黄会减分。当前风格路由以"场景"为键,但真正的主变量是**受众保守度 + 投屏环境**——同一行业,内部白板会与对外发布会是两个审美档。此外认知负荷判据(要点≤3、双线索编码)在母版层有了,视觉层没有对应物(如"强调元素数量"就影响扫读)。
- **原则**:审美路由键 = 行业 × 受众保守度 × 场合正式度 × 投屏环境(亮/暗)——四键决定"皮肤气质档",而非直达具体风格。
- **工程要求**:路由表升级为四键矩阵(风格路由表已有受众保守度轴,补投屏环境轴);亮环境默认 light 档皮肤。

### 3.6 行业资深顾问(金融/政务/医疗/教育/科技,综合立场)

- **批判**:每个行业的"美"由**惯例+合规**共同定义:金融的要害是稳重与精确(蓝灰、细网格、数字右对齐、单位齐全);政务是庄重与规范(红金、对称、仿宋标题、密级与文号版式——受 content_rules 监管);医疗是干净与可信(白底蓝绿、无装饰线、大字号);教育是清晰与节奏(高明度、图示多、每页一个概念);科技是锐度与未来感(暗底、电光强调、等宽点缀)。**这些一半是视觉,一半是结构纪律**——只调色不调密度与版式的"换肤"会立刻露馅。
- **原则**:行业皮肤=视觉气质+信息密度+组件偏好三件套,不能只卖色板。
- **工程要求**:皮肤 schema 必须含 `density_tier`(对齐禅档位)与 `preferred_components`(如金融偏好 spec-table+KPI、教育偏好 timeline+三卡)。

### 3.7 AI 产品工程师(可行性立场)

- **批判**:方案最大风险是"皮肤工厂"失控——318 份 brief 全投影=318 套待维护资产,违背 Gamma 百级精选的业界经验。第二风险是质检判据与风格档耦合(BLANK-01/SIZE-01 教训),皮肤化之后必须同步把判据参数化,否则每套皮肤都要为过门禁"加噪点"。第三,审美质量没有自动裁判,金样板像素基线只能防回归,不能防丑。
- **原则**:皮肤走**精选路线**(8–12 个逻辑皮肤,明暗变体分别验证);皮肤引用经缺陷样本校准的质检档,不能自行降低放行阈值。审美验收靠金样板与行业样张评审,不承诺自动审美分。
- **工程要求**:见 §6 路线图与 §7 风险表。

### 3.8 圆桌收敛(七视角交集)

1. 审美=**知识(角色化色彩/字体气质/密度)× 决策(四键路由)× 执行(token 化皮肤)**,三层都要动;
2. **视觉 token 与骨架解耦**,字体及几何变化显式参与容量,皮肤走精选;
3. 判据**按受治理档位参数化**,颜色角色检查与内容完整性门禁不由皮肤放宽;
4. 行业皮肤是**视觉+密度+组件**三件套;
5. 字体矩阵与跨文化色义是两个被低估的硬缺口。

---

## 4. 目标架构与技术决策

采用 **extend + compose**:扩展现有 `render page/chart`、容量检查和收据;新增的主题模块只负责 schema 校验、解析和表示转换,不接管风格排名、内容规则或运行状态。新资产均归 `leo-ppt-generator/` 所有,不依赖兄弟技能。

```text
内容合同 + 风格选择指纹
  → 合格皮肤/明暗变体 + 逐页模板/版式选择
  → 有效主题(原始皮肤 + 已记录覆盖 + 实际字体/版式依赖)
      → HTML CSS/字体/装饰注入 → 内容与溢出检查 → PNG
      → Mermaid 角色适配 → SVG → HTML 数据槽或 PNG
  → 主题对比度 + 受治理 QA 档 + 行业样张验证
  → 单页输入指纹 + run 内依赖快照 + 交付收据
```

### 4.1 皮肤 schema 与唯一权威

新增 `leo-ppt-generator/runtime/src/leo_ppt_generator/schemas/render-theme-v1.schema.json` 与 `leo-ppt-generator/runtime/src/leo_ppt_generator/render/theme.py`;皮肤存放在 `leo-ppt-generator/assets/industry-skins/<skin_id>/<mode>.theme.json`。schema 使用版本和封闭字段,未知键、空对象、不可解析引用均拒绝;不把自然语言、任意 CSS 或外部 URL 当可执行 token。

三层 token 的最小实现是“原始色值/字体文件 → 语义角色 → 模板组件槽”。不新增通用 token 框架;组件槽的角色绑定由模板适配合同负责,皮肤不能删除必查槽位。

| 字段 | 约束与消费者 |
| --- | --- |
| `schema_version / skin_id / revision / mode` | 版本为 1;id 用 kebab-case;mode 为 light/dark;逻辑皮肤与明暗变体分开计数 |
| `industry / audience_conservatism / formality` | 仅提供推荐适用域;后两者使用 low/medium/high;不承载业务禁词或法定义务 |
| `compatible_templates` | 已逐个验证的模板 id 清单;准入以实际存在、消费测试和金样板为证,不以手填清单为证 |
| `palette` | 明确 primary/on_primary/accent/background/surface/text/muted/warn/border 和数据系列角色;色值为 HEX,透明度作为受限独立数值;角色可用用途由组件合同约束 |
| `typography` | title/body/label 各引用显式 family、weight、字体文件相对包路径;不写“serif-title”等抽象文本代替字体,不合成缺失字重 |
| `layout_profile` | 引用现有版式 sidecar 新增的具名 profile,按模板/variant 解析实际槽位、字号、行高、边距;不在 theme 重复保存第二份网格真值 |
| `shape / ornaments` | 只允许 schema 白名单参数和包内装饰 id;改变内容盒尺寸的边框/内距须进入几何 profile,不视为纯视觉 |
| `density_tier / preferred_components` | 密度为现有 zen 档位的确定映射;组件为已注册模板/组件 id;未实现项只能出现在候选说明,不得标记可执行 |
| `qa_profile` | 引用 `leo-ppt-generator/assets/render-qa-profiles.json` 中已校准档位的 id;主题不得自带数值门槛降低校验强度 |
| `provenance` | brief 的 scope/path/hash、投影器版本、逐字段来源类型(explicit/inferred/default)及准入证据相对路径 |

schema 将具体密度映射与 profile 引用校验固定在 M0a,先盘点当前档位再登记,不另造 `high-scannable` 等无法解析的执行枚举。上表是待实施合同,不是已有 schema 或可直接运行的皮肤文件。

金融种子的色彩起点使用 `primary=#1E3A8A / on_primary=#FFFFFF / accent=#0369A1 / background=#F8FAFC / surface=#FFFFFF / text=#1F2430 / muted=#475569 / warn=#92400E / border=#64748B`。它只是准入前输入,必须按 §4.4 全量校验;v2 的强调色 `#0EA5E9` 对背景约 2.65:1,已弃用为关键文字/信息标记色。

### 4.2 brief 投影、有效主题与兼容输入

M0a 先扩展现有 `style render` owner `leo-ppt-generator/runtime/src/leo_ppt_generator/templates.py`,支持结构化 token 与已登记皮肤的显式绑定,产出字段差异报告和有效主题。计划新增可选 `--render-theme <skin引用> --theme-out <文件>` 参数,与已有 `--expected-selection` 联用;未传时保持现有 prompt 输出不变。CLI envelope 返回主题路径/哈希与选择指纹,现有 generate 流程将其写入 §4.5 的绑定记录,不依赖人手复制隐藏参数。

M2 在该入口基础上补散文字段辅助抽取,由 Agent 在候选生成阶段完成并标记 inferred;确定性 CLI 不内置第二个 LLM 编排器。输出候选主题与字段差异报告,按 §4.4 三关准入后才进入推荐可行集合。M1 的手工种子也走相同三关,由完整 brief 核对并登记来源;不等待 M2,也不自动全量投影风格库。

投影使用完整加载的 brief 及其选择指纹,token_sidecar 优先;散文提取仅标记 inferred,缺省来自具名版本化默认项。无法转换的字体、布局锚或装饰不静默丢弃,差异报告列明且候选保持不可执行。冷门 brief 可先产候选报告,不得因没有 renderability 就改写用户已选方向。

**输入分支**:

- 未传 `--theme-file`:各模板恢复自己的历史默认视觉,不是将七模板统一成一套颜色;不增加严格主题门禁而破坏旧调用。
- 传入带 `schema_version` 的新皮肤:先解析 schema/引用,合并已记录的覆盖,生成有效主题,再检查组件兼容、容量和完整颜色对。空文件、空对象、未知版本、缺引用或不支持模板一律阻断;不得回落默认后声称成功换肤。
- 传入不带版本的旧平铺对象:保留现有 page/chart 分支的实际行为及警告。旧页面输入以前未被模板消费,继续保留此语义并明确披露;不悄悄将旧键升级成新样式。无法识别的旧图表键保持既有默认警告。
- `style render --var`:保留原接口,将其结果中的有效 token_sidecar 送投影/主题合并,不让新增模块重复解释另一套 override 规则。任何覆盖都改变有效主题哈希,重新校验并失效旧样张证据。

HTML 适配将白名单语义角色解析为 `--leo-*` CSS 变量、受控 `@font-face` 与装饰节点,在模板执行与 ready 信号前完成注入。Mermaid 适配把相同有效主题映射成现有 `build_theme_variables` 可消费的平铺锚及 xyChart 配置,明确 primary/on_primary/background/border/data-series 的对应;图表和页面不直接互传不兼容的 JSON。未知方言或缺必要色彩映射阻断新主题分支,不能只发默认警告。

### 4.3 模板迁移、容量与基线

**M0a 必选迁移范围**:当前 `leo-ppt-generator/assets/render-templates/` 下 cover-basic、body-basic、spec-table、timeline、compare、pull-quote、frame-shot 七个模板及 Mermaid 图表入口。保留模板 id、数据槽、页面尺寸、ready 与溢出哨兵合同;分别提取历史默认视觉。支持任一新皮肤必须证明实际 CSS/字体/图表角色已消费,不能仅证明全局变量在场。

新增 `leo-ppt-generator/assets/render-templates/template-contracts.json` 保存每个模板的必需数据槽、组件色彩角色绑定、可用装饰插槽及对应版式 id;不复制 `.layouts.json` 中的几何值。`lint_render_templates.py` 检查迁移声明、消费点与非法硬编码,渲染测试检查实际生效。字体声明与版本化 legacy 默认项是明示白名单,不要求宽高、定位等所有 CSS 都变成变量。新皮肤对比度规则不反向宣称 legacy 默认色已合格。

装饰件落在 `leo-ppt-generator/assets/render-ornaments/`,由渲染器按包内 id 读取并注入,禁止模板 fetch 和主题携带任意脚本/路径。装饰不得遮挡内容、进入正文节点或改变数据值;frame-shot 延续禁倾斜/透视规则,不能被 doodle 的倾斜参数覆盖。

**容量合同**:颜色与不占内容面积的装饰可独立换肤;字体、字重、字号、行高、槽宽、边距和占位边框均参与有效布局。扩展现有 `leo-ppt-generator/runtime/src/leo_ppt_generator/layout_bank.py`、版式 schema 与 `.layouts.json` 的 profile 表达,由同一解析结果供 HTML 和 `check_deck_geometry.py` 使用;sidecar 继续是版式权威,但不能沿用变化前的容量数值。缺精确字体或 profile 时阻断新皮肤,不静默换系统字体。R-31 的 grid/safe_margin/page_no/corner_radius/line_weight 是字符串锚,需解析或映射到已登记 profile,无法映射则报告不支持。

为既有 `layout-bank-v1` 增加可选治理字段 `render_profiles`,只对新主题入口要求该字段,保持原 `content_capacity` 与旧查询/旧 style render 的输出不变。同步更新 `leo-ppt-generator/runtime/src/leo_ppt_generator/schemas/layout-bank-v1.schema.json`、`leo-ppt-generator/scripts/lint_layout_grid.py` 和相关合同的封闭字段定义,不放开任意附加属性。profile 用1280×720逻辑像素存放模板/variant槽位、字号、行高和边距,到2560输出的尺度只在渲染器换算一次。原固定 CJK 等效宽度预检是估算,有效字体下的真实换行与可见性由浏览器终检;不将估算包装成精确字体度量。旧工具与新资产不混装,按 §4.6 同版本回滚。

预检不足时减少内容或选择已验证的版式变体,不自动缩字号。截图前复用 DOM 溢出哨兵,并检查实际所用字体和必需文字节点可见;预检通过不能替代浏览器检查。排印空隙通过 CSS/布局处理,不改写数据文字,以免破坏数值与正文回读。

**基线先于改码**:实施时新增 `leo-ppt-generator/tests/fixtures/render-theme-baseline/manifest.json`,逐项记录源 revision/未提交内容哈希、模板及相邻 CSS、输入 JSON、字体与装饰、PNG、原收据、渲染命令参数、Playwright/Chromium 版本、系统和逻辑/输出尺寸。包内 fixture 使用相对路径;外部实战资产先登记来源再导入可共享副本,不得提交个人业务原文。不能共享时使用受控本地证据包并在 manifest 标明定位方式和 unavailable 状态,不伪造路径或哈希。

M0a 使用当前七模板的脱敏确定性 fixture,每模板覆盖最小有效输入、典型内容、近容量边界三类;原输出在重构前产生并冻结。像素算法沿用 `leo-ppt-generator/tests/render/test_page.py`:ImageChops RGB difference 转 L 后,非零像素占比 ≤0.001;每页分别判定,不以全册平均掩盖失败。固定浏览器/字体环境,阈值在看结果前锁定;内容逐字核对与角色检查独立于像素容差。

**M0b 条件迁移**:仅在定位 blueprint/doodle 源模板、全部 variant 输入及 SDLC r3/r4 原图/收据/环境后开始。核对十种历史 variant,将颜色与装饰提取到主题,网格、页码与连接规则归版式 profile;保留旧 id 与数据合同。十五页 × 两套视觉逐页回归,未覆盖 variant 另加 fixture。历史环境无法恢复时只能报告新环境重建,不能签署历史等价。找不到基线则 M0b 保持未完成,不阻塞 M0a/M1 的在库模板路线,也不把从零创作的种子冒充历史重构。

### 4.4 质检与皮肤准入

皮肤准入分三关,任何一关未通过都不进入面向正常任务的可执行推荐集合。候选可以在静态与依赖关通过后生成隔离验证样张,其准入证据保持空/未完成,不能因允许验证出图就标记正式可用;这样不会形成“先准入才能生成准入样张”的循环。

1. **静态与依赖关**:schema、字体文件/字重/许可、模板与版式引用、装饰白名单均有效。对每个实际组件槽的前景与背景完整配对检查,覆盖 text/background、text/surface、on_primary/primary、标签、警示、数据标记和强调用途;必查对由模板合同生成,不允许皮肤删减。复用 WCAG 相对亮度/比值函数,不用仅检查 override 键的 `_enforce_sidecar_contrast` 作为整主题验收。普通文字 ≥4.5:1,满足 WCAG 大文字条件才用 ≥3:1,承担信息的非文字标记 ≥3:1;透明叠加按最终底色计算。图案底无法由静态值证明时需验证实际文字承载面,不输出“全量合格”。
2. **渲染与缺陷关**:支持模板逐个出图,检查有效主题消费、容量/DOM、字体加载和文字/数字逐字回读。新 render lane 的 SIZE-01 文件大小只作异常提示,不能凭压缩字节数判内容完整;图像 lane 及无新主题输入保持现有行为。BLANK-01 亮度差/内容比按受治理 profile 校准,CONT-01 保留图像启发式语义,不冒称 WCAG。输入缺正文、数据未注入、只有装饰、白字白底、裁切、缺字体等植入缺陷必须全部被相应硬检查拦截;不得以调低阈值替代修复。
3. **行业样张关**:按 §6.2 的行业任务与受众 rubric 评审,记录样张路径、问题与处理结果。模型评分用于辅助诊断;可执行皮肤的视觉准入需真实评审证据,不得伪造人工通过。任务内样张呈现与豁免仍遵守现有 SKILL 合同,不新增重复确认门。

`qa_profile` 的亮度/内容比阈值在 M0a 固定正常样本和缺陷样本后校准,同一 profile 适用于兼容的明暗与密度档,不按单张图片临时调参。合格条件为正常样本无错误阻断、植入缺陷无漏检;无法兼得则改检测器或明确不支持该档。WCAG 下限、内容完整性和溢出规则不允许 profile 放宽。

### 4.5 推荐、选择与执行绑定

复用 `leo-ppt-generator/references/style-recommendation.md` 的现有入口、指纹与优先级,扩展 `references/styles/00_索引/风格路由.md` 的环境维度,不建立第二套风格索引。

| 输入 | 取值/缺失处理 |
| --- | --- |
| 行业 | 从冻结合同与材料取值;未知时用通用皮肤候选,记录 unknown,不臆造行业规则 |
| 受众保守度 | low/medium/high;缺失按 medium 并标记默认来源 |
| 场合正式度 | low/medium/high;缺失按 medium 并标记默认来源 |
| 投屏环境 | light/dark/unknown;unknown 默认优先 light 并披露假设 |

先服从既有内容硬规则,再过滤模板兼容、字体/版式依赖、已通过样张和明暗变体。合格集合内沿用“场景匹配 > 受众风险偏好 > 数据密度 > 自定义复用”的 tie-break,环境作为变体选择条件。保留“显式点名 > 参考图 > 推荐”;点名可覆盖审美建议,不能覆盖缺依赖、文字不可读或容量失败。

亮环境时推荐 tech-dark 的已验证 light 变体;尚无 light 变体则移出默认推荐,不虚构资产。已经冻结选择后不自动换变体,需按既有换风格/样张规则更新选择。文化提示仅在有具体地区、用途和证据时 WARN,不新增金融禁红或东亚禁紫锁定规则。

在既有 run 的 `deck_spec.style` 旁新增结构化 `render_theme` 绑定,包含 `selection_fingerprint`、brief scope/path/hash、skin_id/revision/mode、原主题哈希、覆盖清单、有效主题哈希、推荐信号来源和逐页 template/layout profile 引用;不改既有 style 字段类型。确定性 CLI 产生绑定材料,现有 generate owner 写入既有 deck_spec,由 worker 加载并经渲染入口校验;不新增旁路运行台账。worker 从此记录读取唯一有效主题,不能再次自由推荐或各页自行投影。

同名 user/builtin brief 继续由当前 resolver 与指纹确定;名称相同不能套用 builtin 皮肤证据。没有与所选 brief 相符的可执行皮肤时,返回候选投影或说明能力缺口,在既有视觉方向节点处理替代;不静默换成另一个风格或 lane。选择、覆盖或依赖改变后重新校验并更新指纹,旧样张/交付证据失效;恢复任务发现指纹不符时停止该页,而非混用新旧主题继续。

### 4.6 产物溯源与兼容恢复

扩展现有单页 provenance 为 schema v2,不新增运行状态机。v2 在旧字段之外保存有效主题、模板相邻 CSS、实际字体文件/字重、装饰、layout profile、QA profile、图表主题适配版本和嵌入图表资产的哈希;引用风格选择指纹。`render page/chart`、`image record`、交付收据同时升级,沿用现有锁与原子写纪律。

需要恢复的实际输入在渲染前冻结于 run 的 `input/render-theme/` 下(有效主题、依赖清单和可再分发资产副本),路径相对 run;复用 `render/receipt.py` 的输入指纹分类。新主题渲染从该快照解析模板/字体/装饰,不再从可能变动的安装目录读同名资产;渲染前后校验快照指纹,变化则拒绝生成成功收据。仅有原文件路径或哈希而无可读输入时,记录不可复现,不宣称可恢复。原始主题和覆盖分别记录,有效主题用固定规范 JSON 序列化计算哈希,不将时间戳混入身份。

新代码接受 v1 旧收据但标记 `theme_provenance=unrecorded`,不伪造补齐信息;旧收据与原产物只读。新主题流程要求 v2,`image record` 核对产物哈希、选择绑定及依赖快照,缺字段/篡改/漂移拒绝并入。渲染中途失败不留下可被当成成功记录的 PNG/收据组合。

回滚时恢复模板与 runtime 的同版本组合;已完成旧 run 不重写,新 run 不交给不支持 v2 的旧 runtime 继续执行。先用只读诊断定位不兼容,必要时基于完整冻结输入创建新 run;不得删改旧记录来伪装兼容。

---

## 5. 行业审美矩阵(种子皮肤定义,圆桌 §3.6/§3.5 综合)

| 皮肤 id | 行业 | 视觉气质 | 密度 | 组件偏好 | 文化注意 |
| --- | --- | --- | --- | --- | --- |
| finance-navy | 金融/投资/咨询 | 蓝灰主色+细网格+衬线标题 | 高-可扫读 | spec-table/KPI/对照 | 数字右对齐、单位齐全;涨跌符号与配色按具体地区口径 |
| consulting-pyramid | 咨询/战略 | 白底深蓝+MECE 分组线+脚注源 | 高 | 金字塔/矩阵/瀑布 | action title 是结构纪律,母版层已有 |
| tech-dark | 科技/互联网/AI | 暗底+电光强调+等宽点缀+辉光 | 中 | 系统图/回路/时间线 | 亮环境推荐已验证 light 变体,冻结后不得静默切换 |
| gov-red | 政务/国企 | 红金庄重+对称+仿宋标题 | 中-高 | 清单/规格表/时间线 | 走 content_rules 监管;密级版式 |
| health-clean | 医疗/生物/大健康 | 白底蓝绿+无装饰线+大字号 | 中 | 层级图/时间线/KPI | WCAG 严格档;禁忌词监管 |
| edu-bright | 教育/培训 | 高明度+大圆角+插画感+图文节奏 | 低-中 | 三卡/金字塔/问答 | 受众低认知负荷,双线索编码 |
| brand-creative | 文创/消费/营销 | 暖纸/贴纸/手账(doodle 泛化) | 低 | 大图/引语/贴纸卡 | 情绪优先,允许破网格(仅外框层) |
| academic-austere | 学术/答辩 | 极简黑白+图表语法严格 | 中-高 | 图表/文献/公式 | 对齐既有学术五拍与 dense-defense 档 |

(8 个逻辑种子,明暗变体单独计验证覆盖;上表密度为产品描述,执行须映射 §4.1 的现有档位。组件偏好是目标,仅已实现项进入 compatible 集合。政务/医疗的既有 content_rules 兼容检查前移到 M1 准入;新增监管规则不归皮肤系统生产。)

---

## 6. 路线图与验证合同

### 6.1 阶段、文件与完成条件

以下均为待实施工作。原“约六个工作期”估算不再沿用:先在 M0a 基线盘点后按模板/字体/组件实际覆盖量估算,不承诺尚无数据支撑的工期。表内定义路径前缀:包根 `B=leo-ppt-generator/`,runtime 包 `R=leo-ppt-generator/runtime/src/leo_ppt_generator/`,渲染测试 `T=leo-ppt-generator/tests/render/`;其余路径均相对仓库根。标“新增”的文件当前不要求存在。所有源修改同步根 `CHANGELOG.md`,不在本方案授权下自动提交或发布。

| 单元 | 依赖与目标 | 主要文件 | 验证与完成条件 |
| --- | --- | --- | --- |
| M0a-1 当前基线与主题合同 | 无;先冻结七模板基线,再实现 schema 与解析 | `B/tests/fixtures/render-theme-baseline/`、`R/schemas/render-theme-v1.schema.json`、`R/render/theme.py`、`T/test_theme.py`(均新增) | 基线7×3页可复现;schema/字段转换单测明确缺省、旧对象、新版本、空值和坏引用的结果;灰盒静态全门禁在M0a-3汇合验收 |
| M0a-2 页面/图表消费与容量 | M0a-1;实现 §4.2–§4.3 | `B/assets/render-templates/*.html`、`B/assets/render-templates/template-contracts.json`(新增);`R/render/page.py`、`R/render/chart.py`、`R/render/fonts.py`、`R/render/assets.py`、`R/layout_bank.py`、`R/schemas/layout-bank-v1.schema.json`;`B/references/styles/12_版式库/*.layouts.json`;`B/scripts/check_deck_geometry.py`、`B/scripts/lint_layout_grid.py` | `T/test_page.py`、`T/test_chart.py`、`T/test_template_variants.py`、`T/test_overflow_sentinel.py`、`B/tests/test_layout_bank.py` 及 `B/tests/test_render_theme_capacity.py`(最后一项新增):七模板 legacy 逐页 diff ≤0.001;新主题全量消费;字体/边距变化触发重新预检并拦截超容量 |
| M0a-3 质检、绑定与溯源 | M0a-2;完成严格新主题的执行闭环 | `B/scripts/visual_qa.py`、`B/scripts/lint_render_templates.py`;`B/assets/render-qa-profiles.json`(新增);`R/cli.py`、`R/templates.py`、`R/render/provenance.py`、`R/render/receipt.py`;`B/references/render-contract.md`、`B/references/style-recommendation.md`、`B/references/image-deck-workflow.md`、`B/prompts/render-worker.md` | `B/tests/test_visual_qa.py`、`T/test_provenance.py`、`T/test_theme_binding.py`(最后一项新增):所有植入缺陷被拒绝;正常浅底/深底通过;v1兼容/v2绑定/输入漂移/中途失败可观察;正常 run 真正使用冻结主题 |
| M0b 历史两模板迁移 | 独立条件分支;M0a + 历史基线可读 | 历史模板与输入定位后写入 manifest,才确定导入文件;共享 `B/assets/render-ornaments/`(新增) 和 M0a 测试 | SDLC 15×2页逐页回归、全部 variant 覆盖;缺基线保持未完成,不拖延M1的七模板路径 |
| M1 八个行业种子与路由 | M0a-1/2/3全部通过;不依赖M0b | `B/assets/industry-skins/`、`B/assets/render-ornaments/`(均新增)、`B/assets/render-fonts/`、`B/NOTICE`;`B/references/styles/00_索引/风格路由.md`、`B/references/style-recommendation.md`;`T/test_industry_skins.py`、`B/tests/test_skin_routing.py`(均新增) | 每皮肤声明完整 compatible 集合;集合内模板逐个渲染通过;8×3行业金样板,tech-dark light变体另验3页;默认/显式点名/参考图/缺环境/无兼容项均验证;政务医疗先过content_rules |
| M2 候选投影与数据组件 | M1;支持长尾而不放宽准入 | `R/templates.py`、`R/render/theme.py`;`B/assets/render-templates/` 新增KPI/矩阵组件,条形/趋势优先扩既有Mermaid;相应版式sidecar;`T/test_theme_projection.py`、`T/test_data_components.py`(均新增) | 预先固定3个冷门brief和期望字段来源,全部通过硬检查才评可用率≥2/3;数字/单位/标签全量回读;新增组件走模板、容量和角色绑定门禁;ECharts不在本轮引入 |
| M3 行业视觉评测 | M1/M2;使用005任务定义,不等待或冒充005已执行 | `B/evals/eval.yaml`、`B/evals/cases/industry-skin-*.yaml`、`B/evals/fixtures/industry-skins/`、`B/evals/judges/judge_industry_skin.py`、`B/tests/test_industry_skin_judge.py`(除eval.yaml外均新增) | §6.2视觉矩阵、负例校准、双评审与两次复跑完成;报告逐单元原始证据与失败清单,不以均分或评分替代达标 |

M0a 使用灰盒主题做机制验证,不把它登记为行业成品。M1 每个种子只承诺已验证的组件集合,不提前承诺 M2 的 KPI/矩阵等组件。M2 扩组件时同步重跑受影响皮肤的兼容和容量验证。

### 6.2 行业视觉验收

新增视觉轨复用 [005方案](2026-09-07-005-leo-ppt-20-industries-content-quality-evaluation-plan.md) 的行业、任务和受众定义,但拥有独立 fixture 与结果。005 的“停在样张前”边界不变,不在其结果上直接添加视觉达标结论。

- **机制回归**:M0a 七模板×三类输入×legacy 默认,以及七模板×灰盒 light/dark 两主题。历史 SDLC 只在 M0b 条件满足时作附加回归;另建脱敏固定技术内容作为八皮肤同内容对照,不称其为原 SDLC 复现。
- **种子准入**:每个行业种子至少封面/内容/数据三页,使用本行业材料。金融包含带单位的密集数表;医疗包含长术语、大字号和非绝对化结论;政务包含文号/来源等任务要求;教育包含教学顺序和低认知负荷;科技包含可辨识系统图;咨询包含结论与脚注;文创包含真实视觉素材;学术包含图表/引用。素材缺失显式报缺,不以占位物验收成品。tech-dark 的 light 变体独立同内容验证。
- **覆盖矩阵**:20 行业×light/dark 两种环境=40 单元,每单元至少3页、固定一个主要受众。另选科技/金融/教育/医疗4个行业做同材料保守受众与开放受众对照,每行业补1单元,共44单元、至少132页/轮。明暗环境不强迫选不同皮肤:允许理由充分地复用浅底,但需检查投屏可读性;不宣称物理投影仪现场已测。
- **硬检查**:全部页的文字/数字/单位保真、容量与实际溢出、实际字体、有效主题/图表消费、实际颜色对、输入与选择指纹一致。任何硬失败使该单元失败,不以行业平均分补偿。
- **语义评审**:逐页判定受众气质是否合适、视觉是否支持结论、图表是否易比较、信息层级是否清楚、全册是否一致;输出 pass/fail、图像位置与原因。跨模型评审只在后续评测获得对应外部数据授权且能力在场时执行;缺能力即标未完成,不伪装独立评审。
- **校准与通过线**:开跑前固定 rubric、fixtures、哈希、裁判版本和顺序随机种子;每类植入缺陷至少1例,硬缺陷检出率必须100%。语义校准集中使用人工标注的合格/不合格对照各至少10页,双评审间及各自对人工的逐项一致率均≥80%;未达标先修 rubric,不开始达标声称。正式轮所有硬检查通过,全部语义项经分歧裁决通过,并保留初始分歧率和裁决证据;固定输入独立复跑两轮都满足才声称44单元达标。人工标注或裁决缺失则报告该部分未完成。

执行评测时先按 `skill-upper` 做 validate/list-cases,再跑真实 eval 并以最终结果与 per-case evidence 定结论;当前文档修订不运行评测、不生成假结果。

### 6.3 验证命令与完成判定

实施后的验证复用对应包测试入口:在 `leo-ppt-generator/` 下以 `PYTHONPATH=runtime/src python3 -m unittest discover -s tests/render -p 'test_*.py'` 检查渲染模块,并运行表内对应容量、质检、路由和 judge 单测。浏览器缺失造成的 skip 不算通过。新增风格/版式资产还必须执行 `lint_style_briefs.py` 与 `lint_layout_grid.py`,模板执行 `lint_render_templates.py`;最后运行 `git diff --check`。

整体完成需 M0a、M1、M2、M3 全部有证据;M0b 单独列为已完成或受阻,未完成时不得声称本方案全部历史迁移已完成。每份报告区分源码检查、机制验证、视觉准入、行业矩阵与历史复现,列出失败/跳过及输入快照。交付物包括实现源码、测试、皮肤与许可、基线 manifest、逐页差异及行业评测报告;本次交付仅为修订方案。

## 7. 风险与边界

| 风险 | 缓解 |
| --- | --- |
| 皮肤工厂失控(数量膨胀) | 上限12个逻辑皮肤,明暗变体分别计验证成本;长尾覆盖必须再校验,投影产物只是候选 |
| 判据与皮肤再次错配(调色为过门禁) | 受治理 QA 档 + 全量颜色对 + 正常/缺陷对照;不得按单皮肤任意调低硬门槛 |
| 字体授权风险 | 只收 OFL/APACHE 系;NOTICE 登记;缺字 WARN 不静默换系统字体(渲染合同已有纪律) |
| 审美自动评分过度承诺 | 只承诺:结构/一致性/对比度可机检;"好看"仍走金样板+人审样张双门 |
| 图像 lane 与渲染 lane 双轨混乱 | 明确分工:图像 lane 只做氛围封面/概念图(render lane 也可出),审美皮肤体系只建在渲染 lane;风格库同时服务两轨(brief→图像 prompt / 投影→theme) |
| M0 重构回归破等价 | 改前冻结实际输入与环境;逐页 diff;遇到并行源码变化重新采集受影响基线,不覆盖其他会话修改;旧 run 只读 |
| 历史资产缺失 | M0b 条件分支保持受阻,不阻塞当前七模板主线;新样张不能冒充历史基线 |
| 字体/边距变化导致容量失真 | 渲染与预检消费同一有效 profile,截图前 DOM 检查,缺字体或超容量阻断 |
| 新旧主题/收据协议混用 | 输入按版本分支,v1只读兼容,v2绑定真实依赖;同版本回滚,不让旧 runtime 接管新 run |
| 行业刻板印象替代任务证据 | 四键信号与明确覆盖优先;文化提示保留证据及适用条件,不用未核验统计生成硬规则 |
| **渐进债被误判为阻塞项**(v2 新增) | G2 三项(negative_prompt/别名冲突/同族簇)维持"登记在案、点名触发"节奏,不并入本方案里程碑,防止范围蠕变 |

## 8. 与既有资产的关系

- 005 方案:复用行业任务定义,保持其样张前截断;视觉轨归本方案并单独出结果。
- R-27 token_sidecar / R-31 layout-lock / `--var`:沿用原 owner 和选择守卫,新增显式转换与失败语义;WCAG 只复用数学函数,全量主题准入另由 §4.4 约束。
- 12_版式库 sidecar:继续拥有几何与容量规则;新增 profile 和实际字体参与解析,换肤后重新预检,不承诺原容量数值不变。
- 11_图表语法与图表样式规范:继续拥有图表数据语义,主题适配只提供视觉角色;不改变数值、单位、坐标基线或比较尺度。
- `style-recommendation.md`、worker、render provenance 与 delivery receipt:分别拥有选择、执行、单页溯源和交付新鲜度,本方案扩展既有 owner,不创建平行生命周期。

### 8.1 本轮审查问题的方案闭合表

| 问题 | 修订位置 | 实施后必须提交的证据 |
| --- | --- | --- |
| 换肤仅部分生效/图表默认回落 | §4.2/§4.3、M0a-2 | 七模板实际消费与图表颜色映射结果 |
| 换肤后容量失真 | §4.3、M0a-2 | 字体/边距变化反例与 DOM 拒产证据 |
| 历史模板与回归基线不可定位 | §1.5/§4.3、M0a-1/M0b | 当前基线 manifest;历史资产未定位则显式受阻 |
| 完整皮肤对比度漏检 | §4.4、M0a-3 | 全角色颜色对与植入缺陷检出结果 |
| 四键路由未绑定执行 | §4.5、M0a-3/M1 | 选择指纹、有效主题及 worker 输入一致性 |
| 新依赖未进入溯源 | §4.6、M0a-3 | v2收据、快照恢复与漂移拒绝 |
| 同内容换皮不足以证明行业适配 | §6.2、M1/M3 | 行业金样板、44单元两轮结果及独立评审限制 |

表中“方案闭合”仅指已定义处理方式与验收,不表示上述实现或效果已经通过验证。

---

## 附:研究来源索引

Gamma:[官方模板库](https://gamma.app/templates)/[官方指南](https://gamma.app/explore/content/guides/the-complete-guide-to-presentation-templates-with-ai)/[24Slides 评测](https://24slides.com/presentbetter/gamma-app-review);token 架构:[M3](https://m3.material.io/foundations/design-tokens)/[zeroheight](https://zeroheight.com/learn/multi-brand-multi-product-and-white-label-token-architecture/)/[DSC](https://www.designsystemscollective.com/choosing-the-right-architecture-for-your-multi-brand-design-system-ff8195cba088)/[Style Dictionary](https://alwaystwisted.com/articles/a-design-tokens-workflow-part-9.html);咨询美学:[Deckary](https://deckary.com/blog/consulting-slide-standards)/[Perceptis](https://perceptis.ai/blog/how-to-create-a-slide-like-mckinsey-or-bcg)/[Poesius](https://poesius.com/blog/consulting-slide-design-mckinsey-bcg-bain-guide)/[SlideModel](https://slidemodel.com/mckinsey-presentation-structure/);行业色彩字体:[Slide House](https://theslidehouse.com/color-palettes-for-business-presentations-2026/)/[eWeek](https://eweek.wfglobal.org/weekly/best-practices-typography-color-investor-presentations-158055)/[Piktochart](https://piktochart.com/blog/fonts-and-colors/)/[ResearchGate 门诊字体研究](https://www.researchgate.net/publication/244879477_Evaluating_patient_choice_of_typeface_style_and_font_size_for_written_health_information_in_an_outpatient_setting)/[Adobe](https://www.adobe.com/express/learn/blog/psychology-font)/[Figma](https://www.figma.com/resource-library/professional-fonts/);跨文化:[Eriksen](https://eriksen.com/marketing/color_culture/)/[BINUS](https://international.binus.ac.id/graphic-design/2022/06/01/color-symbolism-psychology-across-cultures/)/[信任与红色研究](https://www.researchgate.net/publication/334550253_Trustworthy_Blue_or_Untrustworthy_Red_The_Influence_of_Colors_on_Trust)/[Academia](https://www.academia.edu/6647564/Colours_Across_Cultures_Translating_Colours_in_Interactive_Marketing_Communications);通用:[NEN](https://www.nen.wfglobal.org/digest/presentation-design-color-contrast-typography-pitch-deck-958075)/[Helion360](https://helion360.com/blog/professional-powerpoint-templates-finance-healthcare-tech)。
