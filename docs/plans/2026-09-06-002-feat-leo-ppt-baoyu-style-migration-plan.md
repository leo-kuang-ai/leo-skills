# baoyu-skills 风格模版迁移方案（P0/P1/P2 三批）· v2 评审修订版

> 调研基线 2026-09-06：逐条校准 `JimLiu/baoyu-skills`（本地 `/Users/kuang/knowledge/baoyu-skills/skills`，
> 快照 commit `6b7a2e4` 2026-07-03）三个包共 39 个风格文件（baoyu-slide-deck 17 +
> baoyu-infographic 22）、46 个版式（10 + 21，另 15 个互借）、5 个维度文件、4 个支撑
> 模板，对本库 `references/styles/` 311+ brief、36 版式骨架、七轴语料做概念配对与
> 原文级抽查。校准结论：**风格条目整迁 0 条**；增量在机制层（00_索引）、既有 brief
> 的词表/规则层（MERGE）、少数真空白条目（候补登记）。
>
> **v2 修订**：本版吸收五位专家评审意见（治理合规 / 视觉设计系统 / 生图 prompt 工程 /
> 许可供应链 / 评测门禁，评审记录见 §8），修正 v1 的 7 处 P0 硬伤与 20 余处 P1/P2
> 问题。相对 v1 的关键变化：许可分层口径（AJ 衍生例外）、注入通道对照表、
> P0-2/P0-3/P0-4 重设计、P1 六组逐组修订、验证命令全部实测修正。

## 0. 总则

### 0.1 格式转换口径（baoyu 八节 → style-brief-v1）

| baoyu 节 | leo brief 字段 |
|---|---|
| Design Aesthetic | `visual_direction` |
| Background（Color + Texture） | `canvas.background`（补 `#RRGGBB` 锚点；质感描述同节） |
| Typography Primary/Secondary | `typography.title` / `body` / `labels` |
| Color Palette 角色表（8-10 色） | 四角色进 `color_palette`，其余色并入 `rule` 说明 |
| Visual Elements（8 条） | `visual_elements.allowed` |
| Style Rules · Do | `rendering_constraints` + `layout_usage_rule` |
| Style Rules · Don't | `negative_prompt` + `visual_elements.avoid`。条数 3-5 是**文档纪律非 lint 机检**（lint 只查存在性与形状）；顶层内置现已 5 条顶格，增补一律**替换/合并式**，不净增条数 |
| Best For | 文件头"适用场景"中文列表 + `best_for` |

### 0.2 治理通道与许可分层口径

**许可分层（内容级逐源核验，非仓库级一刀切）**：

- **Jim Liu 原创内容**（slide-deck 17 风格、dimensions、design-guidelines、infographic
  多数风格）：仓库 MIT（`Copyright (c) 2026 Jim Liu`）覆盖——色值/枚举词表可直引；
  reference 字段统一标 `GitHub: JimLiu/baoyu-skills(MIT,快照 6b7a2e4 2026-07-03) · <技能>/references/<路径>`；
  思想级条目追加"（思想级改写）"后缀。
- **AJ@WaytoAGI 衍生例外（无授权源）**：baoyu README License 节明示第三方内容按原
  许可（"Third-party code and assets retain their original licenses where noted"），
  CHANGELOG 1.35.0/1.114.0 两处明注 `dense-modules` + `morandi-journal`/`pop-laboratory`/
  `retro-pop-grid` 三风格与 `retro-popup-pop` 的 prompt credit 为 AJ（waytoagi.feishu.cn，
  无许可声明）。**该子集按仓库红线"无授权源只做思想级改写"处理**：七原型分类法
  重命名重组、文件名/按钮词表重新设计，不搬文本；或先向源头取得授权再议直引。
- **NOTICE 登记**：`leo-ppt-generator/NOTICE`「移植 / 改编来源」节新增
  `- baoyu-skills — MIT, Copyright (c) 2026 Jim Liu（风格词表/色值直引与机制层借鉴，references/styles/ 与 00_索引/，快照 6b7a2e4）`，
  履行 MIT 保留版权声明义务；AJ 衍生部分注明"思想级改写"。
- 不登记 `upstreams.yaml`/`vendor-lock.json`（二者面向可分发二进制与 vendor 代码，
  内容参考源的正确通道是 style-candidates + NOTICE + CHANGELOG）。

**通道**：P0 机制批直改 references（有 dashi 容量词汇/nano-banana 构图词汇层/huashu
负面语料池等先例支持机制层与条目层分通道）；P1 并入既有 brief；P2 候补登记按使用
信号触发。

### 0.3 注入通道对照表（P1 各组必须按此标注通道）

`compose_style()`（templates.py）输出键白名单实测：`name / visual_direction /
color_palette / typography / layout_patterns`（+条件键 `token_sidecar / brand /
guardrail / layout_lock / image_rendering / mode / style_anchor`）。`rendering_constraints /
negative_prompt / visual_elements / canvas` **不在白名单内**；`prepare_slide_prompts.py`
只消费 `deck_spec.style` dict，不读任何 references 文档；08 轴文件无 JSON 块，
`load_rendering()` 只解析 `positioning / paste_ready / ltd`。

