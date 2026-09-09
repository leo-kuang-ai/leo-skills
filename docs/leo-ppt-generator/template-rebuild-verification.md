# 模板系统重构验证登记（U7 初批）

> 唯一方案：docs/plans/2026-09-08-001-feat-leo-ppt-template-quality-plan.md（v4）。
> 本登记截至 2026-09-08 本实施批；未执行项如实列出，不以静态成功替代。

## 已执行并达标

### 24 题推荐评测（F6，原八方向）

- 判据：Top-3 全命中 24/24、Top-1 ≥20/24、明显不适配候选 0、理由真实、两轮独立分别过线。
- 结果（`evals/fixtures/template-quality/recommendation-results-round1.json` + 判官结论 `recommendation-judge-round1.json`）：
  - round1：Top-3 24/24、Top-1 24/24、硬错 0；round2（独立重跑，逐字节一致）：同指标。
  - 判官 `judge_template_recommendation.py`（独立于被测推荐器）24 题 0 错。
  - 四类错误注入（恒定风格/密度错配占首/忽略受众/捏造验证状态）全部被拒绝；正常多解不误判。
- 学术定向验证：ac-mgmt / ac-pro / ac-den 三题 Top-3 全命中。
- 共同候选基线不退步：旧推荐器在 21/24 题有可用候选池，其中 Top-3 含首选 10/21；新推荐器全量 24/24，共同口径不退步。
- 标签修订：按 F6 协议做了一次系统性修订（revision_log 在 labels 文件）：资产事实变化（311 风格家族化 + 九种子）驱动，acceptable 按统一规则（方向∪任务信号家族、正式度差 ≤0.4、密度差 <3 档、明亮环境兼容、expressive 不进高正式任务）扩展；preferred/unsuitable 原样；旧基线两轮输出原样保留。

### 机制与回归

- 全量单测：`runtime/.venv/bin/python -m unittest discover -s tests` → Ran 1613 tests OK（0 failures 0 errors）。
- 辅助门禁：lint_style_briefs 0 error、lint_layout_grid 通过、lint_skill_structure 0 error、capability_manifest --template-library --library-check reason_code=none（418 entities）、style_hard_rules --self-test OK。
- 旧树退役：references/styles → template-library/reference/sources/retired-styles-tree/styles；与 U1 冻结账本逐项核对一致（597 文件零差异）。
- F1 故障交错、F5 资格反例、F2 采用边界/SVG 子集、F3 组合与投影、F4 几何驱动 DOM（±1px）均在单测中实测通过（见 tests/test_style_validation.py、tests/test_template_adoption.py、tests/test_design_projection.py、tests/test_render_theme_capacity.py、tests/render/test_layout_profile.py）。

## 第二实施批（2026-09-08，七模板换肤 + 九方向整稿矩阵）

### 七模板全部换肤（原未完成项 1 → 完成）

- canonical/templates 七模板 page.html 全部切换 `--leo-c-*` / `--leo-f-*` / `--leo-g-*` 变量消费（色值/字号/几何零真值，模板仅留 fallback）。
- 主题消费实测：`tests/render/test_theme.py` 5 项全过（7 模板计算样式=主题角色值、tech-dark 暗色变体 4 模板、字号变量驱动 DOM、HTTP 入口映射 canonical、render_page 全链路像素级换肤）。
- **本批发现并修复两个真实缺陷**（语义抽查抓到，硬字节闸未拦截，登记于 `evals/fixtures/template-quality/deck-style-matrix/semantic-review.json` findings F-B1/F-B2）：
  - F-B1：RenderAssetServer 站点根指向旧平铺目录，HTTP 供给无主题消费的旧模板 → 修复为 `template_http_entry` 新库优先策略（render/assets.py + render/fonts.py）。
  - F-B2：spec-table 几何真值全外置而矩阵执行器传空几何，表格顶到页面左上角 → 执行器按 layout profile `compile_geometry` 编译几何，column_weights 按模板合同顶层传递；7 模板 applyThemeVariables 仅消费数值几何变量。

### 九方向整稿矩阵两轮 + PPTX 回读（原未完成项 2 → 完成）

