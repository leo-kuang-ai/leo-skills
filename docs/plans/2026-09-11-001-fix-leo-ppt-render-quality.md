---
title: PPT 渲染质量问题核验与修复记录
status: completed
implementation_status: verified-local
target_repo: /Users/kuang/knowledge/leo-skills
---

# PPT 渲染质量问题核验与修复记录

本文承接用户提供的样张评审和根因分析，先保存问题、核验后的修正及实施边界，再记录实际代码修复与验证。原分析是待核验的问题报告；其中模型评分、渠道历史状态和样张观感不自动升级为当前事实。本文不存储原消息中的临时签名 URL 或访问凭据。

当前状态以文末「最终验收」为准；前面两轮的数量、generation 和未完成项是历史快照。

## 问题与结论修正

### 1. 版式推荐与实际渲染能力不一致

原报告指出：版式语义丰富，但 HTML 模板覆盖不足，渲染可能退化成标题与列表。问题方向成立，但“37 个 P 码，37 选 7”的统计不准确。前轮源码核验显示基线为 36 个 P 码加 6 个命名版式，共 42 个；工作树已有 8 个新增模板和绑定，不能将其冒认为本次成果。正式分配器与 content_projection 已检查 backend，未发现自动回退 body-basic 的实现；需核验轻量推荐入口和下游消费者是否遵循同一资格条件。

优化：复用现有 backend 资格规则，对不可实现的候选明确排除或报错；不使用无意义的绑定来填充覆盖率。模板的 slot、角色、几何及真实可渲染结果一起验收。

### 2. 风格资产与渲染消费脱节

原报告指出 320 个 brief 多为提示词，咨询金字塔画廊 theme 为 {}，因此“没有设计系统”。这一推断过强：当前已有 canonical/themes、compute_effective_theme 与 compose_design；既有质量主方案规定 theme 独占精确 token、layout 独占几何。brief 缺少 token_sidecar 不能证明系统没有 token；给每份 brief 再复制一套 token 会制造双真值。

优化：让画廊消费既有 canonical theme，核验模板的实际主题注入，修复占位或旁路。SHA256 金样板是编译回归基线，不是审美认可；不能将空主题样例称为咨询级标准。已有工作树中的 sidecar 和模板改动须保留并兼容处理，不直接重置。

### 3. Mermaid 输出与静态 SVG 策略冲突

原报告的 strict 初始化与 foreignObject 拒绝存在冲突线索，但“所有主力图型不能画”“加一行全部修好”缺少逐图型证据。工作树已有 htmlLabels 配置、foreignObject 转换和 SVG 白名单扩展，尚需真实 Chromium 验证。

优化：用 flowchart、中文多行及边标签等本地图验证输出和安全边界；修复有复现证据的故障。保持脚本、外部资源和不受控 HTML 拒绝，不以静默丢标签换取通过。

### 4. 机器检查被当作设计验收

原报告中的“旧版因稀疏 FAIL、新版 PASS”本身不能证明误报；空白像素占比也不等同布局占用面积。文件体积受编码和背景影响，不能可靠代表内容或视觉质量。现有文档还有视觉复核要求，“用户是唯一设计防线”并不准确。工作树新 DESIGN-01 已提供象限提示，但完全空象限可能跳过失衡判断。

优化：区分渲染事故、可读性和设计提示；修复零象限漏检及不合理的硬失败。明确 PNG 体积、墨迹比例只是代理指标，不给出自动审美分数，不用堆卡片或填满页面代替信息层次。

### 5. 渠道尺寸约束与健康探针失真

原报告的欠费、缺凭据及中文乱码属于当时运行记录，不能外推当前可用性；无原生 16:9 也不等价所有图片路线不可用。当前 probe 在无合法 16:9 候选时仍返回 2560×1440，会将已知不支持的尺寸传到下一层；L1 配置、L2 dry-run 与真实生成必须分开报告。