| brief 字段 | 通道 | 生效方式 |
|---|---|---|
| `visual_direction` / `color_palette` / `typography` / `layout_patterns` | **机器直注** | `style render` → `deck_spec.style` → Global Style 块（JSON dump） |
| 08 轴 `paste_ready` 段落 / 「线条·纹理·深度」表 | **机器直注** | 整段进 `deck_spec.style.image_rendering` |
| `rendering_constraints` / `negative_prompt` / `visual_elements` | **agent 桥接** | 无机器消费点；靠 agent 读 brief 后摘抄进母版视觉行/页级 constraints——P1 需在 `deck-master.md` 组页规范加一句"组页时须把所选 brief 的 negative_prompt/rendering_constraints 摘入该页 constraints"，否则大半增补买不到生图效果 |
| 00_索引 文档（通用设计规范/设计体系） | **治理文档** | 约束 agent 行为，无注入路径 |

**负面词写法纪律**（扩散模型有效性）：裸负面词一律写"模型看得见的视觉现象"——
`anti-aliasing` → `smooth blurry edges, soft vector-like curves`；`glassmorphism/
neumorphism` → `frosted translucent panels, deep soft drop shadows, 3D bevel effects`；
`digital precision` → `flat vector-clean outlines`。正向词进 `visual_direction`（机器
直注）优先于负面词（正向描述对扩散模型更有效，且通道更强）。

### 0.4 遗留清理项

1. baoyu 版式 pairing 表遗留别名（`graphic-novel`/`isometric-3d`/`da-vinci-notebook`/
   `cartoon-hand-drawn`/`paper-cutout`）——迁移素材换算为规范风格名 + 变体描述。
2. pixel-art 两包明暗基调相反——以 leo 像素复古风浅底为基线，黑底 CRT 写 dark 档。
3. baoyu 全局 footer/logo 禁令——按 leo `rendering_constraints` 既有口径改写。
4. **baoyu-comic 处置（v1 缺失，补记）**：character-template 的"跨页视觉角色一致性"
   思路以思想级借鉴补强 `references/style-continuity.md`（标注来源）；storyboard-template
   与 13/案例·分镜 近似不迁；5 个漫画流派预设超出 PPT 域不迁。无条目入库。

---

## 1. P0 机制批（4+1 项，直改 references）

> P0-1..P0-4 涉及的文件均在 style-index 扫描面内（`style_asset_inventory` 全量
> rglob），**落地后必须重生成索引并提交 generation/条目哈希 diff**（briefs= 计数与
> by_role 计数不变）；仅 P0-5 的 `style-recommendation.md`/`deck-master.md` 在
> `references/` 顶层、不影响 style-index。

### P0-1 轴间组合护栏（兼容矩阵）

- **目标**：`references/styles/00_索引/设计体系.md` §3 配对表之后新增 §3a「轴间组合护栏（Avoid With）」。
- **内容草案**（来源 baoyu dimensions Combination Notes，按 leo 六轴改写；经视觉专家
  逐组核证后修订）：

  | 组合 | 忌配 | 理由 |
  |---|---|---|
  | pixel 质感视觉风格 | editorial 高对比衬线标题 | 像素栅格与高对比衬线笔形互斥（库内无反例） |
  | paper 做旧质感 | minimal 密度（geometric 无衬线仅作提示项，不作硬忌配） | 做旧媒介感 × 极简留白才是冲突核；复古海报存在合法 geometric+paper 组合 |
  | 手绘系图片渲染 | 数据仪表盘视觉风格 | 商务/审计/汇报数据页中手绘介质削弱数据可信度；**教学/科普语境除外**（数学可视化教学风先例） |
  | poly-pop 制式 × `--brand` 单色覆盖 | —— | **提示一次制式差异（"强调=最大对比对"语义将失效），提示后按三层 token 覆盖优先序执行，不设确认门**（对齐"冲突劝阻一次，然后尊重"合同） |
  | 台账档密度（≤6 条档） | 陈述/金句版式（P3/P10/P34/P36） | 容量语义相反，预检即拦 |
  | grid 工程纸质感 | organic 有机插画渲染 | 工程秩序 vs 手绘随意，混质 |

- **纪律**：护栏只做预筛与一次劝阻，不做硬失败；**目标态对齐架构文档 §4.5 bindings
  兼容字段（`rendering_id` + `compatible_mode_ids`），本散文表为 v1 过渡层**，避免
  成为第三份手维护映射。

### P0-2 字体渲染翻译层（重设计）

- **目标**：`references/styles/00_索引/通用设计规范.md` §一.6 与 §一.7 之间新增 §6a。
- **定位修正（v1 硬伤）**：v1 声称"只影响 prepare_slide_prompts.py 注入措辞"是机制性
  错误——脚本不读该文档。**本层定位为"治理说明 + brief 写法约定"**：约定每个
  brief 的 `typography` 字段值在字族名后追加视觉描述语（该字段属机器直注通道，
  经 `compose_style` 透传 + JSON dump 自然进 Global Style 块，零代码改动、不违反
  确定性注入纪律）。落位节奏按"点名命中时顺手补"（同 negative_prompt 渐进先例）。
  写法长度注意：`_style_anchor_block` 字族锚截断 80 字符，描述语控制在一短语内。
