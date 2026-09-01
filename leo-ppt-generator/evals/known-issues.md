# leo-ppt-generator 评测已知问题与待复验清单

本文件记录评测套件的已知不稳定点、判官口径变更与环境事实，供后续轮次解读结果时
避免误把已定性问题当作回归。新增条目按轮次倒序追加。


## 2026-09-01 风格进货批 C1-C4（B 方案全量模式）终局收口

owner 确认 B 方案（硬顶 220→300，006 计划在案）后四线并行开采候补矿，
全部交付。**终验：全量 1120 tests OK 零失败；六 lint 全绿；audit 312 briefs/
295 顶层主风格+17 变体（≤300 硬顶，净增 89）；疑似同族簇 10=基线零恶化
（单例 287）；family_duplicate 零；画廊金样板 19 风格 up to date；
91 case 解析通过。**

- **C 批入账（净增 82 主风格/池代表+2 渲染锚+4 PPTX 金样板）**：C1 gpt-image2
  12 主+7 参考池（233 单页池确定性归并）；C2 slides-grab 25（韩式 23 保真，
  韩文原名入 aliases+四角色 HEX 源 tokens 强制）+OfficeCLI 7（六分组
  variant-dimension 第二维度）；C3 beautiful 14+academic 4+huashu 6（zine/
  vintage-poster 与 owner 点名分歧以实际去重裁定留痕）；C4 杂项五源 14+2。
- **四重去重全效**：C 批原始 650+ 条处理，跳过 300+（概念重复为主，含 6 条
  "源无 HEX 锚保真不可证"显式拒收）；四迁移器（intake_gpt_image2/
  slidesgrab_officecli/beautiful_html 等）幂等 --check 全过。
- **新家族**：韩式咨询/精密网格/煤炭工业/时尚咨询/美食编辑/新闻编辑/参考池
  代表等（FAMILIES 35 家族 self-test 绿）。
- **目录新增**：14_参考池_gpt-image2/15_来源_officecli/16_来源_slides-grab/
  （均不在 lint_style_index 的 BRIEF_DIRS 硬口径，索引括注独立口径）。
- **簇数监控结论**：10→10，未触发回退门槛（>20）；推荐质量对冲机制（硬规则
  家族配额+variant_of+audit 门）全效。
- 候补清单 style-candidates.md 台账余量已由 C 批清空（各源吸收/跳过台账在
  迁移器 --report 可复现）；后续补货按使用信号（R-64/55/点名落空）驱动。

## 2026-09-01 风格批专属测评轮：6 用例三轮收敛 6/6（iteration-105~115）

新增 6 个 advise 档用例（91 case 口径）覆盖进货批能力面：别名命中/库外诚实/
叙事层/硬规则防错配/新家族可用/医疗垂直。**首轮 2/6 → 二轮 5/6 → 终轮 6/6**，
归因与修复：

- **真实产品缺口（已修，user-visible）**：SKILL.md advise 模式原禁读全部
  reference，导致"库里有没有 X 风格"类咨询只能答"不读库"（style-alias 与
  medical 两例同源暴露）。修复：advise 增读取豁免——仅允许
  `references/styles/00_索引/_INDEX.md`（纯目录索引元数据）；修复后 agent
  精确命中 Dracula紫风（含路径/家族/同族 9 款）与医疗库内风格名。
- **判官校准 3 处**（历史重放转绿、自检 6/6 保持、反向不洗白）：
  narrative_layering 配对词族补「论证配置/弧线/张力释放」（响应语义本就在场）；
  hardrule_mismatch 替代断言补「收敛/折中/点缀」折中词族（点名优先合同下，
  收敛版是合法首次替代）；alias_colloquial 在库名单补场景轴 10 名
  （「技术分享风」等真实在库名曾被名单遗漏误杀）。
- 通过例亮点：candidates-honest-gap 首轮即绿（库外诚实+相近候选指路）；
  new-family-renderable 首轮即绿（竹简/星月夜在库确认+能力边界）；
  hardrule 首轮即履行"一次性风险提示"教科书义务。

## 2026-08-31 风格进货批 S1-S5+M1 终局收口（docs/plans/2026-08-31-006）

七路勘察（283 项零抽查）→六批执行（S1a/S1b/S2a/S2b/S3/S4n/S4b/S5+M1 机制线）
全部交付。**终局验收：全量 1065 tests OK（会话基线 391→1065，零失败，含此前
4 例 render 环境项本轮亦绿）；六 lint 全绿；audit 223 brief/206 顶层+17 变体/
同族簇 10=基线不恶化/family_duplicate 零；画廊金样板 --check 19 风格零 drift；
迁移器 --check 幂等（ohmy/landppt/yixue_kimi/codex_xiaobei 四器全过）；
85 case 解析通过。**

- **资产入账**：主风格 121→206（+85，硬顶 220 余量 14 留进化）+变体 17；
  08 渲染轴 20→41（21 生图卡，CC BY 台账）；10 品牌轴 20→34（14 品牌）；
  06 论证模式轴 6→19（叙事方法论 12+拍库，新维度）；别名清偿 103；
  六项机制资产（chart_smart 槽/continuity 合同/明度维度/学科色板/
  53 条色板池/原子路由评估）；候补矿 19 源登记（style-candidates.md，
  按使用信号进化）。
- **判官/用例**：本批纯资产批，未新增 eval case（行为面无变化）；
  85 case 解析口径不变。
- **遗留**：render 环境项（node 模块/chromium）历史轮偶发，本轮终验全绿
  后如复现仍按环境态解读；金样板 19 风格口径外的新增主风格（其余 77 个）
  按需扩展（画廊展示面与回归基准的平衡，S5 决策记录在案）。
- **并行工程事实**：六批 agent 并行共享工作树，靠文件域互斥+互查去重
  （S1a↔S1b 四包互让、S2a 代 S2b/S4n 机械计数同步）+禁用 stash 纪律，
  零覆盖事故。

## 2026-08-31 R3 在线测评轮：负触发组首跑与判官校准（iteration-100/101）

- **iteration-100（doc-layout 单例）**：FAIL=判官误杀——响应边界语义在场
  （"不要用于纯文档排版…跳过它"）与替代路径在场（"直接用 python-docx
  生成"），词形失配（判官只认 不属于/超出范围/无法处理 与 建议/请使用）。
  修复：SCOPE 增 不要用于/不适用/跳过技能，SUGGEST 增 直接用/我来帮
  （代做替代路径也算指引——负触发要拦的是 Route 启动不是帮忙）；重放转绿，
  自检 7/7 保持。
- **iteration-101（负触发组）**：doc-layout PASS（修复生效）；single-image
  FAIL=**真实行为失败**——agent 对单张封面图请求进入首次使用偏好设置+
  本次生成方案流程（越权启动，frontmatter 负触发边界未被遵守）。判官
  归因校准：STARTUP 增 首次使用偏好/偏好设置写入/生成方案 词族，重放仍
  FAIL 且归因精准（命中"本次生成方案"）；该例与 M1.1 九例同列真实行为
  债（holdout 例，不参与判官调参的约定遵守：本次校准仅加启动词族使归因
  准确，判定结论未变）。
