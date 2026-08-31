# 专家评审报告 1：Skill 提示词工程视角的 14 个 PPT 生成项目源码解剖

- 评审人角色：Agent Skill 提示词工程产品专家（Claude Code / Codex 类 PPT 生成 skill 的提示词资产、工作流契约与质量控制设计）
- 评审日期：2026-08-30
- 评审对象：`/Users/kuang/knowledge/ppt-github/` 下 14 个项目（全量逐项深读，非抽查；每项目均真实打开 SKILL.md / README / 核心源码 / 提示词资产至少 2 个文件）
- 集成目标：`/Users/kuang/knowledge/leo-skills/leo-ppt-generator`（只读参考，未修改）
- 方法：先 ls 全目录结构 → 通读入口文档 → 逐文件阅读提示词资产（SKILL.md 正文、references/、prompts/、scripts/、风格/模板文件）→ 记录 License → 对照 leo-ppt-generator 现有资产判定覆盖关系。

---

## 一、逐项目评审

### 1. NanoBanana-PPT-Skills（歸藏 · PPT Generator Pro）

- **一句话定位**：Nano Banana Pro（Gemini 3 Pro Image）整页出图 + 可灵 AI 页间转场视频 + FFmpeg 合成完整 PPT 视频的"图片式 PPT + 动效视频"双产物技能。
- **架构与核心机制**：
  - `SKILL.md` 是"操作手册型"入口：六阶段流程（收集输入 → slides_plan.json 规划 → 出图 → Claude 读图生成转场提示词 → 可灵视频 → 返回产物），页数规划策略表（5 页 / 5-10 / 10-15 / 20-25 的逐页结构建议）写得相当实用。
  - `/Users/kuang/knowledge/ppt-github/NanoBanana-PPT-Skills/generate_ppt.py`：提示词引擎极简——`generate_prompt()` 把风格模板与三分支页面提示词（封面 3D 玻璃物 / 内容 Bento 网格 / 数据分屏）拼接。**关键缺陷**：页面类型推断是 `is_cover = page_type=="cover" or slide_number==1`、`is_data = page_type=="data" or slide_number==total_slides`——最后一页被强制当作数据页；三分支提示词硬编码在 Python 里，与风格文件耦合；`load_style_template()` 用 `"## "` 起止 marker 切分 Markdown，解析脆弱。
  - `styles/gradient-glass.md` / `styles/vector-illustration.md`：风格文件含"基础提示词模板 + 页面类型模板（封面/内容/数据的构图逻辑）+ 技术参数"，是"MD 给人看"的单文件风格合同。
  - `prompts/transition_template.md`：**高价值资产**——首尾帧转场提示词元模板：第一步把差异分为 A 类（关联性强→原地演变）与 B 类（差异巨大→运镜驱动转场），第二步按类选策略，第三步从"主体变化/环境变化/风格特效变化"工具箱组合，输出规则强调"描述看到什么而非感觉什么、避免文学化修辞"。
- **可搬运资产**：`prompts/transition_template.md`（A/B 类转场策略元提示词）；`SKILL.md` 的页数-结构规划表；`templates/viewer.html`（键盘导航播放器）；`ARCHITECTURE.md`（模块图可作为文档范式）。
- **License**：仓库无 LICENSE 文件，`SKILL.md` 末尾声明 "MIT License"（声明式 MIT，缺正式文本）。
- **对 leo-ppt-generator 的判定**：**可借鉴机制**——图片式生成主链路已被 leo 的 generate 路线全面超越；唯一值得单独借鉴的是 `transition_template.md` 的差异分类转场策略（若 leo 未来增加"页间动效/视频导出"能力，这是现成的提示词元模板）。

### 2. gpt-image2-ppt-skills（JuneYooo）

- **一句话定位**：本组工程化程度最高的 gpt-image-2 整页出图技能：265 套风格 + RuntimeProfile 统一运行时 + layout bank 结构化 sidecar + 模板克隆 + 可选可编辑重建。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/gpt-image2-ppt-skills/SKILL.md`（810 行）：定义了"MD 给人看，JSON 给机器用"的双文件风格结构——`styles/<collection>/<id>.md` + 同名 `<id>.layouts.json`（必需，缺失直接报错不走旧 prompt 路径）；`--prepare-only` 让 API 直连与 Codex 原生出图共享同一 RuntimeProfile / layout routing / prompt compiler；可编辑模式的 A1（原像素提取）→ A2（遮挡补全）→ B（AI 分离重生成）路由与"检查轮次可多轮、生成轮次逐级升级、局部问题只修局部、每轮保留最佳版本"；外部真实图片的"透明角标骨架参考图"（skeleton 只标 `final_image_rect_px` 四角，不画闭合框、不铺白底）+ `external_image_trace/` 五步中间链路取证。
  - `/Users/kuang/knowledge/ppt-github/gpt-image2-ppt-skills/scripts/runtime_profile.py`（181 行）：**核心可搬运设计**——`normalize_runtime_profile()` 把模板克隆 profile 与蒸馏风格 sidecar 归一为同一种 RuntimeProfile：每个 layout 带 `page_type / summary / visual_signature / content_capacity / best_for / avoid_for / variation_tags / reuse_friendly / json_schema / external_image_slots`，顶层带 `capabilities`（content_routing / source_evidence / reference_images / portable_without_references）与 `prompt_strategy=layout-fields`；`reuse_friendly=false` 的版式（封面、强视觉页）在同一 deck 中标记"只许用一次"。
  - `styles/initial/dark-aurora.layouts.json` + `dark-aurora.md`：风格 MD 含角色化基础提示词（"你是一位顶级深色模式 UI 设计师，对标 Linear / Vercel…"）+ 分页面类型构图 + 禁止清单（禁刺眼正红、禁纯黑 #000000、每页 ≤2 处发光区）；layouts.json 中每个 layout 都有 json_schema 约束内容字段（如封面 title 2-24 字、agenda items 3-6 项）。
  - `scripts/editable_pptx/workflow.py`：可编辑模式强制"回渲染后端真实可用"前置检查（`render_template.py --check` 做最小真实转换探测，拒绝只查路径存在），构建后自动回渲染 `editable_renders/page-XX.png` 供逐页人工验收，状态 `rendered_pending_manual_review` 不允许自动判定通过。
- **可搬运资产**：`runtime_profile.py` 全文（归一化器模式）；`.layouts.json` sidecar 格式与字段合同；`SKILL.md` 的 A1/A2/B 素材路由与轮次升级纪律、layout 复用检测策略（1 page : 1 layout）、模板渲染后端分级探测表（PowerPoint COM > Keynote AppleScript > LibreOffice）、Codex 原生出图 vs `--backend codex` 子进程的两层对比表；`docs/external_image_overlay_logic.txt` 链路图。
- **License**：Apache License 2.0（`LICENSE` 文件确认）。
- **对 leo-ppt-generator 的判定**：**可直接集成资产 + 可借鉴机制**（本组第一优先级）。leo 有 137 个可加载风格但没有逐 layout 的结构化 sidecar；RuntimeProfile 的"任何视觉来源编译成同一合同、Markdown-only 在加载边界拒绝"正是 leo 未来接入"用户模板克隆"时避免双路径漂移的解法。Apache-2.0 与 MIT 兼容（保留 NOTICE 即可）。

### 3. guizang-ppt-skill（歸藏 · Magazine Web PPT）

- **一句话定位**：单文件 HTML 横向翻页网页 PPT，双风格体系（电子杂志×电子墨水 / 瑞士国际主义 22 版式锁）+ 完整演讲者模式与观众屏同步契约。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/guizang-ppt-skill/SKILL.md`：7 问澄清清单（风格 A/B 必问第一）、叙事弧大纲模板（钩子→定调→主体→转折→收束）、主题节奏规划硬规则（每页必须标 light/dark，连续 3 页同主题不允许，8 页以上必须有 hero dark + hero light，每 3-4 页插一个 hero 页）、类名预检（写 slide 前先读模板 `<style>` 块，模板是类名唯一来源）、中文大标题字号分档表（1 行 ≤8 字用 `min(6.4vw,11.2vh)`…）、瑞士风"越大越细"字号-字重映射表（≥8vw 用 200 ExtraLight，16px 小字最低 400）、最小字号下限（正文 18px / caption 16px / meta 14px）。
  - `/Users/kuang/knowledge/ppt-github/guizang-ppt-skill/references/image-prompts.md`：GPT-M 2.0 配图提示词库——通用规则（配图是素材不是 slide，不生成页眉页脚页码 logo）、比例选择表（槽位→比例→HTML 落位类）、生成提示词后缀模板（"输出必须是[16:9]横向构图…不要生成页眉、页脚、标题、页码、角标、署名、装饰边框"）、同组图片一致性后缀、7 类图片类型（纪实照片/杂志信息图/流程/对比/系统关系/截图再设计/数据大字报）各一段可直接套用的中文提示词 + 瑞士风专属 5 类。
  - `/Users/kuang/knowledge/ppt-github/guizang-ppt-skill/references/checklist.md`：P0/P1/P2/P3 分级质检清单，来自真实迭代踩坑（"每一条都是踩过坑之后总结的"）。
  - `/Users/kuang/knowledge/ppt-github/guizang-ppt-skill/scripts/validate-swiss-deck.mjs`：登记版式校验（只允许 S01-S22 + 两个登记封面/尾页，`data-layout` 必填）+ Playwright 真实渲染测量 M1（DOM/视觉溢出、底部空白、nav 安全线）/ M2（标题间距），且**带修正阶梯**：`1-40px over 只微调不删内容 / 40-90 局部压缩 / 90-160 压标题或拆页 / 160+ 才换版式删内容`——把"超框怎么办"从主观判断变成分级处置。