- **表结构修正（v1 硬伤）**：v1 五档把字重固化进描述语（"**bold** geometric"），与
  §一.1 三档表情（Whisper/Speak/Shout）冲突。改为**两列参数正交**——字族气质描述
  （去字重词）× 字重词（由 brief 三档表情声明映射 light/regular/bold）。子档补齐：
  等宽档挂"黑体系·等宽子档（仅 labels/代码/数据位）"，衬线系补 quiet/classic 子档
  （博物馆纪念风的 brass serif 不是 editorial 高对比）。

  | 子档（对接全局栈） | 字族气质描述语（无字重词） |
  |---|---|
  | 黑体系 · geometric | geometric sans-serif with perfect circular O shapes, uniform stroke width |
  | 黑体系 · humanist | humanist sans-serif with open apertures, slightly warm details |
  | 黑体系 · 等宽子档（labels/代码/数据位） | precise sans-serif with monospace numerals, 0/O and 1/l clearly distinguishable |
  | 衬线系 · editorial | high-contrast serif with sharp bracketed serifs, magazine display quality |
  | 衬线系 · quiet/classic | quiet classic serif with modest contrast, catalogue gravitas |
  | 手写系 · handwritten | hand-lettered marker strokes, letters that look drawn not typed, imperfect baseline |

- **纪律**：typography 字段仍以身份字族声明为准（§一.6 不动）；描述语是追加措辞，
  字重词永远来自三档表情声明，不进气质描述语。来源标注：baoyu-slide-deck
  `dimensions/typography.md` Font Rendering Instructions 表（按全局栈改写+扩写）。
  若后续要脚本级确定性翻译（档位数据源进代码 + `--font-visual` 旗标，缺省逐字节
  不变），另立代码任务并比照 `--materialize` 先例，不在本批。

### P0-3 质感档标注维度（五档扩七档 + 非穷举声明）

- **目标**：`references/styles/00_索引/设计体系.md` §一末新增小节 +
  `references/style-library.md`「变体第二维度」节末加一行指引（六分组原文在
  style-library.md，不在设计体系.md——v1 位置描述已修正）。
- **内容草案**（v1 硬伤修正：补 glass/glow 档覆盖玻璃拟态风/博物馆纪念风/荧光系；
  判据改"底材质感 + 画面语法合参"——工程蓝图风的网格在元素层不在底面、像素复古风
  底是纯色 flat）：

  | 档 | 判据（底面与语法合参） | 典型风格系 | 忌配（接 P0-1） |
  |---|---|---|---|
  | `clean` | 纯色无纹理底 | 极简/商务/终端 | — |
  | `grid` | 工程纸网格线（底面或骨架语法） | 蓝图/实验室标签 | organic 渲染 |
  | `organic` | 纸纹画布、不完美边缘 | 手账/水彩/温暖手工 | pixel |
  | `pixel` | 块状像素语法（画面层面） | 像素复古/复古电视 | editorial 衬线 |
  | `paper` | 做旧纸、印刷瑕疵、sepia | 博物/vintage/旧学院 | minimal 密度 |
  | `glass` | 磨砂/透明层叠底面 | 玻璃拟态 | pixel |
  | `glow` | 渐变光效/发光底面 | 荧光科技/暗夜氛围 | paper |

- **纪律**（对齐六分组原文全四条）：只作标注与预筛，不新建条目、不占风格配额、
  **不改 variant_of 主维度语义**、无专用 schema 键；**本维度非穷举——档外质感如实
  留空，仅作预筛不硬归类**。档位写进 brief 散文 `canvas.background`（与六分组的
  明度档写 `visual_direction` 分工：明度归视觉方向、质感归画布底面）。已核证架构
  文档无 texture 轴既有规划，新立不构成双真值。

### P0-4 受众密度联动

- **目标**：`references/styles/12_版式库/00_容量档位参考.md` 文末新增「受众密度联动」节。
- **内容草案**（来源 baoyu design-guidelines 受众系统；v1 修正：补三套词表映射与
  冲突仲裁，防与 §二.6 页面角色档/§二.3 活跃构图档打架）：

  | 受众 | 密度倾向 | 页数参考 | 语气纪律 |
  |---|---|---|---|
  | 初学者 beginners | low | 8-15 | 友好图解、大白话 |
  | 中阶 intermediate | balanced | 10-18 | 图文并重 |
  | 专家 experts | balanced/dense | 12-25 | 精确技术图、术语不降级 |
  | 高管 executives | low | 8-12 | BLUF 底线先行，每页回答"So what?"（论证侧对齐 06/结论先行金字塔） |
  | 通用 general | balanced | — | — |

  词表映射行：low ≈ 陈述档（0-1 条）+ 活跃构图 40-60%；balanced ≈ 论点档
  （≤3 条/≤80 字）+ ~78%；dense ≈ 台账档（≤6 条）+ ~90%。
  冲突仲裁：**受众倾向与页面角色档冲突时，页面角色档为下限、受众倾向只收紧不放松**
  （executives 的 low 表现为论点页仍可 ≤3 条但每条更短、deck 页数取参考下限）。

- **纪律**：受众档是默认建议不是确认门；**用户显式指定密度或页数时，本表整体失效、
  字面执行用户数字**（对齐 page-count 询问门合同）；目标态并入架构文档 §4.4/§8.1
  的 `audiences`/`text_density_levels` versioned vocabulary，散文层为过渡（枚举词
  字段化时与架构示例对齐）。

### P0-5 小项打包（信号词 + 反 AI 腔）