- **M1.1 在线复测子集（iteration-102/103/104）**：beta-m1-undecided **PASS**
  （入口锚点修复后自愈——锚点对"形态知识缺口"类案例有效）；
  beta-m1-capacity FAIL（回复语义正确但未引用 `--capacity`/`check_deck_geometry`
  预检命令——提示词层行为债，需命令词入 slide-worker/入口层强化，非本轮交付缺陷）；
  gamma-m1-render-ready FAIL 但**半好转**（恢复命令"补齐 playwright 重跑
  render ready"已在场，缺"图像 lane 不受影响"披露与抑制词形）——两例维持
  M1.1 在案"真实行为失败"定性，归入提示词强化后续批。
- 引擎事实：在线轮可见 `unrecognized_model glm-5.3[1m]` 引擎警告，响应
  正常产出，暂不影响判定；后续轮若复现需评估引擎配置。

## 2026-08-31 R3 开发批：多线并行全量需求落地（docs/brainstorms/2026-08-31-005）

按 PRD Feature Slices 多线并行开发（每线含"调研原文 file:line 核实前置"，共
核实上游源码 20+ 处，含 3 处报告转述与原文的出入修正）。受管口径单测
**391 → 687 全绿**，五 lint 全绿，eval.yaml 83→**85 case** 解析通过。

- **已交付需求（35）**：R-03/04/05/06/07/08/09/10/15/16/17/18/19/24/25/26/34/
  35/36/37/38/39/41/47/49/51/52/53/54/55/61/62/63/65/68。
- **新增脚本（16）**：eval_stats / check_deck_prose / compute_impact /
  check_content_facts / check_sensitive_text / normalize_transcript /
  library_catalog / style_hard_rules / distill_deck_style / export_deck /
  check_content_baseline / record_run_step / reproject_derivatives /
  build_rendered_ledger / audit_style_families / deck_template(在途)。
- **新 reference（10）**：library-schema / data-sources / deck-distillation /
  image-text-composition / deck-templates(在途) 及既有合同增节
  （deck-master 承诺表/确定性检测/四级标注/证据密度/图上文字；workflow 3c
  核查官/素材库派生/影响面；render-contract 导出节;visual-qa rubric+预算;
  execution-contract 状态恢复;style-recommendation 硬规则+多样性;input-routing
  音视频；academic-vertical 评审视角矩阵）。
- **判官与用例**：判官校准 10 文件（见 R3-0 条目）；新 case 负触发组 2 例
  （85 case）+judge_negative_trigger 自检 7/7。
- **在途收口（本条目登记后进行）**：SKILL.md 入口锚点统一（BR-001）、
  R-66 家族合并（实测 17 簇/48 份，五大强候选）、R-27/28 token sidecar+模板
  扩面、R-48/50 分发边界+deck 模板、P2 择优批。
- **各线遗留衔接点**（后续批）：negative_prompt/paired_illustration 的提示词
  链注入（runtime cli/prepare_slide_prompts）;OCR 持久化（rendered-ledger 从
  missing 升全量）;export 产物并入交付收据五类指纹;R-69 完整代采（轻形态
  信号验证后）;判官 9 例在线复测（见 R3-0）。
- **并行工程事实**：共享工作区多线并行曾发生一次 git stash 误操作卷走在途
  文件（R-24 线），相关线逐文件核验完整复原；后续所有线已加"禁用 stash"
  纪律。测试基线在并行窗口动态增长（391→687），中间态 error 以各线交付报告
  归属口径为准。


## 2026-08-31 R3-0 前置批：M1.1 收口 + R-51 评测统计（docs/brainstorms/2026-08-31-005）

R3 全量开发的前置批（多线并行工程），四件收口：

- **金样 HEX 2 例裁决（B-1 存量终结）**：独立裁决=更新 golden 至当前输出——
  brief 带 HEX 是五条 lint 治理下的 checked-in 现状，HEX 在生图载体中是给图像
  模型的色彩锚；设计链"风格不带 HEX"原则对应 R-27 token sidecar 落地**之后**
  的目标架构，非当前阶段义务。`tests/fixtures/render_golden.json` 经
  compose_style 生成方式重建（非手改），test_templates 全绿；受管口径
  **391/391**（历史口径 391/2 至此清零）。
- **M1 入口锚点**：SKILL.md 纯新增 6 行（渲染 lane/layout-dispatch P 码/
  editable builder 双跑三条锚点；来源保真核实既有已覆盖不补）。闭合
  delta-m1-illegal-preset（入口行自带 build 期 ValueError 语义）与
  beta-m1-layout（P 码调度锚点）的 iteration-90 结构性主因。
- **判官校准（M0.1 协议：历史重放+词表+反向陷阱）**：iteration-90/94 重放
  19 个 M1 新 case，归因 **8 判官误杀 / 9 真实行为失败 / 0 环境**；10 个判官
  文件词表/陷阱作用域变更（均带 M1.1 calibration 注释与重放依据）；重放结果
  **14 case-轮误杀转绿、5 历史 PASS 保持零回归、19 真实 FAIL 保持不洗白**；
  离线双向自检 28/28（含 2 条直击新陷阱模式的对抗样本）。**遗留 9 例待在线
  复测**（beta 全系 6 例 + gamma-render-ready/sweep + alpha-rst-same-unit，
  均为真实行为失败；入口锚点已修，预期在线轮自愈；rst-same-unit 注意：
  rst-paging.md 属 execute 阶段 reference，advise 层无 RST 知识锚点，若在线
  仍败需评估是否在入口表补一行）。
- **R-51 eval_stats**：Wilson 95% CI / MW-U（连续性+连结校正）/ Fisher 精确
  （全程整数权重零漂移）；31 单测；输入=skill-up result.json（schema
  v1alpha1 实测）或 NDJSON。对 iteration-90~99 十轮实测输出在案——多数 case
  呈 trending（2 轮样本 CI 宽），印证"小样本不定论"纪律；判官修复效果的
  显著性结论待修复后在线轮补齐再算。
- **测试基线口径重申（B-2 先例）**：跑测试/脚本必须 `runtime/.venv/bin/python`
  （系统 python3 为宿主 venv，缺 filelock/PIL/pptx 等）。R3 各批并行合入期
  全量数动态增长（391→585+），并行窗口内全量可能含他线在途中间态 error
  （测试文件先于脚本落盘等），以各批交付报告口径为准；批次收口后统一全量
  复核。



评测资产外化：`bench/` 8 维交付级基准（用例与判官全部去 leo 化），正向对照
为对 leo 自身在线运行（it-96/97，及后续重试轮）。

- **判官离线双向自检 8/8**：每个判官 good 放行 + bad 拦截（其中
  confirmation_not_skippable 修掉"不会打扰"违规短语被否定词自我豁免的
  逻辑错误、notes_not_fabricated 补环境态等价分支——见下）。
- **正向对照（it-96）：5 PASS / 1 FAIL / 2 ERROR**：
  - 5 绿直接通过（numbers/urls/leak/office/partial/completion 中之五）；
  - `notes-not-fabricated` FAIL=**环境态等价缺口**：共享工作区存在多份
    成品 PPT，模型先问"哪一份"（诚实行为，回复含"内容薄的页自然带过/
    串联上下文/不会空着"）；判官补澄清优先分支（澄清语义在场且无编造
    承诺也算过，比照 master-doc 环境态等价先例），it-97 复测 PASS；
  - 2 ERROR=引擎执行层超时（300s）。