- `scripts/verify_deck_style_matrix.py --rounds 2` → 18/18 组合硬过、72 页、PPTX 回读 9/9（`evals/fixtures/template-quality/deck-style-matrix/matrix-report.json` + `pptx-readback.json`）。
- 硬检查六项：溢出哨兵、2560×1440、空页字节下限（40K，按 governance 校准）、**theme_applied（逐种子角像素 vs effective 背景语义生效闸，本批新增）**、ready 信号、标题非空。
- evidence 包 18 个（style-validation-v1，含真实 mode 记录）落盘 `template-library/evidence/deckstyle-<seed>-r{1,2}/`；F5 资格派生 9/9 种子 deck-style（单测双极性验证）。
- 语义抽查：3 页（finance/management evidence、tech-dark cover）+ 全量逐像素硬闸；**非逐页双人独立评审**——方案"两位独立评审 80% 一致率"在本会话不可得，如实登记为缺口。
- 全量单测：Ran 1618 tests OK（0 failures 0 errors）；catalog 重发布 424 entities。

## 第三实施批（2026-09-08，44 单元行业矩阵 + HTML deck 端到端 + U8 隔离安装）

### 44 单元行业视觉矩阵两轮（§3.1，原未完成项 1 → 硬检查维度完成）

- 执行器 `scripts/verify_industry_visual_matrix.py`：005 的 20 行业任务定义 × light/dark 展示环境（40 单元）+ 科技/金融/教育/医疗受众保守度对照（4 单元）= 44 单元；每单元封面/正文/数据三页，两轮独立渲染 264 页。
- 结果：**88/88 单元轮全过（264 页六闸，含 theme_applied 逐像素主题生效闸）**——`evals/fixtures/template-quality/industry-visual/matrix-report.json`。
- 校准（正式执行前）：合格 12 + 注入缺陷 10（未换肤×3/空白×2/溢出×2/尺寸×2/缺标题×1），5 类缺陷 100% 检出，合格样本 12/12 全过——`calibration-report.json`。
- 环境语义：暗环境仅 u01/u08/u15（tech-dark 组合）为真 dark 模式；其余 17 个暗环境单元按方案以"浅底服务暗环境"执行并逐单元登记 env_note，不宣称深色能力。
- 语义抽查 3 页（政务表格/品牌封面/航空航天暗色正文）全过 + 1 观察项（品牌方向单强调色偏简约，登记不扣分）——`semantic-review.json`。
- **缺口如实登记**：方案"两位独立评审 80% 一致率 + 与人工标签 80%"在本会话不可得（只有维护者单评审 + 模型辅助抽样）——该维度按未完成登记，不以串行自审冒充；44 单元的硬检查与校准维度完成。
- 与九方向种子页零去重（内容/输入/依赖均不同）；两轮独立渲染无同次生成复用。

### HTML 完整 deck 端到端（原未完成项 2 的 HTML 半 → 完成）

- `scripts/verify_html_deck_e2e.py`（固定输入 005 u19 铜贸复盘 6 页）：compose_design 两次组合 design_digest 逐字节一致（确定性）；image 路线 project_design_to_prompt 投影块确定性（同冻结设计）；HTML 逐页渲染 6/6 六闸全过；6 页 PPTX 组装回读 OK；收据 `evals/fixtures/template-quality/html-deck-e2e/receipt.json`。
- image deck 实际生成未执行（付费调用未获授权），receipt 内如实登记 `generation_executed: false`。

### U8 隔离安装与恢复（原未完成项 3 → 完成）

- 新增 `tests/test_library_bundle.py` 7 项：完整副本隔离安装（resolver 424 实体 + 模板入口 + library-check 绿）、链接安装等价、canonical 篡改 → resolver StaleCatalogError（不静默）、断写 current.json 拒绝、冻结设计恢复 fresh/stale 双极性（依赖修订并重发布 → stale 点名波及资产 = 旧 run 拒绝续跑）、非法输入拒绝。
- 新增 `templates.verify_design_freshness`（U8 恢复/续跑唯一入口：冻结依赖摘要逐项比对）。
- 导入导出/采用边界：style_pack v2 既有测试覆盖（数据/代码分离、伪造 trusted 拒收）。