- `references/style-recommendation.md` §一「信号映射」末尾补来源词参考（双语/
  bilingual → 双语技术简报候选；组装/说明书/how-to → 说明书图解候选；编目/清单/
  工具目录 → 周期表语法；saas/看板/产品 demo → notion UI 构件），标注"R-55 点名
  落空登记用，非自动路由"。
- 反 AI 腔黑名单（禁 "dive into"/"explore"/"let's"/"journey"）：落 `deck-master.md`
  「确定性检测（check_deck_prose，R-15/R-16）」节使其**可机检**（与 R-15/R-16 同
  通道），散文说明附于该节。

---

## 2. P1 MERGE 批（六组，并入既有 brief）

通用规则（v1 修正后）：
- negative_prompt 增补一律**替换/合并式**（目标顶层内置已全部 5 条顶格），保持
  3-5 条总数——条数是文档纪律，**lint 只查存在性与形状，条数人工核对**；
- `draft_negative_prompts.py` 仅适用于 <3 条参考风格的补齐场景（只在 <3 条时写入），
  **本批全部手工编辑**，脚本仅作形状复核参考；
- 每条增补标注注入通道（§0.3），agent 桥接字段依赖 deck-master.md 摘抄指引同步落地；
- 负面词按 §0.3 视觉化改写纪律；
- 涉及顶层内置的组（B/C/E）标注"受必填字段与条数纪律约束"。

### 组 A · 工程制图系（blueprint / technical-schematic）

- **目标**：`references/styles/01_通用母版/科技数字/工程蓝图风.md`（+ 蓝晒图纸风对齐）
- **light 档跨引（v1 撞车修正）**：库内已有 `工程白图风.md`（白底蓝线制图，
  `#1E3A5F`/`#1E40AF`，视觉风格配对表已登记其锚）——工程蓝图风的 light 场景
  **跨引工程白图风锚点**，不再另建第二份 light 色板（避免同概念双源与色值漂移）；
  在两份 brief 散文中互相登记指引行。
- `rendering_constraints` 真增量（机器桥接通道）：连接线仅直线或 90° 直角；
  cross-section 剖面、isometric/orthographic 投影词表。**dimension 词表不新增**——
  既有 `layout_patterns`/`typography.labels`/`visual_elements.allowed` 三处已覆盖，
  仅并入改写。
- `negative_prompt`（替换式）：`curved connector lines, hand-drawn organic shapes,
  photographic elements` 并入既有词条。

### 组 B · 像素/复古媒介系

- `01_通用母版/艺术表现/像素复古风.md`（桥接通道）：色数规则改写为
  `strictly limited flat palette (about 5-8 hues, anchored HEX list)`——扩散模型无
  精确计数能力，靠 `color_palette` HEX 锚（机器直注）承担色数控制；保留
  `visible pixel grid, dithering for transitions, no smooth gradients`（有效视觉词）；
  负面词视觉化：`anti-aliasing` → `smooth blurry edges, soft vector-like curves`。
  **8x8/16x16 bitmap 字符网格不进图片路线 brief**（图片路线图内禁字 guardrail：
  文字由页面布局后期叠加，生图模型永不渲字）——网格规格落全局字体栈等宽子档
  说明与可编辑/render lane 字体选择（`overlay_text.py`/render lane 用真实字体）。
- `01_通用母版/设计流派/复古视窗风.md`（**真增量最大**；v1 逐字重复修正）：
  `layout_patterns` 增语义化文件名文案（PROBLEMS.EXE / METHOD.PNG 式）、按钮短文案
  （OK/CANCEL/FIX IT/RETRY）、楼梯状像素边缘；"窗口化容器"与既有"每页一扇窗口"
  条目**合并改写**而非并列。negative_prompt 剔除与既有重复的 glassmorphism/smooth
  anti-aliased curves，仅以视觉化措辞并入 `deep soft drop shadows and 3D bevel
  effects (neumorphism)` 一条真增量。**注意：该词表上游为 AJ 衍生（无授权源），
  词表重新设计而非逐字照搬**（§0.2 分层口径）。
- `08_图片渲染/古董专利文档.md`（**落点格式修正**：08 轴无 `visual_elements.allowed`
  键，词表写入 paste-ready 段落正文或「线条·纹理·深度」表——两者均机器直注）：
  增探险日志词表节（罗盘玫瑰、标本绘图、绳索/皮革/黄铜饰件、老照片式相框）。
  **复古海报.md 不加**（其定位是 1950s-70s mid-century/Saul Bass，19 世纪博物学
  探险美学错位稀释身份）。

### 组 C · 手绘系（v1 三重自洽破坏修正）

- **`教学课件风.md` 移出本组**：其身份是 evidence-supported 学术教学（白底合法、
  允许真实照片证据、navy+amber 学术色板），手绘媒介规则与其自相矛盾——手绘气质
  属渲染锚 `08_图片渲染/手绘笔记.md`，媒介规则落锚文件而非风格 brief 本体。
- `references/styles/手绘白板风.md` + `手绘技术解释风.md`（顶层内置，替换式增补，
  措辞按各自 palette 改写）：`rendering_constraints` 增——色块填色不填满轮廓、
  全线条 slight hand-drawn wobble、连接线手绘波浪感、概念性抽象图标而非写实场景、
  页底可放一条加粗居中 takeaway；色数措辞按各风格色彩系统写（手绘白板风是
  marker ink 六色系 → "彩色笔标注每页同屏 ≤4 色"，不套"马卡龙"词）。negative_prompt
  以替换式并入（两者均已 5 条顶格）。