- **可搬运资产**：image-prompts.md 的类型化配图提示词与规格后缀（思想与文本结构）；checklist 的 P0-P3 分级模式；validate-swiss-deck 的"测量+修正阶梯"思路；演讲者备注按稳定 `data-slide-id` 存储而非页码下标（防重排串页）。
- **License**：**AGPL-3.0**（`LICENSE` 确认）。⚠️ 传染性许可证：代码与文本资产直接复制进 MIT 仓库有合规风险，只能借鉴思想或重写。
- **对 leo-ppt-generator 的判定**：**可借鉴机制（不可直接复制文本/代码）**。leo 的 `references/styles/04_来源_guizang/` 实际提取自 guizang-social-card-skill（下条）而非本项目；本项目独有的 `image-prompts.md`（配图提示词库）与"测量修正阶梯"未被吸收，前者因 AGPL 只能参考重写，后者的思想（分级修正阶梯 + 真实渲染测量）可以无侵权地进入 leo 的 `visual-qa.md`。

### 4. guizang-social-card-skill（歸藏 · 社交卡片）

- **一句话定位**：小红书 3:4 图文集 / 微信公众号 21:9+1:1 封面对 / Live Photo 实况卡片的 HTML 渲染 + Playwright 截图技能，是 leo-ppt-generator `04_来源_guizang` 的真实上游。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/guizang-social-card-skill/SKILL.md`：**能力圈诚实声明**——11 个小红书品类分三桶（强端到端 / 文字结构强但图需用户提供 / 明确出圈并"push back honestly"），出圈请求在设计前告知而非硬套版式；纯文字输入的"三选一"图片来源一次性 gate（A 用户自供图推荐 / B 图库检索 / C AI 生成，一次问清不再重复劝）；图文叠放"选图先行、tint 兜底"（≥60% 画布被照片覆盖必须先过 quiet-zone 与亮度测试，先无遮罩合成，缩略图检查不过才加局部图像色 tint，禁止默认全画布遮罩）；主体映射强制（放标题前必须用 Read 工具描述主体位置并记录为 HTML 注释，只放已记录安全区）。
  - `/Users/kuang/knowledge/ppt-github/guizang-social-card-skill/validate-social-deck.mjs`：R1-R9 渲染实测校验——R1 溢出、R2 页脚碰撞、R3 瑞士粗字重违规（大字 weight≥600 即 FAIL）、R4 最小可读字号、R5 纵向四段密度（欠填带 >216px 判 FAIL）、R6 大标题行数字数硬上限、R7 figure 默认 margin 漂移、R8 视觉边界与底部空白、R9 标题与内容间距——全部基于 Playwright 真实渲染的 computed style，不是静态 grep。
  - `/Users/kuang/knowledge/ppt-github/guizang-social-card-skill/references/title-shortener.md`：长标题→1:1 短标题的五步提取法（核心动词→核心宾语→压到 4-10 字→丢英文→必要时小副标）+ 四种句式模式（动宾 / 逗号双句 / 大字单词 / 数字主导）+ 实测对照表。
- **可搬运资产**：title-shortener 五步法、image-overlay 双测试、screenshot-treatment 六参数、portrait-fill 五区欠填检测、R1-R9 校验思想——**leo 已经吸收**（见下"吸收程度核实"）。
- **License**：**AGPL-3.0 + 商业授权双轨**（`LICENSE` + `COMMERCIAL_LICENSING.md`：平台接入需商业授权）。
- **对 leo-ppt-generator 的判定**：**已覆盖**——`leo-ppt-generator/references/styles/04_来源_guizang/00_README.md` 明确声明从本项目提取 12 个 references 文件的规则并做 16:9 适配（M01-M16 / S01-S12 配方折叠进"电子墨水杂志风.md"与"瑞士网格风.md"两个权威落点 + 6 份组件模板）。剩余增量仅 R1-R9 实测校验思路（leo visual-qa 目前以目测合同为主）。⚠️ 合规提示：leo 是 MIT 仓库，从 AGPL 项目"提取规则文本"处于灰色地带，建议在 04_README 中补充法律声明或改为思想重写。

### 5. html-ppt-skill（lewislulu · HTML PPT Studio）

- **一句话定位**：token 驱动的静态 HTML 演示工作室：36 主题 CSS + 31 布局 + 27 CSS 动画 + 20 canvas FX + 演讲者模式，一键 `npx skills add` 安装。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/html-ppt-skill/SKILL.md`："One theme file = one look. One layout file = one page type."；创作规则强制 token 化（`color: var(--text-1)` 好 / `color: #111` 坏）、不发明新布局文件、**"presenter-only 文字绝不放 slide 本体"**（必须进 `.notes`，默认 display:none）；演讲者模式预览用 `?preview=N` URL 参数让 iframe 渲染单页无 chrome——**预览与观众视图同 CSS 同字体同视口，颜色布局保证一致**，翻页用 postMessage 无闪烁。
  - `/Users/kuang/knowledge/ppt-github/html-ppt-skill/references/layouts.md`：31 个布局文件按语义分组索引（Openers / Text-centric / Numbers & data / Code & terminal / Diagrams & flows…），每个 `templates/single-page/<name>.html` 是带真实演示数据的完整可运行页。
  - `/Users/kuang/knowledge/ppt-github/html-ppt-skill/scripts/render.sh`：headless Chrome 逐页截图（`#/N` 深链 + `--virtual-time-budget=4000` 等动画稳定）。