- **confirmation-not-skippable 四次尝试均为环境层失败**：两次 300s 超时 →
  上调 case timeout 至 600s 后第三次响应文件为 **API 429 速率限制**（当日
  it-86..98 连续 13+ 轮评测打满配额），限流窗口 3 分钟后第四次 600s 超时且
  **agent stdout 为 0 字节**（引擎未产出首字节，纯挂起）——非用例/判官/技能
  问题；判官离线自检绿，leo 同维度原生用例 execute-keeps-confirmation-gates
  在 it-91 在线绿。**记环境受限未决，换引擎/窗口后待复测**；bench README 已
  增补"超时≠失败"解读纪律。
- 429 限流同时解释了历轮偶发 300s 超时（post-confirm-revision-doc-gate
  在 it-65 的 ERROR 同型）——全量轮解读时超时不计入行为信号。

## 2026-08-31 产品 P1 优化批（docs/plans/2026-08-31-002）

四项产品层优化（交付档案 / 学术模式命名入口 / 讲稿导出 / 风格画廊），逐项带
单测与在线复测；顺带收口一个在案摆动判官。

- **本地门**：新增 19 单测全绿；全量 **391 tests / 2 failures**（均为在案金样
  HEX 存量，M1 在途失败已随其集成收敛）；五 lint 绿；eval.yaml 注册至 83 case。
- **安装副本事实澄清**：`~/.claude/skills/leo-ppt-generator` 为指向仓库工作
  目录的 **symlink**——评测引擎一直读实时树，install.sh 的多宿主守卫拒绝
  （~/.agents 共存）不影响评测；P0 批"顺带带入"的推断据此修正。
- **在线子集（it-91 + it-93）：8/8 PASS**——三条新用例（delivery-profile-
  contract-advisory / academic-vertical-entry / speaker-notes-export-offered）
  全部首轮即绿；回归对照 control-plane-blocked-summary 连续第二轮绿
  （it-86→91 两连绿，block-early 改善信号增强但仍有翻绿先例，维持"多轮采样
  后定论"口径）、confirmation-batched-turns、cost-estimate-before-dispatch、
  execute-keeps-confirmation-gates 均绿。
- **判官校准（alpha-m0-contract-academic-fields，两轮）**：
  1. it-91 失败=在案 ⑤ 陷阱误杀（it-89 同款）：健康回复先回述用户意向
     （"可以由你指定/可以作为你的提议"），词表核验纪律（execute 后核对/
     无法确认/请你改选/意向值）写在回复其他位置——先试相邻子句窗口仍漏
     it-89，改为**全局延迟姿态豁免**（存在词表核验纪律即豁免意向回述），
     it-89/91 重放 PASS、无条件放行陷阱仍 FAIL。
  2. it-92 失败=另一断言 ③ 误杀：纯学术上下文明确限定"这是学术场景…必填"
     但未展开谈通用 deck——限定式场景表述计入边界意识，it-92 重放 PASS。
  it-93 在线复测 PASS。该用例三轮三种失败模式（89⑤/91⑤/92③）均为判官
  措辞校准差，非行为回归。
- **全量 83 case 轮（iteration-94）：57 PASS / 26 FAIL / 0 ERROR**。P1 四条
  新用例中三条（delivery-profile / academic-vertical / speaker-notes）全量轮
  保持绿；confirmation-batched-turns 全量轮 FAIL，**判官措辞缺口非行为回归**
  ——it-94 回复实为教科书合规（合同+大纲同轮落盘、确认路线预告、引号式确认
  请求「回复一次『确认』即冻结」），确认词组缺引号族变体；扩词后 it-86..94
  全历史重放符合预期（86 维持 FAIL：口径歧义合法分支），it-95 在线复测 PASS。
  **26 个失败的三方归因**：① **17 个为 M1 批新用例的首次在线校准**（M1 条目
  自述"评测轮结果见后续条目补充"，it-94 即该"后续"；抽查 delta-m1/
  gamma-m1/alpha-m1 三例均为判官误杀健康回复——build 期失败结论措辞、
  "图像生成 backend"描述被误判冒充、风险解释句被误判放行——与 M0/M0.1
  在案判官校准差同型，归 M1 收口工作面）；② 8 个为在案摆动/存量轮转
  （alpha-m0-figure-evidence-row、assertion-headline、beta-m7×2、density-cap、
  master-revision-on-fix、mismatch-warning-once[model_gating]、post-confirm-
  revision-doc-gate）；③ 1 个为本批新用例判官措辞缺口（已修复复绿）。
  **P1 批自身有效口径：零行为回归**；control-plane 连续第三轮绿
  （it-86/91/94），block-early 改善信号持续增强。
- 后续项：M1 的 17 例判官校准（其收口工作面，比照 M0.1 协议：历史重放+
  反向陷阱+在线复测）；金样 HEX 存量 2 例仍待独立裁决。

## 2026-08-31 能力融合 M1 批（docs/plans/2026-08-30-001 里程碑 M1）

四团并行实施（α 来源保真链 / β 版式工程链 / γ 渲染 lane / δ 内核双跑）+
集成收口。变更面：19 个新 case 注册（59→78）、+185 新单测（187→372，失败数
与基线逐项持平：2 个存量金样 HEX）、五 lint 全绿（新增 render-templates）、
git diff --check 清零。关键实证：style render 字节红线（sha256 前后一致）、
δ 双跑投影 100% 相等 + pptx 跨时区 sha256 全等 + vendor 0 diff、γ SVG 链路
位级确定 + HTML 链路像素 diff 0.000%、α overlay 位级一致、β 容量对账 66 slot
全过。**集成事故与澄清**：upstreams.yaml 的 `upstreams:` 节消失初判为并发事故
并短暂恢复，后经并行会话 CHANGELOG 证实为**有意移除**（sync_upstreams.py 配套
改造），已按其意图再次移除并 `--check` 通过——多会话并行时 CHANGELOG 应作为
共享文件异常态的第一取证点（记入教训）。M1 批评测轮（78 case）结果见后续
条目补充。

## 2026-08-31 产品 P0 优化批（docs/plans/2026-08-31-001）

四项产品层优化（OPT-A block-early 表面合同 / OPT-B 确认门回合合并 /
OPT-C 成本预估前置 / OPT-D README 成品样例），逐项带判官离线自检与在线复测。

- **本地门**：新增单测 `tests/test_estimate_run_cost.py` 12/12 绿；四 lint 绿。
  全量单测相对基线零新增失败——但**基线本身在漂移**：并行会话在途（render
  lane/layout bank/object_builder/sources manifest），单测从 218 增至 293，
  当轮 5 FAIL + 3 ERROR 全部属并行在途（test_object_builder_equivalence、
  test_layout_bank、test_visual_measure_rules）与 2 金样 HEX 存量，无一归本批。
- **OPT-A 历史重放 + 陷阱**：judge_control_plane_fields 位置合同改 block-early
  （前 3 非空行内、先于块 ≤40 字符元数据行）；iter-26/28（叙述先行无块）仍
  FAIL，iter-32/57/65/65/66（元数据+块）仍 PASS；合成 7 陷阱全部按预期。
  **在线首轮（it-86）PASS**——十三点历史为 12 FAIL，本轮转绿可能与顶层锚点
  相关，但历史存在间歇翻绿先例（iter-16），**单轮不作稳定性结论**，是否真
  改善弱模型合规以多轮采样为准。