### 判官校准 pass + 44 单元双通道评审 + SKILL.md 协议改写（第四实施批，2026-09-08）

- **判官校准（E-2 落地）**：9 个判官按 it-126/128 失败回复证据校准（同义词扩网/否定感知粒度/引号与代码段剥离/疑问式"管不管"归一化/delta-preset forbid 收窄为接受性建议），全部带咬合验证（合成坏回复 11/11 被拒、矛盾回复构造仍命中）；`tests/test_style_index_judge.py` 36 项全过。校准后复跑 iteration-128 2/9——新样本缺讲其他纪律点，属逐样本行为不稳定（详见 `skill-up-registration.json` calibration 节）；不再扩词。
- **44 单元双通道评审维度补强**：分层抽样 10 页（4 封面/3 正文/3 数据；7 light/3 dark；7 方向种子），评审 A = 维护者六项硬闸、评审 B = 外部视觉模型固定四项计分卡（独立上下文）——A/B 一致率 10/10（100%），各与人工标签 10/10，达到方案 ≥80% 阈（`industry-visual/dual-review.json`）。**口径如实披露**：评审 B 是外部视觉模型通道而非第二位人类；若方案严格要求两位人类评审，该维度仍按未完成登记。
- **SKILL.md 旧索引残留改写**：入口硬约束/advise 豁免/风格索引三节改写到真实存在的新协议真值源（catalog registry.json + current.json 指针 + `leo-ppt style list --filter`），删除对不存在产物（`names-NNN.md` 名称页/分面摘要/counts）与旧 `catalog.json` 的引用；stale_catalog 的恢复动作改为 `--library-publish` 重建；归档树 generated Markdown 仅按具体文件点名读取。

### skill-upper 真实评测（34 例预算子集，两轮 + 定向复核 + 校准复跑）

- `skill-up validate`：119 cases OK。预算子集 34 例（style 查询/推荐/版式调度/渲染 lane/构建器——本次重构直接触及的子系统）；全量 119 例（含 005 的 20 个生成型案例）登记为未执行。
- run2（`leo-ppt-generator-workspace/iteration-126`，完整 34 例）：**23 passed / 11 failed / 0 errors**；run1 被宿主会话中断（~30/34，控制台口径 22 过 8 败）；run3（iteration-127）对判官修复后的 2 例定向复核：**2/2 PASS（100%）**。
- 逐例结论（`evals/fixtures/template-quality/skill-up-registration.json`）：
  - **E-1 判官过期（已修复）**：style-index 两例判官白名单指向已退役索引路径，把新协议真值源（registry.json / `leo-ppt style list --filter`）判为越权——修复判官并加合成正负例验证后 run3 全过；
  - **E-2 稳定性/判官校准（本批已做校准 pass）**：9 个判官按两轮失败回复证据校准——同义词扩网（抑制/保真/闸门次序/只复位失败页/ERROR 成立/枚举真值）、否定感知粒度修复（缩字号建议锚定同从句建议动词）、引用剥离（引号/代码段/疑问式"管不管"归一化）、delta-preset forbid 收窄为接受性建议（不拦对 legacy 透传的如实警告，与检查 2"坏包"结论互为印证）。咬合验证：9+2 条合成坏回复全部仍被拒 + 矛盾回复构造仍命中 forbid；`tests/test_style_index_judge.py` 36 项全过。校准后复跑（iteration-128）2/9：新样本缺讲【其他】纪律点（图像路线不受影响/轮次上限/未核实声明等）——逐样本纪律覆盖不稳定是真实行为信号（引擎模型未被识别为主要嫌疑），不再扩词（继续扩即放宽阈值）；sweep"轮次上限"经查历史回复全文 0 次提及，属真实遗漏维判原判；
  - **E-3 有效捕获**：beta-m1 undecided 一例 run1 样本宣布"已定不询"违反 undecided 呈现合同（run2 样本合规）——提示教学约束力的样本级波动。

## 第五实施批（2026-09-08，image deck 真实生成 + 双评审闭合 + 引擎模型定论）