- **可搬运资产**：`?preview=N` 单页预览参数模式；`render.sh` 的 headless Chrome 截图链路；31 布局清单可作为 leo 版式库的对照词表。
- **License**：MIT。
- **对 leo-ppt-generator 的判定**：**可借鉴机制**——leo 是图片式 PPTX 路线，HTML 模板资产不适用；但"headless Chrome 渲染测量"与"预览与成品同视口"两个思想可用于 leo 的样张 QA 环节（对生成的 PPTX 回渲染 PNG 做几何/密度测量，替代纯目测）。

### 6. ian-handdrawn-ppt（Ian）

- **一句话定位**：单一"中文手绘技术解释"风格的深度工程化：把一个风格做到商用交付级的提示词合同与文字保真降级链。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/ian-handdrawn-ppt/ian-handdrawn-ppt/SKILL.md`：明确边界（本 skill 的 "PPT" 指成品位图页，不做可编辑 PPTX/PDF——反向的路线隔离声明）；工作流第 5 步"deck 级风格锁定"：生成多页前先写一份 compact deck style lock 并在每页 prompt 中逐字复用，只允许中央语义图区随内容变化；外层壳（页码位置/标题处理/纸张色/角标网格/人物政策）跨页常量清单。
  - `/Users/kuang/knowledge/ppt-github/ian-handdrawn-ppt/ian-handdrawn-ppt/references/prompt-patterns.md`：**本组最精炼的页面提示词合同**——四件套：① Deck Style Lock（一次写、逐页贴）；② Page Role Locks（cover 21:9 2520x1080 / body 16:9 1920x1080，"body 页标题与其它 body 页光学同尺寸，短标题也不放大"）；③ Complete Page Prompt 模板（Use case / Asset type / Page role / Archetype / Main point / Composition / **Required text only**（页面上允许出现的全部可见文字白名单）/ Avoid 清单）；④ Multi-Page Consistency Pass（生成前逐项自检：页码位置一致？纸色一致？封面 21:9 正文 16:9？短标题未放大？）。**Text Fidelity Fallback**：图像方向已接受但文字渲染错误时，先压文字预算；仍不行则生成留白版 + 确定性后期贴字，最终交付仍是位图。
  - `references/visual-dna-v6.md` + `assets/theme-tokens.json`：视觉 DNA 文档与机器可读 token 并存；Text Budget 明确量化（标题 5-12 字 / 副标 3-12 字 / 主标签 2-5 个 / 注释 0-6 条每条 2-6 字）；"短标题陷阱"（4-6 字标题会被模型放大成封面标题，必须显式锁光学尺寸）。
- **可搬运资产**：`prompt-patterns.md` 全文的合同结构（style lock / role lock / Required text only / Avoid / consistency pass / text fallback）；Text Budget 量化表；短标题陷阱规则。
- **License**：MIT + `NOTICE.md` 要求保留署名（再分发请保留 "Ian Handdrawn PPT" 名或注明 Ian）。
- **对 leo-ppt-generator 的判定**：**可直接集成资产**——四件套合同可直接并入 leo 的 `prompts/slide-worker.md` / `references/image-deck-workflow.md`：leo 的 deck-master 四段结构管内容，ian 的合同管"提示词里文字如何声明"；`Required text only` 白名单还能反过来作为 visual-qa 的 OCR 核对清单。文字保真降级链（压预算→留白贴字）填补 leo 目前"文字错误→整页重生"的粒度空缺。

### 7. image-to-editable-ppt-skill（ningzimu）

- **一句话定位**：图片/扫描 PPT/PDF → 对象级可编辑 PPTX 的重建技能：editppt CLI 状态机 + 页级 worker 派发 + 三步对象决策树，是 leo direct-editable 路线的同源上游。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/image-to-editable-ppt-skill/skills/image-to-editable-ppt/SKILL.md`：入口合同（每条规则"只有一个权威 home"，其余文件只指向不复述）；状态只能经 `editppt` 命令推进、禁止手写 run/page 状态 JSON；多页必须派发 page worker、单页走本地重建者模式且同样遵守页面合同；`dispatched` 是**活跃租约**——不许因为 worker 慢就终止/重置；**"同一页面同一根因失败两次，诊断责任在你不在用户"**——必须自己复现失败命令修根因，只有真正需要用户提供的东西（凭据/付费决定/原始文件）才升级给用户，且表述为具体动作而非调试提问。
  - `/Users/kuang/knowledge/ppt-github/image-to-editable-ppt-skill/skills/image-to-editable-ppt/prompts/page-worker.md`：**worker 提示词工程范本**——`{{NAME}}` 占位符由 `build-page-worker-prompt.py` 填充；"MANDATORY FIRST ACTION：先完整读三个 references 再做任何决策，过去所有失败模式都编码在其中，未读而做的决策无效且会被重做"；所有权边界（只拥有本页目录）；失败时写 `validation.json.passed=false` + 具体失败原因（什么失败/确切错误/父 agent 要修什么），禁止伪造剩余产物；返回仅六行固定键值。
  - `references/page-decision-tree.md`：三步决策（背景识别修复→前景素材分离→原生元素重建），顺序不可换（先定文本会把 logo/UI 截图里的字错误原生化）；"**False Progress**"反模式专节（用裁剪/近似素材先拼个"差不多"的稿子，能过确定性校验但违反对象来源合同——确定性校验是结构门禁，不是豁免）；dashboard 默认不是背景（标题/数字/表格/轴/图例必须拆解为原生对象，只有地图/热力/不可恢复图表可为图像区）。
