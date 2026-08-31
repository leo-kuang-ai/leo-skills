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

## 交付

最终回复必须报告 route、runtime/upstream/patch/lock identity、PPTX 和必要逐页/notes/
failure report 路径、准确交付类型、结构验证、未运行的 provider/OCR/viewer/desktop/人工
验证、保留的恢复产物、限制和唯一下一步。

`status=completed` 只表示产物阶段结束；继续读取 `delivery_readiness`。只有结构门禁、
独立渲染和人工验收均完成且状态为 `accepted`，才能声明交付闭环。

### DELIVERY-GATE 指纹收据

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

### 双评审官可选档（高要求交付）

用户显式要求高保障档位时，人工视觉验收可增强为**双独立评审官**：两个互不知晓彼此
的独立会话按同一 rubric（内容准确性/叙事连贯/工艺/视觉/受众适配/来源可信/行动启发/
一致性）分别打分并给一句话理由；任一维度分歧 ≥2 分触发复议（第三会话或用户裁决）。
两份评分与分歧处理记录作为交付回复的补充证据；本档位**不替代**三证，`delivery_readiness`
仍以结构门禁、独立渲染和人工验收为准。默认交付不启用本档位。
