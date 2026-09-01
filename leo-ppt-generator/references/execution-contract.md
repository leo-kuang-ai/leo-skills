# 执行合同

仅在 `interaction_mode=execute` 且 Route 已冻结后读取本页。首次准备细节读取
`first-use.md`；Route 细节读取对应 workflow。本页只拥有跨 Route 的执行、恢复和交付
不变量。

## 项目与 Runtime

- 由当前 Skill 绝对路径运行平台 launcher，只消费成功结果中的绝对 `cli_reference`；
  不从 PATH 猜测 CLI，不安装历史 CLI。
- 在 execute 模式且内容合同确认后即冻结独立 `<project-root>`（早于 backend
  contract、样张与 run），固定使用 `sources/`、`contracts/`、`samples/`、
  `runs/`、`deliveries/`、`content/`。`content/` 承载内容确认文档：版本化的
  `outline-v<N>.md` / `deck-master-v<N>.md` 与其头部 `confirmation` 状态标记
  （`pending` / `confirmed`；母版确认后的 3a 写回与 QA 修复登记
  `revision_kind: post-confirm` 并继承基线 confirmed 状态，页数或结构变化退回
  pending 重新确认）。`content/` 区别于 backend contract 专用的 `contracts/`
  与用户素材的 `sources/`。正式状态只写 `runs/<run-id>/`，canonical PPTX 只写
  当前 run 的 `final/`。
- backend contract 由 registry 创建和验证，不手写 capability、credential 或领域状态
  JSON。凭据只允许 `env:`、`host:`、`keychain:` reference。
- 创建 run 时冻结输入、backend contract、hash、类型、runtime identity 和 idempotency
  key。响应丢失先查询 operation/status，不用新 key 重复 mutation。

### 分节分批母版确认（>40 页，R-42）

- 母版页数超过 40（阈值可按合同声明）时按节分批落盘与确认：大纲全册一次确认；
  各节独立携带 `confirmation` 状态，全部节 confirmed 才构成母版 confirmed 基线；
  节内修订复用既有 post-confirm 机制（继承该节 confirmed，页数或结构变化退回该节
  pending 重新确认），不新增确认门。
- 每节附一行式节摘要（本节结论/新增术语/新增数字/未决承诺），供后续节与组装
  复验引用，防后节按前节早期假设写死。

## 确定性入口

所有上游工具通过当前 runtime 的 `LEO_PPT` 调用：

- `upstream codex-ppt -- ...`：图片生成、编辑、dispatch/result/status、组装；
- `upstream editable-ppt -- ...`：输入规范化、page 状态、manifest、图片和公式工具。

上文为省略全局旗标的简写。实际命令行中 `--backend-contract <path>` 与
`--timeout` 是 `upstream` 的选项，必须位于上游名之前（如
`upstream --backend-contract <run>/input/backend-contract.json codex-ppt -- ...`，
与 worker prompt 中的完整形式一致）。
外层必须是 `leo-ppt-machine/v1`；`result.returncode != 0`、未知协议、缺页、validation
失败或 finalizer 失败都阻止推进。

## Worker

- 多页任务只在用户授权、宿主能力、容量和真实派发均成立后 dispatch；主 Agent 不模拟
  scheduler，也不串行替代。
- 每批 worker 派发前必须 `python3 scripts/check_worker_brief.py <deck 目录|slides.json>`
  （在技能目录内执行）：required_text/style_lock/术语注入（术语表存在时）/数字登记行
  （该页有行时）缺任一即 exit 1 阻断派发并给缺块+页清单（R-46）。
- 恰好一页只有 CLI 返回 `single_unit_current_agent_allowed` 才能由当前 Agent 执行。
- worker 只拥有一个 slide/page 目录，按各自 prompt 的返回合同报告自身 agent id、
  page/slide id、产物绝对路径、backend used/provenance 与 validation/QA 证据；
  失败的稳定 reason code 经 `blocker=<reason>`（slide）或 `validation.json`
  （page）登记。
- worker 不修改其他页面、顶层 run、最终 PPTX 或 Git；父 Agent 负责 record 和最终验证。

### Worker 逐页三层容错协议

1. **阶段分层重试（每页 ≤3 次）**：每页执行分为 `prompt 准备 → backend 执行 → QA`
   三个阶段，各自独立计数；重试只补失败阶段，已成功的阶段不重跑。每页到达
   accepted 的总尝试次数经 `image record --attempts` 如实回报并进入
   backend_stats 路由统计。
2. **全册完成后清扫（≤2 轮）**：全部页完成首轮 record 后，扫描 canonical
   state 中非 rendered 的页，复位重派（复用 `run retry --from-failed-pages` 与
   `Lifecycle.reset_failed_pages()` 既有机器）；清扫轮**只复位非 rendered 页**。
   清扫 2 轮后仍失败的页 → 缺页拒绝组装（既有红线）：upgrade 路线走
   partial-hybrid 确认，generate 路线向用户显式披露缺页，不静默放弃。