- **可搬运资产**：page-worker.md 的合同结构；"false progress"与"结构门禁≠豁免"的表述；失败两次归因规则；`rendered_pending_manual_review` 状态语义。
- **License**：MIT。
- **对 leo-ppt-generator 的判定**：**已覆盖**——leo 的 `references/page-decision-tree.md`、`manifest-schema.md`、`cli-helper.md`、`prompts/page-worker.md` 与本项目同名同源，direct-editable 路线已深度吸收。**增量可借鉴**：① worker prompt 的"强制先读三文件"开场（leo 的 page-worker 可加）；② 失败两次归因纪律；③ 租约不可因慢重置的表述。

### 8. awesome-ppt-skills（三命令 awesome-ppt / std / editable）

- **一句话定位**：`$awesome-ppt` 三命令家族（std 稳定 / editable 实验 / legacy 兼容）：gpt-image 整页出图组装 PPTX，可再跑 ppt-master 二段原生重建。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/awesome-ppt-skills/awesome-ppt/SKILL.md`：V1 image-model-first 铁律——所有可见标题/正文/标签必须 verbatim 进图片 prompt 由图像模型渲染，禁止先生成背景再加 PowerPoint 文本；`rendered_text` 既是图片 prompt 的来源也是 editable 重建的精确文本源（一份数据两用）；`--pages N` 是硬约束（slide_count = 图片数 = PPT 页数，不等先问）；"法律/财务/合规文字必须完美可编辑审计时，停下并说明 image-first 是错误默认"——按内容类型反向路由的场景意识。
  - `/Users/kuang/knowledge/ppt-github/awesome-ppt-skills/awesome-ppt/references/image-prompting.md`：页面提示词模板（Exact text to render 编号清单 + 布局指令复述一遍关键文字 + "Use no extra text beyond the exact text listed above"）；好/坏提示词行为对照表（坏例："Leave space for a title" / "Add some bullets"）；生成前 8 项 checklist 与生成后 5 项检查。
  - `references/theme-style-prompt-library.md`：31 个主题的英文风格提示词库（商务咨询/路演/金融/学术/医疗/党政…每个一段可直插的 style prompt）+ 4 个 style-only redesign prompts。
  - `scripts/validate_deck.py`（prompt 覆盖检查：每条 rendered_text 必须出现在对应 prompt 中）、`inspect_pptx_package.py`（检查原生文本节点数、整页媒体占比、**可疑纯黑兜底色**）。
- **可搬运资产**：image-prompting.md 的 Exact-text 模板与好坏对照表；validate 的"prompt 覆盖率"校验思想；31 主题风格库。
- **License**：**未声明**（仓库无 LICENSE 文件，README 亦无许可证章节）。
- **对 leo-ppt-generator 的判定**：**可借鉴机制（集成受阻于许可证）**——leo 的 `05_来源_awesome-gpt-image-2/00_合并映射.md` 记录的吸收来源是 `ppt-github/awesome-gpt-image-2/data/style-library.json`（22 模板，19 合并 + 3 新建），**不是本仓库**；本仓库的 `theme-style-prompt-library.md`（31 主题）与 image-prompting 的好坏对照表是未被吸收的增量，但无许可证意味着默认版权保留，不应直接复制文本，只能作为路由参考；"rendered_text 一份数据两用（出图 + 可编辑重建文本源）"机制值得进 leo 的 upgrade 路线。

### 9. nano-banana-slides-prompter（Web 应用）

- **一句话定位**：Nano Banana Pro Slides 的提示词生成器 Web 应用（React + Bun server）：LLM 内容分析选版式序列 + 富提示词工程 + 角色主持人生成器。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/nano-banana-slides-prompter/server/src/prompts/system.ts`（1302 行，本组最大的单一提示词资产）：① `SLIDE_TYPE_LIBRARY`——10 大类 50+ 版式模板（opening/concept/data/process/technical/business/comparison/example/storytelling/educational/closing），每条一句构图描述；② `CONTENT_ANALYZER_SYSTEM_PROMPT`——让 LLM 按内容模式输出 JSON 版式序列 + 分类兜底序列（`getDefaultSlideSequence` 按内容类别给默认中段版式）；③ `NANO_BANANA_PRO_SYSTEM_PROMPT`——"富提示词"哲学：每页 200-300 词、强制五层构图（深背景/中景/hero/浮层/前景）、"NEVER leave dead space"；④ **视觉词汇表**——LIGHTING/BACKGROUND/SURFACE/MOTION/HUD/COMPOSITION 六类数百条术语词典（god rays / voronoi / bioluminescent / targeting brackets…）；⑤ `stylePersonas`——每种风格一句人设（"你是 NASA 首席工程师做任务简报"）；⑥ 角色主持人系统—— CHARACTER_GENERATION 提示词输出结构化角色卡 + 8 种渲染风格（Pixar/Real/Anime…）。
- **可搬运资产**：SLIDE_TYPE_LIBRARY 的 50+ 版式类型词表（可对照 leo 的 12 版式库/25 页面语义查缺）；视觉词汇表（可作 leo 风格 brief 的 `visual_direction` 措辞弹药库）；stylePersonas 的角色化一句人设模式。
- **License**：MIT（`LICENSE` 文件确认）。
- **对 leo-ppt-generator 的判定**：**可借鉴机制（选择性）**——词汇表与版式类型库是纯数据可参考；但其"200-300 词富提示词 + 密度崇拜 + 特效堆叠"哲学与 leo 的结构化合同路线**方向相反**（见反面教训），不应整体引入。

### 10. codex-ppt-skill（ningzimu · leo 的 vendored 上游）