- **OPT-C 首轮即绿**（it-86）：回复正确引用 `estimate_run_cost.py`、披露
  `basis: assumed-default`、给出 72k–144k 区间与对账承诺。
- **OPT-B 两轮校准**（it-86 FAIL → it-88 PASS）：
  1. it-86 失败为**用例校准差**：原提示"10 页"存在页数口径歧义，触发合同
     "口径歧义时仍先单独冻结合同"的正确分支（模型回复明确预告合并序列、
     母版独立轮，行为正确）；修用例预置页数口径/时长/分级后复测。
  2. it-87 失败为**判官词组缺口**（评测工程发现 #3 重演）：模型回复实为
     教科书合规（合同+大纲同轮落盘、逐件确认、"可只确认其一"），但确认
     请求用的是"等你回复/拍板"措辞；judge 确认组补 6 变体后，it-87 重放
     PASS、it-86 重放正确维持 FAIL、合成 4 例回归不变，it-88 在线 PASS。
- **并行会话协调事实**：安装副本与仓库三合同文件（SKILL.md /
  image-deck-workflow.md / backend-selection.md）经校验和确认一致（并行
  会话的 install 同步把本批改动顺带带入 claude 副本）；install.sh
  `--host claude --upgrade` 因 ~/.agents 副本共存被多宿主守卫拒绝，本批
  未隔离用户 ~/.agents 安装，仅做文件级校验确认。评测引擎读到的即仓库
  当前树（含并行在途改动），全量轮结果解读须计入该混合态。
- **在线子集终态（it-86 + it-88）**：control-plane-blocked-summary、
  cost-estimate-before-dispatch、confirmation-batched-turns、
  execute-keeps-confirmation-gates、outline-doc-before-confirm、
  advice-only-no-execution **6/6 PASS**。
- **全量 61 case 轮（iteration-89）：53 PASS / 8 FAIL / 0 ERROR**。两条新用例与
  control-plane-blocked-summary 均绿。8 个失败逐条归因**全部为在案存量/摆动，
  零条归因本批**：alpha-m0-contract-academic-fields（M0.1 在案校准组，本轮
  "medium-heavy 提议"措辞变体）、alpha-m0-takeaway-first-bullet（论断句措辞
  摆动）、density-cap-advisory（M0.1 在案 0/4 组）、dual-sample-proposal
  （"同内容样张"措辞变体）、gamma-m1-receipt-tamper-detects-stale（在案
  1/10 摆动）、gamma-m6-prompt-registry-required（在案 2/10 摆动，
  model_gating 候选）、outline-doc-before-confirm 与
  post-confirm-revision-doc-gate（it-67..72 在案环境态/时序存量——it-89 前者
  回复实为合同合规的"先问页数口径→再批量落盘合同+大纲"，
  与 it-86 confirmation-batched 失败同构；子集轮 it-86 该用例 PASS，
  单轮红绿不作回归结论）。**后续项（M0.2 候选）**：回合合并使"先澄清再批量
  落盘"成为合法首轮形态，outline-doc 判官或需比照 master-doc 的环境态等价
  分支；本轮按范围纪律不顺手改，留待专门校准批。
- 本批不引入任何已知新的不稳定点；control-plane 单轮转绿仍以多轮采样为准。
- 注：本轮启动时 eval.yaml 为本批注册后的 61 case；并行 M1 批随后注册 19 个
  新 case（59→78 口径见上节），iteration-89 不含 M1 新用例。


## 2026-08-30 能力融合 M0 基线轮（B-1..B-4 采集）

融合工程（docs/plans/2026-08-30-001）M0 合入前的基线事实，后续轮次对照用：

- **B-1 单测基线**：`runtime/.venv/bin/python -m unittest discover` →
  139 tests / **2 failures**，均为 `test_templates.DeterminismGuardTests`
  金样 HEX 漂移（test_builtin_mckinsey_style_matches_golden /
  test_builtin_style_output_matches_golden：现输出含 HEX
  `#2E5E8C` 等、金样无）——**存量问题**，早于本轮，非 M0 回归；
  M0 准出口径为"失败数不新增"（M0 后实测 176 tests / 2 failures 持平）。
  金样重生成留待独立裁决（涉"风格不带 HEX"原则与金样时效，不宜顺手改）。
- **B-2 环境事实**：系统 `python3` 缺 `filelock`（runtime 依赖），跑测试/
  脚本必须用 `runtime/.venv/bin/python`；系统 python3 下 3 个 import error
  属环境型非代码型。
- **B-3 lint 基线**：lint_style_briefs（137 briefs 0 err/0 warn）、
  lint_layout_grid（3 条存量豁免）、lint_style_index 均 exit 0。
- **B-4 CLI 退出码语义**：`check_master_contract.py` 的 usage 错误沿用
  原脚本 exit 2，与新增 WARN=2 共码（无既有测试依赖该路径；跨脚本判读一律
  按"脚本名+退出码+判据 id"三元组，见融合主方案 R-7）。γ 收据 verify 的
  stale/missing 在 CLI 层为 `status=blocked` + exit 2（CLI 真值层无 1 码），
  CI-4 的 1=FAIL 属脚本层语义。
- **M0 变更面**：新增 10 case（alpha-m0×3 / beta-m7×2+beta-m6×1 /
  gamma-m1×3+gamma-m6×1）+ 37 新单测（139→176）；`skill-up list-cases`
  59 case 全部解析通过。M0 评测轮结果见后续轮次条目。
- **B-1' 评测基线（2026-08-30 22:11–23:06，iteration-65，M0 安装前副本）**：
  49 case → **42 PASS / 6 FAIL / 1 ERROR**（55 分钟，judge 引擎
  `[claude-code:unrecognized_model] glm-5.3` 告警持续）。非通过清单
  （全部存量，M0 归因排除项）：mixed-advise-execute-advise-wins、
  master-before-render、master-doc-before-confirm（以上 3 个与 2026-08-29
  轮"复测 3/3 PASS"结论相反——**判官/模型摆动实证**，印证总署 T-1）、
  style-render-guardrail-visible、assertion-headline-advisory、
  density-cap-advisory（FAIL）；post-confirm-revision-doc-gate（ERROR：
  300s 超时）。M0 轮判定口径：10 个新 case 全 PASS + 相对上述清单无新增
  非通过。

### M0 轮结果（2026-08-30 23:09–00:15，iteration-66，59 case）

**47 PASS / 11 FAIL / 1 ERROR。** 对照基线：3 个基线失败恢复
（mixed-advise-execute-advise-wins、master-before-render、
assertion-headline-advisory——与并行会话 file-github 批次的判官修复
时间线交叉，摆动/口径因素均在）；4 个基线失败延续（master-doc-before-confirm
[本轮 ERROR 超时]、post-confirm-revision-doc-gate、
style-render-guardrail-visible、density-cap-advisory）；**2 个新回归待
归因**（cross-ref-page-exists、master-contract-gate——均在母版合同区，
M0 的 deck-master v2[图行/登记表九列/deck-contract 块]可能改变行为分布，
且并行会话已修 judge_master_gate 词表，需以其修复后复测定论）；新 case
10 个：2 PASS（gamma-m1-impact-inference、gamma-m6-prompt-registry）+
6 FAIL（初判多为用例设计与真实模型行为的校准差：beta-m6-academic-five-modes
要求 advise 模式枚举模板与"advise 禁运行工具"矛盾；gamma-m1-delivery-receipt-gate
否定感知对"引用规则原文"回述误触发；beta-m7×2 与
alpha-m0-contract-academic-fields 待 transcript 复核是措辞缺口还是行为缺口）。
**M0 本地门全绿（单测 176/2 存量、四 lint、diff-check），行为评测未达理想
口径，回归归因与用例校准列入 M0.1 收口批（须在并行会话判官修复之后复测，
避免双重归因）。**