3. **已 rendered 页无条件跳过**：重跑、恢复与清扫过程中，state 为 recorded 的
   页不再派发（防重复计费与风格漂移）。
4. **第 0 条（既有恢复纪律重申）**：重复失败前必须改变输入、配置、backend
   或实现；同输入的原样重试不计入上述任何一层的预算。

## 恢复

- generate 任务中断后恢复时，以 `<project-root>/content/` 的版本化文档为确认
  状态真值：某确认门已过当且仅当存在 confirmed 基线（含其 `post-confirm`
  修订链）；`content/` 为空即从内容合同重新开始。视觉方向与样张批准不落盘，
  恢复到该阶段时重新询问用户。
- 已有 reason code 时才读取 `reason-codes.md`。重复失败前必须改变输入、配置、backend
  或实现；自动重试只在 `safe_to_retry=true` 时复用同一 idempotency key。
- 中断保留 checkpoint；cancel 是 terminal。cleanup 必须先 dry-run，再对相同 fingerprint
  apply；input 只允许 terminal run 清理。
- 已验证的 image deliverable 不得被后续 editable/hybrid 失败删除或降级。

## 内容层状态与恢复

- **基线 CAS（post-confirm 写回前，强制）**：对 `content/` 写回目标（母版 / outline /
  sources-manifest）先用 `python3 scripts/check_content_baseline.py --record <FILE>`
  建立基线锁（`<FILE>.base-lock.json` 记 sha256）；写回前必须 `--verify` 通过
  （exit 0）才允许落笔——即基线哈希 CAS。漂移（exit 3）即停：给有限选项
  （采纳为新版本：重新 `--record` 重锁 / 丢弃：恢复需人工 / 只查看），**不自动
  覆盖**（会话外手改保护）；并发会话场景后者停止并报告，不得互相覆盖。写回
  完成后立即 `--record` 重锁新基线，下次写回前再 `--verify`；verify 与写回
  之间的竞态窗口由重锁+写前复核缩小（锁为 advisory，并发会话最终以基线锁
  判冲突）。
- **run 阶段账本（各阶段完成后）**：每页 prompt / backend / qa / record 各阶段
  与 deck 级 receipt 完成或失败时，`python3 scripts/record_run_step.py --run <run>
  --step <s> --page <N> --status <s> [--artifact <path>]` 追加
  `<run>/reports/run-ledger.jsonl`（追加写，无锁竞争）；`--tail N` 查看，
  `--resume-suggestion` 输出"从哪继续"建议（最后未完成页与阶段，exit 2 =
  闭合状态矛盾或重试预算耗尽须改变输入后再试；exit 2 兼用法错误（参数
  非法）——命令打错重试即可，状态矛盾才需人工裁决）——只给建议，不自动覆盖。
- **派生物重投影（漂移争议时）**：收据 verify 报漂移或人工对派生物起争议时，
  `python3 scripts/reproject_derivatives.py --project-root <root> [--dry-run]` 从
  最高 confirmed 基线（含 post-confirm 链）确定性重建 sources-manifest 图行
  投影与术语表投影（流程字段按 figure_id 继承），并检测 slides.json 页集合
  漂移；先 `--dry-run` 看 diff，再决定写回。母版是真值，投影不得反向覆盖母版。
- **渲染事实账本（每页 record 后）**：每页 image record 后运行
  `python3 scripts/build_rendered_ledger.py <run>` 聚合该页呈现事实（OCR 文本
  摘要 / 关键数值 top5 / 图表计数）到 `<run>/reports/rendered-ledger.json`；
  无 OCR 记录的页如实标注 missing，多轮改稿时以此对照"上轮实际呈现口径"。
- 恢复礼仪统一为**建议不覆盖**：以上脚本任何恢复输出都只给续点与有限选项，
  不代替用户裁决。runtime CLI 的自动接线（`leo-ppt run status` 附续点建议、
  record/receipt 钩子自动记账与 verify）为后续衔接点，当前由主 Agent 按
  上述时机显式调用。

## 交付

最终回复必须报告 route、runtime/upstream/patch/lock identity、PPTX 和必要逐页/notes/
failure report 路径、准确交付类型、结构验证、未运行的 provider/OCR/viewer/desktop/人工
验证、保留的恢复产物、限制和唯一下一步。

`status=completed` 只表示产物阶段结束；继续读取 `delivery_readiness`。只有结构门禁、
独立渲染和人工验收均完成且状态为 `accepted`，才能声明交付闭环。

### 分发边界（R-48）