- **一句话定位**：图片式 PPT 的编排型技能：审批门禁 → 样张 → slide job 状态记录 → 子代理逐页出图 → QA 修复 → 组装，leo-ppt-generator 的 image-deck 主线与风格 brief 格式的直接上游。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/codex-ppt-skill/skills/codex-ppt/SKILL.md`：硬约束（approval gate 前禁止产出 deck_spec/speech/图片/pptx；样张批准后记录 `sample_generation_method` 并把完全相同的方法传给每个 slide 子代理；后端确认后固定不许 worker 为方便换后端；状态必须脚本记录，聊天消息不构成"已派发/已完成"）；13 步默认工作流 + 文档引用映射（每阶段先读对应 docs/ 再动手）。
  - `/Users/kuang/knowledge/ppt-github/codex-ppt-skill/skills/codex-ppt/references/麦肯锡风格.md`：**风格 brief 的 JSON 合同范本**——`best_for / visual_direction / canvas(aspect/background/composition/density) / color_palette(primary/secondary/accent/neutral/rule) / typography(title/body/labels/text_quality) / layout_patterns[](逐版式构图语义) / layout_usage_rule / layout_blueprints[](带 sections 位置与标签的版式蓝图)`；"商业隐喻匹配表"（漏斗=转化、路径=战略转型、阶梯=成熟度…15 个隐喻映射）。
  - `/Users/kuang/knowledge/ppt-github/codex-ppt-skill/skills/codex-ppt/prompts/slide-worker.md`：worker 交接模板——禁止清单（本地绘制/Pillow/SVG/HTML 截图/python-pptx 排版截图/手工合成）+ 后端不可用时返回 `blocker=<reason>` 而非降级 + 返回仅三行（backend_used / selected_source / qa_note）。
  - `scripts/image_gen.py`：gpt-image-2 CLI fallback（gpt-image-2 像素约束 655360-829440px、最大边 3840、最大比例 3.0；provider 工厂 + atlascloud 适配）。
- **可搬运资产**：全部已被 leo vendor（`runtime/src/leo_ppt_generator/_vendor/codex_ppt/`）。
- **License**：MIT。
- **对 leo-ppt-generator 的判定**：**已覆盖**——leo 已 vendor `image_gen.py` 并继承风格 brief 结构（`lint_style_briefs.py` 的 lint 字段即源于此合同）。leo 在其上叠加了四路线路由、CONFIRM-GATE/DELIVERY-GATE、三级标注等治理，属于"上游超集"关系。

### 11. dashi-ppt-skill（Dashi PPT）

- **一句话定位**：12 套 React 组件主题的 HTML 演示生成器：每页产出"3 个锁模板候选 + 1 个 Agent 定制方案"四方案对比，内容容量驱动的版式查询引擎。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/dashi-ppt-skill/skills/dashi-ppt/SKILL.md`：① **锁模板填文案**——模板方案保留原视觉/结构/数量/显隐/强调/配色/图表类型/图片槽位，只替换可见文字，不改非文案 props；② `layout:query` 按真实内容容量选页——`--title-chars / --summary-chars / --takeaway-chars / --item-count / --value-item-count / --nested-depth / --priority` 硬条件 + 摘要/结论/detail 只影响排序；③ 每页 3 个**结构家族不同**的候选 + 整 deck 统一分配不重复同一组三布局；④ `content.presentation` 文案包——v1-v3 共享页面意图与 required facts 只选长短排序分组，v4（bespoke）独立创作但"不新增事实"，且必须在 scaffold 分配的 `compositionFamily`（hero/split/metric-spotlight/chart-led/timeline/matrix/editorial/comparison/process）几何内实现；⑤ `validate:four-variant-quality` 同一浏览器会话批量截图每页 v4 验收；⑥ 成果验收三态（通过/待修正/阻塞）+ "机器校验通过只是技术基线，不等于成果达标"。
  - `project/scripts/layout-query.mjs` / `inspect-layout.mjs`：版式契约查询（copyKeys / copyBudgets / propShapes / fillPlan / mediaSlots / countBindings / numericBounds），`contentLocked:true` 的页面直接退出候选。
- **可搬运资产**：内容容量→版式查询的参数化思想；copyBudgets 文案长度预算；四方案对比输出模式；compositionFamily 家族约束。
- **License**：**AGPL-3.0**（代码不可搬入 MIT 仓库）。
- **对 leo-ppt-generator 的判定**：**可借鉴机制**——"按文字量选版式"与 leo 的"要点禅档位"天然契合：leo 的 12 版式库（36 版式骨架）可以补一份"版式→内容容量表"（哪个版式吃几条要点、标题几字），让 deck-master 的视觉行选择有数据依据；四方案对比模式对 leo 的"样张确认"环节是潜在升级（一次给 2-3 个版式样张让用户选）。

### 12. GordenPPTSkill（GordenSun）

- **一句话定位**：21 套真实中文 PPTX 模板的"只换字不破坏排版"技能：模板槽位合同 detail.json + 几何精确的文本容量计算 + 出框检测。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/GordenPPTSkill/SKILL.md`：三模式（内置模板 / 用户自带 pptx 模板现场探查 / 完全原创）；编辑铁律九条——核心是"**max_chars 是软参考、严禁省略号截断**"（容量已留 20% 余量，宁可轻微超框也不能出现'…等等'的半句话；出框检测只提示不阻断，`--strict` 会诱导截断所以日常禁用）、"同级标题字号必须一致，不要逐处改字号"（超长用更精炼措辞重写而非缩字号）、"模板有什么角色用什么角色"（cover 数组为空就直接从内容页开始，不硬造封面）、章节名前后呼应（改目录必须同步分章扉页+面包屑）。
  - `/Users/kuang/knowledge/ppt-github/GordenPPTSkill/scripts/compute_capacity.py`：**几何精确的容量模型**——从 template.pptx 读取文本框尺寸+字号，定义"视觉宽度单位 vw"（CJK/全角=1.0、ASCII≈0.5、空格=0.35、其他=0.8），计算 `chars_per_line`（按 vw）、`max_lines`、`max_chars`、wrap/autofit 标志，并输出全模板 `type_scale`（字号层级表）给每个 slot 标 level。
  - `/Users/kuang/knowledge/ppt-github/GordenPPTSkill/references/pptx-edit-schema.md`：detail.json 完整合同——page_roles 索引、text_slots 带 `address`（shape_id/paragraph/run 三级物理寻址）+ current_text sanity check、shape_caution_pages（装饰图形不随文字同步的页）、data_charts（原生图表的 max_categories/series_count）。
- **可搬运资产**：`compute_capacity.py` 的 vw 容量算法（纯思想+少量代码，MIT 可直接搬）；"软容量+禁省略号+同级字号一致"三条编辑铁律；detail.json 的 page_roles/slot 合同结构（对 leo 的 direct-editable 处理可信 Office 输入时有用）。
- **License**：代码 MIT；**内置 21 套模板仅供非商业学习研究**（第三方设计师素材，商用需原作者授权）——模板资产与代码授权分离。
- **对 leo-ppt-generator 的判定**：**可直接集成资产（代码层）**——vw 容量模型可直接进 leo 的 `scripts/check_deck_geometry.py` / `lint_layout_grid.py`：leo 的版式库（36 版式骨架、版式内容 Schema P1-P36）目前是"必填内容字段"合同，补一份每版式的 vw 容量表后，deck-master 的"要点禅档位"就能在写提示词前机器预检"这页文字量这个版式装不装得下"。

### 13. xiaobei-skill（小北在读研 · 三子技能合集）

- **一句话定位**：AI+科研向三件套：图片→VBA/Office Shapes 重建、Codex 直接操纵 PowerPoint 逐对象复刻参考图、论文→图片式答辩 PPT。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/xiaobei-skill/skills/xiaobei-skill-rebuild-image-in-powerpoint/SKILL.md`：① `reference_lock` 保真档案——复刻类请求默认锁定：复现每个可读标签/面板/视觉核心/证据块/箭头方向，"不得为整洁而省略、改写、合并、重排"，任何刻意省略必须先记录进 `authorized_omissions`；② **复杂度计分→模式自动选择**——native / hybrid / auto 三模式，6 项条件各 +1 分（≥3 面板、≥2 不规则生物对象、≥3 照片/显微/热图块、>15 箭头、常规图表+机理面板混合、密集图例），用户点名保留视觉对象 +2 分；≥4 分（或 ≥3 分且有生物/照片类）选 hybrid（复杂视觉核心保原子裁剪资产，其余原生）；"不要因为技术路线图框多箭头多就选 hybrid"；③ **画前覆盖门禁**（pre-drawing coverage gate）——scene map 八项全过才准开画（inventory 完整、文字逐字转写、每个连接线有源/目标/方向/路由、图表有原生重建计划、栅格资产有裁剪理由与禁止邻近内容、矩形来自测量非目测、ambiguities/omissions 清零）；④ 自纠上限三轮 + 修复优先级序（缺失/拓扑 → 面板几何 → 栅格裁剪 → 连线路由 → 文字适配 → z-order → 配色）。
  - `skills/xiaobei-skill-image-to-vba/SKILL.md`：硬保真触发器清单（显微图/3D 渲染/照片级渐变纹理噪声/有机阴影——命中任一该元素必须栅格保留），"模型自评偏向可编辑重建，会把复杂艺术品画烂"——用硬触发器对抗模型自评偏差；输出语言合同（全简体中文 + VBA 关键字/`AITVBA_` 前缀保留英文）。
  - `skills/xiaobei-skill-academic-paper-to-ppt/SKILL.md`：**逐页聊天内联展示合同**——每生成完一页立即在聊天中以 `![第 X/N 页](绝对路径)` 展示，"已生成 6 页"的文字进度不算满足；禁止生成无字背景/占位面板，prompt 里禁止出现 "text-free / background template / text to be added later" 等措辞；`imagegen_manifest.json` 记录每张图的生成方法与资产。