- `01_通用母版/艺术表现/粉笔黑板风.md`：**5 色粉笔 HEX 定位为"粉彩粉笔层
  （chalk pastel layer）备选色板"**，不直接进 color_palette 四角色——rule 中写明
  "同页出场 ≤4、一律以粉感透明度/噪点出场、不做饱和填充"（HEX 本身满饱和，
  粉感靠透明度实现），声明 poly-pop 变体制式归属；与既有"永不饱和填充;强调只
  用于下划线/圈注"规则兼容。rendering_constraints 增 imperfect baseline、粉笔尘
  与板擦痕。

### 组 D · UI/SaaS 系（notion）

- `10_品牌身份/notion.md`：新增「版式语言」小节（card-based 卡片布局、checkbox/
  toggle、tag/label chips、面包屑层级、**"一张卡片/按钮呈高亮浮起态、其余处于
  静息态"的静态交互暗示——no cursor arrows**）。知情标注：该文件是 field-style
  文档（`load_brand` 只抽 HEX/字体/语气），此节属 agent 参考层无机器注入。
- `02_行业内容域/互联网科技/SaaS介绍风.md`：**UI 构件词表重心放这里**（`layout_patterns`
  是机器直注通道）——增卡片/chips/状态标签构件入 layout_patterns。
- 不新增 SaaS 风格条目（对齐"身份轴管 VI、视觉风格管长相"分工，视觉专家正向确认）。

### 组 E · 插画/水彩系

- `01_通用母版/艺术表现/吉卜力手绘风.md`（v1 身份稀释修正）：增补降级为
  **"叙事页可选变体"**——"scenery 为主，叙事页可引入单一中心角色（不覆盖主身份）"；
  拟物容器与既有奶油圆角卡片**分场景登记**（章节页拟物、内容页卡片）；**角色画法
  （中心角色+伴侣生物+漂浮物件）移 `08_图片渲染/幻想动画.md`**（渲染管画法的既有分工）。
- `references/styles/复古扁平插画风.md`（顶层内置，替换式）：增几何简化词表
  （树=棒棒糖/三角形、建筑=带网格窗矩形、人物=极简几何形）、2.5D 自由透视、
  深度靠层叠遮挡、放射线太阳/胶囊云/圆点星星装饰件。
- `01_通用母版/艺术表现/水彩晕染风.md`（v1 重复修正）：既有 rule/avoid/constraints
  三处已含 no hard edges——**负面项剔除**；正向措辞改写为 `colors bleed past
  masked/taped edges, visible brush strokes`（消除"bleed beyond sharp edges"歧义）。
- `01_通用母版/艺术表现/黏土定格风.md`：增 fingerprint marks、挤出黏土立体字。
- `01_通用母版/几何装饰/波普艺术风.md`/`胶囊卡波普风.md`：既有 allowed 已含
  halftone——只增 POW/BANG 拟声爆字、action lines。

### 组 F · 轴侧文件（08/11/13/00_索引）

- `08_图片渲染/剖面技术图.md`（写入 paste-ready 正文）：增图解语法——每个部件
  必须标注、方向性流动箭头、编号步骤序列。
- `08_图片渲染/3D 等距.md`（同上落点）：增"地图场景"节——微场景地标、路径连接、
  悬浮标签、legend 与比例尺。
- `11_图表语法/用户旅程.md`：增 winding 变体——S 曲线 + 里程碑旗标 + 障碍/助力者
  侧元素 + 终点地标。
- `13_页面语义/案例·分镜.md`：增画格 + speech/thought bubbles + caption boxes +
  可选音效字 + 画格编号词表。
- `00_索引/构图词汇参考.md`：补 Z-Pattern 阅读动线一行（已核证现无此词，真增量）。
- `00_索引/通用设计规范.md` §一.7 全局字体栈：霞鹜系（LXGW Bright）补进编辑系/
  手写系备选。**知情标注：仅可编辑/render lane 生效（`assets/render-fonts/` 需同步
  登记 NOTICE），与图片路线注入无关**。
- `01_通用母版/商务专业/稳重商务风.md`（+ CEO高级商务风）：`color_palette.rule` 增
  语义色对约定（Success/Alert 类语义色不占强调色配额，仅用于状态语义）。
- `01_通用母版/极简排版/极简风.md`：`rendering_constraints` 增量化硬约束——陈述页
  每页文字 ≤10 词、四边留白 ≥15%、数据可视化仅单色或灰度（视觉专家正向确认与
  §二.6 兼容且为收紧方向）。
- `references/deck-master.md`：组页规范加 agent 桥接摘抄指引一句（§0.3）。

### P1 验证（每批 commit 后）