优化：找不到合法比例时明确报告 unsupported；尺寸约束与执行器一致，不猜测模型档位。不进行未授权的付费生成或改写 credentials。

### 6. 项目 bundle 扩展与模板采用边界

原报告把环境变量注入称为治理逃生口，但项目扩展本身未必违规，需区别可发现、可信采用和可发布。现有 asset_resolver、style_pack 与模板合同应作为唯一机制，不能另建平行准入系统。

优化：检查模板加载与已有 resolver 的关系，堵住有证据的旁路；新增模板继续经过已有结构、绑定、catalog 和本地渲染验证。工作树原有新增资产的作者与历史验证不归本次所有。

## 根因合成

可靠的根因表述是：能力声明、消费链和验收证据没有在所有入口一致贯通。渠道限制可能触发降级，有限模板和未消费的主题可能削弱表达，代理检查又可能被错误解释为设计通过。这是相互独立的条件组合，不能写成已经证明的唯一线性因果链，也不能免除执行者在内容组织、模板选择、失败处理和状态汇报上的责任。

## 样张评审过程本身的问题

- 原评审提示词先植入“像 Word”“图表像水印”“刚按批评重做”等判断，会诱导评审迎合。应先独立检查成图，再比较修复前后，不提前提供期望分数。
- 原工具输出包含“刻度推测，最顶部未见或截断”，后续却被汇报为“刻度齐全已确认”；截断的评分回复也不足以证明 8/10。应区分直接观察、推测与未验证。
- `334→75`（应用数）、`1268→554.5`（CPU 核数）、`1893.11→934.63`（内存 GB）若共用同一绝对数值轴，会引入不同单位不可比较的问题。应按单位分面，或明确各自分母后比较下降比例。`80%+` 的效率指标不能未经来源证明与前三项资源缩减率互换。
- `107.7 万 HKD/年` 与 `20.2 万 HKD/年` 需要各自期间、汇率、扣减项与来源；确定性渲染仅保证输入稳定呈现，不保证财务推导正确。现有材料不足以重新确认这些业务数字。
- 留白少、卡片多不必然更专业；模型评分、PNG 文件变大、哈希稳定都不能替代信息组织、阅读路径、数据语义和投屏可读性验收。

## 实施与验收

1. 保存本记录，冻结本次修改前状态；保留既有 dirty 文件，仅增量修复。
2. 修复渠道探针的无解尺寸分支，并验证合法、不合法与 dry-run 状态。
3. 核验轻量版式推荐 backend 准入，补齐缺失的过滤与可解释输出。
4. 修复画廊主题消费，复用 canonical theme；实际渲染核验。
5. 复现 Mermaid/SVG 边界问题及 QA 代理指标问题，逐项修复并做针对性回归。
6. 核验 bundle 模板加载的既有信任边界；更新文档和 CHANGELOG，审阅本次增量。

验收以实际运行命令和结果为准。样张视觉质量需要实际观察，不能由 lint、哈希或模型的 3/10 → 8/10 自评分替代。本任务交付本地文档及代码，不包括继续制作原 14 页 PPT、提交、推送、发布或付费调用。

## 实施结果

本轮已处理六类问题中的可确认实现缺陷。修改前 HEAD 为 `db2854ac4c4a7fe5fddfa3e9a879257a19b67497`，沿用分支 `leo-2026-09-04-update-style-model`。预存的模板、P 码绑定、schema 等修改保留，未冒认为本次新增。以下结果仅指本轮增量。