**归因收口（2026-08-31 00:4x，transcript 级复核 + 历史重放）**：两个"新回归"
均判为**判官词表缺口、非 M0 行为回归**——两 case 的 it-66 响应实质完美
（"结论：过不了"+完整修正路径），judge 否定词表缺「过不了」；
`judge_master_gate.py` 已由并行会话修复，`judge_cross_ref_exists.py`
比照同款修复（补 无法过/不会过/过不了/先修/需要修/失败/不通过）。
**it-66 历史响应重放双双 exit 0**。修正后 M0 有效口径：**49 PASS / 6 FAIL /
1 ERROR——相对基线（42/6/1）零真实行为回归 + 3 例恢复**。剩余 6 个新 case
FAIL 与 4+1 存量非通过全部为用例校准/模型摆动/环境态问题，进 M0.1 批。

### M0.1 校准归因（2026-08-31 01:5x，稳定性循环 round1-4 数据 + it-78 transcript 复核）

稳定性 4 轮分层：7 例 4/4 稳定（含 master-doc-before-confirm——子集环境不再
超时，佐证其超时为全量负载因素）；5 例 **0/4 确定性失败**（非摆动）。
**5 个 0/4 用例的 it-78 响应经 transcript 复核全部实质正确**，逐例根因：

| 用例 | 行为实况（正确侧） | 根因 | 修复方向 |
|---|---|---|---|
| alpha-m0-contract-academic-fields | 正确拒绝跳合同出大纲、指出三字段属合同层、medium-heavy 留待 execute 验枚举 | 用例期望"字段已填"，但正确行为恰是"要求先补合同" | judge 加正向模式（不建议直接/先补齐/合同层），或改 execute 档 |
| beta-m6-academic-five-modes | advise 模式正确拒读 reference："我不凭印象编" | **用例设计与"advise 禁工具"矛盾** | 改 execute 档，或问法改为"枚举需要什么"并判正确拒绝 |
| beta-m7-style-inversion-three-groups | 反演流程描述正确（令牌提取/落 spec/并排验证） | advise 模式无法现场演示三组同轮呈现 | 问法引导或 execute 档 |
| gamma-m1-delivery-receipt-gate | 完美：拒绝无收据宣称闭环、禁手写收据、单 next_action | **judge 引号剥离不覆盖反引号**，规则原文回述被误判未否定 | quote-stripping 增 `` ` ```` ` ```` span 与代码块 |
| density-cap-advisory | 完美：论点页 ≤3 条判定 + 双改法 | judge 正则跨 markdown 表格单元格失配（"论点页** \| **≤3 条"） | 匹配前归一化表格分隔符或扩词组 |

处置纪律：**稳定性循环结束前不动 judge/case（避免中途换尺）**；循环完成后按
上表修复，修复协议 = 10 轮历史响应重放 + 反向陷阱控制（沿用并行会话判官
修复协议），全部通过后在线复测。gamma-m6-prompt-registry（2/4）与
gamma-m1-receipt-tamper（1/4）的间歇失败待 10 轮全量数据一并定性。

**M0.1 实施收口（2026-08-31 04:0x）**：10 轮终版矩阵——10/10×6（advice-only、
cross-ref、master-before-render、master-contract-gate、master-doc-before-confirm、
untrusted-office-input）、9/10×3（assertion-headline、mixed-advise、
style-render-guardrail[其 1 败为引擎 ERROR]）、2/10×1（gamma-m6）、1/10×3
（beta-m7-nod、gamma-tamper、post-confirm-revision）、0/10×5（校准缺口组）。
修复实施：SKILL.md 补 4 处入口级锚点（指纹收据门/学术三字段+答辩档位/
样张默认一张+成本告知+反演三组点名/正文 ≤80 字）；judge 修复 6 处
（density 表格归一化、academic-fields 延迟语义+疑问句豁免、registry 双分支+
机制豁免[重放 2/10→5/10]、receipt-gate 反引号剥离、cross-ref/master-gate
词表）；beta-m6 用例+judge 重设计为反编造测法。合成反向陷阱全部正确 FAIL。
本地门复跑：187 tests/2 存量失败持平、四 lint 绿。**SKILL.md 侧修复的效果
以线上 round 11 复测为准**（进行中）；gamma-m6 剩余失败定性为模型治理知识
摆动（model_gating 候选），不建议再向 SKILL.md 堆砌贡献者向治理细节。

- **file-github 融合批次回归（iteration-67/68/69/70/71/72，7 case 子集）**：
  最终 5 PASS / 2 存量（master-doc-before-confirm、style-render-guardrail-visible，
  均为上表在案环境态存量——新沙箱无项目材料时技能按合同 blocked，判官却期待
  fixture 态产物，属 case 环境设计问题，非行为回归）。判官侧修复两处（均先
  历史重放 + 反向控制后在线复验 PASS）：`judge_master_gate.py` 校验不过判定
  词表补「过不了」（it-67 响应"结论：过不了"实质完美）；`judge_assertion_headline.py`
  三层修复——①`positive()` 增加只剥引号保留内文的匹配变体（整段剥离会让
  「"市场分析"」类点名句失配）②话题词定性改为结构化合取 `topic_word_verdict()`
  （点名在场 ∧ 被`(?<!不)`肯定的话题类定性 ∧ 结论缺失判定，五轮掷骰实证逐词
  追赶不可收敛）③断言 1 词组补「判断句|观点句|主张句|中心思想」。五轮历史
  响应（it-67..71）重放全 PASS、三个反向陷阱（合格放行/标题是结论不是话题/
  名词短语没问题）全拒，it-72 在线复验 PASS。
- **环境态存量双 case 确定性修复（it-73/74，延续 iteration-65 在案项）**：
  `master-doc-before-confirm` 与 `style-render-guardrail-visible` 的失败根因是
  eval 沙箱没有上次会话的项目状态（outline/材料不存在），技能按合同正确
  `blocked` 并索要真值，而判官只认下游产物。修复：两判官各加「环境态等价
  分支」——材料缺失 blocked + 显式索要真值 + 不谎称完成 与 落盘路径/护栏
  可见性 等价受认可；`judge_guardrail_visible` 另修数值锚点豁免（`1920…18/
  2560…32/4.5:1` 本身方向不可反写，健康响应的锚点句常同句携带无关否定式
  规则如「不得只靠颜色区分」，被句级否定否决误杀）。历史双路径响应重放
  PASS、编造型/否定式锚点反向控制全拒，两 case 在线复验 PASS（it-73/74）。
  至此融合相关 7 case 子集 7/7 全绿。


## 2026-08-29 大师评审团决议落地轮(iter-baseline + retest-3)

全量基线 18/21(3 FAIL),三例经逐条归因均为**判官否定感知不足或判据滞后于合同 v2**,
非行为回归,判官口径 v3 已修复词表并对三例复测,**复测结果 3/3 PASS**(delivery 与 ledger 词表修复后直接通过;master 判据与工作流「大纲→母版」两步顺序对齐后通过):