```sh
python3 leo-ppt-generator/scripts/lint_style_briefs.py      # briefs= 计数不变、形状全绿
cd leo-ppt-generator && python3 scripts/lint_layout_grid.py # 组 F 后（技能目录内）
cd leo-ppt-generator && runtime/.venv/bin/python scripts/capability_manifest.py \
  --style-index --index-out references/styles/generated     # 重生成并提交哈希 diff
cd leo-ppt-generator && runtime/.venv/bin/python scripts/capability_manifest.py \
  --style-index --check                                     # 只读校验（--check 须与 --style-index 同用）
cd leo-ppt-generator && runtime/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

**生图样张抽检（v1 缺失，v2 新增）**：六组完成后每组抽 1 个代表风格 × 2 页
（封面 + 内容页，共约 12 张），走 `image prepare --sample-binding` → worker →
visual-qa 轻量路径。判定口径对齐 `references/visual-qa.md` §四阈值 + 样张继承四维
+ required_text 白名单逐字。重点观察：像素色数与边缘观感、复古视窗容器语法成形、
水彩措辞改写后不再出硬边、notion UI 构件可辨。**抽检不设阻断门**（词表效果允许
迭代），结果回写各 brief `reference`/CHANGELOG 作为词表有效的首份证据。

---

## 3. P2 NEW 候补批

### 3.1 源登记行（写入 `references/style-candidates.md`「择优杂项」段末尾）

> **登记纪律**：`test_style_candidates_doc.py` 合同 LINE_BUDGET=140 行，当前文档
> 127 行——**登记块控制在 ≤10 行**，提交前必跑该单测；同步把表头"大型矿 9 + 择优
> 杂项 11 = 20 源"改为"…12 = 21 源"并更新段头括号描述。

> - **baoyu-skills**（MIT，JimLiu/baoyu-skills，快照 6b7a2e4 2026-07-03；AJ 衍生
>   子集按无授权源思想级）｜实收：机制层 4 项 + 既有 brief 词表增强六组（直改
>   references，无风格条目，明细见台账）｜净新余量：≈15 风格 + 7 版式/图表语法｜
>   精选：高价值 7 项（4 风格 + 周期表/故事山/dense-modules 三配方族）｜触发：
>   双语、无字说明书、编目合集、高密度种草点名落空（R-55）｜去重：blueprint 系
>   light 场跨引工程白图风不另立；corporate-memphis 立独立 family 不挂 memphis；
>   cyberpunk-neon 与合成波/蒸汽波消歧；knolling/ui-wireframe 落 08 轴、subway-map
>   落 07 轴；dense-modules/retro-popup-pop 词表系 AJ 衍生（无授权），入库时思想级
>   重设计；P2 条目散落各轴 + reference 标注，不建 `NN_来源_baoyu/` 整迁目录
>   （awesome-ppt-skills 思想级先例）｜台账：本方案文档；金样板先例
>   `samples/reference-golden/baoyu/`（入库时建，自生成性质，README 对齐 gorden
>   字段：来源/生成方式/回源路径/使用纪律）。

### 3.2 高价值条目骨架（触发入库时按扩展模板填写；v2 补"最相近既有风格"列）

| 建议名 | 轴/目录 | family | best_for 草案 | 触发信号 | 最相近既有风格 + 差异 |
|---|---|---|---|---|---|
| 双语技术简报风 | 01/设计流派 | family:bilingual-brief | 涉外汇报/双语技术讲解：EN TERM 中文对照、每页 3-5 实质文字框、页底 KEY QUOTE 框 | "双语/bilingual/中英对照"落空 | vs 钴蓝网格简报风：双语对照结构 vs 单语网格排版 |
| 说明书图解风 | 01/极简排版 | family:instructional | 无字化分步指令：步骤编号+分解图+人形比例参照 | "组装/说明书/how-to"落空 | vs 手绘技术解释风：无字图解 vs 手绘文字讲解 |
| 博物图鉴风 | 01/东方意蕴邻位评估 | family:naturalist | 科学教育/历史：羊皮纸+铁胆墨+编号图解+拉丁学名标签+cross-hatching | "博物/标本/图鉴"落空 | vs 博物馆纪念风：科学插图/编号图鉴 vs 展陈纪念载体 |
| 实验室标签风 | 01/科技数字 | family:lab-label | 规格对比/精密数据：坐标系编号+尺规刻度+荧光笔错位叠印+十字准星 | "实验室/规格对比"落空 | vs 数据仪表盘风：标注系统语法 vs 数据大屏呈现 |
| 周期表语法 | 12 版式库/13 参考·文献 | — | 编目形状：同构条目×类别归属 | "清单/目录/编目"落空 | vs P33 Team_Grid：周期表色编码+分组空档语法 |
| 故事山语法 | 07 信息图/06 故事弧配对 | — | 叙事张力曲线：坡度承载语义+峰=高潮+首尾基线 | 叙事结构点名落空 | vs 时间线：张力曲线 vs 时序直线 |
| dense-modules 配方族 | 12 版式库 + 4 风格打包 | family:dense-guide | 高密度种草/避坑：模块化原型语法，配实验室系 4 风格 | 小红书高密度点名落空 | vs 台账档密度：模块原型+坐标编号语法 vs 纯行数上限；**AJ 衍生，思想级重设计后入库** |

**双语条目专项条款**（生图专家意见）：骨架补两行——①约束声明"高文字密度双语页，
文本框 >4 或含长英文术语时优先评估 TF-2 或可编辑路线（文字层走 overlay/HTML，
图像层只出媒介底图）"；②入库门加"双语类条目样张必须走图像 lane（`image
sample-record`），render lane 金样板不构成文字保真证据"。

### 3.3 中低价值排队

corporate-memphis（独立 family 边界）、折纸几何风、cyberpunk-neon（家族消歧）、
knolling（→08）、ui-wireframe（→08）、jigsaw、iceberg、bridge（并 13/落地·下一步
作变体）、kawaii、lego-brick。

### 3.4 入库门（v2 对齐补货门五步全流程）

逐条对齐 `style-candidates.md` 补货门：①**信号确认**（点名落空持续出现）→
②**四重去重**（概念级 SKIP／色板指纹 family_duplicate／同板并入 variant_of／
跨源同名同族合并）→ ③**许可核验**（Jim 原创直引 MIT 口径 / AJ 衍生思想级重设计）→
④**金样板三页（自生成：用 baoyu 风格 prompt 由 leo 管线产三页，非上游实体复制，
README 对齐 gorden 字段）+ 视觉风格配对预览行** → ⑤**六条治理 lint 全绿（风格级
四条 + 仓库级 `lint_render_templates`/`lint_skill_structure` 两条）+ audit 簇数门
（当前基线 10、回退门槛 >20）** → style-index 重生成 + `--style-index --check` →
重跑风格相关 eval 子集（对照 known-issues 在案存量/摆动清单零新增）→ CHANGELOG。
金样板页型：封面/内容/图表（复杂页）。别名登记不与既有 ~40 组口语别名撞车。

---

## 4. 验证命令清单（v2 全部实测修正）

```sh
# 环境前置（known-issues B-2 纪律：脚本用 runtime/.venv 解释器；索引命令依赖 jsonschema）
cd leo-ppt-generator/runtime && uv sync