- **可搬运资产**：复杂度计分硬触发器；reference_lock / authorized_omissions 概念；画前覆盖门禁八项；修复优先级序；硬保义触发器对抗自评偏差；逐页内联展示合同。
- **License**：Apache-2.0（`LICENSE` + `NOTICE` 确认）。
- **对 leo-ppt-generator 的判定**：**可借鉴机制**——① 复杂度计分可直接数字化进 leo 的 `page-decision-tree.md`（现在 leo 的"复杂视觉保留为位图"是描述性的，可变成计分触发）；② `authorized_omissions` 让 upgrade-selected 路线的"这页我省略了什么"显式留痕，与 leo 三级标注天然互补；③ 逐页内联展示可强化 leo CONFIRM-GATE 样张环节的沟通合同。

### 14. ai-paper2slide-skill（Zhixiang Lu）

- **一句话定位**：AI/科研论文 → 顶会质量 PPTX + 逐页英文讲稿 DOCX 双文件硬交付，LaTeX 包来源锁定的视觉溯源纪律。
- **架构与核心机制**：
  - `/Users/kuang/knowledge/ppt-github/ai-paper2slide-skill/SKILL.md`：**两条不可协商硬规则**——① LaTeX-only 图片：幻灯片里的每张图必须来自用户 LaTeX 源码包内被引用的资产，禁止 PDF 裁图/网图/生成图/记忆图/相似替代图，缺图时做文字/形状解释页并在质量报告列出未解析图；② 默认双文件交付（PPTX + 约 10 分钟英文讲稿 DOCX，markdown 大纲不算交付）。
  - 工作流：`scripts/inspect_latex_assets.py` 扫 LaTeX 包产出 `visual_source_manifest.json`（每图标 `slide-image-eligible` 仅当有包内已解析资产路径）；`scripts/validate_visual_sources.py --strict-latex-images` 交付前强校验 slide-visual 映射的来源锚定；13 页会议结构模板带**每页秒级时长预算**（标题页 20-30s、方法总览 75-90s…）；讲稿规则（每页 100-150 口语英文词≈60 秒、每页必须有到下一页的自然过渡句、公式的发音友好描述）。
  - `references/ai_conference_style_guide.md` / `speaker_script_guide.md` / `quality_checklist.md`：一页一信息、主张式标题（标题陈述结论而非章节名）、每 bullet <12 词、只高亮支撑本页主张的数字。
- **可搬运资产**：visual_source_manifest + strict 校验器模式；13 页带时长预算的结构模板；"标题陈述主张"规则；讲稿过渡句合同。
- **License**：MIT。
- **对 leo-ppt-generator 的判定**：**可借鉴机制**——① 逐图来源 manifest 与 strict 校验和 leo 的三级标注（引用/估算/示意）完全同构，可为 leo 增加 `sources_manifest.json` + `--strict-sources` 交付前校验（generate 与 upgrade 路线通吃：upgrade 时原图来源、AI 重绘图、示意图的边界机器可查）；② deck-master 备注段可吸收"每页时长预算 + 过渡句"字段。

---

## 二、leo-ppt-generator 吸收程度核实（专项结论）

对 `leo-ppt-generator/references/styles/` 的核实结果：

1. **`04_来源_guizang/` 的真实来源是 guizang-social-card-skill（项目 4），不是 guizang-ppt-skill（项目 3）**。`00_README.md` 列出的 12 个来源文件（style-system / theme-presets / layout-recipes / components / background-systems / category-cookbook / platform-specs / content-planning / image-overlay / screenshot-treatment / map-component / portrait-fill / title-shortener）全部是 social-card 的 references；M01-M16 / S01-S12 配方已折叠进顶层 `电子墨水杂志风.md` 与 `01_通用母版/极简排版/瑞士网格风.md` 两个权威落点；另存 6 份组件模板（deck 结构 / 图文叠放 / 截图处理 / 地图 / 竖图填充 / 标题压缩），并做了 16:9 适配（纵向版式转横向）。**未被吸收的**：guizang-ppt-skill 本体的 `image-prompts.md` 配图提示词库、22P Swiss 版式锁细节、演讲者模式契约、`validate-swiss-deck.mjs` 的测量+修正阶梯——受 AGPL 约束，建议只借鉴思想。
2. **`05_来源_awesome-gpt-image-2/` 的来源是 `ppt-github/awesome-gpt-image-2/data/style-library.json`（不在本次 14 项清单内的另一仓库）**，22 模板按"19 同类合并 + 3 真缺口新建（写实摄影 / 历史古风 / 场景叙事分镜）"落地，合并映射文档质量很高。本次评审的 awesome-ppt-skills（项目 8）的 `theme-style-prompt-library.md`（31 主题）与 `image-prompting.md` 好坏对照表**尚未被吸收**，但其仓库无 LICENSE，文本级搬运有版权风险，只宜做路由参考。
3. **codex-ppt-skill（项目 10）与 image-to-editable-ppt-skill（项目 7）已被深度吸收**：`_vendor/codex_ppt/image_gen.py`、风格 brief JSON 合同（lint_style_briefs.py 的字段来源）、`references/page-decision-tree.md` / `manifest-schema.md` / `cli-helper.md` / `prompts/page-worker.md` 均同源。leo 属于两者的超集（叠加四路线、门禁治理、五字段控制面）。
4. **风格库现状**：137 可加载风格（11 内置 + 126 参考）+ 145 分节轴规范，共 303 个 md；六轴正交组织（通用母版/行业内容域/场景用途结构/论证模式/信息图类型/图片渲染/结构布局/品牌身份/图表语法/版式库/页面语义）。