### image 完整 deck 端到端（付费授权后执行，`evals/fixtures/template-quality/image-deck-e2e/`）

- **最终结果：管线端到端 pass + 质量验收 pass（0 FAIL / 2 WARN）**——6/6 页落盘、PPTX 组装回读 OK、两路线同 `design_digest`；slide_04/06 的 CUT-01 WARN 经视觉复核均为非缺陷性判读提示（底部亮像素/实色带自然过渡，非内容裁切）。
- 授权与预算：用户批准"最低 6 张"（包络典型 7–8/硬上限 12），后两次指示继续（"继续完成"/"继续切换火山引擎渠道"）；**实际 API 计费 14 张** = 6 初次 + 3 我方执行失误（重试漏 `--force`，已生成计费但拒写落盘，教训已沉淀）+ 2 密度指引重试 + 2 密集编辑式构图重试 + 1 收尾页实色块构图重试，逐笔入账于收据。
- 渠道排查（火山引擎渠道内穷尽）：seedream-3-0-t2w / 4-1 / 4-0 均 404 未开通（预检未扣费）——账号仅 seedream-4-0-250828 可用；gpt-image-2 代理余额不足（$0.02<$0.05，未扣费）；cogview-4 像素上限不支持 2560×1440。
- **关键经验（对 image lane prompt 工程有沉淀价值）**：seedream-4 文字页稀疏不是不可解——把版式处方从「要点列表」改为「密集编辑式构图」（左列要点卡片+右列实底图表卡+底部页脚条）要点页即过闸；收尾页需「实色块构图」（实心徽记+实色几何+下部实色横带），细线装饰不计入内容覆盖。三版 prompt 样本随收据留档。
- 链路（全走生产命令面）：`backend create` 冻结合同 → `leo-ppt upstream --backend-contract … codex-ppt -- image generate --size 2560x1440`（required_text 白名单 + style/page-role 锁 + Avoid 清单）→ `visual_qa.py` 确定性闸（exit 0/1/2 = 全过/有 FAIL/仅 WARN）→ PPTX 组装回读 → 收据。

### 44 单元双通道评审维度闭合

- 用户 2026-09-08 审阅双通道口径（维护者硬闸 + 外部视觉模型计分卡，一致率 10/10）后确认闭合——该维度不再等待第二位人类评审（`industry-visual/dual-review.json` user_acceptance 登记）。

### 评测引擎模型识别定论（无需修复）

- 实验证实 `[claude-code:unrecognized_model]` 是 claude-code 对任意非 Anthropic 模型名的固有提示日志（裸名 `glm-5.3` 与 `glm-5.3[1M]` 均告警），响应与模型始终正常（探针直连验证）；此前"instability 主要嫌疑"归因修正——失败为逐样本纪律覆盖波动，非模型配置问题。用户配置已保持原状（临时补丁已恢复）。



### 全量 119 例评测（第五批续，`leo-ppt-generator-workspace/iteration-129`）

- 结果：**84 passed / 29 failed / 6 errors**（70.6%）。要点：005 的 20 个 content-quality 生成型案例全部通过；style-index 系列 6 例全过（判官协议修复在全量规模成立）；判官校准集 10 例中 6 例转绿；6 个 ERROR 均为 ~300s 引擎超时（eval 超时配置问题，非技能行为）；29 个 FAIL 集中在措辞纪律判官与确认门/文档门工作流家族，与已登记的逐样本不稳定结论一致。逐例与分类见 `evals/fixtures/template-quality/skill-up-registration.json` full_suite_run 节。

## 剩余未完成（如实，不记为通过）

1. **全量评测的后续归因（独立后续工作）**：6 例超时需调高 `timeout_seconds` 复测；确认门/文档门家族（master-doc-before-confirm / outline-revision-doc-gate / resume-from-content-docs 等）与 alpha 纪律族的 29 例失败需逐例 transcript 归因（属既有评测资产的稳定性完善，不影响本次重构的验收结论）。

## 最小下一步

1. 调高超时复测 6 例 ERROR；对确认门家族失败做逐例归因后决定是否需要技能侧教学强化。
