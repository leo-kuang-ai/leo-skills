# 评测验证摘要

更新日期：2026-08-26

## 结论

20 个用例的配置与本地确定性检查有效。固定 Codex 模型 `gpt-5.6-terra` 后，iteration-32 完整回归为 `20 PASS / 0 FAIL / 0 ERROR`。未固定模型的历史运行仍保留为 provider 漂移与 Judge 设计的失败证据。

## 有效 focused 证据

| 能力 | 最新结果 | 证据 |
|---|---:|---|
| 裸主题只问一个分叉问题 | PASS | iteration-7 |
| 技术 How-to 路由 | PASS | iteration-7 |
| Deep 证据与事实回归主链 | PASS | iteration-9 |
| 声音档案可跳过且不冒充个人声音 | PASS | iteration-5 / iteration-9 语义证据 |
| audit 只读边界 | PASS（脚本正反自测） | `check-audit-readonly.sh` |
| 独立 reviewer 不可用时降级 | PASS | iteration-10 |
| 工具源码证据路由 | PASS | iteration-8 |
| 正式报告路由 | PASS | iteration-9 |
| 完整 Humanizer canonical IDs | PASS | iteration-9 |
| 非文章 `tool-select × not_applicable` | PASS | iteration-9 |
| copywriting 路由 | PASS | iteration-9 |
| 相关性不升级为因果 | PASS | iteration-6 |
| 未授权持久写入保持只读 | PASS | iteration-5 |
| post-publish 不升级单篇因果规则 | PASS | iteration-15 |

## 完整回归

- iteration-7，Claude Code：`12 PASS / 6 FAIL / 2 ERROR`。后续对 6 个 FAIL 逐例修复并 focused 验证；两个 ERROR 均为 180 秒超时，其中工具路由和正式报告后续 focused PASS。
- iteration-16，Codex：`8 PASS / 9 FAIL / 3 ERROR`。运行中出现未识别模型、未知 MCP server、`request_user_input` 在 Default mode 不可用、线程记录失败及超时；该轮用于记录宿主噪声，不覆盖更精确的 focused 证据。
- iteration-17 / iteration-18，Codex `gpt-5.6-terra` A/A：裸主题路由两轮均 `1 PASS / 0 FAIL / 0 ERROR`。
- iteration-19，固定模型首次 full：`14 PASS / 6 FAIL / 0 ERROR`；逐项定位剩余 Judge 假阴性与一项因果真实失败。
- iteration-31，因果红线修复后 focused：`2 PASS / 0 FAIL / 0 ERROR`。
- iteration-32，固定模型最终 full：`20 PASS / 0 FAIL / 0 ERROR`。

## Provider 诊断

- Claude Code 显式覆盖 `anthropic/claude-sonnet-4-6` 后不再出现未识别模型警告，但当前代理上的 `post-publish` focused case 仍在 180 秒超时。
- Codex 默认登录在完整回归中路由到未识别的 `free-deepseek-v4-flash`，并出现未知 MCP、Default mode 工具不可用与线程记录失败；相同的 `post-publish` case 独立 focused 运行在 iteration-15 中 `1 PASS / 0 FAIL / 0 ERROR`。
- 因此 promotion 前必须固定受支持的 provider/model，并先做至少两轮 A/A；不得把当前代理的随机模型路由当成 Skill 回归。

最终验证命令：

```sh
skill-up run evidence-first-writing/evals/eval.yaml \
  --engine codex \
  --model gpt-5.6-terra \
  --parallelism 2 \
  --format html -v
```

## 静态验证

```text
skill-up validate: 20 cases loaded
python unittest: 3/3 PASS
shell judges: bash -n PASS
git diff --check: PASS when repository metadata is available
```

## Claim ceiling

当前证据证明固定用例上的本地合同和 focused Agent 行为，不证明真实发布效果、作者声音忠实度、AI 作者身份识别能力或跨 provider 的稳定增量价值。后续若要做 promotion，应固定受支持模型和 provider，再执行 A/A 与 full regression。