- leo 的交付止于文件与导出形态（handout-PDF / 长图 / 轮播卡片择优）；**不代发任何
  平台、不请求也不存储平台凭据**。用户要求代为发布到平台时拒绝并指路已登记的外部
  工具（Wechatsync 系），发布动作由用户在外部工具内人工完成（草稿先行原则）。
  本节与 DELIVERY-GATE 同构，是防止范围蠕变的边界声明，不新增人在回路门。

### DELIVERY-GATE 指纹收据

- 交付声明前可先运行 `python3 scripts/build_delivery_preflight.py <run>`（R-59）聚合
  geometry/sources --strict/sensitive/receipt 四门为单文件
  `<run>/reports/delivery-preflight.json`，交付披露引用该文件；blocked（exit 1）
  时不得声明交付，not_run 项须披露原因。
- 交付声明前必须对当前 run 运行 `leo-ppt delivery receipt create <run>`，把五类
  sha256 指纹（页产物 / 本地输入资产 / QA 报告 / 渲染预览 / 模板样式源）原子写入
  `<run>/reports/delivery-receipt.json`；某类产物不存在时按显式空清单登记，
  不视为漏采。
- 交付或导出前必须运行 `leo-ppt delivery receipt verify <run>`：五类指纹重算后
  与收据全一致（`delivery_receipt_fresh`）才允许继续；任一漂移
  （`delivery_receipt_stale`）阻断交付，并按 verify 输出的波及面处理——页产物
  漂移 → 该页重走视觉 QA 并创建新的 artifact revision；本地资产或模板样式源
  漂移 → 全册页都在波及面，重估样张继承；QA 报告漂移 → 仅重跑 QA，不必重建
  页面；渲染预览漂移 → 重跑独立渲染证据。处理完成后重建收据再交付。
- `delivery_readiness=accepted` 隐含收据存在且 fresh（`receipt_gate` 为 passed）；
  无收据时该 gate 按 `not_run` 在 readiness 输出中披露，`delivery_readiness`
  不得为 `accepted`。收据文件自身不进入任何指纹。
- 含图片证据的交付（generate 全部；upgrade 路线先 `python3 scripts/check_sources_manifest.py
  --compile <run> [--out <path>]` 聚合）交付前必须运行
  `python3 scripts/check_sources_manifest.py <run> --strict`（在技能目录内执行）：
  退出 1（含 `source_unverifiable`——引用级无法回溯用户输入、AI 图冒充引用）
  阻断交付；退出 2（低审查状态图等 WARN）可交付但须在交付披露中逐条列明。
  与 `check_deck_geometry.py` 同一交付门模式，不新增人在回路门。

### 双评审官可选档（高要求交付）

用户显式要求高保障档位时，人工视觉验收可增强为**双独立评审官**：两个互不知晓彼此
的独立会话按同一 rubric（内容准确性/叙事连贯/工艺/视觉/受众适配/来源可信/行动启发/
一致性）分别打分并给一句话理由；任一维度分歧 ≥2 分触发复议（第三会话或用户裁决）。
两份评分与分歧处理记录作为交付回复的补充证据；本档位**不替代**三证，`delivery_readiness`
仍以结构门禁、独立渲染和人工验收为准。默认交付不启用本档位。

## Editable builder 双跑（F1 迁移期）

- 默认 builder 为 `legacy`（vendored zip writer，冻结不动）。对象级
  python-pptx builder（`leo-ppt-generator/object-builder-1`）经
  `LEO_EDITABLE_BUILDER=pptx|legacy` 切换；非法值 fail-closed 回落 legacy。
- run 创建时（`editable prepare`）把生效值冻结进 `page_jobs.json` 的
  `builder` 字段；finalize/重建按冻结字段分派，环境变量改值不影响已创建
  run 的重建一致性。无字段的旧 run 视为 legacy。
- **默认翻转的前置条件**：`tests/boundary/test_object_builder_equivalence.py`
  等价投影套件全绿 + 全量 evals 在两种 builder 下双跑通过一个发布周期
  （阶段 A→B）；legacy 在 P2 结束前保留为显式逃生路径。
- vendor 命令面 `leo-ppt upstream editable-ppt -- run finalize` 内部固定
  vendored builder，迁移期保持 legacy-only；顶层 `leo-ppt editable finalize`
  为可切换路径。
- 对象级路径产物身份写入 `docProps/app.xml`
  （`Application=leo-ppt-generator/object-builder-1`）；canonical zip
  （条目序 `[Content_Types].xml`→`_rels/.rels`→字典序、1980-01-01、
  DEFLATED）保证同 manifest 同 builder 两次构建 sha256 相等，指纹收据
  可直接取 final/page pptx 的 sha256。
- manifest 可选段（`theme`/`tables[]`）仅对象级路径消费，字段合同见
  [`manifest-schema.md`](manifest-schema.md)。
- image sweep（清扫重派）的用法与轮次预算见
  [`render-contract.md`](render-contract.md)（γ 集成）。