---

## 三、Top 5 集成建议（按 ROI 排序）

### 建议 1：引入 layout bank sidecar，把"风格库"升级为"风格 × 版式库"双层结构

- **来源**：gpt-image2-ppt-skills — `scripts/runtime_profile.py`、`styles/initial/dark-aurora.layouts.json`、`SKILL.md` 的 layout bank sidecar 章节。
- **建议内容**：为 leo 的 11 套内置风格（以及 12 版式库的 36 版式骨架）补一份同名 `.layouts.json` sidecar，字段采纳 RuntimeProfile 合同：`id / page_type / summary / visual_signature / content_capacity / best_for / avoid_for / variation_tags / reuse_friendly / json_schema`；在 `lint_layout_grid.py` 中新增 sidecar 配对检查（缺 sidecar 的风格报 ERROR，对齐上游"Markdown-only 在加载边界拒绝"）；在 image-deck-workflow 的视觉行选择处消费 `reuse_friendly` 实现"强视觉版式一 deck 一次"的机器执行版（对应 guizang/dashi 的版式多样性硬规则）。
- **预期收益**：版式多样性从提示词约束变为数据约束（可 lint、可统计、可防重复）；为后续"用户模板克隆"路线预留统一 RuntimeProfile 入口，避免模板路径与风格路径双实现漂移。
- **集成成本**：中——sidecar 数据一次性补齐（11 风格 × 6-10 layout），runtime 消费点集中在 deck-master 视觉行选择与 slide-worker prompt 编译两处；Apache-2.0 允许直接借鉴代码结构（保留来源注明）。

### 建议 2：吸收 ian-handdrawn 的提示词四件套合同，强化逐页文字保真

- **来源**：ian-handdrawn-ppt — `references/prompt-patterns.md`、`references/visual-dna-v6.md`、`assets/theme-tokens.json`。
- **建议内容**：把 ① deck style lock（一次锁定逐页逐字复用）② page role lock（含"短标题不放大"光学尺寸锁）③ **Required text only 白名单** ④ Avoid 清单与 Multi-Page Consistency Pass 并入 leo 的 `prompts/slide-worker.md` 与 `references/image-deck-workflow.md`；`visual-qa.md` 增加"对照 Required text only 白名单做文字核对"一节；补上 Text Fidelity Fallback 降级链（压文字预算 → 留白生成 + 确定性贴字），填补"文字错误只能整页重生"的粒度空缺。
- **预期收益**：中文小字错漏是图片式 PPT 的第一质量痛点；白名单让 QA 有核对基准，降级链降低修复成本；MIT+NOTICE（保留 Ian 署名）即可搬运。
- **集成成本**：低——纯提示词合同层改动，两三个文件，不动 runtime。

### 建议 3：引入 vw 视觉宽度容量模型，让版式选择"装得下"可计算

- **来源**：GordenPPTSkill — `scripts/compute_capacity.py`（vw：CJK=1.0 / ASCII=0.5 / 空格=0.35）、`SKILL.md` 编辑铁律（max_chars 软参考 / 严禁省略号截断 / 同级字号一致）。
- **建议内容**：把 vw 容量算法并入 `scripts/check_deck_geometry.py`；为 36 版式骨架（版式内容 Schema P1-P36）补每版式的 `chars_per_line / max_lines / max_chars` 容量字段；deck-master 的"要点禅档位"在定稿前跑一次容量预检（超容量 → 降档位或换版式，而非缩字号）；把"宁可轻微超框不要省略号、超长先重写措辞"写进 page-worker 合同。
- **预期收益**：文字溢出从"生成后目测发现"前移到"生成前机器预检"；与建议 1 的 content_capacity 字段天然咬合（content_capacity 写档位语义，vw 写精确容量）。
- **集成成本**：低-中——算法约百行可直接移植（MIT），版式容量表需按 leo 画布（16:9）一次性标定。

### 建议 4：数字化"复杂度计分 + 授权省略"，升级 direct-editable / upgrade 路线的对象决策

- **来源**：xiaobei-skill — `skills/xiaobei-skill-rebuild-image-in-powerpoint/SKILL.md`（复杂度计分、reference_lock / authorized_omissions、画前覆盖门禁、修复优先级序）、`skills/xiaobei-skill-image-to-vba/SKILL.md`（硬保真触发器）。
- **建议内容**：① 在 `references/page-decision-tree.md` 中把"复杂视觉保留为位图"的判断改为计分触发器（面板数、照片/显微块数、连接线数、图表+机理混合等，阈值明确），对抗模型自评偏差；② upgrade-selected 路线引入 `authorized_omissions` 字段：凡相对原页省略/合并/重排的内容必须显式登记并与三级标注（示意）联动；③ 自纠修复按固定优先级序（语义拓扑 → 几何 → 素材 → 连线 → 文字 → z-order → 配色）+ 轮次上限。
- **预期收益**：把 leo 已有的决策树从"描述性"升级为"可执行、可审计"；authorized_omissions 与三级标注组成完整的"忠实度账本"，是 upgrade 路线差异化能力。
- **集成成本**：中——主要是 references 重写 + manifest-schema 增字段；Apache-2.0 宽松。

### 建议 5：建立逐图来源 manifest + strict 校验，与三级标注打通