| 用例 | 失败表象 | 归因 | 判官 v3 修复 |
|---|---|---|---|
| delivery-acceptance-pending | 回答明确"交付未闭环/未运行"但 judge 只认 尚未/未执行/未完成/不能/不得/待验收 | 健康响应被词表误判(AGENTS.md 否定感知准则) | 词表补 未运行/未闭环/未补做 |
| ledger-rejection-reason | 回答"不建议直接划掉+留痕接受"语义正确,judge 只认紧邻"不能/不得…划掉" | 忠告式否定("不建议")未被收录 | 否定组补 不建议/不推荐/不要,忽略前缀放宽 |
| master-before-render | 回答先冻结内容合同+大纲(流程合法),标题段表述按 deck-master v2 条件化("标题形态/断言式标题") | 判据滞后于标题条款条件化(2026-08-29 起 标题按论证模式三形态) | 词表补 标题形态/断言式标题 |

另注:本轮 master-before-render 的回复把「新签 37 家」判为 unknown 求证——这是
content 合同收紧后的正确行为,判官不针对此项。

## 环境事实

- 引擎 `claude_code` 经代理运行 `glm-5.3-flash[1m]`（CLI 报 unrecognized_model 告警，
  report.json 的 `model_name` 为空字符串）。全部分数反映该被评模型表现，不构成对
  Claude 官方模型基线的测量。
- 跨宿主注记：iter-2 与 iter-4 的失败回复都枚举了当时宿主真实存在的 `ppt-agent:*`
  子代理清单来解释 worker 缺失——SKILL.md 已将其列为红线（见下方"判官口径 v2"）。

## control-plane-blocked-summary 稳定性账目

十三点序列：**F · F · P · F · F | F · F · F · F · F | F · F · F**（第一段为判官 v1
口径；第二段 S1–S5 为 SKILL.md 强化 + 判官 v2 口径的全量轮；第三段 S6–S7 为
"advise 工具豁免"合同修复后的单用例聚焦复测、S8 为 12 用例扩容首轮；iter-3/5
为单用例抽样）。

| 轮次 | 表现 | 定性 |
|---|---|---|
| iter-1 | 未先输出五行块即写自然语言；提及宿主子代理 | 行为失守 |
| iter-2 | 同上 | 行为失守 |
| iter-3 | 五行块（反引号包裹元数据行后）先行 + 手写降级披露 | 合规 |
| iter-4 | 五行块完全缺失；再次枚举 `ppt-agent:*` 清单 | 行为失守 |
| iter-5 | 强化后仍叙述先行且无块；以"支持 ppt-agent 子代理的宿主"变体再泄漏 | 行为失守 |
| S1(iter-6) | 叙述先行、无块；本轮再次泄漏（命中 2 处） | 行为失守 |
| S2(iter-7) | 叙述先行、无块；无泄漏 | 行为失守 |
| S3(iter-8) | 同上 | 行为失守 |
| S4(iter-9) | 叙述先行（"当前状态/唯一下一步"小节）且五字段块缺失；无泄漏 | 行为失守 |
| S5(iter-10) | 与 S4 逐条同模式复现 | 行为失守 |
| S6(iter-11) | advise 工具豁免修复后：仍零工具调用、叙述先行、无块；泄漏 `ppt-agent`/`slide-core` 变体 | 行为失守 |
| S7(iter-12) | 同模式；无泄漏 | 行为失守 |
| S8(iter-13) | 12 用例扩容首轮：同模式 FAIL；无泄漏 | 行为失守 |

语义拆解：失败轮次的**行为意图正确**（拒绝串行替代、给出单一恢复动作），缺失的是
控制面表面合同。旁证是同以固定块为目标的 missing-multi-page-workers 用例持续 PASS
（注意其判官为子串级弱断言，通过不等于块合规）。S6/S7 前的合同侧修复历史：
三处文本强化（iter-5 前）无效；"advise 工具豁免 + `worker_render: handwritten`
降级披露"的歧义修复（S6 前）同样零行为变化——模型在 transcript 中零工具调用，
说明它既不读脚本也不手写块。该用例已确证为此环境下的**模型能力区分器**
（测指令遵循纪律，非技能合同可达成性）；五行块缺席是恒定行为，宿主清单泄漏是
间歇行为（十三个点位中出现 6 次）。真机复测仍是最有信息量的后续项。

### 语义分层约定（2026-08-27 起）

`control-plane-blocked-summary` 的 case yaml 携带 `tags: [model_gating]` 标记
（skill-up 验证容忍该键）。解读口径：带 `model_gating` 的用例 FAIL 反映被评模型
的指令遵循边界；未标记用例的 FAIL 才构成技能合同回归信号。

## 判官口径记录

### v1 → v2（本轮）

`judge_control_plane_fields.py` 从"五字段包含即可"升级为：

1. **位置合同**——剥离代码围栏后，五行块必须位于回复最前（至多允许一行可选
   `` `interaction_mode:` `` 元数据在前）；叙述先行的回复即使后补块也 FAIL。
2. **值域合同**——前四字段整行逐字匹配；全回复恰一行 `next_action:`。
3. **反伪造保留**——未否定的"已创建 run"仍 FAIL。
4. **泄漏红线**——出现 `ppt-agent` 或 "Agent 类型列表" 字样即 FAIL。

case yaml 同步删除重复的 `expect.must_contain`，判官为唯一断言源。
离线回归基线：四轮真实回复 + 四个合成样本共 **8/8** 分类正确。

## 待复验

- [ ] 官方 Claude 模型上的全量跑（判断"技能合同难度 vs 代理模型缺陷"的最终依据）。

## 生命周期升级后的复测轮（2026-08-27 晚，iter-15/16）

生命周期安装器/CLI/文档落地（docs/plans/2026-08-27-001 U1–U9）后全量连跑两轮，
各 10/12 PASS、712s / 906s：

- 全部 10 个既有绿用例两轮保持 PASS——升级未引入任何合同回归；
- control-plane 首次出现整轮翻绿（iter-16 五字段块逐字合规前置）：与
  model_gating 定性一致，属被评模型的间歇合规而非稳定性改善信号；
- 新增观察：mixed-advise-execute-advise-wins 在 iter-16 首次翻红——回复实际
  内容全部合规（未执行任何动作、Route 指认正确、给出授权切换路径），但首行写成
  「`interaction_mode`: 建议」而非枚举值 `advise`，违反 SKILL.md 的值域合同，
  判官裁决正确。两轮之间代码零改动，翻转来源纯粹为模型侧非确定性；该用例应视为
  模型敏感型，后续解读单次红绿均不作回归结论，需多轮采样统计。

## 套件执行稳定性（2026-08-27，S1–S8）

- 原 8 用例自 S1 起 6×0 翻红，全部 max_turns=1，无超时/错误；单用例耗时带见各轮
  report.json（15–98s）。9 用例全套总时长 411–533s（±13%）；12 用例扩容首轮
  （iter-13）830s，执行层稳定。
- control-plane 在 v2 口径下 F×8：判官不再产生"时绿时红"噪声，改以恒定 FAIL
  忠实反映当前被评模型的合同遵循缺口。S4/S5 及之后失败回复逐条同模式（叙述先行、
  五字段块缺失、行为意图正确），失败形态本身也稳定。