# 结构 lint（系统 python3 可跑，纯 stdlib）
python3 leo-ppt-generator/scripts/lint_style_briefs.py
cd leo-ppt-generator && python3 scripts/lint_layout_grid.py

# P0-5 涉及文档时补两条（style-recommendation.md 在 lint_style_index 链接检查面内）
cd leo-ppt-generator && python3 scripts/lint_style_index.py
cd leo-ppt-generator && python3 scripts/lint_style_governance.py

# 索引（--check 必须与 --style-index 同用，实测独立使用 exit 2）
cd leo-ppt-generator && runtime/.venv/bin/python scripts/capability_manifest.py \
  --style-index --index-out references/styles/generated
cd leo-ppt-generator && runtime/.venv/bin/python scripts/capability_manifest.py --style-index --check

# 单测（P2 登记批必跑 test_style_candidates_doc，行预算 140）
cd leo-ppt-generator && runtime/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'

# 评测（run + report 都要；解读口径：相对 known-issues 在案存量/摆动/model_gating 清单零新增失败）
cd leo-ppt-generator && skill-up run evals/eval.yaml && skill-up report evals/eval.yaml

# 仓库级
rg -n "TODO|FIXME" --glob '!AGENTS.md'
git diff --check
```

P0/P1 为 references 文档与 brief 字段增补，不改风格名/目录结构/评测断言依赖面
（已核 style-* 与 style-index-* 判官均自包含），评测预期零新增失败。bench/ 与本
方案无关（8 维交付基准，不依赖本库风格资产）。

## 5. CHANGELOG 条目草案

```markdown
### Changed
- leo-ppt-generator: 风格库吸收 baoyu-skills（MIT，JimLiu 原创部分直引、AJ 衍生
  子集思想级）机制层——轴间组合护栏、字体渲染翻译层（brief 写法约定）、质感七档
  标注维度、受众密度联动（P0 批，00_索引/版式库支撑文档 + style-library.md 变体
  维度节指引行）。
- leo-ppt-generator: 既有 brief 词表增强六组（工程制图/像素复古媒介/手绘媒介/
  SaaS UI 构件/插画水彩/轴侧文件），负面提示词替换式增补（P1 批）。
### Added
- leo-ppt-generator: style-candidates 登记新源矿 baoyu-skills（≈15 风格 + 7 版式
  语法余量，按使用信号触发入库）；NOTICE「移植 / 改编来源」补 baoyu-skills 行。