| 问题 | 本轮落地 | 验证依据 |
| --- | --- | --- |
| backend 未贯通轻量推荐 | `suggest_layout.py` 支持 CLI/JSON backend，评分前过滤无声明候选，输出实际绑定；未指定明确标记未检查 | 旧实现忽略 backend 的红测试与修复后回归 |
| 无合法比例仍给非法尺寸 | `provider_health.py` 按约束求解精确 16:9，无解返回 `aspect_ratio_unsupported`；清除继承的其他渠道参数；缺凭据明确标记；L1/L2 不通过不进入 L3 | 无解、菜单外合法尺寸、环境隔离、缺凭据和 L3 拦截回归；真实 L2 dry-run |
| 风格主题未进入页面 | `generate_style_gallery.py` 通过 resolver 计算 canonical effective theme，同时传给 chart/page；九个 direction 占位替换成既有特征描述；正文样例标为主题预览 | canonical theme 等值检查、真实渲染、18 风格 × 3 页重生成 |
| Mermaid 静态 SVG 冲突 | 顶层与 flowchart 同时关闭 htmlLabels，保留原生 SVG 换行；删除原有手工 HTML 标签转 text 的近似转换；仅移除装饰阴影；加入时序图安全静态属性；阻断浏览器外部资源请求 | 本地 Chromium：flowchart、graph、mindmap、sequence、state、class、er、pie、xychart；中文标签与静态安全边界回归 |
| 图表主题映射只加载不消费 | canonical effective theme 使用治理表，补齐 XY 图表标题、两轴标签、标题与轴线颜色；不再把 on_primary 当暗底图表文字 | 暗色主题红绿测试；重生成后查看 `科技暗色风/thumb-chart.png`，标题、轴名与刻度可见 |
| QA 代理指标误报与漏检 | 文件体积只作 WARN；近乎纯色继续 FAIL，稀疏墨迹改复核提示；按 RGB 差异而非亮度区分同亮度色块；包含零象限失衡 | 稀疏标题、同亮度双色、单象限孤岛、纯色空页和退出码回归 |
| 裸模板遮蔽与 HTTP 绕行 | 模板通过 catalog resolver 校验 manifest、lane 和可信根，再读同目录 HTML；标准 id 校验覆盖带前缀路径；HTTP 拒绝直接目录入口 | 部分 bundle 遮蔽、非法 slug、目录绕行、symlink 越界、正式入口与隔离安装回归 |

### 复现与检查记录

- `runtime/.venv/bin/python -m unittest tests.test_provider_health tests.boundary.test_suggest_layout`：初次 14 项中 5 FAIL、1 ERROR，精确捕获忽略 backend、无解尺寸、缺凭据及跨渠道参数继承；修复后通过。首轮环境隔离断言曾打印进程环境，随即收窄为布尔断言；最终持久化日志只保留修复后的脱敏结果，不复制该原始失败输出。
- theme/QA/SVG 第一组 19 项检查：修复前 5 FAIL、1 ERROR，修复后通过。
- Mermaid 浏览器补充探针：仅 flowchart.htmlLabels=false 时有 2 个 foreignObject，加顶层 htmlLabels=false 后为 0。原生 SVG 保留 `<br/>` 对应的 tspan 行；标签匹配按解析后的文本检查，不错误要求文字不能跨 tspan。
- 暗图主题测试：修复前标题颜色为 `#0B1220`，而应取 `text=#E6EDF7`，红测试已复现；修复后标题和两轴走治理角色。
- 渠道 L2 实测：qianxing 返回 `aspect_ratio_unsupported`；zhipu 为 `1792x1008`，ark 为 `2560x1440`，二者参数 dry-run 通过。整条体检因 qianxing 不支持返回 1，属于预期拒绝，不写成三渠道可真实生图。

最终检查和脱敏日志位于 `.spec-first/workflows/spec-debug/leo-skills/render-quality-20260911-local/`。源码按最终工作树复验；结果来自本地实际命令转录，不代表外部审阅或真实渠道验证。

验证摘要：[verification-run-summary.json](../../.spec-first/workflows/spec-debug/leo-skills/render-quality-20260911-local/verification-run-summary.json)。声明一致性校验：[closeout.json](../../.spec-first/workflows/spec-debug/leo-skills/render-quality-20260911-local/closeout.json)，返回 `verified / all-claims-consistent`，仅覆盖所记录的本地验证和定向自审。