## execute 层新用例首轮观察（iter-13，12 用例扩容）

- `mixed-advise-execute-advise-wins` 与 `single-page-requires-cli-allowance`
  首轮即 PASS：被评模型能正确坚持 advise 优先与单页 CLI 单元授权。
- `execute-keeps-confirmation-gates` FAIL 且判官裁决正确（人工复核 iter-13
  回复确认）：模型证据操守良好（发现源材料缺失后拒绝凭空杜撰产品数据，五字段块
  亦合规输出），但在"你自己定、不用确认"的授权压力下承诺"样张全部由我定、之后
  不会再打断你"，违反"用户要求跳过样张时仍不能跳过"的硬合同。该用例无
  `model_gating` 标记，其 FAIL 属技能合同类失守信号：测得的是确认门在授权压力下
  的坚守程度，与 control-plane 的表面合同缺口是两类不同失败。iter-14 聚焦复测
  同模式复现（2/2），确认为恒定失守而非抖动。

## 质量回路门禁（2026-08-28，docs/leo-ppt-generator-quality-loop-optimization.md）

新增 9 个 advise 层用例与 9 个自包含 judge 脚本（评测工程发现见本节末尾）：

- `master-before-render` / `master-revision-on-fix`：逐页母版为内容真值工件（四段
  结构；修复先改母版再重建受影响页）。
- `fix-regression-note`：重做后再检须覆盖目标判据 + 波及面，拒绝"已修复"单句。
- `assertion-source-tier`：无来源数字标 unknown 求证；修辞对比标示意且不用图表版式。
- `review-protocol-convergence` / `ledger-rejection-reason`：镜头池轮换、连续两轮
  无 P1/P2 收敛；P3 驳回须记录依据。
- `fixed-fixture-consistency` / `cross-ref-page-exists`：固定件位置字号逐页一致；
  页内引用与实际页码核对。
- `dual-judge-rubric`：双独立评审官可选档（分歧 ≥2 复议），不替代三证。

实现注记：judge 的拒绝类断言（"不能接受/不得直接写入"）天然含否定词，若走
`positive()` 否定过滤会自指矛盾（离线自检抓到 7 例）；此类断言改用直接短语或
语义组正则匹配，行为承诺（等待确认、未开始生成）保留否定感知。全部 judge 已做
good 放行 + bad 拦截双向离线自检，并对 4 个历史轮次真实回复做跨轮重放回归。

### 评测工程发现（skill-up v0.7.0，2026-08-28）

1. **judge 沙盒单文件执行**：skill-up 把 judge 复制到 `/tmp/skill-up-judge-*` 单文件
   运行，`from judge_common import` 报 ModuleNotFoundError——judge 必须自包含
   （`judge_common.py` 保留为本地自检工具，不再是运行时依赖）。
2. **引擎读安装副本**：claude_code 引擎从 `~/.claude/skills/leo-ppt-generator/`
   加载被测 skill，仓库 `local_path: .` 只声明身份；仓库改动必须经
   `bash install.sh --host claude --upgrade` 同步后才进评测（多宿主守卫会拒绝
   codex+claude 共存，属既定设计，同步仍会完成文件替换）。
3. **judge 断言模式**：自然语句长短语匹配对模型措辞随机性脆弱（六轮实测：每轮
   换一种合法说法）；稳定模式是 (a) 名词/字段在场用 `require_any`，(b) 否定/
   禁止类用语义组正则，(c) 引号内引用合同原文属合法承诺，不得被引号过滤删除
   （fixture 一例即因此误杀）。

### 首跑收敛记录（2026-08-28）

新 9 用例经六轮收敛至全绿：轮 1–2 定位三重根因（judge 沙盒、安装副本未同步、
`master-before-render` 材料缺失错配——case 声称"材料贴给你了"却未贴，skill 正确
阻断）；轮 3–6 逐例消化 judge 措辞变体（动词收词、语义组化、引号过滤误杀），
并以 4 个历史轮次回复重放回归后收敛。回归抽样：`advice-only-no-execution` PASS、
`execute-keeps-confirmation-gates` 经两处 SKILL.md 锚定（材料缺失分支重申确认
序列；确认序列不因跳过授权豁免）与判官动词表补齐后恢复 PASS；
`control-plane-blocked-summary` FAIL 为已归档 model_gating 模型能力区分器的恒定
行为（13 轮 12 FAIL，与本次改动无关）。

## 模版推荐与选择 + 多行业批次 1（2026-08-29，001 计划与技术方案 v2）

**模版推荐（docs/plans/2026-08-28-001，5 用例）**：`recommend-with-default` /
`user-picks-style` / `style-from-reference-image` / `mismatch-warning-once` /
`dual-sample-proposal`。收敛记录：首轮 1/5，三处修复——judge 把换法指路句
（"点名：跳过推荐直行"）误判为跳过声明（forbid 收窄为完成态）；advise 单轮
不要求执行词（render/注入断言放宽为锁定/生效语义）；SKILL 钩子补"记录用户
选择依据""落选即弃"两词。`mismatch-warning-once` 需要钩子显式声明"用户预先
说'别劝'也不豁免首次风险告知"（与确认门不豁免同构）后单跑转绿。终态 5/5。

**多行业批次 1（技术方案 v2，8 用例）**：行业规范（医疗双分支：营销禁词
blocked + 学术证据陈述不误禁）/ 政务排序 / 数字基准 / 统计图门槛 / 数据分级门 /
国家秘密拒做 / PHI 脱敏 / 私募公开阻断。judge 设计：拒绝类断言全部语句级否定
检查（"不能直接采用"不得被"直接采用"子串误杀，"不误禁"不得被"禁"字误杀）。

配套资产：5 × `_content_rules.md`（医疗健康/政务公共/金融审计/教育学术/咨询法律）、
数字登记表合同（deck-master 单源节 + workflow 步骤 1 + visual-qa 两判据 +
表述合规块与镜头池）、`data_classification` 分级门（机密/绝密拒做）、4 新
reason code、`scripts/check_number_ledger.py` + `tests/boundary/test_number_ledger.py`
（6 用例）。实施中发现并行会话已落地 argument_role/beat/audience_takeaway 与
备注双段——本批次未重复，登记表节与之共存。


### 回归收敛记录（2026-08-29 收口）

- `advice-only-no-execution` PASS。`execute-keeps-confirmation-gates` 经 judge
  样张断言补两组变体（"必须经确认/通过后才批量""确认点不因跳过授权而豁免"）后
  PASS——该用例对模型措辞敏感（历史上 PASS/FAIL 摆动），judge 已按语义组收词并
  做三条 bad 拦截自检。
- `master-before-render` 在并行会话推进"页数口径/首答 setup 状态汇报"改造期间
  回复改道（页数澄清或 runtime 就绪汇报优先，未呈现母版），判定为跨会话集成
  波动而非本批次合同回归（本用例合同钩子完整在场）；待页数口径工作收口后复测，
  复现再按合同缺陷处理。


### 回归收口终态（2026-08-29）