```

## 6. 风险与回滚

- **P0 风险**：设计体系/通用设计规范是上位护栏 → 每项独立 commit；护栏均为预筛+
  一次劝阻非硬失败；散文表均已标注"架构文档目标态过渡层"防双真值。
- **P1 风险**：negative_prompt 条数 lint 不机检 → 替换式增补 + 人工核对；生图词表
  效果依赖样张抽检环节取证。
- **P2 风险**：新条目撞车 → 登记行去重边界 + 入库门四重去重双检；AJ 衍生许可
  红线 → 思想级重设计硬性前置。
- **回滚**：三批独立 commit 序列，`git revert` 单 commit 粒度；**任一触及
  references/styles/ 的 commit 被 revert 后必须重跑 `--style-index --index-out`**
  使 `--style-index --check` 通过；`references/styles/generated/` 保持 untracked、
  不提交（重生成产物）。
- **生图效果不确定性**：若不执行样张抽检，则词表效果未验证、依赖后续真实任务
  反馈——此风险须在 CHANGELOG 如实登记。

## 7. 执行顺序与依赖

0. **前置**：确认工作树干净或与在途批次文件域互斥（当前有并行会话在途改动）。
1. **P0**（P0-1+P0-3 同文件同 commit；P0-2、P0-4、P0-5 各一 commit；落地后即重生成
   索引提交 diff）→ 2. **P1 六组**（组 A-F 无相互依赖可并行；每组 commit 后跑
   lint；全部完成后重生成索引 + 单测 + 样张抽检）→ 3. **P2 登记**（1 commit，
   行预算内，跑 test_style_candidates_doc）→ 4. **P2 按信号逐项入库**（长期，
   事件驱动，每条走 §3.4 五步门）。

## 8. 专家评审记录（v2 修订依据）

五位专家并行评审（2026-09-06），全部判定"需修订后通过"，无否定三批架构意见：

| 专家 | 关键发现（v1 → v2 处置） |
|---|---|
| 治理合规 | negative_prompt 3-5 条 lint 不机检且顶层已 5 条顶格（→ §0.1/组 B/C/E 替换式）；"索引无 diff"错误（→ P0 头注 + 重生成提交 diff）；入库门五步/六条 lint 缺漏（→ §3.4）；P0-2 生效载体矛盾（→ 重设计）；登记行字段对齐先例、骨架表补区分列、架构文档对齐句、金样板页型/簇数门数值（→ 采纳） |
| 视觉设计 | 教学课件风三重自洽破坏（→ 移出组 C，手绘规则落 08/手绘笔记）；质感五档覆盖不足+判据混杂（→ 七档+非穷举+合参判据）；字体层等宽悬空+字重固化（→ 两列参数+子档补齐）；工程白图风撞车（→ light 档跨引）；粉笔 5 色与 rule 冲突（→ 粉彩粉笔层定位）；复古视窗/水彩/波普逐字重复（→ 剔除改写）；poly-pop×--brand 升格确认门（→ 一次提示后执行）；密度三套词表无映射（→ 映射行+仲裁句）；吉卜力身份稀释（→ 叙事页可选变体+画法移渲染锚）；复古海报词表错位（→ 只落古董专利文档） |
| 生图工程 | P0-2 文档≠注入（→ brief 写法约定生效路径）；注入通道白名单（→ §0.3 对照表+deck-master 摘抄指引）；负面词有效性（→ 视觉化改写纪律）；bitmap 网格与图内禁字 guardrail 冲突（→ 移 render lane）；色数愿望式（→ HEX 锚承担）；08 轴无 visual_elements 键（→ paste-ready 正文落点）；双语 TF-2 降级+图像 lane 样张（→ §3.2 专项）；P1 样张抽检缺失（→ 新增环节）；hover state 措辞（→ 视觉化改写）；LXGW 仅 render lane（→ 标注） |
| 许可供应链 | AJ@WaytoAGI 衍生例外（dense-modules/retro-popup-pop/三风格，无授权）（→ 思想级硬性前置）；MIT 内容级分层（→ §0.2）；NOTICE 版权行缺失（→ 新增）；owner 大小写 JimLiu+快照 commit（→ reference 格式）；baoyu-comic 处置缺失（→ §0.4 补记）；P0-2 来源标注（→ 补）；金样板自生成性质+README 字段（→ §3.4）；不建来源目录决策（→ 登记行注明） |
| 评测门禁 | `--check` 不可独立用（→ 修正命令）；"P0 无 diff"与生成逻辑矛盾（→ 修正）；jsonschema 缺失须 uv sync+venv 解释器（→ §4 前置）；单测门禁缺失含 test_style_candidates_doc 行预算 140（→ §3.1/§4）；draft_negative_prompts 仅 <3 条场景（→ §2 通用规则）；回滚后索引重生成（→ §6）；目标文件全路径（→ 各组）；skill-up report+known-issues 口径（→ §4）；六 lint 清单（→ §4）；工作树卫生（→ §7 第 0 步） |

## 9. 实施偏离记录（2026-09-06 执行批）

执行中发现并处置的偏离（同步补记 CHANGELOG"计划内未落地项"）：

1. **反 AI 腔族编号 R-24 → R-27**：R-24 已被 image-text-composition 协议占用，
   R-25/R-26 亦已占用，族 m 顺延 R-27。
2. **5 个 intake 产物文件的增补撤销**：工程白图风/吉卜力手绘风/古董专利文档/
   剖面技术图/notion.md 系 `intake_*.py` 幂等产物（test_intake_* 断言磁盘=脚本
   重生成，手工增补即 drift），增补全部撤销、测试恢复全绿。价值承接：
   - 工程白图风 dark 反向跨引 → 单向指引保留在工程蓝图风侧；
   - 吉卜力叙事页角色变体 → 角色画法已在 08/幻想动画.md paste-ready（来源注已
     改写指向本节），容器语言转 P2 候补词表；
   - 古董专利探险日志词表 / 剖面技术图图解语法余量（方向箭头/编号步骤）→
     登记进 style-candidates baoyu 行余量，按信号触发；
   - notion 版式语言 → 卡片/chips/面包屑/浮起态已由 SaaS介绍风 layout_patterns
     （机器直注）承接，checkbox/toggle 登记候补余量。
3. **环境注意**：`uv sync` 会按 lock 移除手动增装的 resvg-py/playwright（pyproject
   未声明），执行后需 `uv pip install resvg-py==0.5.0 playwright==1.62.0` 装回。
4. **commit 策略调整**：工作树与并行批次（渠道目录/style-model 更新）混杂且组间
   文件域交叉，本批未形成分批 commit；提交编排留给收口会话，至少按 P0/P1/P2
   三批拆分并在触及 references/styles/ 的 commit 后重跑 style-index 重生成。