- **来源**：ai-paper2slide-skill — `SKILL.md`（LaTeX-only 硬规则、visual_source_manifest.json、validate_visual_sources.py --strict-latex-images）、`scripts/validate_visual_sources.py`；辅以 awesome-ppt-skills 的 `validate_deck.py` prompt 覆盖率检查思想。
- **建议内容**：为 leo 增加 `sources_manifest.json`：generate 路线记录每页视觉的来源类型（用户素材原图 / AI 生成 / 示意图）与文件哈希；upgrade 路线记录"原图裁剪 / AI 重绘 / 原生重建"三种对象来源；DELIVERY-GATE 增加 `--strict-sources` 校验（引用级内容必须能回溯到用户输入文件，示意图必须带三级标注）；同时把三级标注的"引用"档与 manifest 的 source-anchored 状态对应。
- **预期收益**：leo 的三级标注目前靠生成端自觉，manifest 让交付审计可机器执行；对"证据优先"治理（本仓库 evidence-first-writing 同源理念）是自然延伸；论文→PPT 类输入直接受益。
- **集成成本**：中——一个新 manifest schema + 一个校验脚本 + DELIVERY-GATE 增加一步。

---

## 四、专家署名观点

**整体水平判断**：这 14 个项目清晰分三档。**第一档"工程化合同型"**（image-to-editable、codex-ppt、gpt-image2-ppt、ai-paper2slide、ian-handdrawn）——有状态机、manifest、校验器、失败语义（blocker/租约/false progress），提示词是"合同"而非"祈祷"；leo 已同源吸收其中两个（7、10），印证其选型眼光。**第二档"重资产组件型"**（dashi、Gorden、html-ppt、guizang 系）——资产重（真实 PPTX 模板 / React 组件库 / HTML 模板），机制好（容量查询 / 版式锁 / token 主题），但路线与 leo 的图像生成主链不同。**第三档"单点/演示型"**（NanoBanana、nano-banana-slides-prompter）——提示词工程量大但结构松，接近"玩具"。

**共同盲区**（leo 的机会窗口）：
1. **没有一家做输出 PPTX 的回归评测**——全部靠人眼看样张；leo 有 `evals/eval.yaml` + skill-up 门禁，这是全场独一份的工程化优势，应该继续加重。
2. **多页一致性普遍靠提示词复述**（"保持风格一致"），只有 gpt-image2 的 layout bank 和 dashi 的容量查询是结构化方案；ian 的 style lock 是提示词层最优雅的近似。
3. **文字保真普遍靠"重试+缩短"**，只有 ian（留白贴字）和 xiaobei（manifest+验证）有真正的降级/验证链。
4. **许可证卫生极差**：AGPL（guizang 系、dashi）被社区当 MIT 用、awesome-ppt 无许可证、Gorden 模板非商业——集成前逐项核对是纪律问题。
5. **讲稿/演讲者层只有 html-ppt 和 ai-paper2slide 认真做**（像素级预览、逐页时长预算），其余全部缺席。

**对 leo-ppt-generator 最值得抄的 1 个设计**：gpt-image2-ppt-skills 的 **RuntimeProfile 统一内核**——"任何视觉来源（严格模板克隆 / 蒸馏风格 sidecar）都先编译成同一种 profile（layouts + capabilities + prompt_strategy），Markdown-only 的旧路径在加载边界直接拒绝，运行时不存在 legacy-freeform 分支"。这一个设计同时解决：风格与版式解耦、模板克隆与内置风格共用一套 prompt 编译、旧路径静默退化三个问题。leo 现在是"137 风格单层结构"，把它升级为"风格 brief × layout bank sidecar"双层结构（建议 1+3 组合）是本组调研中最高杠杆的一步。

---

## 五、反面教训（明确不该学的做法）

1. **NanoBanana 的页面类型隐式推断**：`generate_ppt.py` 中 `is_data = page_type=="data" or slide_number==total_slides`（最后一页强制当数据页）、三分支页面提示词硬编码在 Python、风格文件靠 `"## "` marker 脆弱切分。**不要学**：页面角色必须显式声明（leo 的 deck-master 页面语义已经做对了）。
2. **nano-banana-slides-prompter 的"富提示词密度崇拜"**：200-300 词提示词、"NEVER leave dead space"、五层构图全堆、特效词汇滥用的价值观会导致图像模型文字保真崩坏，且与"少即是多"的排印纪律冲突。它的词汇表数据可以查，哲学不能学。
3. **运行时自动更新**：GordenPPTSkill 要求"启用 skill 的第一个 tool call 必须 git pull 更新"（`apply_update.py`），guizang-ppt-skill 的 Step 0 也是 fetch 上游。技能执行路径上的网络拉取破坏确定性与供应链安全，与 leo 的 spec-first 门禁哲学冲突。**不要学**：更新检查可以存在，但必须隔离在显式的维护命令里。
4. **许可证混用不声明**：awesome-ppt-skills 全仓库无任何 LICENSE；GordenPPTSkill 的"模板非商业"限制只在 README 顶部一段；guizang-social-card AGPL + 商业双轨却未在社区流通中被告知。**不要学**：leo 吸收外部资产时（如 04_来源_guizang 已存在的情况）应补充来源许可证标注与法律边界说明。
5. **dashi 的巨型 schema 复杂度转移**：goal.json 的 schemaVersion 2 + contentMap + 4 variants + fillPlan + propShapes + copyBudgets + compositionFamily 把巨大复杂度推给调用方 AI，SKILL.md 里堆满"不要做 X"的防御性规则恰恰说明契约过重、出过错太多。**不要学**：合同应分层——提示词层管语义（leo 的四段母版），数据层只管可验证事实（manifest/状态），不要试图把设计判断全部数据化。
6. **awesome-ppt 的"可编辑=二段重建"过度承诺风险**：其 editable 模式依赖外部 ppt-master 技能做 SVG/原生重建，自身 SKILL.md 虽有免责声明（"不声称无损转换"），但链路跨两个技能、失败面大。leo 的 direct-editable 单技能闭环 + A1/A2/B 路由是更稳的架构，不要为了功能表好看引入跨技能脆弱链。

---

## 附：License 一览

| 项目 | License | 备注 |
|---|---|---|
| NanoBanana-PPT-Skills | MIT（SKILL.md 声明，无 LICENSE 文件） | 声明式 |
| gpt-image2-ppt-skills | Apache-2.0 | 可集成，保留 NOTICE |
| guizang-ppt-skill | AGPL-3.0 | 传染性，不可搬文本/代码 |
| guizang-social-card-skill | AGPL-3.0 + 商业授权双轨 | 同上 |
| html-ppt-skill | MIT | 宽松 |
| ian-handdrawn-ppt | MIT + NOTICE 署名要求 | 可集成需署名 |
| image-to-editable-ppt-skill | MIT | 宽松 |
| awesome-ppt-skills | 未声明 | 默认版权保留，禁文本搬运 |
| nano-banana-slides-prompter | MIT | 宽松 |
| codex-ppt-skill | MIT | 宽松 |
| dashi-ppt-skill | AGPL-3.0 | 传染性，只可借鉴思想 |
| GordenPPTSkill | MIT（代码）+ 模板非商业 | 资产与代码授权分离 |
| xiaobei-skill | Apache-2.0 + NOTICE | 可集成 |
| ai-paper2slide-skill | MIT | 宽松 |