| 最终检查 | 结果 |
| --- | --- |
| provider / suggest / QA / chart / SVG / template resolution / page 回归 | 59 项通过，退出码 0，无 skip |
| theme / adoption / library bundle / capacity / gallery 集成 | 38 项通过，退出码 0；包括主动模拟缺后端和漂移的负向测试，其 WARN/STALE 是预期输入 |
| 风格 lint | 320 briefs，0 errors，0 warnings |
| 版式 lint | 0 errors |
| 模板合同与 render lint | 各 15 templates，0 errors |
| 画廊重生成 | 18 个风格、54 张 PNG；10 个内置风格消费 canonical theme，8 个历史家族明确保留兼容预览 |
| 画廊 `--check` | 18 风格重渲染与输入/PNG 哈希一致，退出码 0 |
| catalog | 556 entities，generation `cc30339bff1d3b888f51cfda7f7164ed`，reason_code `none` |
| `git diff --check` | 本次包及文档范围通过，退出码 0 |

### 第一轮覆盖边界（历史快照，后续增量已推进）

当前实际清单为 **42 layouts、15 HTML 绑定、其中 7 个带 structure 声明**。另外八个预存 pro 模板的 slots、几何和内容投影尚不能据绑定数量宣布完成；例如 P20 的旧 rows slot 与新 kpis 输入存在语义差异。本轮选择“按 backend 区分可实现候选”这一修复路径，没有冒充已实现全部高频 P 码。

本轮没有给 320 个 brief 批量复制 token，没有把八个无 theme 绑定的历史家族伪装成完整换肤；已有咨询 sidecar 原样保留但不成为新消费链真值。对 pro 模板硬编码字号和颜色的全量重构、完整主题家族覆盖与整册视觉验收仍需后续专门验证。

未运行付费 Provider 生成，未复核原 14 页 PPT 的全部业务数字，未进行独立设计师或用户验收。canonical 画廊只是主题与编译回归预览；本轮看到的正确换肤和可读轴标签不代表达到某个咨询公司的审美标准。未提交、推送或发布。

质量收尾为当前 Agent 对本次增量的定向自审，非独立评审；因重叠预存修改跳过文件级自动简化，避免重写其他作者的工作。CHANGELOG 已同步。

## 后续完整修复增量（2026-09-11）

- 新增 `template_inputs.py` 共享模板输入校验；`content_pack.py` 支持单行 `结构数据: {...}`，拒绝重复键、非法 JSON、非有限数值、重复来源与未知字段。
- `content_projection.py` 将显式结构按 manifest 形状物化，保留对象和原始文字；数字覆盖只检查实际绑定字段，直接渲染也走同一校验。
- 八个 pro 模板与 layout 的 regions、slots、structure、notes 已对齐；修复封面、对照、表格、引文、时间线的真实 DOM/数据缺陷，统一消费主题字体、颜色和几何变量。
- `render/page.py` 增加入口数据校验、几何注入、脚本错误与字体缺失报告；`render/chart.py` 增加受限 XY 图表尺寸、标签字号和柱体数值标注选项。
- 新增 8 个 canonical theme 绑定历史画廊家族，加入固定版本 Noto Serif SC 离线字体；18 风格画廊重生成与 `--check` 通过，catalog generation 为 `3fa9d582a7fdd4914e0a875d81aaa339`（565 entities）。

本轮验证：结构化内容、旧内容包兼容、布局准入、隔离 bundle、画廊及渲染回归共 90 项通过；八模板 × 浅/暗主题端到端浏览器渲染通过；15 个模板合同 lint、render lint、版式 lint、320 brief lint、`git diff --check` 全部通过。未宣称真实 Provider 生图、14 页业务数字复核、独立设计师验收或提交/推送/发布。

### 后续收口增量（2026-09-11）

针对上述覆盖边界又完成一轮确定性修复：

- `render/page.py` 不再吞掉表格列数/版式几何错误，统一返回 `layout_profile_invalid`；
  页面 JSON 与结构数据共用重复键、非有限数值、未知字段校验，保留既有 `page_no`
  元数据兼容。