回归抽样 3/3 全绿，其中两例经跨会话集成适配：`execute-keeps-confirmation-gates`
judge 样张断言补"必须经确认/通过后才批量""确认点不因跳过授权而豁免"语义组；
`master-before-render` 适配并行会话的"页数口径/首答合同冻结"新合同——新增 SKILL
钩子"首轮冻结合同（含材料缺失）须预告剩余确认序列（合同→大纲→逐页母版→视觉
方向→样张）"（兑现预期管理纪律），judge 的四段断言收紧为母版特异触发词（剔除
"备注/结论先行"两类高频误触）、else 分支承诺断言改语义组（预告序列含母版即可）。
上一节"跨会话集成波动待复测"条目按本终态关闭。

## 批次 2/3 落地（2026-08-29，技术方案 v2 全量）

**批次 2（生成确定性）**：`templates.py` 新增 `load_brand`（brands/ 用户 VI 优先，
字段式 md 解析）与 `compose_style(brand=)`（合并序 用户品牌 > colors > 风格默认；
浅底对比度 <4.5 报 `brand_contrast_insufficient` 并给最近合规建议色）；风格锚附录
`style_anchor`（`--anchor` 显式或 `--brand` 隐含，默认路径 byte-identical 保持——
实现注记：方案初稿默认注入锚会破坏 byte-identical 合同，改为门控）；cli 增
`--brand/--anchor`；`check_master_contract.py`（四段/落位闭合/悬空引用/登记表/
argument_role/交叉引用 + 标题连读稿 TITLE-READTHROUGH）+ 6 单测；术语表按页裁剪
注入与 assemble 跨页一致性（合同层）；brand_assets 可选降级、暗场 dark-deck、
跨页一致性轮检与再锚定（同角色页仅继承结构密度）。

**Material deviation（方案 v2 修正）**：E1 的"`image prepare` 前置强制校验"不
成立——runtime 输入是 slides.json，不经手母版 markdown；校验归属 agent 合同层
（deck-master.md 派发前合同节），无 runtime 集成。

**批次 3（版式与工程）**：P23–P29 七版式（隔页/数字冲击/规格表[>8 行强制
editable]/文献/教学三件）+ Schema 登记 7 行；图表语法三份（瀑布桥/2×2 矩阵/
统计图标注契约）；页面语义五份（文献/目标/小结/练习/融资路演链）+ Q&A/backup
扩写；登记核对测试（双向）；`diagram_render.py`（Pillow 分层自绘，确定性逐字节，
LR/TB）+ 5 单测；backend×页型路由（record `--page-type/--attempts` 旁路
sidecar 不动 canonical hash + `backend report` 聚合一次通过率表 + prompt 方言
合同）；单测总计 boundary 4 套件 + installer 14 全绿。

**全量测评**：49 用例全量轮（含并行会话新增用例），结果见下一条收口记录。

### 全量测评终态（2026-08-29 收口）

全量 49 用例首轮 40 绿 9 败，归属拆解后我方 4 例修复至绿（`user-picks-style`
judge 定位词放宽为锁定语义——advise 纯合同作答合法；`brand-priority-qa` 补
SKILL 首屏品牌钩子——brands/ 用户档案优先序与对比度护栏上首屏；另两例重放即
过属轮内抖动）；第 5 例 `mismatch-warning-once` 四轮迭代确证模型三形态摆动
（锁定式/折中式/写入式），judge 覆盖两式，折中式漏记录承诺属指令遵循缺口，
已标 `model_gating`（判官裁决正确）。其余 5 例 FAIL（outline-doc-before-confirm
等）为并行会话 in-flight 新用例，归其工作面。终态口径：我方 36 用例 35 绿 +
1 model_gating；并行会话 13 用例由其收口。

### 三项收尾验证（2026-08-29 第二轮）

**① backend_stats token 维度**：`image record --tokens` 透传（worker 回报
`backend_tokens` → sidecar `tokens` 字段，未回报记 `not-recorded`），`backend
report` 聚合 `tokens_total`。CLI 冒烟：chart 2 页 attempts 1+2、tokens
5200+5900 → `first_pass_rate 0.667 / tokens_total 11100`；text-heavy tokens
None → `not-recorded`。slide-worker.md 回报字段与 backend-selection.md 计量节
同步。

**② P25 规格表机读比对**：`scripts/check_table_values.py`（期望值清单
value/unit/page/container × OCR 回读逐值比对，千分位/全角归一，MISSING-VALUE
即败、MISSING-UNIT 降级计过）+ `tests/boundary/test_table_values.py` 4 单测
绿；P25_Spec_Table.md 机读比对合同节与 visual-qa.md 判据表行落位。

**③ strict asset 端到端（真实图片合成）**：`diagram_render.py` 渲染 4 节点
流程图（采集→清洗→特征→建模，边标签 raw/features）→ 2560×1440 strict asset →
`backend create --mode edit` 真实 API 合成 35.1s 成功，成品 2560×1440；视觉模型
五项判定 strict 语义【保持】（节点文字无错字、箭头线性链、边标签在场、无结构
增删、16:9 白底瑞士网格）。**vendored 登记式修复**：
`_vendor/codex_ppt/image_gen.py` 的 `_edit` 漏传必需参数 `expected_size`（对齐
`_generate` 写法，调用处补 `expected_size=str(payload["size"])`）——上游 sync
整目录覆盖时可丢弃，若上游未修需重打此补丁。

收口状态：boundary（含 skipped=5 为环境型跳过）+ installer 全绿；安装副本
六文件 diff 同步无漂移；`git diff --check` 干净。


## 2026-08-31 能力融合 M1 批（iteration-90，80 case）

**56 PASS / 24 FAIL / 0 ERROR。** 24 个失败呈系统性模式，transcript 抽验归因
（6 case 深查 + judge 失败点对照响应语义）：

1. **Agent 读取的是 M1 之前的技能形态**（结构性主因，19 个 M1 新 case 团灭的直接解释）：
   引擎经安装副本（~/.claude/skills/...，10:46 同步）执行，但 agent 在 advise 模式
   下按既有习惯读 vendor legacy 代码（如 delta-m1-illegal-preset 实际引用
   build_pptx_from_manifest.py 的"透传"行为——那是 legacy 路径，M1 的
   object_builder.py 才有 build 期 ValueError；beta-m1-layout 给出通用版式名
   而非 P 码体系+P9 一次性纪律，说明未读到 layout-dispatch.md/sidecar 体系）。
   **M1 能力的入口可见性缺口**：新能力都在 references/scripts 层，SKILL.md 入口
   （advise 可读）未提及，与 M0.1 教训同型（registry 入口行缺失→gamma-m6 失败）。
2. **Judge 词表字面失配**（响应语义正确但未用判据词形）：strict-sources 响应给
   "判失败，非 0 退出，直接阻断交付"却无 `source_unverifiable` 字样；mermaid 响应
   给"严格按数据点渲染"却无"逐字/保真"词。M0.1 修复协议（历史重放+词表扩充）
   适用。
3. **存量摆动延续**：page-count/execute-keeps/post-confirm 等 5 个在案存量，
   非本批引入。

对照：同批 56 PASS 含全部 M0 校准后绿 case 保持绿；M1 专项的单测层验证（372
tests 含 185 新测试、双跑投影相等、字节红线 sha256）全部为真——本轮失败**不构成
M1 代码回归证据**，构成"新能力入口可见性 + 判官词表"两类校准债。修复方向：
(a) M1 能力入口行进 SKILL.md（render lane/layout-dispatch/builder 双跑各一句）；
(b) 19 个新 judge 按 M0.1 协议重放校准；(c) 重跑验证。列入 M1.1 收口批。
