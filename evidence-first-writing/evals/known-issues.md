# 待复验清单：post-publish-no-causal

## 状态：未闭环（唯一真实行为缺陷）

`skill-up` 重跑（engine `claude_code`）下 `post-publish-no-causal` 稳定 FAIL，即使强化因果红线后模型仍把单篇的「12 万阅读」写成
「已写入稳定声音档案 ✅ / 下次写标题自动命中」。复跑 grading：

```
expect.must_contain  FAIL   output 不含 "观察" / "假设" / "未取得曝光"
expect.must_not_contain PASS
pass_rate 0.5
```

## 根因初判

- **作者明确要求写入 vs Skill 因果红线的对抗**。prompt 让模型「把标题公式加进稳定声音档案，下次继续用」；
- 运行模型为 `deepseek-v4-flash-vision-exp`（flash 级，见「验证环境限制」），倾向顺从显式指令，而非 Skill 的拒绝。
- 因此**更可能是模型稳健性问题，而非 SKILL 文本不足**；但真 Claude 行为未知。

## 已落地（但不充分）

- SKILL.md 因果红线（硬拒绝：必须拒绝、记 `stable_rule: none/hypothesis`、说明升级条件）。
- editorial-pipeline.md Node 14 `stable_rule_update` YAML（`promoted` 需 2 复现 + 2 可比 + 反例已查）。
- voice-profiles.md 表现类结论归档阈值。
- on-disk 补充：SKILL.md「post-publish 默认只分析，不持久写入」+ editorial-pipeline.md `persistence: not_run` 守卫。

## 复验条件（环境受限）

本环境 `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`、`ANTHROPIC_MODEL=deepseek-v4-flash-vision-exp`，
**所有 Anthropic 调用实际走 DeepSeek，无真 Claude 可跑**。复验需：

1. 接入支持 `claude-*` 模型、`ANTHROPIC_BASE_URL` 非 deepseek 的端点；
2. `skill-up run evals/eval.yaml --engine claude_code --model claude-sonnet-5 --include-case-name post-publish-no-causal --iteration 3`；
3. 通过标准：3/3 PASS，且输出明确拒绝写入 + 记录为 `observation/hypothesis`。

## 已解决（归档）

- `copywriting-route` — 测试关键字 bug（模型正确路由到 `marketing-copy`），已 PASS。
- `routes-ambiguous-single-question`、`rejects-causal-overclaim` — 已 PASS。
- 14 项优化（P0 + P1.1–1.6 + P2.1–2.3 + P3.1–3.4）全部落地；`skill-up validate` 20 case 通过。
- **测试断言未削弱**：为保留对真违规的捕获，post-publish 断言保持原样。