- `template_inputs.py` 将 `enum` 归一为 JSON Schema 字符串枚举，SVG 证据只提取
  `<text>` 文本，不把坐标、颜色、装饰数值当作正文数字；引文类型错误返回合同错误。
- Mermaid XY 图表从解析后的各序列逐组生成柱体数值标签，限制标签字号并在矮图表
  上稀疏 y 轴刻度；治理映射新增暗色主题的数据标签与图例文字色。
- 页面渲染对主题声明的每个字族/字重执行 Chromium `document.fonts.load/check`；
  未登记或损坏字体返回 `render_font_missing`。新增 frame-shot 枚举、字体加载和
  多序列图表回归，并同步 deck master、render contract、reason codes 与 CHANGELOG。

本轮新增/修改后定向回归 **69 项通过**（含真实 Chromium）；覆盖内容投影、页面溢出、
主题消费、Mermaid/SVG、结构输入与字体加载。catalog 已由
canonical 重新发布，generation 为 `e483ed0d93736774ab3142848dbec997`。本地仍不
宣称真实 Provider 生图、整册视觉审美验收或外部用户验收；未提交、推送或发布。

### 最终验收

本计划确认的六类实现问题已在本地修复。八个预存 pro 模板完成合同、几何、主题和
内容投影修复；当前 42 个 layout 中 15 个同时具有 HTML 绑定及 structure 声明，
其他 27 个保持 unknown，不冒充已实现。18 个画廊风格均绑定 canonical theme；
历史风格仍保留其 draft 生命周期，不扩大为全 320 风格可执行声明。

最终大组合回归 **139 项通过，无 skip**（内容包、结构投影、版式选择、隔离 bundle、
画廊、八模板 × 浅/暗主题、页面/图表/SVG、溢出和字体加载）。15 模板合同 lint、
15 模板 render lint、42 版式 lint、320 brief lint 通过；18 风格共 54 张画廊 PNG
重新渲染校验通过。生成的图表逐组数值标签与主题颜色已做确定性断言。

补充兼容回归 **64 项通过，无 skip**：旧五类模板（含 frame-shot 多种参数）、
真实 CLI 参数和失败 envelope、Provider 探针、轻量版式过滤、QA、模板解析。
与 139 项存在重叠，不相加宣称独立用例数。新增 CLI 测试确认成功产物的尺寸与
sidecar 选项一致；非法高度 exit 2，失败 envelope 从 stderr 读取。
单独保存八模板 × 两主题 **16 张样张**的两项回归通过，记录在 `pro-samples.log`。
浅/暗 KPI 样张用于本地可读性检查，图内金额和降幅仍标注为示例，未复核业务口径。

最终日志、补充检查与样张统一存放于仓库根
`.spec-first/workflows/spec-debug/leo-skills/render-quality-20260911-final2/`。
验证摘要：[verification-run-summary.json](../../.spec-first/workflows/spec-debug/leo-skills/render-quality-20260911-final2/verification-run-summary.json)；
声明校验：[closeout.json](../../.spec-first/workflows/spec-debug/leo-skills/render-quality-20260911-final2/closeout.json)。后者按工具规则为
`degraded / degraded-claim`：汇总中保留了未授权的付费 Provider 检查，因此不能把本地
通过项升级为所有渠道均已验证；这不否定已执行的本地回归。
此前 complete 目录的错误占位摘要和四份占位日志已删除；该目录的历史样张保留。
技能子目录中误放的真实日志已移回仓库根，不作为待提交的技能产物。

本次定向自审覆盖输入类型、数字覆盖、主题实际消费、几何失败、脚本异常、字体加载、
SVG 静态策略和 CLI 参数。未委派独立 reviewer；重叠预存修改保持原样，不做文件级
自动简化。完成范围为本计划的本地代码修复与验证，原 14 页 PPT、财务口径与整册
视觉验收不在本任务内；无付费调用、提交、推送或发布。
