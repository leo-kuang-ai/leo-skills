# 执行合同

仅在 `interaction_mode=execute` 且 Route 已冻结后读取本页。首次准备细节读取
`first-use.md`；Route 细节读取对应 workflow。本页只拥有跨 Route 的执行、恢复和交付
不变量。

## 项目与 Runtime

- 由当前 Skill 绝对路径运行平台 launcher，只消费成功结果中的绝对 `cli_reference`；
  不从 PATH 猜测 CLI，不安装历史 CLI。
- 在 backend contract、样张或 run 前冻结独立 `<project-root>`，固定使用
  `sources/`、`contracts/`、`samples/`、`runs/`、`deliveries/`。正式状态只写
  `runs/<run-id>/`，canonical PPTX 只写当前 run 的 `final/`。
- backend contract 由 registry 创建和验证，不手写 capability、credential 或领域状态
  JSON。凭据只允许 `env:`、`host:`、`keychain:` reference。
- 创建 run 时冻结输入、backend contract、hash、类型、runtime identity 和 idempotency
  key。响应丢失先查询 operation/status，不用新 key 重复 mutation。

## 确定性入口

所有上游工具通过当前 runtime 的 `LEO_PPT` 调用：

- `upstream codex-ppt -- ...`：图片生成、编辑、dispatch/result/status、组装；
- `upstream editable-ppt -- ...`：输入规范化、page 状态、manifest、图片和公式工具。

外层必须是 `leo-ppt-machine/v1`；`result.returncode != 0`、未知协议、缺页、validation
失败或 finalizer 失败都阻止推进。

## Worker

- 多页任务只在用户授权、宿主能力、容量和真实派发均成立后 dispatch；主 Agent 不模拟
  scheduler，也不串行替代。
- 恰好一页只有 CLI 返回 `single_unit_current_agent_allowed` 才能由当前 Agent 执行。
- worker 只拥有一个 slide/page 目录，返回 agent id、page id、产物绝对路径、输入与
  backend provenance、validation/QA 证据和稳定 reason code。
- worker 不修改其他页面、顶层 run、最终 PPTX 或 Git；父 Agent 负责 record 和最终验证。

## 恢复

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
